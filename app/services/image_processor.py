"""Crop có padding và biến biển hai dòng thành một dòng để OCR ổn định hơn."""

from __future__ import annotations

import cv2
import numpy as np

from app.domain import BoundingBox


class PlateImageProcessor:
    def __init__(
        self,
        padding_ratio: float,
        square_plate_labels: frozenset[str],
        minimum_ocr_height: int = 120,
    ) -> None:
        self.padding_ratio = padding_ratio
        self.square_plate_labels = square_plate_labels
        self.minimum_ocr_height = minimum_ocr_height

    def crop(self, frame, box: BoundingBox):
        """Crop biển số và chừa viền để tránh mất nét ký tự ngoài cùng."""
        frame_height, frame_width = frame.shape[:2]
        box_width = max(1, box.x2 - box.x1)
        box_height = max(1, box.y2 - box.y1)
        pad_x = int(box_width * self.padding_ratio)
        pad_y = int(box_height * self.padding_ratio)

        x1 = max(0, box.x1 - pad_x)
        y1 = max(0, box.y1 - pad_y)
        x2 = min(frame_width, box.x2 + pad_x)
        y2 = min(frame_height, box.y2 + pad_y)
        crop = frame[y1:y2, x1:x2].copy()

        if crop.size == 0:
            raise ValueError("Bounding box tạo ra ảnh crop rỗng.")
        return crop

    def prepare_for_ocr(self, crop, plate_type: str):
        """Tạo bản ảnh chỉ dùng cho OCR; ảnh crop gốc vẫn được giữ riêng."""
        image = crop.copy()

        if plate_type.strip().upper() in self.square_plate_labels:
            image = self._join_two_lines(image)

        height = image.shape[0]
        if height < self.minimum_ocr_height:
            scale = self.minimum_ocr_height / max(height, 1)
            image = cv2.resize(
                image,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        # Tăng tương phản cục bộ nhẹ, hữu ích khi biển bị tối hoặc phản sáng.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lightness, channel_a, channel_b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = cv2.merge((clahe.apply(lightness), channel_a, channel_b))
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    @staticmethod
    def _join_two_lines(image):
        """Cắt nửa trên/dưới của BSV rồi ghép ngang theo thứ tự đọc."""
        height, width = image.shape[:2]
        if height < 4 or width < 4:
            return image

        split_y = height // 2
        top = image[:split_y, :]
        bottom = image[split_y:, :]
        target_height = max(top.shape[0], bottom.shape[0])

        def resize_to_height(part):
            scale = target_height / max(part.shape[0], 1)
            return cv2.resize(
                part,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        top = resize_to_height(top)
        bottom = resize_to_height(bottom)
        gap = np.full((target_height, 12, 3), 255, dtype=np.uint8)
        return cv2.hconcat([top, gap, bottom])
