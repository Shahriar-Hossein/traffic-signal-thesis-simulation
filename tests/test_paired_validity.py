"""Failure-case tests use temporary synthetic logs, never historical data."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analyzers.analyze_paired import analyze_pair, analyze_batch
from core.plan import build_plan, write_plan, load_plan
from core.provenance import fingerprint


class ReplayValidityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'fixture'
        self.plan = build_plan(7, 3, 'even', plan_id='fixture')
        write_plan(self.plan, str(self.directory / 'plan.json'))
        self.arms = {}
        for name in ('fixed', 'priority'):
            folder = self.directory / name
            folder.mkdir()
            rows = []
            for vehicle in self.plan['vehicles']:
                rows.append({
                    'plan_seq': str(vehicle['seq']), 'wait_time_sec': '1.25', 'mode': name,
                    **{key: str(vehicle[key]) for key in (
                        'vehicle_type', 'direction', 'lane', 'will_turn',
                        'turn_direction', 'target_turn_lane')},
                })
            meta = dict(
                generation_source='plan', run_mode='vehicles', stop_reason='target_reached',
                plan_id='fixture', plan_hash=self.plan['header']['content_hash'], arm=name,
                uneven_mode='even', provenance_version=1, controller=name,
                vehicle_log='run.csv', signal_log='run_signal.csv', plan_path='plan.json',
                started_at='2026-09-10 00:00:00', ended_at='2026-09-10 00:01:00',
                vehicles_planned=3, target_vehicle_count=3, vehicles_released=3,
                vehicles_generated=3, vehicles_crossed=3, duration_sec=60,
                fps_mean=60, fps_min=59, frames_total=3600,
                release_drift_mean_ms=1, release_drift_max_ms=2,
                configuration={'speed': 2}, source_files={'main.py': 'abc'},
            )
            meta['configuration_hash'] = fingerprint(meta['configuration'])
            meta['source_hash'] = fingerprint(meta['source_files'])
            self.arms[name] = {'rows': rows, 'meta': meta}
        self.save()

    def save(self):
        for name, arm in self.arms.items():
            folder = self.directory / name
            with (folder / 'run.csv').open('w', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=list(arm['rows'][0]))
                writer.writeheader()
                writer.writerows(arm['rows'])
            (folder / 'run_meta.json').write_text(json.dumps(arm['meta']))
            (folder / 'run_signal.csv').write_text('timestamp,direction\n2026-09-10,right\n')

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

    def test_every_required_metadata_field(self):
        original = copy.deepcopy(self.arms)
        for key in original['fixed']['meta']:
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

    def test_missing_baseline_and_invalid_tolerances(self):
        self.assertFalse(analyze_pair(str(self.directory), write=False, baseline='absent')['valid'])
        for tolerance in (-1, float('nan'), float('inf')):
            self.assertFalse(analyze_pair(str(self.directory), write=False, fps_tolerance=tolerance)['valid'])


if __name__ == '__main__':
    unittest.main()
