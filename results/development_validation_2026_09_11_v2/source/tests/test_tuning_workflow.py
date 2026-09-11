import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import tune_fixed


class FixedTuningWorkflowTests(unittest.TestCase):
    def test_demand_split_is_bounded_exact_and_deterministic(self):
        self.assertEqual(tune_fixed.allocate_green(96, [.25] * 4), [24] * 4)
        self.assertEqual(tune_fixed.allocate_green(96, [.35, .35, .15, .15]),
                         [34, 34, 14, 14])
        self.assertEqual(tune_fixed.allocate_green(96, [.85, .05, .05, .05]),
                         [60, 12, 12, 12])
        for values in tune_fixed.candidate_scenarios()['demand_split96'].values():
            self.assertEqual(sum(values), 96)
            self.assertTrue(all(6 <= value <= 60 for value in values))

    def test_prepare_refuses_heldout_and_only_writes_inputs(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'study'
            with self.assertRaisesRegex(ValueError, 'reserved'):
                tune_fixed.prepare(target, seeds=(301, 9001))
            manifest = tune_fixed.prepare(target, seeds=(301,), count=3)
            self.assertEqual(len(manifest['pairs']), 36)
            self.assertFalse((target / 'results').exists())
            self.assertIn('--arms fixed fixed_tuned', manifest['pairs'][0]['command'])
            self.assertEqual(len(manifest['candidates']), 3)

    def test_selection_rejects_missing_and_invalid_candidates(self):
        manifest = {
            'count': 3, 'development_seeds': [301],
            'candidate_order': list(tune_fixed.CANDIDATES),
            'plans': [{'scenario': 'even_high_3', 'seed': 301, 'plan_hash': 'h'}],
            'pairs': [], 'candidates': {},
            'frozen_simulator': {'source_hash': 'source',
                                 'runtime_identity_hash': 'runtime'},
        }
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for name in tune_fixed.CANDIDATES:
                timing = root / f'{name}.json'
                timing.write_text('{}')
                manifest['candidates'][name] = {
                    'timing_table': timing.name,
                    'input_sha256': tune_fixed.digest(timing),
                }
                manifest['pairs'].append({
                    'candidate': name, 'scenario': 'even_high_3', 'seed': 301,
                    'result_dir': f'results/{name}/pair',
                })
            (root / 'manifest.json').write_text(json.dumps(manifest))
            tables = {name: {'scenarios': {'even_high_3': [12] * 4}}
                      for name in tune_fixed.CANDIDATES}
            with patch.object(tune_fixed, '_validated_manifest',
                              return_value=(manifest, tables)):
                with self.assertRaisesRegex(ValueError, 'missing candidate'):
                    tune_fixed.select(root)
            for item in manifest['pairs']:
                (root / item['result_dir']).mkdir(parents=True)
            with patch.object(tune_fixed, '_validated_manifest',
                              return_value=(manifest, tables)), patch.object(
                    tune_fixed, '_complete_pair', return_value={
                        'scenario': 'even_high_3', 'generation_seed': 301,
                        'plan_hash': 'h'}), patch.object(
                    tune_fixed, '_raw_evidence', side_effect=ValueError('invalid raw')):
                with self.assertRaisesRegex(ValueError, 'invalid raw'):
                    tune_fixed.select(root)

    def test_existing_pair_must_reanalyse_as_valid(self):
        with patch.object(tune_fixed, 'analyze_pair', return_value={
                'publication_eligible': False, 'arm_names': ['fixed'],
                'invalid_reasons': ['missing fixed_tuned']}):
            with self.assertRaisesRegex(ValueError, 'incomplete or invalid'):
                tune_fixed._complete_pair(Path('/tmp/incomplete'))

    def test_selection_uses_raw_means_and_candidate_order_for_ties(self):
        manifest = {
            'count': 3, 'development_seeds': [301],
            'candidate_order': list(tune_fixed.CANDIDATES),
            'plans': [{'scenario': 'even_high_3', 'seed': 301, 'plan_hash': 'h'}],
            'pairs': [], 'candidates': {},
            'frozen_simulator': {'source_hash': 'source',
                                 'runtime_identity_hash': 'runtime'},
        }
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for name in tune_fixed.CANDIDATES:
                timing = root / f'{name}.json'
                timing.write_text(name)
                manifest['candidates'][name] = {
                    'timing_table': timing.name,
                    'input_sha256': tune_fixed.digest(timing),
                }
                pair = root / 'results' / name / 'pair'
                pair.mkdir(parents=True)
                manifest['pairs'].append({
                    'candidate': name, 'scenario': 'even_high_3', 'seed': 301,
                    'result_dir': str(pair.relative_to(root)),
                })
            (root / 'manifest.json').write_text(json.dumps(manifest))
            comparison = {'scenario': 'even_high_3', 'generation_seed': 301,
                          'plan_hash': 'h'}
            waits = {'uniform12': [2, 4], 'uniform24': [3, 3],
                     'demand_split96': [9, 9]}
            with patch.object(tune_fixed, '_complete_pair', return_value=comparison), \
                    patch.object(tune_fixed, '_validated_manifest',
                                 return_value=(manifest, {
                                     name: {'scenarios': {'even_high_3': [12] * 4}}
                                     for name in tune_fixed.CANDIDATES})), \
                    patch.object(tune_fixed, '_raw_evidence',
                                 side_effect=lambda path, table:
                                 (waits[path.parent.name], 'source', 'runtime')):
                result = tune_fixed.select(root)
            self.assertEqual(result['evidence']['even_high_3']['selected_candidate'],
                             'uniform12')
            self.assertEqual(result['scenarios']['even_high_3'], [12, 12, 12, 12])


if __name__ == '__main__':
    unittest.main()
