"""Observable scheduling rules before collecting study runs."""
import unittest
from unittest.mock import patch

from core import cycle_priority, policy
from analyzers.analyze_timing import compare_timing, study_controller_errors


class PriorityRoundTests(unittest.TestCase):
    def test_reranks_remaining_directions_and_serves_all_four(self):
        snapshots = [
            {'right': 1, 'down': 5, 'left': 3, 'up': 2},
            {'right': 10, 'down': 0, 'left': 3, 'up': 2},
            {'right': 0, 'down': 0, 'left': 3, 'up': 20},
            {'right': 0, 'down': 0, 'left': 3, 'up': 0},
        ]
        decisions = [
            ({'right': 1, 'down': 5, 'left': 3, 'up': 2}, 5),
            ({'right': 10, 'down': 0, 'left': 3, 'up': 2}, 10),
            ({'right': 0, 'down': 0, 'left': 3, 'up': 20}, 20),
            ({'right': 0, 'down': 0, 'left': 3, 'up': 0}, 3),
        ]
        calls = []
        def decide(index):
            weights, selected_weight = decisions[len(calls)]
            return weights, weights, selected_weight
        def run_phase(index, green, round_index, phase_index, weights, queues):
            calls.append((index, green, round_index, phase_index))
            if len(calls) == 4:
                cycle_priority.state.running = False
        with patch.object(cycle_priority.state, 'running', True), \
             patch.object(cycle_priority, 'all_red_start'), \
             patch.object(cycle_priority, 'get_weighted_vehicle_counts',
                          side_effect=snapshots), \
             patch.object(cycle_priority, 'decide', side_effect=decide), \
             patch.object(cycle_priority, 'run_phase', side_effect=run_phase):
            cycle_priority.control_traffic_cycle()
        self.assertEqual(calls, [
            (1, 6, 0, 0), (0, 7, 0, 1),
            (3, 15, 0, 2), (2, 6, 0, 3),
        ])
        self.assertEqual(set(index for index, *_ in calls), set(range(4)))

    def test_fixed_settings_are_distinct_timing_schedules(self):
        base = {'arm': 'fixed12', 'meta': {'controller': 'fixed',
                'configuration_hash': 'green12'}, 'rows': [], 'phases': []}
        other = {'arm': 'fixed24', 'meta': {'controller': 'fixed',
                 'configuration_hash': 'green24'}, 'rows': [], 'phases': []}
        self.assertFalse(compare_timing(base, other, None)['same_controller'])
        other['meta']['configuration_hash'] = 'green12'
        self.assertTrue(compare_timing(base, other, None)['same_controller'])

    def test_logged_green_must_match_the_arm_rule(self):
        fixed = {'arm': 'fixed12', 'meta': {'controller': 'fixed'}, 'phases': [
            {'round_index': '0', 'phase_index': '0', 'direction': 'right',
             'green_selected_sec': '12', 'decision_weight': '10'}]}
        self.assertEqual(study_controller_errors(fixed), [])
        fixed['phases'][0]['green_selected_sec'] = '24'
        self.assertIn('fixed12 selected green disagrees with its rule',
                      study_controller_errors(fixed))
        priority = {'arm': 'priority', 'meta': {'controller': 'priority'}, 'phases': [
            {'round_index': '0', 'phase_index': '0', 'direction': 'down',
             'green_selected_sec': '7', 'decision_weight': '10'}]}
        self.assertEqual(study_controller_errors(priority), [])
        priority['phases'][0]['green_selected_sec'] = '12'
        self.assertIn('priority selected green disagrees with its rule',
                      study_controller_errors(priority))

    def test_selected_green_stays_in_six_to_twenty_four_seconds(self):
        for weight, expected in ((0, 6), (10, 7), (20, 15), (32, 24), (100, 24)):
            with self.subTest(weight=weight):
                self.assertEqual(policy.priority_green(weight), expected)
