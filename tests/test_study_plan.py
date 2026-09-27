"""Fixed-duration demand schedules for development study plans."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from core.plan import build_plan, content_hash, load_plan, write_plan
from scripts.make_plan import SCENARIOS, DEVELOPMENT_SEEDS, make_plans


class ScheduledPlanTests(unittest.TestCase):
    def make_plan(self, schedule=None, mode='even', scenario='balanced_moderate'):
        if schedule is None:
            schedule = [{'condition': 'medium', 'duration_sec': 10}]
        return build_plan(301, None, mode, schedule=schedule, scenario=scenario)

    @staticmethod
    def resign(plan, path):
        plan['header']['content_hash'] = content_hash(plan)
        Path(path).write_text(json.dumps(plan))

    def test_study_grid_has_five_independent_plans_per_environment(self):
        self.assertEqual(set(SCENARIOS), {
            'balanced_moderate', 'one_busy', 'two_busy',
            'high_low_high', 'sustained_high',
        })
        self.assertEqual(len(set(DEVELOPMENT_SEEDS)), 5)
        self.assertEqual([name for name, _ in SCENARIOS['high_low_high'][1]],
                         ['high', 'low', 'high'])
        with tempfile.TemporaryDirectory() as root:
            selected = {'balanced_moderate': SCENARIOS['balanced_moderate']}
            paths = make_plans(root, selected, (301, 302))
            self.assertEqual(len(paths), 2)
            self.assertNotEqual(load_plan(str(paths[0]))['header']['content_hash'],
                                load_plan(str(paths[1]))['header']['content_hash'])
            with self.assertRaises(FileExistsError):
                make_plans(root, selected, (301, 303))
            self.assertFalse((Path(root) / 'balanced_moderate_seed303').exists())

    def test_study_environments_derive_count_from_full_duration(self):
        cases = (
            ('balanced_moderate', 'even', [('medium', 10)], 20),
            ('one_busy', 'up', [('medium', 10)], 20),
            ('two_busy', 'up_down', [('medium', 10)], 20),
            ('high_low_high', 'even', [('high', 10), ('low', 10), ('high', 10)], 85),
            ('sustained_high', 'even', [('high', 30)], 120),
        )
        for name, mode, phases, expected_count in cases:
            with self.subTest(name=name):
                schedule = [{'condition': c, 'duration_sec': d} for c, d in phases]
                plan = self.make_plan(schedule, mode, name)
                self.assertEqual(plan['header']['schema_version'], 2)
                self.assertEqual(plan['header']['scenario'], name)
                self.assertEqual(plan['header']['arrival_schedule'], schedule)
                self.assertEqual(len(plan['vehicles']), expected_count)
                self.assertEqual(plan['header']['target_vehicle_count'], expected_count)
                self.assertLess(plan['vehicles'][-1]['t_offset_sec'], sum(d for _, d in phases))
                with tempfile.TemporaryDirectory() as root:
                    path = Path(root) / 'plan.json'
                    write_plan(plan, str(path))
                    self.assertEqual(load_plan(str(path))['vehicles'], plan['vehicles'])

    def test_boundaries_are_exact_and_labels_follow_the_schedule(self):
        schedule = [{'condition': 'high', 'duration_sec': 1},
                    {'condition': 'low', 'duration_sec': 0.1},
                    {'condition': 'high', 'duration_sec': 1}]
        plan = self.make_plan(schedule, scenario='high_low_high')
        self.assertEqual(plan['condition_timeline'], [
            {'t_offset_sec': 0.0, 'condition': 'high'},
            {'t_offset_sec': 1.0, 'condition': 'low'},
            {'t_offset_sec': 1.1, 'condition': 'high'},
        ])
        self.assertEqual([v['t_offset_sec'] for v in plan['vehicles']],
                         [0, 0.25, 0.5, 0.75, 1, 1.1, 1.35, 1.6, 1.85])
        self.assertEqual([v['condition'] for v in plan['vehicles']],
                         ['high'] * 4 + ['low'] + ['high'] * 4)

    def test_schedule_is_part_of_identity_and_does_not_mutate_input(self):
        first = [{'condition': 'high', 'duration_sec': 4}]
        second = [{'condition': 'high', 'duration_sec': 5}]
        a = self.make_plan(first)
        b = self.make_plan(second)
        self.assertNotEqual(a['header']['plan_id'], b['header']['plan_id'])
        self.assertNotEqual(content_hash(a), content_hash(b))
        alternate_name = self.make_plan(first, scenario='another_environment')
        self.assertNotEqual(a['header']['plan_id'],
                            alternate_name['header']['plan_id'])
        first[0]['duration_sec'] = 10
        self.assertEqual(a['header']['arrival_schedule'][0]['duration_sec'], 4)

    def test_builder_rejects_bad_schedule_and_count_quota(self):
        bad = ([], [{'condition': 'bad', 'duration_sec': 1}],
               [{'condition': 'high', 'duration_sec': 0}],
               [{'condition': 'high', 'duration_sec': float('nan')}],
               [{'condition': 'high', 'duration_sec': 0.0000001}],
               [{'condition': 'high', 'duration_sec': 1, 'extra': 3}])
        for schedule in bad:
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                self.make_plan(schedule)
        with self.assertRaisesRegex(ValueError, 'count=None'):
            build_plan(301, 5, 'even', schedule=[{'condition': 'high', 'duration_sec': 1}])

    def test_rehashed_malformed_schedules_and_arrivals_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            original = self.make_plan([
                {'condition': 'high', 'duration_sec': 2},
                {'condition': 'low', 'duration_sec': 2},
                {'condition': 'high', 'duration_sec': 2},
            ], scenario='high_low_high')
            for mutation in ('duration', 'boundary', 'arrival', 'label', 'count', 'scenario'):
                with self.subTest(mutation=mutation):
                    plan = copy.deepcopy(original)
                    if mutation == 'duration':
                        plan['header']['arrival_schedule'][1]['duration_sec'] = -1
                    elif mutation == 'boundary':
                        plan['condition_timeline'][1]['t_offset_sec'] = 2.25
                    elif mutation == 'arrival':
                        plan['vehicles'][1]['t_offset_sec'] = 0.3
                    elif mutation == 'label':
                        plan['vehicles'][1]['condition'] = 'low'
                    elif mutation == 'count':
                        plan['vehicles'].pop()
                        plan['header']['target_vehicle_count'] -= 1
                    else:
                        plan['header']['scenario'] = []
                    self.resign(plan, path)
                    with self.assertRaises(ValueError):
                        load_plan(str(path))


if __name__ == '__main__':
    unittest.main()
