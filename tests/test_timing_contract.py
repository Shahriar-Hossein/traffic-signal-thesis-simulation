import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzers.timing_contract import fps_intervals, compare_fps
from analyzers.analyze_paired import analyze_pair, analyze_batch
from analyzers.analyze_timing import analyze_timing
from tests import test_paired_validity as fixtures
from scripts import export_results


def telemetry(values=(60, 60), duration=10):
    width = duration / len(values)
    return {'fps_windows': list(values), 'duration_sec': duration,
            'fps_window_bounds': [[i * width, (i + 1) * width]
                                  for i in range(len(values))],
            'fps_covered_sec': duration}


class IntervalEvidenceTests(unittest.TestCase):
    def test_unequal_run_lengths_compare_common_elapsed_time(self):
        result = compare_fps(telemetry(), telemetry((60, 60, 60), 15))
        self.assertTrue(result['comparable'])
        self.assertEqual(result['common_coverage'], 1)
        self.assertEqual(max(result['gaps']), 0)

    def test_missing_or_malformed_boundaries_cannot_pass(self):
        for bounds in (None, [], [[0, 5]], [[0, 6], [5, 10]],
                       [[0, 5], [5, 11]], [[0, float('nan')], [5, 10]],
                       [[0, 1], [9, 10]]):
            with self.subTest(bounds=bounds):
                meta = telemetry()
                meta['fps_window_bounds'] = bounds
                self.assertFalse(compare_fps(meta, telemetry())['comparable'])

    def test_coverage_summary_cannot_hide_missing_intervals(self):
        meta = telemetry()
        meta['fps_window_bounds'] = [[0, 1], [9, 10]]
        evidence = fps_intervals(meta)
        self.assertTrue(evidence['errors'])
        self.assertEqual(evidence['coverage'], .2)

    def test_common_coverage_requires_overlapping_observations(self):
        a, b = telemetry(), telemetry()
        a['fps_window_bounds'] = [[0, 5], [5, 9.5]]
        b['fps_window_bounds'] = [[.5, 5], [5, 10]]
        for meta in (a, b):
            meta['fps_covered_sec'] = 9.5
        self.assertFalse(compare_fps(a, b)['comparable'])


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReplayValidityTests('test_complete_pair_and_batch')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_shifted_stalls_reject_pair_batch_and_export(self):
        f = self.fixture
        for name, arm in f.arms.items():
            values = [30, 90, 30, 90] if name == 'fixed' else [90, 30, 90, 30]
            arm['meta'].update(telemetry(values, arm['meta']['duration_sec']))
            arm['meta']['fps_min'] = 30
        f.save()
        pair = analyze_pair(str(f.directory), write=False)
        self.assertTrue(pair['measurement_valid'])
        self.assertFalse(pair['publication_eligible'])
        self.assertEqual(pair['paired'], [])
        self.assertIn('interval FPS divergence', ' '.join(pair['invalid_reasons']))
        batch = analyze_batch(str(f.root), write=False)
        self.assertEqual(batch['plans_valid'], 0)
        self.assertEqual(batch['invalid_by_scenario'], {'even_mixed_3': 1})
        with tempfile.TemporaryDirectory() as destination:
            with patch.object(export_results, 'RESULTS_ROOT', destination):
                path = export_results.export([str(f.directory)], name='rejected',
                                             allow_dirty=True, baseline='fixed')
            exported = json.loads((Path(path) / 'fixture/comparison.json').read_text())
            self.assertFalse(exported['publication_eligible'])

    def test_missing_phases_withhold_effects_despite_coherent_vehicle_rows(self):
        f = self.fixture
        for path in f.directory.glob('*/run_phases.csv'):
            path.unlink()
        pair = analyze_pair(str(f.directory), write=False)
        self.assertTrue(pair['measurement_valid'])
        self.assertEqual(pair['timing_acceptance']['result'], 'rejected')
        self.assertFalse(pair['valid'])
        self.assertEqual(pair['paired'], [])

    def test_phase_after_run_end_is_rejected(self):
        path = self.fixture.directory / 'fixed' / 'run_phases.csv'
        import csv
        with path.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        rows[0]['phase_end_sec'] = '1000'
        with path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        pair = analyze_pair(str(self.fixture.directory), write=False)
        self.assertFalse(pair['valid'])
        self.assertIn('inconsistent transition', ' '.join(pair['invalid_reasons']))

    def test_missing_boundaries_are_insufficient_evidence(self):
        f = self.fixture
        for arm in f.arms.values():
            del arm['meta']['fps_window_bounds']
        f.save()
        self.assertEqual(analyze_timing(str(f.directory), write=False)
                         ['acceptance']['result'], 'insufficient evidence')
        self.assertFalse(analyze_pair(str(f.directory), write=False)['valid'])


class FpsTrackerTests(unittest.TestCase):
    def test_shutdown_includes_the_partial_window_without_mutating_tracker(self):
        import main
        with patch.object(main.runclock, 'elapsed', return_value=0):
            tracker = main.FpsTracker()
        for frame in range(1, 31):
            with patch.object(main.runclock, 'elapsed', return_value=frame / 60):
                tracker.tick()
        first = tracker.stats(0.5)
        self.assertEqual(first['fps_covered_sec'], 0.5)
        self.assertEqual(first['fps_windows'], [60.0])
        self.assertEqual(first, tracker.stats(0.5))
        self.assertEqual(tracker.windows, [])
        after_sleep = tracker.stats(0.5 + 1 / 60)
        self.assertEqual(after_sleep['fps_window_bounds'], [[0, 0.5]])
        self.assertEqual(after_sleep['fps_windows'], [60.0])
        self.assertEqual(after_sleep['fps_telemetry_end_sec'], 0.5)
