"""The scenario grid and the plan knobs it depends on."""
import json
from pathlib import Path
import tempfile
import unittest

from core.plan import build_plan, content_hash, load_plan, write_plan, default_plan_id
from scripts import scenarios


class DemandRegimeTests(unittest.TestCase):
    def test_pinned_condition_holds_for_the_whole_plan(self):
        for condition in ('low', 'medium', 'high'):
            plan = build_plan(5, 40, 'even', condition=condition)
            self.assertEqual({v['condition'] for v in plan['vehicles']}, {condition})
            self.assertEqual({e['condition'] for e in plan['condition_timeline']},
                             {condition})
            self.assertEqual(plan['header']['pinned_condition'], condition)

    def test_regime_changes_arrival_times_but_not_the_vehicles(self):
        # The regime must be the only thing that varies, or a scenario
        # comparison confounds demand with a different vehicle mix.
        busy = build_plan(5, 40, 'even', condition='high')['vehicles']
        quiet = build_plan(5, 40, 'even', condition='low')['vehicles']
        for one, other in zip(busy, quiet):
            self.assertEqual(
                (one['direction'], one['lane'], one['vehicle_type'],
                 one['will_turn'], one['turn_direction'], one['target_turn_lane']),
                (other['direction'], other['lane'], other['vehicle_type'],
                 other['will_turn'], other['turn_direction'], other['target_turn_lane']),
            )
        self.assertLess(busy[-1]['t_offset_sec'], quiet[-1]['t_offset_sec'])

    def test_pinning_produces_a_distinct_plan_and_id(self):
        self.assertNotEqual(content_hash(build_plan(5, 40, 'even')),
                            content_hash(build_plan(5, 40, 'even', condition='high')))
        self.assertNotEqual(default_plan_id('even', 40, 5),
                            default_plan_id('even', 40, 5, 'high'))

    def test_unknown_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            build_plan(5, 40, 'even', condition='rush_hour')

    def test_unknown_skew_is_rejected_not_silently_uniform(self):
        with self.assertRaises(ValueError):
            build_plan(5, 40, 'evne')

    def test_plan_without_the_field_loads_as_unpinned(self):
        # Plans written before pinned_condition existed must stay readable:
        # adding the key would change their content hash.
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            write_plan(build_plan(5, 40, 'even'), str(path))
            stored = json.loads(path.read_text())
            del stored['header']['pinned_condition']
            stored['header']['content_hash'] = content_hash(stored)
            path.write_text(json.dumps(stored))
            self.assertIsNone(load_plan(str(path))['header'].get('pinned_condition'))

    def test_pinned_plan_round_trips_through_load(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            write_plan(build_plan(5, 40, 'even', condition='high'), str(path))
            self.assertEqual(load_plan(str(path))['header']['pinned_condition'], 'high')

    def test_timeline_contradicting_the_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            plan = build_plan(5, 40, 'even', condition='high')
            write_plan(plan, str(path))
            stored = json.loads(path.read_text())
            stored['condition_timeline'][0]['condition'] = 'low'
            stored['header']['content_hash'] = content_hash(stored)
            path.write_text(json.dumps(stored))
            with self.assertRaisesRegex(ValueError, 'contradicts pinned_condition'):
                load_plan(str(path))


class GridTests(unittest.TestCase):
    def test_grid_is_the_full_skew_by_regime_cross(self):
        cells = list(scenarios.scenarios())
        self.assertEqual(len(cells), len(scenarios.SKEWS) * len(scenarios.REGIMES))
        self.assertEqual(len({cell['scenario'] for cell in cells}), len(cells))

    def test_evaluation_seeds_are_disjoint_from_development(self):
        self.assertFalse(set(scenarios.EVALUATION_SEEDS)
                         & set(scenarios.DEVELOPMENT_SEEDS))

    def test_every_cell_builds_a_plan(self):
        for cell in scenarios.scenarios():
            plan = build_plan(1, 5, cell['uneven_mode'], condition=cell['condition'])
            self.assertEqual(len(plan['vehicles']), 5)

    def test_commands_cover_every_cell_and_seed(self):
        lines = scenarios.commands([1, 2], ['fixed', 'priority'])
        self.assertEqual(len(lines), len(list(scenarios.scenarios())) * 2)
        self.assertTrue(all('--arms fixed priority' in line for line in lines))
        # A changing-demand cell must not pin a condition.
        changing = [line for line in lines if '--uneven-mode even' in line
                    and '--condition' not in line]
        self.assertEqual(len(changing), 2)


if __name__ == '__main__':
    unittest.main()
