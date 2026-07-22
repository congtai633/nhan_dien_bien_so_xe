"""Hợp đồng giúp thay Google OCR mà không sửa controller."""

from __future__ import annotations

from typing import Protocol

class OCRProvider(Protocol):
    def recognize(self, image: object) -> str:
        """Trả về văn bản thô đọc được từ một ảnh."""
