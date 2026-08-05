"""Điều phối phiên camera nhiều frame và chỉ OCR ảnh tốt nhất một lần."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Callable
from uuid import uuid4

from app.domain import (AccessDirection,AutoScanResult,AutoScanStatus,FrameCandidate,)
from app.services.frame_selector import FrameSelector
from app.services.recognition_service import PlateRecognitionService


class UnknownScanSessionError(ValueError):
    """Phiên quét không tồn tại hoặc đã kết thúc."""


@dataclass
class _ScanSession:
    selector: FrameSelector
    started_at: float
    access_direction: AccessDirection
    best_candidate: FrameCandidate | None = None
    frame_width: int = 0
    frame_height: int = 0
    finished: bool = False
    lock: Lock = field(default_factory=Lock)


class AutomaticScanService:
    """Giữ trạng thái riêng cho từng trình duyệt đang quét camera."""

    def __init__(
        self,
        recognition_service: PlateRecognitionService,
        frame_selector_factory: Callable[[], FrameSelector],
        scan_timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.recognition_service = recognition_service
        self.frame_selector_factory = frame_selector_factory
        self.scan_timeout_seconds = scan_timeout_seconds
        self._clock = clock
        self._sessions: dict[str, _ScanSession] = {}
        self._sessions_lock = Lock()

    def start_session(
        self,
        access_direction: AccessDirection,
    ) -> str:
        """Tạo phiên mới và khóa hướng IN/OUT cho toàn bộ phiên."""

        session_id = uuid4().hex
        session = _ScanSession(
            selector=self.frame_selector_factory(),
            started_at=self._clock(),
            access_direction=access_direction,
        )

        with self._sessions_lock:
            self._sessions[session_id] = session

        return session_id

    def observe(self, session_id: str, image) -> AutoScanResult:
        """Nhận một frame, theo dõi độ ổn định và quyết định lúc gọi OCR."""

        session = self._get_session(session_id)

        # JavaScript gửi tuần tự, nhưng khóa này vẫn bảo vệ khi có hai request
        # cùng phiên vô tình đến đồng thời.
        with session.lock:
            if session.finished:
                raise UnknownScanSessionError(
                    "Phiên quét không tồn tại hoặc đã kết thúc."
                )

            session.frame_height, session.frame_width = image.shape[:2]
            candidate_data = self.recognition_service.detect_candidate(image)
            elapsed = self._clock() - session.started_at

            if candidate_data is None:
                if elapsed >= self.scan_timeout_seconds:
                    return self._finish_after_timeout(session_id, session)

                return AutoScanResult(
                    status=AutoScanStatus.SEARCHING,
                    required_stable_count=session.selector.stable_frame_count,
                    access_direction=session.access_direction,
                )

            crop, detection = candidate_data
            selected = session.selector.observe(
                crop=crop,
                detection=detection,
                frame_shape=image.shape,
            )

            current = FrameCandidate(
                crop=crop.copy(),
                detection=detection,
                sharpness_score=session.selector.last_sharpness_score,
            )
            session.best_candidate = self._choose_better(
                session.best_candidate,
                current,
            )

            if selected is not None:
                return self._finish_with_ocr(
                    session_id,
                    session,
                    selected,
                    session.selector.stable_frame_count,
                )

            if elapsed >= self.scan_timeout_seconds:
                return self._finish_after_timeout(session_id, session)

            return AutoScanResult(
                status=AutoScanStatus.COLLECTING,
                crop=crop,
                detection=detection,
                frame_width=session.frame_width,
                frame_height=session.frame_height,
                stable_count=session.selector.stable_count,
                required_stable_count=session.selector.stable_frame_count,
                sharpness_score=session.selector.last_sharpness_score,
                access_direction=session.access_direction,
            )

    def cancel_session(self, session_id: str) -> None:
        """Hủy dữ liệu tạm khi người dùng tắt camera hoặc quét lại."""

        with self._sessions_lock:
            session = self._sessions.pop(session_id, None)

        if session is not None:
            session.finished = True

    def _finish_with_ocr(
        self,
        session_id: str,
        session: _ScanSession,
        candidate: FrameCandidate,
        stable_count: int,
    ) -> AutoScanResult:
        # Đây là điểm duy nhất trong luồng camera tự động được phép gọi OCR.
        try:
            result = self.recognition_service.recognize_candidate(
                candidate.crop,
                candidate.detection,
            )
        except Exception:
            # Lỗi API/credentials là lỗi hệ thống, không phải fallback ảnh mờ.
            # Vẫn phải đóng session để tránh giữ dữ liệu tạm vô thời hạn.
            session.finished = True
            self.cancel_session(session_id)
            raise

        # Đánh dấu trước khi xóa để request thứ hai đang chờ cùng session
        # không thể gọi OCR thêm lần nữa.
        session.finished = True
        self.cancel_session(session_id)

        if result.status == "SUCCESS":
            return AutoScanResult(
                status=AutoScanStatus.SUCCESS,
                crop=result.crop,
                detection=result.detection,
                frame_width=session.frame_width,
                frame_height=session.frame_height,
                formatted_plate=result.formatted_plate,
                stable_count=stable_count,
                required_stable_count=stable_count,
                sharpness_score=candidate.sharpness_score,
                access_direction=session.access_direction,
            )

        return AutoScanResult(
            status=AutoScanStatus.RETRY_REQUIRED,
            crop=result.crop,
            detection=result.detection,
            frame_width=session.frame_width,
            frame_height=session.frame_height,
            formatted_plate=result.formatted_plate,
            stable_count=stable_count,
            required_stable_count=stable_count,
            sharpness_score=candidate.sharpness_score,
            reason=(
                "OCR_NO_TEXT"
                if result.status == "NO_TEXT"
                else "OCR_INVALID_FORMAT"
            ),
            access_direction=session.access_direction,
        )

    def _finish_after_timeout(
        self,
        session_id: str,
        session: _ScanSession,
    ) -> AutoScanResult:
        best = session.best_candidate
        session.finished = True
        self.cancel_session(session_id)

        if best is None:
            return AutoScanResult(
                status=AutoScanStatus.PLATE_NOT_FOUND,
                required_stable_count=session.selector.stable_frame_count,
                access_direction=session.access_direction,
            )

        # YOLO đã thấy biển nhưng chưa có crop đủ rõ để gọi OCR.
        # Trả crop tốt nhất để giao diện hiển thị và yêu cầu quét lại.
        return AutoScanResult(
            status=AutoScanStatus.RETRY_REQUIRED,
            crop=best.crop,
            detection=best.detection,
            frame_width=session.frame_width,
            frame_height=session.frame_height,
            stable_count=session.selector.stable_count,
            required_stable_count=session.selector.stable_frame_count,
            sharpness_score=best.sharpness_score,
            reason="LOW_IMAGE_QUALITY",
            access_direction=session.access_direction,
        )

    def _get_session(self, session_id: str) -> _ScanSession:
        with self._sessions_lock:
            session = self._sessions.get(session_id)

        if session is None:
            raise UnknownScanSessionError(
                "Phiên quét không tồn tại hoặc đã kết thúc."
            )

        return session

    @staticmethod
    def _choose_better(
        current: FrameCandidate | None,
        candidate: FrameCandidate,
    ) -> FrameCandidate:
        if current is None:
            return candidate

        current_score = (
            current.sharpness_score,
            current.detection.confidence,
        )
        candidate_score = (
            candidate.sharpness_score,
            candidate.detection.confidence,
        )
        return candidate if candidate_score > current_score else current
