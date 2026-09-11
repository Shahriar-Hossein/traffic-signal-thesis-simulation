import csv
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import state
from config import defaultGreen, defaultRed, defaultYellow
from core import observations, phase
from models.traffic_signal import TrafficSignal, signals
from utils import logger


class Rect:
    width = 30
    height = 20


def vehicle(x=0, crossed=False, waiting=False):
    return SimpleNamespace(
        x=x, y=0, crossed=crossed, is_waiting=waiting,
        image=SimpleNamespace(get_rect=lambda: Rect()),
    )


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def elapsed(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class LaneObservationTests(unittest.TestCase):
    def test_snapshot_counts_offscreen_uncrossed_waiting_and_detection(self):
        lanes = {
            0: [vehicle(x=0), vehicle(x=200, waiting=True),
                vehicle(x=210, crossed=True)],
            1: [], 2: [],
        }
        snapshot = observations.capture_lane_observations('right', 3.25, lanes)
        self.assertEqual(snapshot['sample_elapsed_sec'], 3.25)
        self.assertEqual(snapshot['direction'], 'right')
        self.assertEqual(snapshot['lanes'][0], {
            'lane': 0, 'uncrossed_count': 2, 'stopped_count': 1,
            'detection_zone_count': 1,
        })


class PhaseObservationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.phase_log = Path(self.temp.name) / 'phases.csv'
        with self.phase_log.open('w', newline='') as handle:
            csv.writer(handle).writerow(logger.PHASE_LOG_COLUMNS)

        for name, value in (('phase_log_filename', str(self.phase_log)),
                            ('signal_log_filename', str(Path(self.temp.name) / 'signal.csv')),
                            ('_active_phase', None)):
            patcher = mock.patch.object(logger, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.clock = FakeClock()
        for module, name, value in ((phase, 'runclock', self.clock),
                                    (logger, 'state', state)):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(phase.time, 'sleep', self.clock.sleep)
        patcher.start()
        self.addCleanup(patcher.stop)

        signals.clear()
        signals.extend(TrafficSignal(defaultRed, defaultYellow, defaultGreen[i])
                       for i in range(4))
        self.addCleanup(signals.clear)
        for direction in ('right', 'down', 'left', 'up'):
            for lane in range(3):
                state.vehicles[direction][lane].clear()
        state.currentGreen = phase.NO_GREEN
        state.currentYellow = 0
        state.vehicles['right'][0].append(vehicle(x=200, waiting=True))

    def rows(self):
        with self.phase_log.open(newline='') as handle:
            return list(csv.DictReader(handle))

    def serve(self, **kwargs):
        weights = {'right': 1, 'down': 0, 'left': 0, 'up': 0}
        queues = {'right': 1, 'down': 0, 'left': 0, 'up': 0}
        phase.run_phase(0, 2, 0, 0, weights, queues, **kwargs)

    def test_completed_phase_serializes_start_and_end_snapshots(self):
        self.serve()
        row = self.rows()[0]
        start = json.loads(row['lane_observations_start'])
        end = json.loads(row['lane_observations_end'])
        self.assertEqual(start['sample_elapsed_sec'], 0.0)
        self.assertEqual(start['lanes'][0]['uncrossed_count'], 1)
        self.assertEqual(start['lanes'][0]['detection_zone_count'], 1)
        self.assertEqual(end['sample_elapsed_sec'], 2.0)
        self.assertEqual(end['direction'], 'right')

    def test_green_censor_gets_end_snapshot(self):
        def stop_during_green(direction, second):
            if second == 1:
                logger.finalize_phase(self.clock.elapsed())
                raise SystemExit
            return False

        with self.assertRaises(SystemExit):
            self.serve(early_exit=stop_during_green)
        row = self.rows()[0]
        end = json.loads(row['lane_observations_end'])
        self.assertEqual(row['status'], logger.PHASE_CENSORED)
        self.assertEqual(end['sample_elapsed_sec'], 1.0)

    def test_yellow_censor_preserves_true_green_end_snapshot(self):
        real_sleep = self.clock.sleep
        seen = {'yellow': False}

        def sleeping(seconds):
            real_sleep(seconds)
            if state.currentYellow == 1 and not seen['yellow']:
                self.assertEqual(state.currentGreen, 0)
                seen['yellow'] = True
                logger.finalize_phase(self.clock.elapsed())
                raise SystemExit

        with mock.patch.object(phase.time, 'sleep', sleeping):
            with self.assertRaises(SystemExit):
                self.serve()
        row = self.rows()[0]
        end = json.loads(row['lane_observations_end'])
        self.assertEqual(row['status'], logger.PHASE_CENSORED)
        self.assertEqual(end['sample_elapsed_sec'], 2.0)


if __name__ == '__main__':
    unittest.main()
