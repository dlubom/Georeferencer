"""Samodzielny audyt musi czytać zweryfikowane obrazy niezależnie od kolejności importów."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CatalogueAuditTest(unittest.TestCase):
    def test_standalone_audit_decodes_trusted_tiff_above_pillow_default_limit(self):
        program = r"""
import hashlib
import runpy
import sys
import tempfile
from pathlib import Path
from PIL import Image

with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'trusted.tif'
    Image.new('1', (8, 6), color=1).save(path)
    Image.MAX_IMAGE_PIXELS = 10
    runpy.run_path(sys.argv[1], run_name='standalone_catalogue_audit')
    from geotiff_output import decoded_pixels
    size, pixels = decoded_pixels(path)
    assert tuple(size) == (8, 6), size
    assert pixels == hashlib.sha256(bytes([255]) * 48).hexdigest(), pixels
"""
        completed = subprocess.run([sys.executable, '-c', program,
            str(ROOT / 'docs/reports/v0.7.0-catalogue-audit.py')],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(completed.returncode, 0, completed.stdout)


if __name__ == '__main__':
    unittest.main()
