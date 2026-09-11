"""Timing report tests use synthetic arms, never historical data."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analyzers.analyze_timing import analyze_timing
from core.plan import build_plan, write_plan
from utils.logger import PHASE_LOG_COLUMNS


class TimingReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'fixture'
        self.plan = build_plan(7, 3, 'even', plan_id='fixture')
        write_plan(self.plan, str(self.directory / 'plan.json'))

    def write_arm(self, name, release_shift=0.0, phase_shift=0.0, windows=(60, 60),
                  controller='fixed', phases=None, granted=24, window_sec=30.0):
        """
        One arm. `phases` is a list of (direction, start, granted[, status,
        termination]); the default is two 24s greens in the fixed order.
        """
        folder = self.directory / name
        folder.mkdir(parents=True)
        rows = [{
            'plan_seq': str(vehicle['seq']),
            'wait_time_sec': '1.0',
            'released_sec': f"{vehicle['t_offset_sec'] + release_shift:.4f}",
            'crossed_sec': f"{vehicle['t_offset_sec'] + release_shift + 10:.4f}",
        } for vehicle in self.plan['vehicles']]
        with (folder / 'run.csv').open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        if phases is None:
            phases = [(direction, 10.0 + index * 30 + phase_shift, granted)
                      for index, direction in enumerate(('right', 'down'))]
        with (folder / 'run_phases.csv').open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=PHASE_LOG_COLUMNS)
            writer.writeheader()
            for index, record in enumerate(phases):
                direction, start, length = record[:3]
                status = record[3] if len(record) > 3 else 'complete'
                termination = record[4] if len(record) > 4 else 'duration'
                actual = length if termination != 'duration' else length + 0.5
                writer.writerow({
                    'round_index': 0, 'phase_index': index, 'direction': direction,
                    'green_start_sec': start, 'green_selected_sec': length,
                    'green_end_sec': start + actual,
                    'phase_end_sec': start + actual + 5,
                    'status': status, 'termination': termination,
                })
        # One signal onset per phase row, which is what a complete log means.
        with (folder / 'run_signal.csv').open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['timestamp', 'direction'])
            for record in phases:
                writer.writerow(['2026-09-10 00:00:00', record[0]])

        duration = max(record[1] + record[2] + 7 for record in phases)
        actual_window = duration / len(windows)
        (folder / 'run_meta.json').write_text(json.dumps({
            'controller': controller, 'started_at': f'2026-09-10 00:0{len(name)}:00',
            'fps_mean': 60, 'fps_min': min(windows), 'fps_windows': list(windows),
            'fps_window_sec': window_sec,
            'fps_window_bounds': [[i * actual_window, (i + 1) * actual_window]
                                  for i in range(len(windows))],
            'fps_covered_sec': duration,
            'last_crossing_sec': duration - 1.5,
            'duration_sec': duration,
        }))
        return folder

    def report(self):
        return analyze_timing(str(self.directory), write=False)

    def test_reports_overrun_bounds_and_cross_arm_gaps(self):
        self.write_arm('a')
        self.write_arm('b', release_shift=0.25, phase_shift=0.1, windows=(60, 30))
        report = self.report()

        first = report['arms'][0]
        self.assertEqual(first['phases'], 2)
        # Greens were granted 24s and ran 24.5s.
        self.assertEqual(first['green_overrun_max_ms'], 500.0)
        self.assertEqual(first['green_distribution'], {'24.0': 2})
        self.assertEqual(first['release_lateness_max_ms'], 0.0)
        self.assertEqual(first['phase_completeness']['records_status'], 'complete')

        contrast = report['contrasts'][0]
        self.assertEqual(contrast['matched_vehicles'], 3)
        self.assertEqual(contrast['release_gap_max_ms'], 250.0)
        # Both arms ran `fixed`, so this is repeatability, and 100ms of drift
        # between two runs of one controller is a clock statement.
        self.assertTrue(contrast['same_controller'])
        self.assertEqual(contrast['phase_onset_drift_max_ms'], 100.0)
        self.assertIsNone(contrast['phase_onset_divergence_max_ms'])
        self.assertTrue(contrast['phase_order_matches_over_prefix'])
        self.assertEqual(contrast['fps_window_gap_max_pct'], 50.0)

    def test_fixed_duration_controllers_have_no_bounds_to_sit_on(self):
        self.write_arm('a')
        arm = self.report()['arms'][0]
        self.assertIsNone(arm['green_bounds'])
        self.assertIsNone(arm['green_at_upper_bound'])

    def test_a_green_at_the_fairness_ceiling_counts_against_that_ceiling(self):
        # 18s is this controller's maximum; against a hard-coded 24 it would
        # never be reported as sitting at its ceiling.
        self.write_arm('a', controller='fairness_priority', granted=18)
        arm = self.report()['arms'][0]
        self.assertEqual(arm['green_bounds'], [6, 18])
        self.assertEqual(arm['green_at_upper_bound'], 2)

        self.directory = self.directory.parent / 'other'
        write_plan(self.plan, str(self.directory / 'plan.json'))
        self.write_arm('a', controller='priority', granted=18)
        self.assertEqual(self.report()['arms'][0]['green_at_upper_bound'], 0)

    def test_a_shared_order_with_different_durations_is_not_a_clock_fault(self):
        """
        The duration ablation serves `fixed`'s order and grants different
        greens, so its onsets drift apart by design. Reporting that under the
        same heading as repeatability drift reads as a timing fault.
        """
        self.write_arm('a', controller='fixed', granted=24)
        self.write_arm('b', controller='fixed_order_adaptive_duration', granted=8,
                       phases=[('right', 10.0, 8), ('down', 25.0, 8)])
        contrast = self.report()['contrasts'][0]
        self.assertFalse(contrast['same_controller'])
        self.assertTrue(contrast['phase_order_matches_over_prefix'])
        # Divergence, reported as divergence; drift, withheld.
        self.assertIsNone(contrast['phase_onset_drift_max_ms'])
        self.assertEqual(contrast['phase_onset_divergence_max_ms'], 15000.0)
        self.assertEqual(self.report()['acceptance']['result'], 'accepted')

    def test_a_matching_prefix_of_unequal_sequences_is_said_to_be_a_prefix(self):
        self.write_arm('a')
        self.write_arm('b', phases=[('right', 10.0, 24), ('down', 40.0, 24),
                                    ('left', 70.0, 24)])
        contrast = self.report()['contrasts'][0]
        self.assertTrue(contrast['phase_order_matches_over_prefix'])
        self.assertFalse(contrast['phase_counts_equal'])
        self.assertEqual(contrast['phases_compared'], 2)

    def test_onset_gap_is_withheld_when_orders_differ(self):
        self.write_arm('a')
        folder = self.write_arm('b')
        rows = (folder / 'run_phases.csv').read_text().replace('right', 'left')
        (folder / 'run_phases.csv').write_text(rows)
        contrast = self.report()['contrasts'][0]
        self.assertFalse(contrast['phase_order_matches_over_prefix'])
        self.assertIsNone(contrast['phase_onset_drift_max_ms'])
        self.assertIsNone(contrast['phase_onset_divergence_max_ms'])

    def test_an_early_exit_is_not_counted_as_overrun(self):
        self.write_arm('a', controller='fairness_priority',
                       phases=[('right', 10.0, 18, 'complete', 'early_exit'),
                               ('down', 40.0, 18)])
        arm = self.report()['arms'][0]
        self.assertEqual(arm['greens_ended_early'], 1)
        # Only the green that ran to its granted duration contributes.
        self.assertEqual(arm['green_overrun_max_ms'], 500.0)

    def test_a_censored_green_is_not_a_granted_duration(self):
        self.write_arm('a', phases=[('right', 10.0, 24),
                                    ('down', 40.0, 24, 'censored', 'shutdown')])
        arm = self.report()['arms'][0]
        self.assertEqual(arm['phase_completeness']['phases_censored'], 1)
        self.assertEqual(arm['phase_completeness']['records_status'],
                         'final phase censored')
        self.assertEqual(arm['green_distribution'], {'24.0': 1})

    def test_greens_missing_from_the_log_are_rejected_not_averaged(self):
        folder = self.write_arm('a')
        # The signal log records three onsets; the phase log has two. That is
        # the defect the pilot had in every arm.
        with (folder / 'run_signal.csv').open('a', newline='') as output:
            csv.writer(output).writerow(['2026-09-10 00:00:00', 'left'])
        report = self.report()
        self.assertEqual(report['arms'][0]['phase_completeness']['phases_missing'], 1)
        self.assertEqual(report['acceptance']['result'], 'rejected')
        self.assertIn('missing from the phase log',
                      ' '.join(report['acceptance']['reasons']))

    def test_missing_telemetry_is_insufficient_evidence_not_a_pass(self):
        self.write_arm('a')
        self.write_arm('b')
        for path in self.directory.glob('*/run_phases.csv'):
            path.unlink()
        report = self.report()
        self.assertEqual(report['arms'][0]['phases'], 0)
        self.assertIsNone(report['arms'][0]['green_overrun_max_ms'])
        self.assertEqual(report['contrasts'][0]['phases_compared'], 0)
        # A pair with no phase logs used to produce a clean-looking report.
        self.assertEqual(report['acceptance']['result'], 'rejected')

    def test_series_that_are_not_sample_comparable_say_so(self):
        self.write_arm('a', windows=(60, 60))
        self.write_arm('b', windows=(60, 60, 60), window_sec=0.5)
        contrast = self.report()['contrasts'][0]
        self.assertTrue(contrast['fps_windows_comparable'])
        self.assertEqual(self.report()['acceptance']['result'], 'accepted')

    def test_stalls_at_different_moments_are_not_hidden_by_equal_extremes(self):
        """
        [30,60,60] and [60,60,30] share a mean and a minimum and slowed at
        different times. Equal summary values are not equal physics, and the
        boundaries are what tell them apart.
        """
        first = self.write_arm('a', windows=(30, 60, 60))
        second = self.write_arm('b', windows=(60, 60, 30))
        report = self.report()
        contrast = report['contrasts'][0]
        # The series themselves diverge sample against sample, which the
        # extremes alone never showed.
        self.assertEqual(contrast['fps_window_gap_max_pct'], 100.0)
        self.assertEqual(report['acceptance']['result'], 'rejected')
        self.assertEqual(report['arms'][0]['fps_mean'],
                         report['arms'][1]['fps_mean'])

        # And where a run recorded when each window actually ran, series that
        # cover different seconds are not treated as comparable.
        for folder, offset in ((first, 0.0), (second, 30.0)):
            meta = json.loads((folder / 'run_meta.json').read_text())
            meta['fps_window_bounds'] = [[offset + i, offset + i + 1]
                                         for i in range(3)]
            (folder / 'run_meta.json').write_text(json.dumps(meta))
        self.assertFalse(self.report()['contrasts'][0]['fps_windows_comparable'])
        self.assertEqual(self.report()['acceptance']['result'],
                         'rejected')

    def test_missing_clearance_is_none_not_an_invented_zero(self):
        self.write_arm('a')
        folder = self.write_arm('b')
        meta = json.loads((folder / 'run_meta.json').read_text())
        del meta['last_crossing_sec']
        (folder / 'run_meta.json').write_text(json.dumps(meta))
        self.assertIsNone(self.report()['contrasts'][0]['clearance_gap_sec'])

    def test_malformed_metadata_is_reported_rather_than_raised(self):
        self.write_arm('a')
        folder = self.write_arm('b')
        for payload in ('3', 'null', '[]', '{'):
            with self.subTest(payload=payload):
                (folder / 'run_meta.json').write_text(payload)
                report = self.report()
                self.assertTrue(report['errors'])
                self.assertNotEqual(report['acceptance']['result'], 'accepted')
                json.dumps(report, allow_nan=False)

    def test_report_is_json_serializable(self):
        self.write_arm('a')
        self.write_arm('b')
        report = analyze_timing(str(self.directory), write=True)
        self.assertTrue(Path(report['written_to']).exists())
        json.dumps(report, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
