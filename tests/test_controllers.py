"""Controller registry and ablation rules. No simulation is started here."""
import ast
import inspect
import unittest

from core import cycle_ablation, cycle_priority
from core.controllers import NAMES, resolve


class RegistryTests(unittest.TestCase):
    def test_every_name_resolves_to_a_callable(self):
        for name in NAMES:
            self.assertTrue(callable(resolve(name)), name)

    def test_unknown_controller_raises_instead_of_running_fixed(self):
        # The old dispatch fell through to fixed, so a mistyped arm produced
        # fixed-24 results labelled as something else.
        with self.assertRaises(ValueError):
            resolve('priorty')

    def test_cli_accepts_exactly_the_registered_names(self):
        import main
        for name in NAMES:
            self.assertEqual(main.parse_args(['--controller', name]).controller, name)
        with self.assertRaises(SystemExit):
            main.parse_args(['--controller', 'priorty'])


class AblationRuleTests(unittest.TestCase):
    def test_adaptive_green_matches_the_proposed_controller(self):
        """
        The ablation restates the duration rule instead of importing it, so
        that cycle_priority keeps running exactly the code it was validated
        with. This pins the two together.
        """
        source = inspect.getsource(cycle_priority.control_traffic_cycle)
        tree = ast.parse(source.strip())
        expressions = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(getattr(t, 'id', None) == 'green_time' for t in node.targets)
        ]
        self.assertEqual(len(expressions), 1, 'green_time is assigned once')

        original = compile(ast.Expression(expressions[0].value), '<rule>', 'eval')
        for weight in [0, 0.5, 1, 7.9, 8, 8.1, 16, 31.9, 32, 32.1, 100, 1000]:
            expected = eval(original, {'vehicle_required_time': weight * 0.75})
            self.assertEqual(cycle_ablation.adaptive_green(weight), expected, weight)

    def test_rule_respects_both_bounds(self):
        self.assertEqual(cycle_ablation.adaptive_green(0), 6)
        self.assertEqual(cycle_ablation.adaptive_green(1000), 24)
        self.assertEqual(cycle_ablation.adaptive_green(16), 12)


if __name__ == '__main__':
    unittest.main()
