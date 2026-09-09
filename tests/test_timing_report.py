"""Timing report tests use synthetic arms, never historical data."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analyzers.analyze_timing import analyze_timing
from core.plan import build_plan, write_plan


class TimingReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'fixture'
        self.plan = build_plan(7, 3, 'even', plan_id='fixture')
        write_plan(self.plan, str(self.directory / 'plan.json'))

    def write_arm(self, name, release_shift=0.0, phase_shift=0.0, windows=(60, 60)):
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
        with (folder / 'run_phases.csv').open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['round_index', 'phase_index', 'direction',
                             'green_start_sec', 'green_selected_sec',
                             'green_end_sec', 'phase_end_sec'])
            for index, direction in enumerate(('right', 'down')):
                start = 10.0 + index * 30 + phase_shift
                writer.writerow([0, index, direction, start, 24,
                                 start + 24.5, start + 29.5])
        (folder / 'run_meta.json').write_text(json.dumps({
            'controller': 'fixed', 'started_at': f'2026-09-10 00:0{len(name)}:00',
            'fps_mean': 60, 'fps_min': min(windows), 'fps_windows': list(windows),
            'last_crossing_sec': 58.5 + phase_shift, 'duration_sec': 60,
        }))

    def test_reports_overrun_bounds_and_cross_arm_gaps(self):
        self.write_arm('a')
        self.write_arm('b', release_shift=0.25, phase_shift=0.1, windows=(60, 30))
        report = analyze_timing(str(self.directory), write=False)

        first = report['arms'][0]
        self.assertEqual(first['phases'], 2)
        # Greens were granted 24s and ran 24.5s.
        self.assertEqual(first['green_overrun_max_ms'], 500.0)
        self.assertEqual(first['green_at_upper_bound'], 2)
        self.assertEqual(first['green_distribution'], {'24.0': 2})
        self.assertEqual(first['release_lateness_max_ms'], 0.0)

        contrast = report['contrasts'][0]
        self.assertEqual(contrast['matched_vehicles'], 3)
        self.assertEqual(contrast['release_gap_max_ms'], 250.0)
        self.assertEqual(contrast['phase_onset_gap_max_ms'], 100.0)
        self.assertTrue(contrast['phase_order_identical'])
        self.assertEqual(contrast['fps_window_gap_max_pct'], 50.0)

    def test_onset_gap_is_withheld_when_orders_differ(self):
        self.write_arm('a')
        folder = self.directory / 'b'
        self.write_arm('b')
        rows = (folder / 'run_phases.csv').read_text().replace('right', 'left')
        (folder / 'run_phases.csv').write_text(rows)
        contrast = analyze_timing(str(self.directory), write=False)['contrasts'][0]
        self.assertFalse(contrast['phase_order_identical'])
        self.assertIsNone(contrast['phase_onset_gap_max_ms'])

    def test_missing_phase_log_does_not_crash(self):
        self.write_arm('a')
        self.write_arm('b')
        for path in self.directory.glob('*/run_phases.csv'):
            path.unlink()
        report = analyze_timing(str(self.directory), write=False)
        self.assertEqual(report['arms'][0]['phases'], 0)
        self.assertIsNone(report['arms'][0]['green_overrun_max_ms'])
        self.assertEqual(report['contrasts'][0]['phases_compared'], 0)

    def test_report_is_json_serializable(self):
        self.write_arm('a')
        self.write_arm('b')
        report = analyze_timing(str(self.directory), write=True)
        self.assertTrue(Path(report['written_to']).exists())
        json.dumps(report, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
