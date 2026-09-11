import json
from pathlib import Path
import tempfile
import unittest

from core.plan import build_plan, content_hash, load_plan, write_plan


class ArrivalContractTests(unittest.TestCase):
    @staticmethod
    def resign(plan, path):
        plan['header']['content_hash'] = content_hash(plan)
        Path(path).write_text(json.dumps(plan))

    def test_rehashed_irregular_pinned_arrivals_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            plan = build_plan(5, 3, 'even', condition='high')
            write_plan(plan, str(path))
            stored = json.loads(path.read_text())
            stored['vehicles'][1]['t_offset_sec'] = 100
            stored['vehicles'][2]['t_offset_sec'] = 200
            self.resign(stored, path)

            with self.assertRaisesRegex(ValueError, 'irregular arrival gap'):
                load_plan(str(path))

    def test_generated_pinned_and_mixed_transitions_load(self):
        with tempfile.TemporaryDirectory() as root:
            plans = [
                (f'pinned_{condition}',
                 build_plan(seed, 500, 'even', condition=condition))
                for seed in (5, 301)
                for condition in ('low', 'medium', 'high')
            ]
            plans.extend(
                (f'mixed_{seed}', build_plan(seed, 500, 'right'))
                for seed in (5, 9, 301, 302)
            )
            for name, plan in plans:
                with self.subTest(name=name):
                    path = Path(root) / f'{name}.json'
                    write_plan(plan, str(path))
                    self.assertEqual(load_plan(str(path))['vehicles'],
                                     plan['vehicles'])

    def test_legacy_shaped_generated_plan_still_loads(self):
        # Plans written before pinned_condition existed remain hash-stable and
        # decode as changing-demand plans when that field is absent.
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'legacy.json'
            plan = build_plan(301, 500, 'even')
            write_plan(plan, str(path))
            stored = json.loads(path.read_text())
            del stored['header']['pinned_condition']
            self.resign(stored, path)
            self.assertIsNone(load_plan(str(path))['header'].get('pinned_condition'))

    def test_removed_final_pinned_timeline_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            plan = build_plan(5, 500, 'even', condition='high')
            write_plan(plan, str(path))
            stored = json.loads(path.read_text())
            self.assertGreater(len(stored['condition_timeline']), 1)
            stored['condition_timeline'].pop()
            self.resign(stored, path)
            with self.assertRaisesRegex(ValueError, 'final interval boundary'):
                load_plan(str(path))


if __name__ == '__main__':
    unittest.main()
