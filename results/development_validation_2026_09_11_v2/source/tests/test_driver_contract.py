"""Paired-driver path, preflight, persistence, and exit-status contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from analyzers.analyze_paired import analyze_batch, analyze_pair
from core.plan import build_plan, write_plan
import run_paired


ARMS = [('fixed', 'fixed'), ('priority', 'priority')]


class DriverContractTests(unittest.TestCase):
    def make_plan(self, root, plan_id='fixture', seed=7, condition='high'):
        path = Path(root) / plan_id / 'plan.json'
        write_plan(build_plan(seed, 3, 'even', plan_id=plan_id,
                              condition=condition), str(path))
        return path

    def test_run_arm_passes_explicit_output_and_timing_paths(self):
        process = Mock()
        process.wait.return_value = 0
        with tempfile.TemporaryDirectory() as root, \
                patch.object(run_paired.subprocess, 'Popen', return_value=process) as popen, \
                patch.object(run_paired, 'read_arm_meta',
                             return_value={'stop_reason': 'target_reached'}):
            timing = str(Path(root) / 'timing.json')
            result = run_paired.run_arm(
                'plan.json', 'fixture', 'fixed', 'fixed', 90, root, timing,
            )

        self.assertTrue(result['ok'])
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index('--paired-root') + 1],
                         str(Path(root).resolve()))
        self.assertEqual(command[command.index('--fixed-timing-plan') + 1],
                         str(Path(timing).resolve()))
        self.assertEqual(command[command.index('--timeout') + 1], '90')

    def test_malformed_arm_metadata_is_a_failure_not_a_crash(self):
        with tempfile.TemporaryDirectory() as root:
            arm = Path(root) / 'fixture' / 'fixed'
            arm.mkdir(parents=True)
            path = arm / 'fixed_meta.json'
            for payload in ([], 'bad', 7):
                with self.subTest(payload=payload):
                    path.write_text(json.dumps(payload))
                    self.assertIsNone(
                        run_paired.read_arm_meta('fixture', 'fixed', root)
                    )

    def test_sweep_preflights_all_destinations_before_first_launch(self):
        with tempfile.TemporaryDirectory() as source, \
                tempfile.TemporaryDirectory() as output:
            self.make_plan(source, 'one', 1)
            self.make_plan(source, 'two', 2)
            (Path(output) / 'two' / 'priority').mkdir(parents=True)
            with patch.object(run_paired, 'run_pair') as launch:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    run_paired.main([
                        '--plans', source, '--output-root', output,
                        '--arms', 'fixed', 'priority',
                    ])
            launch.assert_not_called()

    def test_plans_default_to_input_root_and_batch_exact_selected_ids(self):
        with tempfile.TemporaryDirectory() as source:
            first = self.make_plan(source, 'one', 1)
            second = self.make_plan(source, 'two', 2)
            completed = {'valid': True, 'publication_eligible': True}
            aggregate = {
                'plans_valid': 2, 'plans_total': 2, 'plans_invalid': [],
                'cohort_errors': [], 'duplicate_plans': [], 'per_contrast': {},
            }
            with patch.object(run_paired, 'run_pair', return_value=completed) as launch, \
                    patch.object(run_paired, 'analyze_batch',
                                 return_value=aggregate) as batch:
                status = run_paired.main(['--plans', source])

            self.assertEqual(status, 0)
            expected_root = str(Path(source).resolve())
            self.assertEqual(
                [item.args[5] for item in launch.call_args_list],
                [expected_root, expected_root],
            )
            self.assertEqual(batch.call_args.args[0], expected_root)
            self.assertEqual(batch.call_args.kwargs['plan_ids'], ['one', 'two'])
            self.assertEqual(
                [Path(item.args[0]) for item in launch.call_args_list],
                [first, second],
            )

    def test_batch_returns_nonzero_for_invalid_cohort_or_rerun(self):
        cases = (
            ({'plans_invalid': [{'plan_id': 'one'}], 'cohort_errors': [],
              'duplicate_plans': []}, 1),
            ({'plans_invalid': [], 'cohort_errors': ['mixed'],
              'duplicate_plans': []}, 1),
            ({'plans_invalid': [], 'cohort_errors': [],
              'duplicate_plans': [{'plan_id': 'two'}]}, 1),
        )
        for finding, expected in cases:
            with self.subTest(finding=finding), tempfile.TemporaryDirectory() as source:
                self.make_plan(source, 'one', 1)
                aggregate = {
                    'plans_valid': 1, 'plans_total': 1, 'per_contrast': {},
                    **finding,
                }
                with patch.object(run_paired, 'run_pair', return_value={
                        'valid': True, 'publication_eligible': True}), \
                        patch.object(run_paired, 'analyze_batch',
                                     return_value=aggregate):
                    self.assertEqual(run_paired.main(['--plans', source]), expected)

    def test_arm_failure_is_persisted_and_clears_derived_effects(self):
        with tempfile.TemporaryDirectory() as source, \
                tempfile.TemporaryDirectory() as output:
            plan_file = self.make_plan(source)
            results = [
                {'arm': 'fixed', 'ok': True, 'reason': None},
                {'arm': 'priority', 'ok': False, 'reason': 'exit code 9'},
            ]
            bogus = {
                'valid': True, 'publication_eligible': True,
                'measurement_valid': True, 'invalid_reasons': [],
                'arms': {'fixed': {'wait_mean': 1}},
                'baseline_arm': 'fixed', 'paired': [{'delta_wait_mean': -3}],
            }
            with patch.object(run_paired, 'run_arm', side_effect=results), \
                    patch.object(run_paired, 'analyze_pair', return_value=bogus), \
                    patch.object(run_paired, 'analyze_timing', return_value={}) as timing, \
                    patch.object(run_paired, 'print_pair'), \
                    patch.object(run_paired, 'print_report'):
                comparison = run_paired.run_pair(
                    str(plan_file), ARMS, fps_tolerance=.07,
                    output_root=output,
                )

            self.assertFalse(comparison['publication_eligible'])
            self.assertFalse(comparison['measurement_valid'])
            self.assertEqual(comparison['paired'], [])
            self.assertEqual(comparison['arms'], {})
            status = json.loads(
                (Path(output) / 'fixture' / 'driver_status.json').read_text()
            )
            self.assertEqual(status['plan_hash'],
                             json.loads(plan_file.read_text())['header']['content_hash'])
            self.assertEqual(status['failures'][0]['reason'], 'exit code 9')
            timing.assert_called_once_with(
                str(Path(output) / 'fixture'), baseline='fixed',
                fps_tolerance=.07,
            )

    def test_exact_batch_selection_ignores_unrelated_existing_folder(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('selected', 'unrelated'):
                (Path(root) / name).mkdir()
            invalid = {
                'valid': False, 'plan_id': 'selected', 'scenario': 'unknown',
                'invalid_reasons': ['fixture'],
            }
            with patch('analyzers.analyze_paired.analyze_pair',
                       return_value=invalid) as analyze:
                result = analyze_batch(root, write=False,
                                       plan_ids=['selected'])
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(Path(analyze.call_args.args[0]).name, 'selected')
            self.assertEqual(result['plans_total'], 1)


if __name__ == '__main__':
    unittest.main()
