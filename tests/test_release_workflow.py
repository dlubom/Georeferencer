import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTest(unittest.TestCase):
    def test_geotiff_release_archive_is_zip(self):
        workflow = ROOT / ".github" / "workflows" / "release-geotiff.yml"
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("gdal-bin zip", text)
        self.assertIn('zip -q -r "../geotiff-tatry-${TAG}.zip" .', text)
        self.assertIn('ARCHIVE=geotiff-tatry-${TAG}.zip', text)
        self.assertNotIn(".tar.gz", text)
        self.assertNotIn("tar czf", text)


if __name__ == "__main__":
    unittest.main()
