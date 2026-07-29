"""Theo dõi nhiều frame và chọn ảnh biển số rõ nhất trước khi OCR."""

from __future__ import annotations

from math import hypot
import time

import cv2

from app.domain import FrameCandidate, PlateDetection


class FrameSelector:
    def __init__(
        self,
        stable_frame_count: int,
        candidate_window_seconds: float,
        min_sharpness_score: float,
        max_center_shift_ratio: float,
    ) -> None:
        self.stable_frame_count = stable_frame_count
        self.candidate_window_seconds = candidate_window_seconds
        self.min_sharpness_score = min_sharpness_score
        self.max_center_shift_ratio = max_center_shift_ratio
        self.reset()

    def reset(self) -> None:
        """Xóa dữ liệu tạm của phiên theo dõi hiện tại."""
        self._anchor_detection: PlateDetection | None = None
        self._window_started_at = 0.0
        self._stable_count = 0
        self._candidates: list[FrameCandidate] = []
        self._last_sharpness_score = 0.0

    @property
    def stable_count(self) -> int:
        return self._stable_count

    @property
    def last_sharpness_score(self) -> float:
        return self._last_sharpness_score

    def observe(
        self,
        crop,
        detection: PlateDetection,
        frame_shape,
    ) -> FrameCandidate | None:
        """Nhận một detection; trả về frame tốt nhất khi biển đã ổn định."""
        now = time.monotonic()

        window_expired = (
            self._window_started_at > 0
            and now - self._window_started_at
            > self.candidate_window_seconds
        )

        same_target = (
            self._anchor_detection is not None
            and self._is_same_target(
                self._anchor_detection,
                detection,
                frame_shape,
            )
        )

        if self._anchor_detection is None or window_expired or not same_target:
            self._start_track(detection, now)
        else:
            self._stable_count += 1

        sharpness_score = self._calculate_sharpness(crop)
        self._last_sharpness_score = sharpness_score

        if sharpness_score >= self.min_sharpness_score:
            self._candidates.append(
                FrameCandidate(
                    crop=crop.copy(),
                    detection=detection,
                    sharpness_score=sharpness_score,
                )
            )

        if (
            self._stable_count < self.stable_frame_count
            or not self._candidates
        ):
            return None

        best = max(
            self._candidates,
            key=lambda item: (
                item.sharpness_score,
                item.detection.confidence,
            ),
        )

        self.reset()
        return best

    def _start_track(
        self,
        detection: PlateDetection,
        now: float,
    ) -> None:
        self._anchor_detection = detection
        self._window_started_at = now
        self._stable_count = 1
        self._candidates = []

    def _is_same_target(
        self,
        anchor: PlateDetection,
        current: PlateDetection,
        frame_shape,
    ) -> bool:
        if (
            anchor.class_name.strip().upper()
            != current.class_name.strip().upper()
        ):
            return False

        frame_height, frame_width = frame_shape[:2]
        frame_diagonal = max(
            hypot(frame_width, frame_height),
            1.0,
        )

        anchor_center_x = (anchor.box.x1 + anchor.box.x2) / 2
        anchor_center_y = (anchor.box.y1 + anchor.box.y2) / 2

        current_center_x = (current.box.x1 + current.box.x2) / 2
        current_center_y = (current.box.y1 + current.box.y2) / 2

        center_shift = hypot(
            current_center_x - anchor_center_x,
            current_center_y - anchor_center_y,
        )

        return (
            center_shift / frame_diagonal
            <= self.max_center_shift_ratio
        )

    @staticmethod
    def _calculate_sharpness(crop) -> float:
        if crop is None or crop.size == 0:
            return 0.0

        if crop.ndim == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop

        return float(
            cv2.Laplacian(gray, cv2.CV_64F).var()
        )