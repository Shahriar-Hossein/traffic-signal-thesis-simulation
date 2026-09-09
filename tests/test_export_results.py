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
        self.assertIn('commit', manifest['revision'])
        self.assertIn('export', manifest['commands'])
        self.assertIn('fixture', (path / 'SUMMARY.md').read_text())

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
