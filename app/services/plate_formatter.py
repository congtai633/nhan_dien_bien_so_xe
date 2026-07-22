"""Làm sạch, sửa nhầm ký tự ở vị trí số và định dạng biển số Việt Nam."""

from __future__ import annotations

import re

from app.domain import FormattedPlate


class VietnamesePlateFormatter:
    # Chỉ sửa các ký tự này tại vị trí chắc chắn phải là chữ số.
    _DIGIT_LOOKALIKES = str.maketrans(
        {
            "O": "0",
            "Q": "0",
            "D": "0",
            "I": "1",
            "L": "1",
            "Z": "2",
            "S": "5",
            "G": "6",
            "B": "8",
        }
    )

    def format(self, raw_text: str) -> FormattedPlate:
        compact = re.sub(r"[^A-Z0-9]", "", str(raw_text).upper())
        corrected = self._correct_numeric_positions(compact)
        display_text = self._add_separators(corrected)

        return FormattedPlate(
            raw_text=raw_text,
            compact_text=corrected,
            display_text=display_text,
            is_valid=self._is_valid(corrected),
        )

    def _correct_numeric_positions(self, value: str) -> str:
        if len(value) < 2:
            return value

        characters = list(value)

        # Hai ký tự đầu là mã tỉnh/thành và năm ký tự cuối thường là số sê-ri.
        for index in (0, 1):
            characters[index] = characters[index].translate(self._DIGIT_LOOKALIKES)
        if len(characters) >= 7:
            for index in range(len(characters) - 5, len(characters)):
                characters[index] = characters[index].translate(
                    self._DIGIT_LOOKALIKES
                )

        return "".join(characters)

    @staticmethod
    def _add_separators(value: str) -> str:
        patterns = (
            # Ô tô phổ biến: 51A-123.45
            (r"^(\d{2}[A-Z])(\d{3})(\d{2})$", r"\1-\2.\3"),
            # Mô tô phổ biến: 59A1-123.45
            (r"^(\d{2}[A-Z]\d)(\d{3})(\d{2})$", r"\1-\2.\3"),
            # Ký hiệu hai chữ: 51LD-123.45
            (r"^(\d{2}[A-Z]{2})(\d{3})(\d{2})$", r"\1-\2.\3"),
            # Biển cũ có bốn số cuối: 51A-1234
            (r"^(\d{2}[A-Z])([0-9]{4})$", r"\1-\2"),
        )
        for pattern, replacement in patterns:
            if re.fullmatch(pattern, value):
                return re.sub(pattern, replacement, value)
        return value

    @staticmethod
    def _is_valid(value: str) -> bool:
        return any(
            re.fullmatch(pattern, value) is not None
            for pattern in (
                r"\d{2}[A-Z]\d{5}",
                r"\d{2}[A-Z]\d{6}",
                r"\d{2}[A-Z]{2}\d{5}",
                r"\d{2}[A-Z]\d{4}",
            )
        )
