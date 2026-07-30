import unittest

import numpy as np

from app.domain import BoundingBox, PlateDetection
from app.services.plate_formatter import VietnamesePlateFormatter
from app.services.recognition_service import PlateRecognitionService


class _Detector:
    """YOLO giả, luôn trả về detection đã chuẩn bị."""

    def detect(self, image):
        return [
            PlateDetection(
                box=BoundingBox(0, 0, 40, 20),
                class_name="BSD",
                confidence=0.91,
            )
        ]

class _NoDetectionDetector:
    """YOLO giả, không phát hiện biển số."""

    def detect(self, image):
        return []

class _ImageProcessor:
    """Bộ xử lý ảnh giả."""

    def crop(self, image, box):
        return image.copy()

    def prepare_for_ocr(self, crop, plate_type):
        return crop


class _OCR:
    """Google Vision giả, luôn trả về một chuỗi cố định."""

    def recognize(self, image):
        return "50L 347.98"


class RecognitionServiceTests(unittest.TestCase):

    def test_recognize_success(self):
        # Tạo một ảnh OpenCV giả
        image = np.zeros((20, 40, 3), dtype=np.uint8)

        service = PlateRecognitionService(
            detector=_Detector(),
            image_processor=_ImageProcessor(),
            ocr=_OCR(),
            formatter=VietnamesePlateFormatter(),
            detection_threshold=0.80,
        )

        result = service.recognize(image)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(
            result.formatted_plate.display_text,
            "50L-347.98",
        )

    def test_no_plate_detected(self):
        image = np.zeros((20, 40, 3), dtype=np.uint8)

        service = PlateRecognitionService(
            detector=_NoDetectionDetector(),
            image_processor=_ImageProcessor(),
            ocr=_OCR(),
            formatter=VietnamesePlateFormatter(),
            detection_threshold=0.80,
        )

        result = service.recognize(image)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()