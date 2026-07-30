"""Xử lý nhận diện biển số từ một ảnh tĩnh."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import RecognitionResult
from app.interfaces import OCRProvider

if TYPE_CHECKING:
    from app.services.image_processor import PlateImageProcessor
    from app.services.plate_detector import YOLOPlateDetector
    from app.services.plate_formatter import VietnamesePlateFormatter


class PlateRecognitionService:
    def __init__(
        self,
        detector: YOLOPlateDetector,
        image_processor: PlateImageProcessor,
        ocr: OCRProvider,
        formatter: VietnamesePlateFormatter,
        detection_threshold: float,
    ) -> None:
        self.detector = detector
        self.image_processor = image_processor
        self.ocr = ocr
        self.formatter = formatter
        self.detection_threshold = detection_threshold

    def recognize(self, image) -> RecognitionResult | None:
        """Nhận diện biển số tốt nhất trong một ảnh."""

        # 1. Kiểm tra ảnh đầu vào
        if image is None or not hasattr(image, "size") or image.size == 0:
            raise ValueError("Ảnh đầu vào rỗng hoặc không hợp lệ.")

        # 2. Dùng YOLO phát hiện biển số
        detections = self.detector.detect(image)

        # 3. Lấy biển số đầu tiên đạt confidence yêu cầu
        detection = next(
            (
                item
                for item in detections
                if item.confidence >= self.detection_threshold
            ),
            None,
        )

        # Không phát hiện được biển số đạt ngưỡng
        if detection is None:
            return None

        # 4. Crop biển số khỏi ảnh gốc
        crop = self.image_processor.crop(
            image,
            detection.box,
        )

        # 5. Xử lý ảnh trước khi OCR
        ocr_image = self.image_processor.prepare_for_ocr(
            crop,
            detection.class_name,
        )

        # 6. Google Vision đọc ký tự
        raw_text = self.ocr.recognize(ocr_image)

        # 7. Định dạng thành biển số Việt Nam
        formatted = self.formatter.format(raw_text)

        # 8. Xác định trạng thái kết quả
        if not raw_text:
            status = "NO_TEXT"
        elif formatted.is_valid:
            status = "SUCCESS"
        else:
            status = "INVALID_FORMAT"

        # 9. Trả kết quả cho nơi gọi service
        return RecognitionResult(
            crop=crop,
            detection=detection,
            formatted_plate=formatted,
            status=status,
        )