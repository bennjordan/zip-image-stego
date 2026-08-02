#!/usr/bin/env python3
import os
import zlib
import zipfile
import io
import unittest
from PIL import Image
import numpy as np

from stego_engine import MultiMethodFileSteg, PNGDeflateFileSteg, RobustBlockFileSteg


class TestZipSteganography(unittest.TestCase):
    def setUp(self):
        self.password = "Secr3tP@ssw0rd!"
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Paths
        self.cover_png_path = os.path.join(self.test_dir, "test_cover.png")
        self.cover_jpg_path = os.path.join(self.test_dir, "test_cover.jpg")
        self.stego_deflate_path = os.path.join(self.test_dir, "stego_deflate.png")
        self.stego_robust_path = os.path.join(self.test_dir, "stego_robust.jpg")

        # Create a mock cover image (800x800 gradient)
        # Create a nice high-contrast gradient so it works well for robust block stego
        w, h = 800, 800
        pixels = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                r = int((x / w) * 200) + 20
                g = int((y / h) * 200) + 20
                b = 128
                pixels[y, x] = [r, g, b]

        img = Image.fromarray(pixels)
        img.save(self.cover_png_path, "PNG")
        img.save(self.cover_jpg_path, "JPEG", quality=95)

        # Create a mock zip file with small text data
        self.zip_data_buffer = io.BytesIO()
        with zipfile.ZipFile(self.zip_data_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("secret.txt", b"This is a top-secret message stored in a zip archive!")
        self.original_zip_bytes = self.zip_data_buffer.getvalue()

    def tearDown(self):
        # Clean up files
        for path in [
            self.cover_png_path,
            self.cover_jpg_path,
            self.stego_deflate_path,
            self.stego_robust_path
        ]:
            if os.path.exists(path):
                os.remove(path)

    def test_deflate_stego_roundtrip(self):
        """Test the PNG structure-based Deflate method."""
        steg = PNGDeflateFileSteg(self.password)
        
        # Hide
        success = steg.hide(self.original_zip_bytes, self.cover_png_path, self.stego_deflate_path)
        self.assertTrue(success, "Deflate hide should succeed")
        self.assertTrue(os.path.exists(self.stego_deflate_path))

        # Reveal
        recovered_bytes = steg.reveal(self.stego_deflate_path)
        self.assertIsNotNone(recovered_bytes, "Deflate reveal should return data")
        self.assertEqual(recovered_bytes, self.original_zip_bytes, "Recovered bytes must match original zip bytes")

    def test_robust_block_stego_roundtrip(self):
        """Test the robust block stego method with simulated lossy JPEG compression."""
        # Setup engine with parameters
        block_size = 8
        redundancy = 3
        strength = 35  # Higher strength for solid recovery under JPEG compression
        
        steg = RobustBlockFileSteg(self.password, block_size=block_size, redundancy=redundancy, strength=strength)
        
        # Max capacity check
        max_capacity = steg.get_max_capacity(800, 800)
        self.assertGreater(max_capacity, len(self.original_zip_bytes), "Image must be large enough for testing")

        # Hide (writes as JPEG)
        success = steg.hide(self.original_zip_bytes, self.cover_png_path, self.stego_robust_path)
        self.assertTrue(success, "Robust hide should succeed")
        self.assertTrue(os.path.exists(self.stego_robust_path))

        # Simulate compression / Re-save at a lower quality (JPEG quality = 80)
        stego_img = Image.open(self.stego_robust_path)
        compressed_path = os.path.join(self.test_dir, "stego_robust_compressed.jpg")
        stego_img.save(compressed_path, "JPEG", quality=80)

        # Reveal from compressed image
        recovered_bytes = steg.reveal(compressed_path)
        
        # Clean up temp compressed file
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
            
        self.assertIsNotNone(recovered_bytes, "Robust reveal should return data after compression")
        self.assertEqual(recovered_bytes, self.original_zip_bytes, "Recovered bytes must match original zip bytes")


if __name__ == "__main__":
    unittest.main()
