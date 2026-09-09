"""Discharge measurement tests use synthetic arms, never historical data."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analyzers.analyze_discharge import analyze_discharge


class DischargeTests(unittest.TestCase):
    def build(self, crossings, phases):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name) / 'arm'
        folder.mkdir()
        with (folder / 'run.csv').open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['plan_seq', 'direction', 'lane', 'crossed_sec', 'wait_time_sec'])
            for index, (direction, lane, moment) in enumerate(crossings):
                writer.writerow([index, direction, lane, moment, 1.0])
        with (folder / 'run_phases.csv').open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['round_index', 'phase_index', 'direction',
                             'green_start_sec', 'green_selected_sec',
                             'green_end_sec', 'phase_end_sec'])
            for index, (direction, start, length) in enumerate(phases):
                writer.writerow([0, index, direction, start, length,
                                 start + length, start + length + 5])
        (folder / 'run_meta.json').write_text(json.dumps({'controller': 'fixed'}))
        return str(folder)

    def test_headways_are_measured_within_a_lane(self):
        # Two lanes discharging together: the across-lane gap is 0.1s, but the
        # within-lane headway is 2s. Only the latter is a headway.
        arm = self.build(
            crossings=[('right', 0, 11.0), ('right', 1, 11.1),
                       ('right', 0, 13.0), ('right', 1, 13.1)],
            phases=[('right', 10.0, 24)],
        )
        report = analyze_discharge(arm)
        self.assertEqual(report['headways_measured'], 2)
        self.assertEqual(report['headway_mean_sec'], 2.0)
        self.assertEqual(report['served_per_green_mean'], 4)
        self.assertEqual(report['crossings_outside_green'], 0)

    def test_crossings_outside_any_green_are_counted_not_attributed(self):
        arm = self.build(
            crossings=[('right', 0, 11.0), ('right', 0, 40.0), ('down', 0, 11.5)],
            phases=[('right', 10.0, 24)],
        )
        report = analyze_discharge(arm)
        # One after the green ended, one on an approach that never had one.
        self.assertEqual(report['crossings_outside_green'], 2)
        self.assertEqual(report['served_per_green_mean'], 1)
        self.assertEqual(report['headways_measured'], 0)

    def test_startup_delay_and_utilisation(self):
        arm = self.build(
            crossings=[('right', 0, 12.0), ('right', 0, 22.0)],
            phases=[('right', 10.0, 20)],
        )
        report = analyze_discharge(arm)
        self.assertEqual(report['startup_delay_mean_sec'], 2.0)
        # Discharging stopped 12s into a 20s green.
        self.assertEqual(report['green_utilisation_mean'], 0.6)

    def test_missing_arm_reports_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            report = analyze_discharge(empty)
            self.assertIn('error', report)


if __name__ == '__main__':
    unittest.main()
