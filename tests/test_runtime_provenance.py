import json
import sys
import unittest
from unittest.mock import patch

import config
from core.provenance import capture_provenance, fingerprint


class RuntimeProvenanceTests(unittest.TestCase):
    def test_runtime_record_is_serializable_and_repeatable(self):
        one = capture_provenance(config, 1800)
        two = capture_provenance(config, 1800)

        self.assertEqual(one['runtime'], two['runtime'])
        self.assertEqual(one['runtime_identity'], two['runtime_identity'])
        self.assertEqual(
            one['runtime_identity_hash'], fingerprint(one['runtime_identity']))
        json.dumps(one, allow_nan=False)
        self.assertEqual(list(one['runtime']['argv']), list(sys.argv))
        self.assertIn('executable', one['runtime'])
        self.assertIn('sdl_video_driver', one['runtime'])

    def test_runtime_identity_excludes_executable_and_argv(self):
        original_argv = list(sys.argv)
        with patch('core.provenance.sys.executable', '/tmp/other-python'), \
                patch('core.provenance.sys.argv', ['runner', '--output', '/tmp/other']):
            changed = capture_provenance(config, 1800)

        baseline = capture_provenance(config, 1800)
        self.assertNotEqual(changed['runtime'], baseline['runtime'])
        self.assertEqual(changed['runtime_identity'], baseline['runtime_identity'])
        self.assertEqual(changed['runtime_identity_hash'],
                         baseline['runtime_identity_hash'])
        self.assertEqual(sys.argv, original_argv)

    def test_sdl_video_driver_is_recorded_without_other_environment_values(self):
        with patch.dict('core.provenance.os.environ', {'SDL_VIDEODRIVER': 'dummy'}, clear=False):
            captured = capture_provenance(config, 1800)
        self.assertEqual(captured['runtime']['sdl_video_driver'], 'dummy')
        self.assertNotIn('environment', captured)
        self.assertNotIn('env', captured['runtime'])


if __name__ == '__main__':
    unittest.main()
