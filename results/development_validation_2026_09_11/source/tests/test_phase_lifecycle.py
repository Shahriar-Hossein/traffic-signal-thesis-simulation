"""
The phase record's lifecycle, driven on a fake clock.

No display and no real sleeping: `core.phase.run_phase` is the only thing
under test, and what is being tested is that the log describes the phase that
was actually served — including the one the run ended in the middle of.
"""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import state
from core import phase
from config import defaultGreen, defaultRed, defaultYellow
from models.traffic_signal import TrafficSignal, signals
from utils import logger


class FakeClock:
    """A monotonic run clock that only advances when the phase sleeps."""

    def __init__(self):
        self.now = 0.0

    def elapsed(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class PhaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.phase_log = folder / 'run_phases.csv'
        self.signal_log = folder / 'run_signal.csv'

        with self.phase_log.open('w', newline='') as handle:
            csv.writer(handle).writerow(logger.PHASE_LOG_COLUMNS)

        for name, value in (('phase_log_filename', str(self.phase_log)),
                            ('signal_log_filename', str(self.signal_log)),
                            ('_active_phase', None)):
            patcher = mock.patch.object(logger, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        signals.clear()
        signals.extend(TrafficSignal(defaultRed, defaultYellow, defaultGreen[i])
                       for i in range(4))
        self.addCleanup(signals.clear)

        self.clock = FakeClock()
        for module, name, value in ((phase, 'runclock', self.clock),
                                    (logger, 'state', state)):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(phase.time, 'sleep', self.clock.sleep)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.addCleanup(setattr, state, 'currentGreen', state.currentGreen)
        self.addCleanup(setattr, state, 'currentYellow', state.currentYellow)
        # Where every controller starts a phase from: the all-red the warm-up
        # sets, and the state the previous phase's end restores.
        state.currentGreen = phase.NO_GREEN
        state.currentYellow = 0

    def rows(self):
        with self.phase_log.open(newline='') as handle:
            return list(csv.DictReader(handle))

    def serve(self, green_time=4, **kwargs):
        weights = {'right': 8.0, 'down': 1.0, 'left': 0.0, 'up': 0.0}
        queues = {'right': 8, 'down': 1, 'left': 0, 'up': 0}
        phase.run_phase(0, green_time, 0, 0, weights, queues, **kwargs)

    def test_completed_phase_is_recorded_once_with_valid_transitions(self):
        self.serve(green_time=4)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['status'], logger.PHASE_COMPLETE)
        self.assertEqual(row['termination'], 'duration')
        self.assertEqual(row['direction'], 'right')
        start, end = float(row['green_start_sec']), float(row['green_end_sec'])
        self.assertEqual(end - start, 4)
        self.assertGreater(float(row['phase_end_sec']), end)
        self.assertEqual(float(row['green_selected_sec']), 4)

    def test_early_exit_is_a_termination_reason_not_a_short_green(self):
        self.serve(green_time=10, early_exit=lambda direction, second: second >= 3)
        row = self.rows()[0]
        self.assertEqual(row['status'], logger.PHASE_COMPLETE)
        self.assertEqual(row['termination'], 'early_exit')
        self.assertEqual(float(row['green_selected_sec']), 10)
        self.assertEqual(float(row['green_end_sec']) - float(row['green_start_sec']), 3)

    def test_shutdown_during_green_still_records_the_phase(self):
        def stop_during_green(direction, second):
            if second == 2:
                logger.finalize_phase(self.clock.elapsed())
                raise SystemExit  # the daemon thread is killed here
            return False

        with self.assertRaises(SystemExit):
            self.serve(green_time=10, early_exit=stop_during_green)

        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['status'], logger.PHASE_CENSORED)
        self.assertEqual(row['termination'], 'shutdown')
        # The green never ended on its own terms, so its recorded end is the
        # run end and its duration is not a granted duration.
        self.assertEqual(float(row['green_end_sec']), float(row['phase_end_sec']))
        self.assertLess(float(row['green_end_sec']) - float(row['green_start_sec']),
                        float(row['green_selected_sec']))

    def test_shutdown_during_yellow_keeps_the_measured_green(self):
        real_sleep = self.clock.sleep
        seen = {'yellow': False}

        def sleeping(seconds):
            real_sleep(seconds)
            if state.currentYellow == 1 and not seen['yellow']:
                seen['yellow'] = True
                logger.finalize_phase(self.clock.elapsed())
                raise SystemExit

        with mock.patch.object(phase.time, 'sleep', sleeping):
            with self.assertRaises(SystemExit):
                self.serve(green_time=4)

        row = self.rows()[0]
        self.assertEqual(row['status'], logger.PHASE_CENSORED)
        # The green did end normally; only the phase was cut short.
        self.assertEqual(float(row['green_end_sec']) - float(row['green_start_sec']), 4)

    def test_shutdown_after_a_phase_boundary_adds_nothing(self):
        self.serve(green_time=2)
        self.assertIsNone(logger.finalize_phase(self.clock.elapsed()))
        self.assertEqual(len(self.rows()), 1)

    def test_no_approach_is_green_while_the_record_is_written(self):
        permission = []
        original = logger.log_phase

        def watched(**fields):
            permission.append((state.currentGreen, state.currentYellow))
            original(**fields)

        with mock.patch.object(logger, 'log_phase', watched):
            self.serve(green_time=2)

        # `Vehicle.move` grants green on (currentGreen == index and
        # currentYellow == 0). During the write no approach may satisfy that.
        self.assertEqual(permission, [(phase.NO_GREEN, 0)])

    def test_the_decision_is_recorded_before_the_green_is_exposed(self):
        exposed = []
        original = logger.log_signal_change

        def watched(direction):
            exposed.append((state.currentGreen, logger._active_phase is not None))
            original(direction)

        with mock.patch.object(phase, 'log_signal_change', watched):
            self.serve(green_time=1)

        self.assertEqual(exposed, [(phase.NO_GREEN, True)])


if __name__ == '__main__':
    unittest.main()
