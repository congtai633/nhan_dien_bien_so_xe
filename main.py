"""Điểm khởi động của hệ thống nhận diện biển số xe."""

from __future__ import annotations

import logging

from app.config import AppConfig
from app.controller import LicensePlateController
from app.services.camera_service import CameraService
from app.services.google_vision_ocr import GoogleVisionOCR
from app.services.image_processor import PlateImageProcessor
from app.services.plate_detector import YOLOPlateDetector
from app.services.plate_formatter import VietnamesePlateFormatter
from app.services.frame_selector import FrameSelector
from app.ui import OpenCVDisplay


def build_application(config: AppConfig) -> LicensePlateController:
    """Khởi tạo và kết nối các module bằng dependency injection."""
    return LicensePlateController(
        config=config,
        camera=CameraService(
            source=config.camera_source,
            width=config.camera_width,
            height=config.camera_height,
        ),
        detector=YOLOPlateDetector(
            model_path=config.model_path,
            preview_confidence=config.detection_preview_threshold,
        ),
        image_processor=PlateImageProcessor(
            padding_ratio=config.crop_padding_ratio,
            square_plate_labels=config.square_plate_labels,
        ),
        ocr=GoogleVisionOCR(config.google_credentials_path),
        formatter=VietnamesePlateFormatter(),
        display=OpenCVDisplay(),
        frame_selector=FrameSelector(
            stable_frame_count=config.stable_frame_count,
            candidate_window_seconds=config.candidate_window_seconds,
            min_sharpness_score=config.min_sharpness_score,
            max_center_shift_ratio=config.max_center_shift_ratio,
        ),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    try:
        config = AppConfig.from_env()
        build_application(config).run()
    except KeyboardInterrupt:
        print("\nĐã dừng chương trình.")
    except Exception as exc:
        logging.getLogger(__name__).exception("Không thể khởi động hệ thống: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
