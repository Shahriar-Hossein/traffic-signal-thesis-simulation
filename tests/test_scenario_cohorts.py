"""
Grouping and pooling: what counts as a stratum, and what counts as a plan.

Built from synthetic valid pairs so the twelve grid cells and the pooling
refusals can be exercised without collecting anything.
"""
import json
import shutil
import sys
import unittest
from pathlib import Path
import tempfile

from analyzers.analyze_paired import (
    MIXED_REGIME, analyze_batch, scenario_identity, scenario_label,
)
from core.plan import build_plan, write_plan
from scripts.scenarios import REGIMES, SKEWS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_paired_validity import ReplayValidityTests  # noqa: E402


class ScenarioIdentityTests(unittest.TestCase):
    def test_a_plan_without_a_pin_is_the_changing_regime(self):
        header = {'uneven_mode': 'even', 'target_vehicle_count': 500}
        self.assertEqual(scenario_identity(header)['regime'], MIXED_REGIME)
        self.assertEqual(scenario_label(scenario_identity(header)),
                         'even_mixed_500')

    def test_regimes_that_differ_only_in_demand_get_different_strata(self):
        labels = {
            scenario_label(scenario_identity(
                {'uneven_mode': 'even', 'target_vehicle_count': 500,
                 'pinned_condition': regime}))
            for regime in ('low', 'medium', 'high', None)
        }
        self.assertEqual(len(labels), 4)

    def test_the_frozen_grid_has_one_stratum_per_cell(self):
        labels = {
            scenario_label(scenario_identity(
                {'uneven_mode': skew, 'target_vehicle_count': 500,
                 'pinned_condition': regime}))
            for skew in SKEWS.values() for regime in REGIMES.values()
        }
        self.assertEqual(len(labels), len(SKEWS) * len(REGIMES))
        self.assertEqual(len(labels), 12)

    def test_an_unreadable_plan_is_not_silently_a_stratum(self):
        self.assertIsNone(scenario_identity(None))
        self.assertEqual(scenario_label(None), 'unknown')


class BatchGroupingTests(unittest.TestCase):
    """One valid pair per grid cell, then the pooling rules against it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixtures = []

    def build(self, seed, skew, regime, plan_id):
        plan = build_plan(seed, 3, skew, condition=regime, plan_id=plan_id)
        fixture = ReplayValidityTests('test_complete_pair_and_batch')
        fixture.root = self.root
        fixture.directory = self.root / plan_id
        fixture.plan = plan
        write_plan(plan, str(fixture.directory / 'plan.json'))
        ReplayValidityTests.build_arms(fixture)
        fixture.save()
        self.fixtures.append(fixture)
        return fixture

    def test_twelve_cells_give_twelve_strata_each_with_safeguards(self):
        seed = 40
        for skew in SKEWS.values():
            for regime in REGIMES.values():
                seed += 1
                self.build(seed, skew, regime,
                           f"{skew}_{regime or MIXED_REGIME}_seed{seed}")

        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['plans_valid'], 12, batch['plans_invalid'])
        self.assertEqual(len(batch['per_scenario']), 12)
        for scenario, contrasts in batch['per_scenario'].items():
            block = contrasts['fixed_vs_priority']
            self.assertEqual(block['plans'], 1, scenario)
            self.assertEqual(
                set(block['safeguards']),
                {'wait_p95', 'worst_approach_wait', 'approach_service_gap',
                 'clearance_sec'},
                scenario,
            )
        self.assertEqual(batch['cohort_errors'], [])

    def test_a_copied_plan_folder_is_not_a_second_plan(self):
        self.build(41, 'even', 'high', 'even_high_seed41')
        shutil.copytree(self.root / 'even_high_seed41', self.root / 'duplicate')

        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['per_contrast']['fixed_vs_priority']['plans'], 1)
        self.assertEqual(len(batch['duplicate_plans']), 1)
        self.assertEqual(batch['duplicate_plans'][0]['duplicate_of'],
                         'even_high_seed41')

    def test_genuinely_independent_plans_still_aggregate(self):
        self.build(42, 'even', 'high', 'even_high_seed42')
        self.build(43, 'even', 'high', 'even_high_seed43')
        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['per_contrast']['fixed_vs_priority']['plans'], 2)
        self.assertEqual(batch['duplicate_plans'], [])
        self.assertEqual(batch['cohort_errors'], [])

    def test_a_different_source_revision_is_a_different_cohort(self):
        self.build(44, 'even', 'high', 'even_high_seed44')
        other = self.build(45, 'even', 'high', 'even_high_seed45')
        from core.provenance import fingerprint
        for arm in other.arms.values():
            arm['meta']['source_files'] = {'main.py': 'a-later-revision'}
            arm['meta']['source_hash'] = fingerprint(arm['meta']['source_files'])
        other.save()

        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['plans_valid'], 2)
        self.assertTrue(batch['cohort_errors'])
        # Refused, not averaged: each cohort is summarized on its own.
        self.assertEqual(batch['per_contrast'], {})
        self.assertEqual(len(batch['per_cohort']), 2)
        for block in batch['per_cohort'].values():
            self.assertEqual(block['fixed_vs_priority']['plans'], 1)

    def test_a_swapped_controller_mapping_is_a_different_cohort(self):
        self.build(46, 'even', 'high', 'even_high_seed46')
        other = self.build(47, 'even', 'high', 'even_high_seed47')
        # The arm folders still say fixed and priority; the controller each
        # one actually ran has been exchanged.
        for name, swapped in (('fixed', 'priority'), ('priority', 'fixed')):
            other.arms[name]['meta']['controller'] = swapped
            for row in other.arms[name]['rows']:
                row['mode'] = swapped
        other.save()

        batch = analyze_batch(str(self.root), write=False, baseline='fixed')
        self.assertEqual(batch['plans_valid'], 2, batch['plans_invalid'])
        self.assertTrue(batch['cohort_errors'])
        self.assertEqual(batch['per_contrast'], {})

    def test_the_batch_records_the_settings_it_ran_under(self):
        self.build(48, 'even', 'low', 'even_low_seed48')
        batch = analyze_batch(str(self.root), write=False, baseline='fixed',
                              drift_tolerance_ms=99.0)
        self.assertEqual(batch['analysis']['baseline'], 'fixed')
        self.assertEqual(batch['analysis']['drift_tolerance_ms'], 99.0)
        json.dumps(batch, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
