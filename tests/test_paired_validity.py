"""Failure-case tests use temporary synthetic logs, never historical data."""
import copy
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

from analyzers.analyze_paired import analyze_pair, analyze_batch
from core.plan import build_plan, write_plan, load_plan
from core.provenance import fingerprint
from utils.logger import PHASE_LOG_COLUMNS


class ReplayValidityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'fixture'
        self.plan = build_plan(7, 3, 'even', plan_id='fixture')
        write_plan(self.plan, str(self.directory / 'plan.json'))
        self.build_arms()
        self.save()

    def build_arms(self):
        """Two coherent arms for `self.plan`, in `self.directory`."""
        self.arms = {}
        # A coherent arm, not just a complete one: every summary field is
        # derived from the rows it summarises, so a negative case can be made
        # by mutating exactly one thing and nothing else has to move.
        release_lateness = 0.002   # the run clock, a couple of ms behind plan
        travel = 12.0              # release to stop line
        wait = 1.25                # stopped delay, necessarily below travel
        drain = 1.5                # rendering after the final crossing
        fps_window_sec = 5.0
        for name in ('fixed', 'priority'):
            folder = self.directory / name
            folder.mkdir()
            rows = []
            for vehicle in self.plan['vehicles']:
                released = vehicle['t_offset_sec'] + release_lateness
                rows.append({
                    'plan_seq': str(vehicle['seq']), 'wait_time_sec': f'{wait:.2f}',
                    'mode': name,
                    'released_sec': f"{released:.4f}",
                    'crossed_sec': f"{released + travel:.4f}",
                    **{key: str(vehicle[key]) for key in (
                        'vehicle_type', 'direction', 'lane', 'will_turn',
                        'turn_direction', 'target_turn_lane')},
                })
            last_crossing = round(max(float(row['crossed_sec']) for row in rows), 4)
            duration = round(last_crossing + drain, 2)
            # 61/59 alternating: mean 60, worst window 59, and enough windows
            # to cover the whole run rather than its first few seconds.
            windows = [61, 59] * math.ceil(duration / fps_window_sec / 2)
            meta = dict(
                generation_source='plan', run_mode='vehicles', stop_reason='target_reached',
                plan_id=self.plan['header']['plan_id'],
                plan_hash=self.plan['header']['content_hash'], arm=name,
                uneven_mode=self.plan['header']['uneven_mode'],
                provenance_version=1, controller=name,
                vehicle_log='run.csv', signal_log='run_signal.csv', plan_path='plan.json',
                started_at='2026-09-10 00:00:00', ended_at='2026-09-10 00:01:00',
                vehicles_planned=len(rows), target_vehicle_count=len(rows),
                vehicles_released=len(rows), vehicles_generated=len(rows),
                vehicles_crossed=len(rows), duration_sec=duration,
                last_crossing_sec=last_crossing,
                fps_mean=60, fps_min=min(windows), frames_total=round(60 * duration),
                fps_window_sec=fps_window_sec, fps_windows=windows,
                release_drift_mean_ms=1, release_drift_max_ms=2,
                final_phase_censored=False,
                configuration={'speed': 2}, source_files={'main.py': 'abc'},
            )
            meta['configuration_hash'] = fingerprint(meta['configuration'])
            meta['source_hash'] = fingerprint(meta['source_files'])
            self.arms[name] = {'rows': rows, 'meta': meta}

    def save(self):
        for name, arm in self.arms.items():
            folder = self.directory / name
            with (folder / 'run.csv').open('w', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=list(arm['rows'][0]))
                writer.writeheader()
                writer.writerows(arm['rows'])
            (folder / 'run_meta.json').write_text(json.dumps(arm['meta']))
            (folder / 'run_signal.csv').write_text('timestamp,direction\n2026-09-10,right\n')
            # A complete phase record: the columns a run actually writes,
            # with a status that says this green ended on its own terms.
            with (folder / 'run_phases.csv').open('w', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=PHASE_LOG_COLUMNS)
                writer.writeheader()
                writer.writerow({
                    'round_index': 0, 'phase_index': 0, 'direction': 'right',
                    'green_start_sec': 10.0, 'green_selected_sec': 24,
                    'green_end_sec': 34.0, 'phase_end_sec': 39.0,
                    'decision_weight': 3.0,
                    'decision_counts': '{"down": 0, "left": 0, "right": 3, "up": 0}',
                    'queue_counts': '{"down": 0, "left": 0, "right": 3, "up": 0}',
                    'status': 'complete', 'termination': 'duration',
                })

    def result(self):
        return analyze_pair(str(self.directory), write=False, baseline='fixed')

    def assert_invalid(self, text):
        result = self.result()
        self.assertFalse(result['valid'])
        self.assertIn(text, '\n'.join(result['invalid_reasons']))
        self.assertEqual(result['paired'], [])
        json.dumps(result, allow_nan=False)

    def test_complete_pair_and_batch(self):
        result = self.result()
        self.assertTrue(result['valid'], result['invalid_reasons'])
        self.assertEqual(result['paired'][0]['n_matched'], 3)
        self.assertIsNone(result['paired'][0]['wilcoxon_p_value'])
        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['per_contrast']['fixed_vs_priority']['plans'], 1)
        narrowed = analyze_batch(str(self.root), write=False, baseline='fixed',
                                 only='nothing_*')
        self.assertEqual(narrowed['plans_total'], 0)

        # Safeguards travel with the headline number, not separately from it.
        guards = batch['per_contrast']['fixed_vs_priority']['safeguards']
        self.assertEqual(
            set(guards),
            {'wait_p95', 'worst_approach_wait', 'approach_service_gap', 'clearance_sec'},
        )
        # Both fixture arms log identical waits, so every safeguard is flat.
        self.assertEqual(guards['wait_p95']['mean_of_plan_deltas'], 0.0)
        self.assertEqual(guards['wait_p95']['plans_worse_under_arm'], 0)
        # The stratum carries the demand regime, not just skew and workload.
        self.assertEqual(result['scenario'], 'even_mixed_3')
        self.assertEqual(result['scenario_fields'],
                         {'skew': 'even', 'regime': 'mixed', 'workload': 3})
        self.assertIn('even_mixed_3', batch['per_scenario'])
        # Safeguards are reported per stratum, at the level the headline
        # number for that stratum is read.
        self.assertEqual(
            set(batch['per_scenario']['even_mixed_3']['fixed_vs_priority']['safeguards']),
            set(guards),
        )
        self.assertEqual(batch['analysis']['baseline'], 'fixed')
        self.assertEqual(batch['cohort_errors'], [])
        self.assertEqual(len(batch['cohorts']), 1)
        # One plan cannot support an interval; it must say so, not invent one.
        self.assertIsNone(batch['per_contrast']['fixed_vs_priority']['ci_low'])
        arm = result['arms']['fixed']
        self.assertEqual(arm['wait_p95'], 1.25)
        self.assertIn(arm['worst_direction'], ('right', 'down', 'left', 'up'))
        self.assertEqual(arm['direction_service_gap'], 0.0)

    def test_sidecar_logs_are_not_mistaken_for_vehicle_logs(self):
        result = self.result()
        self.assertTrue(result['valid'], result['invalid_reasons'])

    def test_missing_fps_series_is_rejected(self):
        del self.arms['fixed']['meta']['fps_windows']
        self.save()
        self.assert_invalid('fps_windows missing or invalid')

    def test_worst_window_disagreement_is_rejected(self):
        meta = self.arms['priority']['meta']
        meta['fps_windows'] = [60, 30, 61]
        meta['fps_min'] = 30
        self.save()
        self.assert_invalid('fps_min spread')

    def test_crossing_before_release_is_rejected(self):
        row = self.arms['fixed']['rows'][0]
        row['crossed_sec'] = str(float(row['released_sec']) - 1)
        self.save()
        self.assert_invalid('crossed before it was released')

    def test_release_ahead_of_plan_is_rejected(self):
        rows = self.arms['fixed']['rows']
        late = max(rows, key=lambda row: float(row['released_sec']))
        late['released_sec'] = '0.0'
        self.save()
        self.assert_invalid('released before its planned offset')

    def test_last_crossing_after_run_end_is_rejected(self):
        self.arms['fixed']['meta']['last_crossing_sec'] = 61
        self.save()
        self.assert_invalid('last crossing falls after the run ended')

    def test_missing_last_crossing_is_rejected(self):
        del self.arms['priority']['meta']['last_crossing_sec']
        self.save()
        self.assert_invalid('last_crossing_sec missing')

    def test_duplicate_ids_zero_shared_reproduction(self):
        for name, seq in (('fixed', '0'), ('priority', '1')):
            for row in self.arms[name]['rows']:
                row['plan_seq'] = seq
        self.save()
        self.assert_invalid('duplicate plan_seq')
        self.assertEqual(analyze_batch(str(self.root), write=False)['plans_valid'], 0)

    def test_missing_and_unexpected_ids(self):
        self.arms['fixed']['rows'][0]['plan_seq'] = '99'
        self.save()
        self.assert_invalid('unexpected plan_seq')
        self.assert_invalid('missing 1 planned crossings')

    def test_bad_rows(self):
        original = copy.deepcopy(self.arms)
        for key, value in [('plan_seq', ''), ('plan_seq', '0.5'),
                           ('wait_time_sec', 'nan'), ('wait_time_sec', 'inf'),
                           ('wait_time_sec', '-1'), ('wait_time_sec', ''),
                           ('lane', '99'), ('will_turn', 'unknown'),
                           ('vehicle_type', 'unknown'), ('mode', 'other')]:
            with self.subTest(key=key, value=value):
                self.arms = copy.deepcopy(original)
                self.arms['fixed']['rows'][0][key] = value
                self.save()
                self.assertFalse(self.result()['valid'])

    # Recorded by every run from now on, but absent from runs archived before
    # the phase log gained a censoring status. Requiring it in the gate would
    # invalidate the existing archive, which is evidence, not a defect.
    OPTIONAL_METADATA = {'final_phase_censored'}

    def test_every_required_metadata_field(self):
        original = copy.deepcopy(self.arms)
        for key in set(original['fixed']['meta']) - self.OPTIONAL_METADATA:
            with self.subTest(key=key):
                self.arms = copy.deepcopy(original)
                del self.arms['fixed']['meta'][key]
                self.save()
                self.assertFalse(self.result()['valid'], key)

    def test_nonfinite_and_wrong_type_metadata(self):
        original = copy.deepcopy(self.arms)
        for key in ('fps_mean', 'fps_min', 'duration_sec', 'frames_total',
                    'release_drift_max_ms', 'release_drift_mean_ms'):
            for value in (float('nan'), float('inf'), -1, '60', True):
                with self.subTest(key=key, value=value):
                    self.arms = copy.deepcopy(original)
                    self.arms['fixed']['meta'][key] = value
                    self.save()
                    self.assert_invalid(key)

    def test_mismatched_provenance(self):
        for payload, key in [('configuration', 'configuration_hash'), ('source_files', 'source_hash')]:
            with self.subTest(payload=payload):
                self.arms['fixed']['meta'][payload]['changed'] = 1
                self.arms['fixed']['meta'][key] = fingerprint(self.arms['fixed']['meta'][payload])
                self.save()
                self.assert_invalid(f'{key} differs across arms')

    def test_timing_and_timeout(self):
        self.arms['fixed']['meta']['fps_mean'] = 40
        self.arms['priority']['meta']['release_drift_max_ms'] = 251
        self.arms['priority']['meta']['stop_reason'] = 'timeout'
        self.save()
        self.assert_invalid('fps_mean spread')
        self.assert_invalid('exceeds 250')
        self.assert_invalid('stop_reason')

    def test_missing_corrupt_and_tampered_plan(self):
        path = self.directory / 'plan.json'
        original = path.read_text()
        for contents in ('null', '{', '{}'):
            path.write_text(contents)
            self.assert_invalid('cannot verify plan.json')
        plan = json.loads(original)
        del plan['header']['content_hash']
        path.write_text(json.dumps(plan))
        self.assert_invalid('content_hash')
        plan = json.loads(original)
        plan['vehicles'][0]['lane'] = 2
        path.write_text(json.dumps(plan))
        self.assert_invalid('content_hash')
        path.unlink()
        self.assert_invalid('cannot verify plan.json')

    def test_resigned_malformed_plan_rejected(self):
        self.plan['vehicles'][1]['seq'] = 0
        path = self.directory / 'plan.json'
        write_plan(self.plan, str(path))
        with self.assertRaises(ValueError):
            load_plan(str(path))
        self.assert_invalid('vehicle IDs')

    def test_resigned_incomplete_header_and_timeline(self):
        original = copy.deepcopy(self.plan)
        for section, key, value in [
            ('header', 'uneven_mode', 42),
            ('header', 'traffic_conditions', None),
            ('header', 'traffic_conditions', {'high': float('nan')}),
            ('root', 'condition_timeline', []),
            ('root', 'condition_timeline', [None]),
        ]:
            with self.subTest(key=key, value=value):
                plan = copy.deepcopy(original)
                (plan if section == 'root' else plan[section])[key] = value
                write_plan(plan, str(self.directory / 'plan.json'))
                self.assert_invalid('cannot verify plan.json')

    def test_malformed_metadata_and_ambiguous_log(self):
        path = self.directory / 'fixed' / 'run_meta.json'
        for payload in ('null', '[]', '{', '3'):
            path.write_text(payload)
            self.assertFalse(self.result()['valid'])
        self.save()
        (self.directory / 'fixed' / 'extra.csv').write_text('plan_seq\n0\n')
        self.assert_invalid('2 vehicle logs')

    def test_summary_that_contradicts_the_rows_is_rejected(self):
        """
        Each field below is well-formed on its own and contradicts the rows.

        Every one of these passed the gate before: the gate checked that the
        fields existed and were finite, never that they described the run the
        rows describe.
        """
        original = copy.deepcopy(self.arms)
        cases = [
            ('release far later than the tolerance allows',
             lambda arm: arm['rows'][0].update(released_sec='5'),
             'release lateness'),
            ('a crossing after the run ended',
             lambda arm: arm['rows'][0].update(crossed_sec='1000'),
             'after the run ended'),
            ('stopped delay longer than the whole journey',
             lambda arm: arm['rows'][0].update(wait_time_sec='1000'),
             'exceeds its release-to-crossing interval'),
            ('one frame claimed as 60 fps for a minute',
             lambda arm: arm['meta'].update(frames_total=1),
             'not the reported'),
            ('a clearance unrelated to the last crossing',
             lambda arm: arm['meta'].update(last_crossing_sec=58.5),
             'does not match the last logged crossing'),
            ('drift the rows cannot account for',
             lambda arm: arm['meta'].update(release_drift_max_ms=200),
             'not supported by the logged releases'),
            ('telemetry covering the first seconds only',
             lambda arm: arm['meta'].update(fps_windows=[59], fps_min=59),
             'fps telemetry covers'),
        ]
        for label, mutate, expected in cases:
            with self.subTest(case=label):
                self.arms = copy.deepcopy(original)
                mutate(self.arms['fixed'])
                self.save()
                self.assert_invalid(expected)

    def test_rounding_does_not_reject_a_coherent_arm(self):
        """The allowances are for measurement, not for contradictions."""
        meta = self.arms['fixed']['meta']
        # Clearance rounded at the fourth decimal, frames a hair off 60 fps,
        # stopped delay a rounding step above the travel time.
        meta['last_crossing_sec'] = round(meta['last_crossing_sec'] + 0.002, 4)
        meta['frames_total'] = round(meta['frames_total'] * 1.02)
        row = self.arms['fixed']['rows'][0]
        travel = float(row['crossed_sec']) - float(row['released_sec'])
        row['wait_time_sec'] = f'{travel + 0.05:.2f}'
        self.save()
        self.assertTrue(self.result()['valid'], self.result()['invalid_reasons'])

    def test_missing_baseline_and_invalid_tolerances(self):
        self.assertFalse(analyze_pair(str(self.directory), write=False, baseline='absent')['valid'])
        for tolerance in (-1, float('nan'), float('inf')):
            self.assertFalse(analyze_pair(str(self.directory), write=False, fps_tolerance=tolerance)['valid'])


class IntervalTests(unittest.TestCase):
    def test_bootstrap_interval_brackets_the_mean_and_is_reproducible(self):
        from analyzers.analyze_paired import bootstrap_ci, contrast_summary
        values = [-1.0, -0.8, -1.4, -0.2, -1.1, -0.6, -0.9, -1.3]
        first = bootstrap_ci(values)
        self.assertEqual(first, bootstrap_ci(values))
        mean = sum(values) / len(values)
        self.assertLess(first['ci_low'], mean)
        self.assertGreater(first['ci_high'], mean)
        self.assertLess(first['ci_high'], 0)

        summary = contrast_summary(values)
        self.assertEqual(summary['plans'], 8)
        self.assertEqual(summary['plans_favouring_arm'], 8)

    def test_replication_count_grows_with_variability_and_precision(self):
        from analyzers.analyze_paired import plans_needed
        self.assertEqual(plans_needed(3, 1.0), 35)
        # Halving the target half-width costs four times the plans.
        self.assertEqual(plans_needed(3, 0.5), 139)
        self.assertLess(plans_needed(1, 1.0), plans_needed(3, 1.0))
        self.assertIsNone(plans_needed(None, 1.0))
        self.assertIsNone(plans_needed(3, 0))

    def test_interval_spanning_zero_is_reported_as_such(self):
        from analyzers.analyze_paired import bootstrap_ci
        interval = bootstrap_ci([-1.0, 1.2, -0.4, 0.9, 0.1, -0.7])
        self.assertLess(interval['ci_low'], 0)
        self.assertGreater(interval['ci_high'], 0)


if __name__ == '__main__':
    unittest.main()
