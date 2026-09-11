"""Integration checks for startup provenance, log schema and driver preflight."""
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import config
from core.plan import build_plan, write_plan
from core.provenance import capture_provenance, fingerprint
import run_paired
import utils.logger as logger


class ProvenanceTests(unittest.TestCase):
    def test_snapshot_is_detached_and_deterministic(self):
        one = capture_provenance(config, 1800)
        two = capture_provenance(config, 1800)
        self.assertEqual(one, two)
        one['configuration']['x']['right'][0] = 999
        self.assertNotEqual(one['configuration'], two['configuration'])
        self.assertEqual(config.x['right'][0], two['configuration']['x']['right'][0])
        self.assertIn('models/vehicle.py', one['source_files'])
        self.assertIn('images/right/car.png', one['source_files'])
        self.assertNotEqual(fingerprint(one['configuration']), one['configuration_hash'])

    def test_paired_logger_records_actual_attributes_and_startup_snapshot(self):
        plan = build_plan(7, 1, 'even', plan_id='fixture')
        state = SimpleNamespace(
            pair_id='fixture', arm_label='fixed', currentMode='fixed', run_mode='vehicles',
            target_vehicle_count=1, count_mode_timeout=1800, vehicle_plan=plan,
            generation_source='plan', vehicle_plan_path='plan.json', uneven_mode='even',
            release_count=1, release_drift_sum_ms=1, release_drift_max_ms=1,
        )
        record = plan['vehicles'][0]
        vehicle = SimpleNamespace(
            actual_wait_time=2.12, vehicleClass=record['vehicle_type'],
            plan_seq=0, released_sec=1.5, crossed_sec=9.25, **{key: record[key] for key in (
                'direction', 'lane', 'will_turn', 'turn_direction', 'target_turn_lane')},
        )
        with tempfile.TemporaryDirectory() as root, patch.object(logger, 'state', state), patch.object(logger, 'BASE_DATA_DIR', root):
            logger.init_logger(60, 'even')
            logger.log_vehicle(vehicle)
            path = logger.write_run_meta(stop_reason='target_reached')
            meta = json.loads(Path(path).read_text())
            self.assertEqual(meta['configuration_hash'], fingerprint(meta['configuration']))
            with open(logger.log_filename) as handle:
                rows = list(csv.DictReader(handle))
            for key in ('lane', 'will_turn', 'turn_direction', 'target_turn_lane'):
                self.assertEqual(rows[0][key], str(record[key]))
            self.assertEqual(rows[0]['released_sec'], '1.5')
            self.assertEqual(rows[0]['crossed_sec'], '9.25')
            state.pair_id = None
            logger.init_logger(60, 'even')
            logger.log_vehicle(vehicle)
            with open(logger.log_filename) as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], logger.VEHICLE_LOG_COLUMNS)
            self.assertEqual(len(rows[1]), 6)

    def test_driver_archives_external_plan_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            plan = build_plan(7, 1, 'even', plan_id='fixture')
            external = root / 'external.json'
            write_plan(plan, str(external))
            destination = root / 'paired'
            def launched(path, *args):
                self.assertEqual(Path(path), destination / 'fixture' / 'plan.json')
                self.assertEqual(Path(path).read_bytes(), external.read_bytes())
                return {'ok': True}
            with patch.object(run_paired, 'PAIRED_ROOT', str(destination)), patch.object(run_paired, 'run_arm', side_effect=launched) as launch:
                with patch.object(run_paired, 'analyze_pair', return_value={}), patch.object(run_paired, 'print_pair'):
                    run_paired.run_pair(str(external), [('a', 'fixed'), ('b', 'priority')])
                    self.assertEqual(launch.call_count, 2)
                (destination / 'fixture' / 'a').mkdir()
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    run_paired.run_pair(str(external), [('a', 'fixed'), ('b', 'priority')])
                self.assertEqual(launch.call_count, 2)


if __name__ == '__main__':
    unittest.main()
