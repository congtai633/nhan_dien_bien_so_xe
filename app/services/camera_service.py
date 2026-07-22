"""Đóng gói việc mở, đọc và đóng webcam/camera RTSP."""

from __future__ import annotations

import cv2


class CameraService:
    def __init__(self, source: int | str, width: int, height: int) -> None:
        self.source = source
        self.width = width
        self.height = height
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        self._capture = cv2.VideoCapture(self.source)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not self._capture.isOpened():
            self.release()
            raise RuntimeError(
                f"Không mở được camera {self.source!r}. Hãy đóng ứng dụng đang "
                "chiếm camera hoặc đổi CAMERA_SOURCE trong file .env."
            )

    def read(self):
        if self._capture is None:
            raise RuntimeError("Camera chưa được mở.")

        success, frame = self._capture.read()
        if not success or frame is None:
            raise RuntimeError("Không đọc được khung hình từ camera.")
        return frame

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
