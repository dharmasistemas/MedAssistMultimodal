"""O manifesto de release não promete módulos ainda não implementados."""
import unittest
from scripts.build_release_candidate import build_manifest


class DemoAssetsTests(unittest.TestCase):
    def test_release_has_all_baseline_files_but_remains_blocked(self):
        manifest = build_manifest()
        self.assertEqual(manifest["missing_paths"], [])
        self.assertEqual(manifest["status"], "preparation")
        self.assertTrue(manifest["open_blockers"])
