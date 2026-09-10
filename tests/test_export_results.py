"""Export tests build their own paired folder; they never read data/."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scripts.export_results as export_results
from core.plan import build_plan, write_plan


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan_dir = self.root / 'source' / 'fixture'
        plan = build_plan(7, 3, 'even', plan_id='fixture')
        write_plan(plan, str(self.plan_dir / 'plan.json'))
        for name in ('fixed', 'priority'):
            folder = self.plan_dir / name
            folder.mkdir()
            with (folder / 'run.csv').open('w', newline='') as output:
                writer = csv.writer(output)
                writer.writerow(['plan_seq', 'wait_time_sec'])
                writer.writerow([0, 1.0])
            (folder / 'run_meta.json').write_text(json.dumps({'controller': name}))
        self.destination = self.root / 'results'

    def export(self, **kwargs):
        with patch.object(export_results, 'RESULTS_ROOT', str(self.destination)):
            return export_results.export([str(self.plan_dir)], **kwargs)

    def test_package_carries_inputs_logs_and_revision(self):
        path = Path(self.export(name='pkg', allow_dirty=True))
        self.assertTrue((path / 'fixture' / 'plan.json').exists())
        self.assertTrue((path / 'fixture' / 'fixed' / 'run.csv').exists())
        for derived in ('comparison.json', 'timing.json', 'discharge.json'):
            self.assertTrue((path / 'fixture' / derived).exists(), derived)

        manifest = json.loads((path / 'manifest.json').read_text())
        self.assertEqual(manifest['plans'], ['fixture'])
        self.assertIn('commit', manifest['analysis_revision'])
        self.assertIn('export', manifest['commands'])
        self.assertIn('fixture', (path / 'SUMMARY.md').read_text())

    def test_the_analysis_specification_travels_with_the_package(self):
        path = Path(self.export(name='pkg', allow_dirty=True, baseline='fixed',
                                drift_tolerance_ms=99.0))
        analysis = json.loads((path / 'manifest.json').read_text())['analysis']
        self.assertEqual(analysis['baseline'], 'fixed')
        self.assertEqual(analysis['drift_tolerance_ms'], 99.0)
        self.assertIn('schema_version', analysis)
        # And the comparison in the package was produced under them.
        comparison = json.loads((path / 'fixture' / 'comparison.json').read_text())
        self.assertEqual(comparison['arm_names'][0], 'fixed')
        self.assertIn('--baseline fixed', json.loads(
            (path / 'manifest.json').read_text())['commands']['export'])

    def test_the_run_revision_is_not_the_export_revision(self):
        path = Path(self.export(name='pkg', allow_dirty=True))
        manifest = json.loads((path / 'manifest.json').read_text())
        # The arms here recorded no provenance, so the package says so rather
        # than letting the export's own commit stand in for theirs.
        arms = manifest['run_revisions']['fixture']
        self.assertEqual(set(arms), {'fixed', 'priority'})
        self.assertIsNone(arms['fixed']['source_hash'])
        self.assertIsNone(arms['fixed']['checkout'])
        self.assertNotIn('revision', manifest)

    def test_every_copied_file_can_be_verified(self):
        path = Path(self.export(name='pkg', allow_dirty=True))
        digests = json.loads((path / 'manifest.json').read_text())['file_digests']
        self.assertIn('fixture/fixed/run.csv', digests)
        for name, recorded in digests.items():
            self.assertEqual(export_results.digest(path / name), recorded, name)

    def test_plan_folders_that_share_a_name_are_refused(self):
        twin = self.root / 'other' / 'fixture'
        twin.mkdir(parents=True)
        with patch.object(export_results, 'RESULTS_ROOT', str(self.destination)):
            with self.assertRaises(SystemExit):
                export_results.export([str(self.plan_dir), str(twin)],
                                      name='clash', allow_dirty=True)

    def test_a_failed_export_leaves_no_package_behind(self):
        with patch.object(export_results, 'export_plan',
                          side_effect=RuntimeError('analysis blew up')):
            with self.assertRaises(RuntimeError):
                self.export(name='half', allow_dirty=True)
        self.assertFalse((self.destination / 'half').exists())
        self.assertFalse((self.destination / 'half.partial').exists())

    def test_recorded_fingerprints_resolve_to_a_checkout(self):
        """
        The point of recording source fingerprints is being able to get those
        bytes back. On a clean tree the current run's own fingerprints must
        resolve to the commit that holds them.
        """
        import config
        from core.provenance import capture_provenance
        if export_results.revision()['dirty']:
            self.skipTest('working tree is dirty; HEAD does not hold these bytes')
        recipe = export_results.checkout_recipe(
            capture_provenance(config, 1800)['source_files'])
        self.assertIsNotNone(recipe)
        self.assertTrue(recipe['command'].startswith('git checkout '))

    def test_unretrievable_source_bytes_are_reported_as_such(self):
        # A run made from an uncommitted tree cannot be checked out. Saying
        # None is the finding; naming the export's commit would be a lie.
        self.assertIsNone(export_results.checkout_recipe(
            {'main.py': 'not-a-real-digest'}))
        self.assertIsNone(export_results.checkout_recipe({}))
        self.assertIsNone(export_results.checkout_recipe(None))

    def test_invalid_pairs_are_reported_not_dropped(self):
        # These synthetic arms cannot pass the gate; the package must say so
        # rather than quietly export an empty table.
        path = Path(self.export(name='pkg', allow_dirty=True))
        comparison = json.loads((path / 'fixture' / 'comparison.json').read_text())
        self.assertFalse(comparison['valid'])
        self.assertTrue(comparison['invalid_reasons'])
        self.assertIn('NO', (path / 'SUMMARY.md').read_text())

    def test_existing_package_is_never_overwritten(self):
        self.export(name='pkg', allow_dirty=True)
        with self.assertRaises(SystemExit):
            self.export(name='pkg', allow_dirty=True)

    def test_dirty_tree_is_refused_by_default(self):
        with patch.object(export_results, 'revision',
                          return_value={'dirty': True, 'uncommitted': ['x']}):
            with self.assertRaises(SystemExit):
                self.export(name='other')


if __name__ == '__main__':
    unittest.main()
