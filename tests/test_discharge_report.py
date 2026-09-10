"""Discharge measurement tests use synthetic arms, never historical data."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import analyzers.analyze_discharge as discharge
from analyzers.analyze_discharge import analyze_discharge
from utils.logger import PHASE_LOG_COLUMNS


class DischargeTests(unittest.TestCase):
    def build(self, crossings, phases, fps=60.0, configuration=None, meta=None):
        """
        One arm folder.

        `phases` entries are (direction, start, granted[, status]); the
        captured configuration is part of the arm, because a report about an
        archived run must come from what that run recorded.
        """
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name) / 'arm'
        folder.mkdir()
        with (folder / 'run.csv').open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['plan_seq', 'direction', 'lane', 'crossed_sec',
                             'wait_time_sec', 'vehicle_type'])
            for index, (direction, lane, moment) in enumerate(crossings):
                writer.writerow([index, direction, lane, moment, 1.0, 'car'])
        with (folder / 'run_phases.csv').open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=PHASE_LOG_COLUMNS)
            writer.writeheader()
            for index, record in enumerate(phases):
                direction, start, length = record[:3]
                status = record[3] if len(record) > 3 else 'complete'
                writer.writerow({
                    'round_index': 0, 'phase_index': index, 'direction': direction,
                    'green_start_sec': start, 'green_selected_sec': length,
                    'green_end_sec': start + length,
                    'phase_end_sec': start + length + 5,
                    'status': status,
                    'termination': 'shutdown' if status == 'censored' else 'duration',
                })
        sidecar = {'controller': 'fixed', 'fps_mean': fps}
        if configuration is not False:
            sidecar['configuration'] = configuration or {
                'movingGap': 15, 'speeds': {'car': 2.0}}
        sidecar.update(meta or {})
        (folder / 'run_meta.json').write_text(json.dumps(sidecar))
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

    def test_first_crossing_delay_is_not_called_startup_lost_time(self):
        arm = self.build(
            crossings=[('right', 0, 12.0), ('right', 0, 22.0)],
            phases=[('right', 10.0, 20)],
        )
        report = analyze_discharge(arm)
        self.assertEqual(report['first_crossing_delay_mean_sec'], 2.0)
        self.assertNotIn('startup_delay_mean_sec', report)
        # Discharging spanned 12s of a 20s green.
        self.assertEqual(report['discharge_span_fraction_mean'], 0.6)

    def test_four_greens_that_must_not_read_alike(self):
        """
        A continuously queued green, one late isolated crossing, an empty
        green, and a green whose first arrival is late with no onset queue.

        The old utilisation number gave the second of these almost 100% and
        excluded the third entirely, so all four collapsed into one figure.
        """
        queued = self.build(
            crossings=[('right', 0, m) for m in (11.0, 13.0, 15.0, 17.0, 19.0)],
            phases=[('right', 10.0, 10)])
        late_single = self.build(
            crossings=[('right', 0, 19.5)], phases=[('right', 10.0, 10)])
        empty = self.build(crossings=[], phases=[('right', 10.0, 10)])
        delayed = self.build(
            crossings=[('right', 0, 16.0), ('right', 0, 18.0)],
            phases=[('right', 10.0, 10)])

        spans = {name: analyze_discharge(arm)['discharge_span_fraction_mean']
                 for name, arm in (('queued', queued), ('late_single', late_single),
                                   ('empty', empty), ('delayed', delayed))}
        self.assertEqual(spans['empty'], 0.0)
        self.assertEqual(len(set(spans.values())), 4, spans)

        # A single crossing is not a discharge rate, however late it lands.
        self.assertIsNone(analyze_discharge(late_single)['crossings_per_green_second_mean'])
        self.assertEqual(analyze_discharge(queued)['greens_qualifying_for_rate'], 1)
        # Empty greens are counted, not dropped.
        self.assertEqual(analyze_discharge(empty)['greens_serving_nobody'], 1)

    def test_no_residual_queue_is_claimed(self):
        arm = self.build(crossings=[('right', 0, 11.0)], phases=[('right', 10.0, 24)])
        report = analyze_discharge(arm)
        self.assertFalse(report['residual_queue_measured'])
        self.assertNotIn('residual queue', discharge.__doc__.lower().split('there is no')[1][:40])

    def test_a_censored_green_is_excluded_from_rates_but_not_from_service(self):
        arm = self.build(
            crossings=[('right', 0, 11.0), ('right', 0, 13.0),
                       ('down', 0, 41.0), ('down', 0, 43.0), ('down', 0, 45.0)],
            phases=[('right', 10.0, 24), ('down', 40.0, 24, 'censored')],
        )
        report = analyze_discharge(arm)
        self.assertEqual(report['phases_censored'], 1)
        # The vehicles it served are still served.
        self.assertEqual(report['served_per_green_mean'], 2.5)
        # Its truncated green does not normalise anything.
        self.assertEqual(report['greens_qualifying_for_rate'], 0)

    def test_prediction_uses_the_runs_own_configuration_not_the_live_one(self):
        arm = self.build(
            crossings=[('right', 0, 11.0), ('right', 0, 13.0)],
            phases=[('right', 10.0, 24)],
            configuration={'movingGap': 182, 'speeds': {'car': 2.0}},
        )
        report = analyze_discharge(arm)
        self.assertEqual(report['headway_p05_by_leader'], {'car': 2.0})
        # (54 px + the run's own 182 px gap) / (2.0 px/frame * 60 fps)
        self.assertAlmostEqual(
            report['headway_predicted_by_leader']['car'], 1.967, places=3)

        # Changing the live module cannot move an archived run's prediction.
        import config
        original = config.movingGap
        try:
            config.movingGap = 999
            self.assertAlmostEqual(
                analyze_discharge(arm)['headway_predicted_by_leader']['car'],
                1.967, places=3)
        finally:
            config.movingGap = original

    def test_prediction_is_withheld_without_provenance_or_a_frame_rate(self):
        no_fps = self.build(
            crossings=[('right', 0, 11.0), ('right', 0, 13.0)],
            phases=[('right', 10.0, 24)], fps=None)
        self.assertEqual(analyze_discharge(no_fps)['headway_predicted_by_leader'], {})
        self.assertTrue(analyze_discharge(no_fps)['headway_prediction_withheld'])

        no_config = self.build(
            crossings=[('right', 0, 11.0)], phases=[('right', 10.0, 24)],
            configuration=False)
        report = analyze_discharge(no_config)
        self.assertEqual(report['headway_predicted_by_leader'], {})
        self.assertIn('configuration', report['headway_prediction_withheld'])

    def test_malformed_input_reports_rather_than_raises(self):
        for payload in ('null', '[]', '3', '"text"', '{'):
            with self.subTest(payload=payload):
                arm = self.build(crossings=[('right', 0, 11.0)],
                                 phases=[('right', 10.0, 24)])
                (Path(arm) / 'run_meta.json').write_text(payload)
                report = analyze_discharge(arm)
                json.dumps(report, allow_nan=False)

    def test_nonfinite_phase_values_are_missing_not_measurements(self):
        arm = self.build(crossings=[('right', 0, 11.0)], phases=[('right', 10.0, 24)])
        path = Path(arm) / 'run_phases.csv'
        path.write_text(path.read_text().replace(',24,', ',nan,'))
        report = analyze_discharge(arm)
        self.assertEqual(report['phases'], 0)
        json.dumps(report, allow_nan=False)

    def test_missing_arm_reports_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            report = analyze_discharge(empty)
            self.assertIn('error', report)


if __name__ == '__main__':
    unittest.main()
