import unittest

from app.services.plate_formatter import VietnamesePlateFormatter


class VietnamesePlateFormatterTests(unittest.TestCase):
    def setUp(self):
        self.formatter = VietnamesePlateFormatter()

    def test_formats_common_car_plate(self):
        result = self.formatter.format("51A 12345")
        self.assertEqual(result.display_text, "51A-123.45")
        self.assertTrue(result.is_valid)

    def test_joins_square_plate_ocr_lines_into_one_display_line(self):
        result = self.formatter.format("50L\n347.98")
        self.assertEqual(result.display_text, "50L-347.98")
        self.assertTrue(result.is_valid)

    def test_formats_common_motorbike_plate(self):
        result = self.formatter.format("59A1\n123.45")
        self.assertEqual(result.display_text, "59A1-123.45")
        self.assertTrue(result.is_valid)

    def test_corrects_lookalikes_only_in_numeric_positions(self):
        result = self.formatter.format("5IA-12S.4O")
        self.assertEqual(result.display_text, "51A-125.40")
        self.assertTrue(result.is_valid)

    def test_keeps_raw_text_for_audit(self):
        result = self.formatter.format("abc")
        self.assertEqual(result.raw_text, "abc")
        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
