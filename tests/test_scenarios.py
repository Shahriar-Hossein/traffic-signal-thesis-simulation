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

    @staticmethod
    def draws(plan):
        return [(v['direction'], v['lane'], v['vehicle_type'], v['will_turn'],
                 v['turn_direction'], v['target_turn_lane'])
                for v in plan['vehicles']]

    def test_pinned_regimes_share_a_vehicle_sequence_at_several_seeds(self):
        # Among the pinned cells the regime must be the only thing that
        # varies, or a scenario comparison confounds demand with a different
        # vehicle mix. Checked at several seeds and a realistic size: a small
        # fixture at one lucky seed proves nothing here.
        for seed in (5, 301, 302, 9001):
            for count in (40, 500):
                with self.subTest(seed=seed, count=count):
                    busy = build_plan(seed, count, 'even', condition='high')
                    quiet = build_plan(seed, count, 'even', condition='low')
                    self.assertEqual(self.draws(busy), self.draws(quiet))
                    self.assertLess(busy['vehicles'][-1]['t_offset_sec'],
                                    quiet['vehicles'][-1]['t_offset_sec'])

    def test_the_changing_regime_does_not_share_that_sequence(self):
        """
        The documented guarantee stops at the pinned cells.

        A mixed plan draws its condition from the same generator as its
        vehicles, so it consumes draws a pinned plan does not. The comment in
        core/plan.py used to claim the opposite; this pins the real behaviour
        so the claim cannot quietly come back.
        """
        pinned = build_plan(301, 500, 'even', condition='high')
        mixed = build_plan(301, 500, 'even')
        differing = sum(1 for one, other in zip(self.draws(pinned), self.draws(mixed))
                        if one != other)
        self.assertGreater(differing, 400, 'pinned and mixed do not share draws')

        # And a small fixture at a lucky seed hides it entirely.
        self.assertEqual(self.draws(build_plan(5, 40, 'even', condition='low')),
                         self.draws(build_plan(5, 40, 'even')))
        self.assertNotEqual(self.draws(build_plan(5, 500, 'even', condition='low')),
                            self.draws(build_plan(5, 500, 'even')))

    def test_pinning_produces_a_distinct_plan_and_id(self):
        self.assertNotEqual(content_hash(build_plan(5, 40, 'even')),
                            content_hash(build_plan(5, 40, 'even', condition='high')))
        self.assertNotEqual(default_plan_id('even', 40, 5),
                            default_plan_id('even', 40, 5, 'high'))

    def test_the_builders_default_id_carries_the_pin(self):
        # Two plans that differ only in regime must not collide on a folder
        # name. The CLI worked around this by constructing the ID itself.
        self.assertNotEqual(
            build_plan(5, 40, 'even', condition='low')['header']['plan_id'],
            build_plan(5, 40, 'even', condition='high')['header']['plan_id'])
        self.assertEqual(
            build_plan(5, 40, 'even', condition='high')['header']['plan_id'],
            default_plan_id('even', 40, 5, 'high'))
        self.assertEqual(build_plan(5, 40, 'even')['header']['plan_id'],
                         default_plan_id('even', 40, 5))

    def test_unknown_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            build_plan(5, 40, 'even', condition='rush_hour')

    def test_unknown_skew_is_rejected_not_silently_uniform(self):
        with self.assertRaises(ValueError):
            build_plan(5, 40, 'evne')

    def resign(self, plan, path):
        """Write a plan with a hash that matches its (modified) contents."""
        plan['header']['content_hash'] = content_hash(plan)
        Path(path).write_text(json.dumps(plan))

    def test_a_rehashed_contradiction_is_rejected_not_just_a_tampered_hash(self):
        """
        The hash proves the file is unchanged since it was written. It says
        nothing about whether its fields agree with each other, and the
        replay uses the vehicle's own condition rather than the timeline.
        """
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            original = build_plan(5, 40, 'even', condition='high')
            write_plan(original, str(path))
            self.assertTrue(load_plan(str(path)))

            plan = json.loads(path.read_text())
            # A valid rate-table name, and not the regime this plan pins.
            plan['vehicles'][0]['condition'] = 'low'
            self.resign(plan, path)
            with self.assertRaises(ValueError) as caught:
                load_plan(str(path))
            self.assertIn('labelled', str(caught.exception))

    def test_a_vehicle_that_disagrees_with_a_mixed_timeline_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            write_plan(build_plan(5, 500, 'even'), str(path))
            plan = json.loads(path.read_text())
            other = next(event['condition'] for event in plan['condition_timeline']
                         if event['condition'] != plan['vehicles'][0]['condition'])
            plan['vehicles'][0]['condition'] = other
            self.resign(plan, path)
            with self.assertRaises(ValueError):
                load_plan(str(path))

    def test_a_valid_mixed_timeline_still_loads(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            plan = build_plan(9, 500, 'right')
            write_plan(plan, str(path))
            loaded = load_plan(str(path))
            self.assertGreater(len(loaded['condition_timeline']), 1)

    def test_a_malformed_pin_is_an_ordinary_plan_error(self):
        """
        `pinned_condition: []` reached dictionary membership before the type
        check and raised TypeError, which the CLI does not catch.
        """
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            write_plan(build_plan(5, 40, 'even'), str(path))
            for value in ([], {}, 3, True):
                with self.subTest(value=value):
                    plan = json.loads(path.read_text())
                    plan['header']['pinned_condition'] = value
                    self.resign(plan, path)
                    with self.assertRaises(ValueError):
                        load_plan(str(path))

    def test_an_unsupported_skew_name_is_rejected_by_the_loader_too(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            write_plan(build_plan(5, 40, 'even'), str(path))
            plan = json.loads(path.read_text())
            plan['header']['uneven_mode'] = 'evne'
            self.resign(plan, path)
            with self.assertRaises(ValueError):
                load_plan(str(path))

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
