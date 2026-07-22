"""Điều phối luồng C/R/Q -> YOLO -> crop -> Google OCR -> hiển thị."""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

from app.domain import (
    AppState,
    PlateDetection,
    ProcessingResult,
)
from app.interfaces import OCRProvider

if TYPE_CHECKING:
    # Các import này chỉ phục vụ type hint. Controller có thể được unit test mà
    # không cần nạp OpenCV, Ultralytics hoặc cấu hình môi trường.
    from app.config import AppConfig
    from app.services.camera_service import CameraService
    from app.services.image_processor import PlateImageProcessor
    from app.services.plate_detector import YOLOPlateDetector
    from app.services.plate_formatter import VietnamesePlateFormatter
    from app.ui import OpenCVDisplay


LOGGER = logging.getLogger(__name__)


class LicensePlateController:
    """State machine bảo đảm mỗi phiên quét chỉ gọi OCR tối đa một lần."""

    def __init__(
        self,
        config: AppConfig,
        camera: CameraService,
        detector: YOLOPlateDetector,
        image_processor: PlateImageProcessor,
        ocr: OCRProvider,
        formatter: VietnamesePlateFormatter,
        display: OpenCVDisplay,
    ) -> None:
        self.config = config
        self.camera = camera
        self.detector = detector
        self.image_processor = image_processor
        self.ocr = ocr
        self.formatter = formatter
        self.display = display

        self.state = AppState.IDLE
        self.message = "Ready. Press C to check a license plate."
        self.scan_started_at = 0.0
        self.latest_crop = None
        self.latest_plate_text = ""
        self._future: Future[ProcessingResult] | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")

    def run(self) -> None:
        self.camera.open()
        LOGGER.info(
            "Camera sẵn sàng. Nhấn C để kiểm tra, R để tải lại, Q để thoát."
        )

        try:
            while True:
                frame = self.camera.read()
                self._poll_processing_result()
                detections = self._scan_frame(frame)

                self.display.render(
                    frame=frame,
                    detections=detections,
                    state=self.state,
                    message=self.message,
                    threshold=self.config.detection_threshold,
                )
                self.display.show_result(
                    self.latest_crop,
                    self.latest_plate_text,
                )

                key = self.display.read_key()
                if key == "q":
                    break
                if key == "c":
                    self._start_check()
                elif key == "r":
                    self._reload()
        finally:
            self.camera.release()
            self.display.close()
            self._executor.shutdown(wait=True, cancel_futures=True)
            LOGGER.info("Đã đóng hệ thống.")

    def _start_check(self) -> None:
        """C bắt đầu kiểm tra khi ứng dụng đang ở màn hình chờ."""
        if self.state == AppState.PROCESSING:
            self.message = "OCR is processing; please wait."
            return

        if self.state == AppState.SCANNING:
            self.message = "Already checking. Press R to reload."
            return

        if self.state in {AppState.RESULT, AppState.ERROR}:
            self.message = "Press R to reload before a new check."
            return

        self.state = AppState.SCANNING
        self.scan_started_at = time.monotonic()
        self.message = (
            "Checking locally... waiting for confidence >= "
            f"{self.config.detection_threshold:.2f}"
        )
        LOGGER.info("Bắt đầu kiểm tra biển số.")

    def _reload(self) -> None:
        """R xóa kết quả và đưa ứng dụng về trạng thái chờ."""
        if self.state == AppState.PROCESSING:
            self.message = "OCR is processing; reload when it finishes."
            return

        self.state = AppState.IDLE
        self.scan_started_at = 0.0
        self.latest_crop = None
        self.latest_plate_text = ""
        self.display.clear_result()
        self.message = "Reloaded. Press C to check a license plate."
        LOGGER.info("Đã tải lại trạng thái chương trình.")

    def _scan_frame(self, frame) -> list[PlateDetection]:
        if self.state != AppState.SCANNING:
            return []

        if time.monotonic() - self.scan_started_at > self.config.scan_timeout_seconds:
            self.state = AppState.ERROR
            self.message = "Check timeout. Press R to reload."
            LOGGER.warning("Hết thời gian quét nhưng chưa có detection đạt ngưỡng.")
            return []

        try:
            detections = self.detector.detect(frame)
            candidate = next(
                (
                    item
                    for item in detections
                    if item.confidence >= self.config.detection_threshold
                ),
                None,
            )
            if candidate is not None:
                self._submit_for_ocr(frame, candidate)
            return detections
        except Exception as exc:
            LOGGER.exception("Lỗi khi chạy YOLO: %s", exc)
            self.state = AppState.ERROR
            self.message = f"Detection error: {exc}"
            return []

    def _submit_for_ocr(self, frame, detection: PlateDetection) -> None:
        # Chuyển trạng thái trước khi tạo job để frame kế tiếp không gửi lần hai.
        self.state = AppState.PROCESSING
        self.message = "Plate captured. Sending one cropped image to Google Vision..."

        crop = self.image_processor.crop(frame, detection.box)
        ocr_image = self.image_processor.prepare_for_ocr(
            crop,
            detection.class_name,
        )
        self.latest_crop = crop
        self._future = self._executor.submit(
            self._recognize,
            crop,
            ocr_image,
        )
        LOGGER.info(
            "Đã crop %s với confidence %.3f; bắt đầu OCR một lần.",
            detection.class_name,
            detection.confidence,
        )

    def _recognize(
        self,
        crop,
        ocr_image,
    ) -> ProcessingResult:
        try:
            raw_text = self.ocr.recognize(ocr_image)
            formatted = self.formatter.format(raw_text)
            if not raw_text:
                status = "NO_TEXT"
            elif formatted.is_valid:
                status = "SUCCESS"
            else:
                status = "INVALID_FORMAT"

            return ProcessingResult(
                display_image=crop,
                status=status,
                formatted_plate=formatted,
            )
        except Exception as exc:
            LOGGER.exception("Google OCR thất bại: %s", exc)
            return ProcessingResult(
                display_image=crop,
                status="OCR_ERROR",
                error_message=str(exc),
            )

    def _poll_processing_result(self) -> None:
        if self._future is None or not self._future.done():
            return

        future = self._future
        self._future = None
        try:
            result = future.result()
            self.latest_crop = result.display_image
            formatted = result.formatted_plate

            if result.status == "SUCCESS" and formatted is not None:
                self.state = AppState.RESULT
                self.latest_plate_text = formatted.display_text
                self.message = f"Plate: {formatted.display_text} | R: Reload"
            elif result.status == "INVALID_FORMAT" and formatted is not None:
                self.state = AppState.RESULT
                self.latest_plate_text = formatted.display_text
                self.message = (
                    f"OCR: {formatted.display_text or '(empty)'} | "
                    "Format not recognized | R: Reload"
                )
            elif result.status == "NO_TEXT":
                self.state = AppState.ERROR
                self.latest_plate_text = "NO TEXT"
                self.message = "Google OCR found no text. Press R to reload."
            else:
                self.state = AppState.ERROR
                self.latest_plate_text = "OCR ERROR"
                self.message = (
                    f"OCR error: {result.error_message} | Press R to reload."
                )

            LOGGER.info(
                "Hoàn tất OCR | status=%s | plate=%s",
                result.status,
                self.latest_plate_text,
            )
        except Exception as exc:
            LOGGER.exception("Không thể hoàn tất OCR: %s", exc)
            self.state = AppState.ERROR
            self.latest_plate_text = "PROCESS ERROR"
            self.message = f"Process error: {exc} | Press R to reload."
