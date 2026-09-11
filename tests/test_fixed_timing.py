import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import policy
from core.controllers import NAMES, resolve
from core.fixed_timing import load_fixed_timing, resolve_fixed_greens
from core import cycle_tuned_fixed


def table():
    return {
        'schema_version': 1,
        'development_seeds': [301, 302],
        'selection_method': 'development-only fixture',
        'scenarios': {
            'even_high_500': [24, 20, 18, 16],
            'even_mixed_500': [12, 13, 14, 15],
        },
    }


class FixedTimingTableTests(unittest.TestCase):
    def write(self, value):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        json.dump(value, handle)
        handle.close()
        return handle.name

    def test_valid_table_loads_and_resolves_pinned_and_mixed(self):
        loaded = load_fixed_timing(self.write(table()))
        self.assertEqual(resolve_fixed_greens(
            loaded, {'uneven_mode': 'even', 'pinned_condition': 'high',
                     'target_vehicle_count': 500}),
            (24, 20, 18, 16))
        self.assertEqual(resolve_fixed_greens(
            loaded, {'uneven_mode': 'even', 'target_vehicle_count': 500}),
            (12, 13, 14, 15))

    def test_loader_rejects_schema_seeds_and_green_bounds(self):
        cases = [
            ('schema_version', lambda x: x.update(schema_version=2)),
            ('empty seeds', lambda x: x.update(development_seeds=[])),
            ('bool seed', lambda x: x.update(development_seeds=[True])),
            ('reserved seed', lambda x: x.update(development_seeds=[9001])),
            ('method', lambda x: x.update(selection_method='')),
            ('label', lambda x: x['scenarios'].update(bad=[24, 24, 24, 24])),
            ('green count', lambda x: x['scenarios'].update(even_high_500=[24])),
            ('green bound', lambda x: x['scenarios'].update(even_high_500=[5, 24, 24, 24])),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                value = table()
                mutate(value)
                with self.assertRaises(ValueError):
                    load_fixed_timing(self.write(value))

    def test_missing_scenario_fails_closed(self):
        loaded = load_fixed_timing(self.write(table()))
        with self.assertRaisesRegex(ValueError, 'no scenario'):
            resolve_fixed_greens(loaded, {
                'uneven_mode': 'right', 'pinned_condition': 'high',
                'target_vehicle_count': 500})


class FixedTunedControllerTests(unittest.TestCase):
    def test_registry_and_bounds_declare_fixed_tuned(self):
        self.assertIn('fixed_tuned', NAMES)
        self.assertTrue(callable(resolve('fixed_tuned')))
        self.assertIsNone(policy.DURATION_RULES['fixed_tuned'])
        self.assertIsNone(policy.GREEN_BOUNDS['fixed_tuned'])

    def test_controller_passes_selected_greens_in_fixed_order(self):
        state = cycle_tuned_fixed.state
        original = {name: getattr(state, name, None) for name in (
            'fixed_timing_plan', 'vehicle_plan', 'running')}
        state.fixed_timing_plan = table()
        state.vehicle_plan = {'header': {
            'uneven_mode': 'even', 'pinned_condition': 'high',
            'target_vehicle_count': 500}}
        state.running = True
        calls = []

        def stop_after_four(index, green, round_index, phase_index,
                            weights, queues, red_extra=1, early_exit=None):
            calls.append((index, green, red_extra))
            state.running = len(calls) < 4

        try:
            with patch.object(cycle_tuned_fixed, 'all_red_start'), \
                    patch.object(cycle_tuned_fixed, 'decide', return_value=(
                        {'right': 0, 'down': 0, 'left': 0, 'up': 0}, {}, 0)), \
                    patch.object(cycle_tuned_fixed, 'run_phase', side_effect=stop_after_four):
                cycle_tuned_fixed.fixed_tuned_traffic_cycle()
        finally:
            for name, value in original.items():
                setattr(state, name, value)
        self.assertEqual(calls, [(0, 24, 0), (1, 20, 0), (2, 18, 0), (3, 16, 0)])


if __name__ == '__main__':
    unittest.main()
