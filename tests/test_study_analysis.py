"""Focused contracts for scheduled scenarios and fixed-duration contrasts."""
import copy
import unittest

from analyzers.analyze_paired import (
    check_validity, compare_arms, contrast_block, scenario_identity,
    scenario_label,
)
from core.provenance import fingerprint
from core.plan import build_plan
from tests.test_paired_validity import ReplayValidityTests


class StudyAnalysisTests(unittest.TestCase):
    def test_scheduled_identity_uses_scenario_and_arrival_schedule(self):
        plan = build_plan(
            8, None, 'even', plan_id='scenario-a',
            schedule=[{'condition': 'low', 'duration_sec': 10}],
            scenario='low-load',
        )
        identity = scenario_identity(plan['header'])
        self.assertEqual(identity['scenario'], 'low-load')
        self.assertEqual(identity['schedule'], fingerprint(plan['header']['arrival_schedule']))
        self.assertIn('low-load_', scenario_label(identity))

        changed_schedule = copy.deepcopy(plan['header'])
        changed_schedule['arrival_schedule'][0]['duration_sec'] = 12
        self.assertNotEqual(identity, scenario_identity(changed_schedule))
        changed_scenario = copy.deepcopy(plan['header'])
        changed_scenario['scenario'] = 'medium-load'
        self.assertNotEqual(identity, scenario_identity(changed_scenario))
        changed_skew = copy.deepcopy(plan['header'])
        changed_skew['uneven_mode'] = 'right'
        self.assertNotEqual(identity, scenario_identity(changed_skew))

    def test_priority_is_compared_to_each_fixed_setting_with_other_minus_fixed_sign(self):
        fixed12 = {'arm': 'fixed12', 'rows': [
            {'plan_seq': '0', 'direction': 'right', 'wait_time_sec': '8'},
            {'plan_seq': '1', 'direction': 'up', 'wait_time_sec': '4'},
        ]}
        fixed24 = {'arm': 'fixed24', 'rows': [
            {'plan_seq': '0', 'direction': 'right', 'wait_time_sec': '6'},
            {'plan_seq': '1', 'direction': 'up', 'wait_time_sec': '6'},
        ]}
        priority = {'arm': 'priority', 'rows': [
            {'plan_seq': '0', 'direction': 'right', 'wait_time_sec': '3'},
            {'plan_seq': '1', 'direction': 'up', 'wait_time_sec': '5'},
        ]}
        against12 = compare_arms(fixed12, priority)
        against24 = compare_arms(fixed24, priority)
        self.assertEqual(against12['baseline'], 'fixed12')
        self.assertEqual(against12['delta_wait_mean'], -2)
        self.assertEqual(against12['delta_wait_mean_by_direction'],
                         {'right': -5.0, 'up': 1.0})
        self.assertEqual(against24['baseline'], 'fixed24')
        self.assertEqual(against24['delta_wait_mean'], -2)

    def test_direction_effects_are_summarized_by_independent_plan(self):
        pairs = [
            {'arms': {}, 'paired': [{
                'baseline': 'fixed24', 'arm': 'priority', 'delta_wait_mean': -2,
                'delta_wait_mean_by_direction': {'right': -3, 'up': -1},
            }]},
            {'arms': {}, 'paired': [{
                'baseline': 'fixed24', 'arm': 'priority', 'delta_wait_mean': -4,
                'delta_wait_mean_by_direction': {'right': -5, 'up': -3},
            }]},
        ]
        result = contrast_block(pairs)['fixed24_vs_priority']
        by_direction = result['delta_wait_mean_by_direction']
        self.assertEqual(by_direction['right']['plans'], 2)
        self.assertEqual(by_direction['right']['mean_of_plan_deltas'], -4)
        self.assertIsNotNone(by_direction['right']['ci_low'])
        self.assertIsNotNone(by_direction['right']['ci_high'])

    def test_fixed_green_variation_is_the_only_configuration_difference_allowed(self):
        fixture = ReplayValidityTests('test_complete_pair_and_batch')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        arms = {}
        for name, controller, green in (
                ('fixed12', 'fixed', 12), ('fixed24', 'fixed', 24),
                ('priority', 'priority', 24)):
            source = fixture.arms['fixed' if controller == 'fixed' else 'priority']
            arm = copy.deepcopy(source)
            arm['arm'] = name
            arm['log_path'] = f'/tmp/{name}.csv'
            arm['signal_changes'] = 1
            arm['meta']['arm'] = name
            arm['meta']['vehicle_log'] = f'{name}.csv'
            arm['meta']['signal_log'] = f'{name}_signal.csv'
            arm['meta']['controller'] = controller
            for row in arm['rows']:
                row['mode'] = controller
            arm['meta']['configuration']['defaultGreen'] = {
                str(index): green for index in range(4)
            }
            arm['meta']['configuration_hash'] = fingerprint(arm['meta']['configuration'])
            arms[name] = arm
        self.assertEqual(check_validity(list(arms.values()), fixture.plan, .05, 250), [])

        arms['fixed24']['meta']['configuration']['stoppingGap'] = 99
        arms['fixed24']['meta']['configuration_hash'] = fingerprint(
            arms['fixed24']['meta']['configuration'])
        reasons = check_validity(list(arms.values()), fixture.plan, .05, 250)
        self.assertIn('configuration_hash differs across arms', reasons)

    def test_fixed_green_exception_rejects_swapped_labels(self):
        fixture = ReplayValidityTests('test_complete_pair_and_batch')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        arms = {}
        for name, controller, green in (
                ('fixed12', 'fixed', 24), ('fixed24', 'fixed', 12),
                ('priority', 'priority', 24)):
            source = fixture.arms['fixed' if controller == 'fixed' else 'priority']
            arm = copy.deepcopy(source)
            arm['arm'] = name
            arm['log_path'] = f'/tmp/{name}.csv'
            arm['signal_changes'] = 1
            arm['meta']['arm'] = name
            arm['meta']['vehicle_log'] = f'{name}.csv'
            arm['meta']['signal_log'] = f'{name}_signal.csv'
            arm['meta']['controller'] = controller
            for row in arm['rows']:
                row['mode'] = controller
            arm['meta']['configuration']['defaultGreen'] = {
                str(index): green for index in range(4)
            }
            arm['meta']['configuration_hash'] = fingerprint(arm['meta']['configuration'])
            arms[name] = arm
        reasons = check_validity(list(arms.values()), fixture.plan, .05, 250)
        self.assertIn('configuration_hash differs across arms', reasons)


if __name__ == '__main__':
    unittest.main()
