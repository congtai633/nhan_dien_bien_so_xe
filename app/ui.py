"""Giao diện OpenCV: vẽ box, phím tắt, ảnh crop và chuỗi OCR."""

from __future__ import annotations

import cv2

from app.domain import AppState, PlateDetection


class OpenCVDisplay:
    MAIN_WINDOW = "Vietnam License Plate Control"
    RESULT_WINDOW = "License plate OCR result"

    _STATE_COLORS = {
        AppState.IDLE: (220, 220, 220),
        AppState.SCANNING: (0, 220, 255),
        AppState.PROCESSING: (255, 180, 0),
        AppState.RESULT: (0, 220, 0),
        AppState.ERROR: (0, 0, 255),
    }

    def render(
        self,
        frame,
        detections: list[PlateDetection],
        state: AppState,
        message: str,
        threshold: float,
    ) -> None:
        color = self._STATE_COLORS[state]
        for detection in detections:
            box = detection.box
            box_color = (
                (0, 255, 0) if detection.confidence >= threshold else (0, 165, 255)
            )
            cv2.rectangle(
                frame,
                (box.x1, box.y1),
                (box.x2, box.y2),
                box_color,
                2,
            )
            cv2.putText(
                frame,
                f"{detection.class_name} {detection.confidence:.2f}",
                (box.x1, max(25, box.y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                box_color,
                2,
                cv2.LINE_AA,
            )

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 92), (20, 20, 20), -1)
        cv2.putText(
            frame,
            f"STATE: {state.value} | C: Check | R: Reload | Q: Quit",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            color,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            message[:110],
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            color,
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(self.MAIN_WINDOW, frame)

    def show_result(self, image, plate_text: str) -> None:
        """Hiện ảnh crop và đầy đủ chuỗi biển số."""
        if image is None:
            return

        result_image = image.copy()

        # Phóng lớn ảnh crop nếu ảnh quá nhỏ
        height, width = result_image.shape[:2]
        min_width = 420

        if width < min_width:
            scale = min_width / width
            new_height = int(height * scale)
            result_image = cv2.resize(
                result_image,
                (min_width, new_height),
                interpolation=cv2.INTER_CUBIC,
            )

        if plate_text:
            label = f"BIEN SO: {plate_text}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.9
            thickness = 2

            # Tính chiều rộng thực tế của dòng chữ
            (text_width, _), _ = cv2.getTextSize(
                label,
                font,
                font_scale,
                thickness,
            )

            # Mở rộng ảnh nếu dòng chữ dài hơn ảnh crop
            required_width = text_width + 32
            right_padding = max(0, required_width - result_image.shape[1])

            result_image = cv2.copyMakeBorder(
                result_image,
                0,                 # trên
                65,                # dưới: dành chỗ hiện biển số
                0,                 # trái
                right_padding,     # phải: tự động mở rộng
                cv2.BORDER_CONSTANT,
                value=(20, 20, 20),
            )

            cv2.putText(
                result_image,
                label,
                (16, result_image.shape[0] - 20),
                font,
                font_scale,
                (0, 255, 0),
                thickness,
                cv2.LINE_AA,
            )

        cv2.imshow(self.RESULT_WINDOW, result_image)

    @classmethod
    def clear_result(cls) -> None:
        """Đóng ảnh và chuỗi cũ khi người vận hành nhấn R."""
        try:
            cv2.destroyWindow(cls.RESULT_WINDOW)
        except cv2.error:
            # Cửa sổ chưa từng được tạo thì không có gì cần đóng.
            pass

    @staticmethod
    def read_key() -> str | None:
        key = cv2.waitKey(1) & 0xFF
        if key == 255:
            return None
        try:
            return chr(key).lower()
        except ValueError:
            return None

    @staticmethod
    def close() -> None:
        cv2.destroyAllWindows()
