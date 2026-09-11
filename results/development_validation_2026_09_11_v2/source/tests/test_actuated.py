"""Deterministic specification tests for the simple actuated comparator."""
import unittest
from types import SimpleNamespace
from unittest import mock

import state
from core import cycle_actuated, policy
from core.detectors import GapOut, approach_occupied, in_detection_zone


class Rect:
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height


def vehicle(x=0, y=0, width=20, height=20, crossed=False):
    return SimpleNamespace(
        x=x, y=y, crossed=crossed,
        image=SimpleNamespace(get_rect=lambda: Rect(width, height)),
    )


class StopLineDetectorTests(unittest.TestCase):
    def test_directional_front_geometry_and_queued_vehicle_are_observed(self):
        # These leading edges are at, or upstream of, the configured stop line.
        cases = [
            ('right', vehicle(x=210, width=30)),  # front 240
            ('down', vehicle(y=220, height=20)),  # front 240
            ('left', vehicle(x=780)),
            ('up', vehicle(y=750)),
        ]
        for direction, candidate in cases:
            self.assertTrue(in_detection_zone(candidate, direction), direction)

    def test_approach_zone_excludes_crossed_and_outside_uncrossed_vehicles(self):
        queued = vehicle(x=200, width=30)       # right front 230, queued
        upstream = vehicle(x=0, width=20)       # front 20, outside zone
        departed = vehicle(x=241, width=20)     # beyond the stop line
        crossed = vehicle(x=210, width=30, crossed=True)
        self.assertTrue(approach_occupied('right', [queued, upstream]))
        self.assertFalse(approach_occupied('right', [upstream, departed, crossed]))


class GapOutTests(unittest.TestCase):
    def callback_for(self, observations):
        values = iter(observations)
        return GapOut(lambda direction: next(values), policy.ACTUATED_MIN_GREEN,
                      policy.ACTUATED_GAP_OUT_SEC)

    def test_empty_phase_honours_the_six_second_minimum(self):
        callback = self.callback_for([False] * 7)
        self.assertEqual([callback('right', second) for second in range(6)],
                         [False] * 6)
        self.assertTrue(callback('right', 6))

    def test_gap_out_waits_for_two_full_empty_seconds_after_vehicle_leaves(self):
        callback = self.callback_for([True] * 6 + [False] * 3)
        self.assertEqual([callback('right', second) for second in range(8)],
                         [False] * 8)
        self.assertTrue(callback('right', 8))

    def test_occupancy_resets_the_gap_timer(self):
        callback = self.callback_for([False, False, True, False, False, False])
        self.assertEqual([callback('right', second) for second in range(6)],
                         [False] * 6)


class ActuatedCycleTests(unittest.TestCase):
    def test_cycle_keeps_fixed_rotation_and_passes_the_bounded_phase_rule(self):
        calls = []

        def run_phase(green_index, green_time, round_index, phase_index,
                      weights, queues, **kwargs):
            calls.append((green_index, green_time, round_index, phase_index, kwargs))
            if len(calls) == 4:
                state.running = False

        previous_running = state.running
        self.addCleanup(setattr, state, 'running', previous_running)
        state.running = True
        weights = {'right': 0, 'down': 0, 'left': 0, 'up': 0}
        with mock.patch.object(cycle_actuated, 'all_red_start'), \
             mock.patch.object(cycle_actuated, 'decide', return_value=(weights, weights, 0)), \
             mock.patch.object(cycle_actuated, 'run_phase', side_effect=run_phase):
            cycle_actuated.actuated_traffic_cycle()

        self.assertEqual([call[0] for call in calls], [0, 1, 2, 3])
        self.assertEqual([call[1] for call in calls], [policy.ACTUATED_MAX_GREEN] * 4)
        self.assertEqual([call[3] for call in calls], [0, 1, 2, 3])
        self.assertTrue(all(call[4]['red_extra'] == 0 for call in calls))
        self.assertTrue(all(isinstance(call[4]['early_exit'], GapOut) for call in calls))

    def test_policy_declares_detector_limited_green_bounds(self):
        self.assertIsNone(policy.DURATION_RULES['actuated'])
        self.assertEqual(policy.GREEN_BOUNDS['actuated'], (6, 24))


if __name__ == '__main__':
    unittest.main()
