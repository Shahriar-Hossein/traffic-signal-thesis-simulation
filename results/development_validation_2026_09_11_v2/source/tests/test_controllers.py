"""Controller registry and duration rules. No simulation is started here."""
import unittest

from core import policy
from core.controllers import NAMES, REGISTRY, resolve


class RegistryTests(unittest.TestCase):
    def test_every_name_resolves_to_a_callable(self):
        for name in NAMES:
            self.assertTrue(callable(resolve(name)), name)

    def test_names_and_mapping_cannot_disagree(self):
        # One definition: a controller cannot be listed and unresolvable, or
        # resolvable and unlisted.
        self.assertEqual(set(NAMES), set(REGISTRY))

    def test_unknown_controller_raises_instead_of_running_fixed(self):
        # The old dispatch fell through to fixed, so a mistyped arm produced
        # fixed-24 results labelled as something else.
        for name in ('priorty', None, '', 42):
            with self.assertRaises(ValueError):
                resolve(name)

    def test_cli_accepts_exactly_the_registered_names(self):
        import main
        for name in NAMES:
            self.assertEqual(main.parse_args(['--controller', name]).controller, name)
        with self.assertRaises(SystemExit):
            main.parse_args(['--controller', 'priorty'])


class DurationRuleTests(unittest.TestCase):
    """
    The rule is specified here, not compared against a copy of itself.

    Both the proposed controller and its duration ablation call
    `policy.priority_green`, so there is one implementation and these cases
    are the specification of it.
    """

    def test_priority_rule_cases(self):
        for weight, expected in [(0, 6), (0.5, 6), (8, 6), (8.1, 6), (9, 6),
                                 (16, 12), (31.9, 23), (32, 24), (100, 24),
                                 (1000, 24)]:
            self.assertEqual(policy.priority_green(weight), expected, weight)

    def test_fairness_rule_has_its_own_coefficient_and_ceiling(self):
        self.assertEqual(policy.fairness_green(0), 6)
        self.assertEqual(policy.fairness_green(1000), 18)
        self.assertEqual(policy.fairness_green(20), 13)
        # 18, not the proposed controller's 24.
        self.assertEqual(policy.GREEN_BOUNDS['fairness_priority'], (6, 18))

    def test_truncation_happens_before_clamping(self):
        # A whole number of one-second timer ticks, then the bounds.
        self.assertEqual(policy.adaptive_green(9.99, 1.0, 6, 24), 9)
        self.assertEqual(policy.adaptive_green(9.99, 1.0, 10, 24), 10)

    def test_fixed_duration_controllers_declare_no_rule(self):
        for name in ('fixed', 'adaptive_order_fixed_duration'):
            self.assertIsNone(policy.DURATION_RULES[name])
            self.assertIsNone(policy.GREEN_BOUNDS[name])
            self.assertEqual(policy.green_for(name, 99, fixed_seconds=24), 24)

    def test_every_controller_has_a_declared_rule_and_bounds(self):
        self.assertEqual(set(policy.DURATION_RULES), set(NAMES))
        self.assertEqual(set(policy.GREEN_BOUNDS), set(NAMES))


if __name__ == '__main__':
    unittest.main()
