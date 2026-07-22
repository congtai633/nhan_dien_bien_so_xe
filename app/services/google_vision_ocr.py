"""Adapter duy nhất được phép gọi Google Cloud Vision TEXT_DETECTION."""

from __future__ import annotations

from pathlib import Path

import cv2
from google.cloud import vision


class GoogleVisionOCR:
    def __init__(self, credentials_path: Path | None = None) -> None:
        if credentials_path is not None:
            self._client = vision.ImageAnnotatorClient.from_service_account_json(
                str(credentials_path)
            )
        else:
            # Cho phép dùng Application Default Credentials nếu máy đã chạy
            # `gcloud auth application-default login`.
            self._client = vision.ImageAnnotatorClient()

    def recognize(self, image) -> str:
        """Gửi đúng một ảnh crop lên Vision và trả về văn bản thô."""
        success, encoded = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), 95],
        )
        if not success:
            raise ValueError("Không mã hóa được ảnh trước khi gửi Google Vision.")

        response = self._client.text_detection(
            image=vision.Image(content=encoded.tobytes()),
            timeout=15,
        )
        if response.error.message:
            raise RuntimeError(f"Google Vision API: {response.error.message}")
        if not response.text_annotations:
            return ""

        return response.text_annotations[0].description.strip()
