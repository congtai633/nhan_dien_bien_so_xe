"""Đọc toàn bộ cấu hình từ file .env và kiểm tra giá trị đầu vào."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _camera_source(value: str) -> Union[int, str]:
    value = value.strip()
    return int(value) if value.isdigit() else value


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình bất biến được truyền cho các module khi khởi động."""

    model_path: Path
    google_credentials_path: Path | None
    camera_source: int | str
    camera_width: int
    camera_height: int
    detection_threshold: float
    detection_preview_threshold: float
    scan_timeout_seconds: float
    crop_padding_ratio: float
    square_plate_labels: frozenset[str]
    stable_frame_count: int
    candidate_window_seconds: float
    min_sharpness_score: float
    max_center_shift_ratio: float

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv(PROJECT_DIR / ".env")

        credential_value = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        labels = {
            item.strip().upper()
            for item in os.getenv("SQUARE_PLATE_LABELS", "BSV").split(",")
            if item.strip()
        }

        config = cls(
            model_path=_project_path(os.getenv("MODEL_PATH", "models/best.pt")),
            google_credentials_path=(
                _project_path(credential_value) if credential_value else None
            ),
            camera_source=_camera_source(os.getenv("CAMERA_SOURCE", "0")),
            camera_width=int(os.getenv("CAMERA_WIDTH", "1280")),
            camera_height=int(os.getenv("CAMERA_HEIGHT", "720")),
            detection_threshold=float(os.getenv("DETECTION_THRESHOLD", "0.80")),
            detection_preview_threshold=float(
                os.getenv("DETECTION_PREVIEW_THRESHOLD", "0.25")
            ),
            scan_timeout_seconds=float(os.getenv("SCAN_TIMEOUT_SECONDS", "15")),
            crop_padding_ratio=float(os.getenv("CROP_PADDING_RATIO", "0.08")),
            square_plate_labels=frozenset(labels),
            stable_frame_count=int(os.getenv("STABLE_FRAME_COUNT", "5")),
            candidate_window_seconds=float(os.getenv("CANDIDATE_WINDOW_SECONDS", "1.5")),
            min_sharpness_score=float(os.getenv("MIN_SHARPNESS_SCORE", "100.0")),
            max_center_shift_ratio=float(os.getenv("MAX_CENTER_SHIFT_RATIO", "0.03"))
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy model YOLO: {self.model_path}")
        if self.google_credentials_path and not self.google_credentials_path.is_file():
            raise FileNotFoundError(
                "Không tìm thấy JSON Google Cloud: "
                f"{self.google_credentials_path}"
            )
        if not 0.0 < self.detection_threshold <= 1.0:
            raise ValueError("DETECTION_THRESHOLD phải nằm trong khoảng (0, 1].")
        if not 0.0 < self.detection_preview_threshold <= self.detection_threshold:
            raise ValueError(
                "DETECTION_PREVIEW_THRESHOLD phải lớn hơn 0 và không vượt "
                "DETECTION_THRESHOLD."
            )
        if self.scan_timeout_seconds <= 0:
            raise ValueError("SCAN_TIMEOUT_SECONDS phải lớn hơn 0.")
        if not 0.0 <= self.crop_padding_ratio <= 0.5:
            raise ValueError("CROP_PADDING_RATIO phải nằm trong khoảng [0, 0.5].")
        if self.stable_frame_count <= 0:
            raise ValueError("STABLE_FRAME_COUNT phải lớn hơn 0.")
        if self.candidate_window_seconds <= 0:
            raise ValueError("CANDIDATE_WINDOW_SECONDS phải lớn hơn 0.")
        if self.min_sharpness_score < 0:
            raise ValueError("MIN_SHARPNESS_SCORE phải lớn hơn hoặc bằng 0.")
        if not 0.0 <= self.max_center_shift_ratio <= 1.0:
            raise ValueError("MAX_CENTER_SHIFT_RATIO phải nằm trong khoảng [0, 1].")
