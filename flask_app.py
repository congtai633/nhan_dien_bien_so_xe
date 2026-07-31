import base64

import cv2
import numpy as np

from flask import Flask, jsonify, render_template, request
from app.config import AppConfig
from app.domain import AutoScanStatus
from app.services.automatic_scan_service import (
    AutomaticScanService,
    UnknownScanSessionError,
)
from app.services.frame_selector import FrameSelector
from app.services.google_vision_ocr import GoogleVisionOCR
from app.services.image_processor import PlateImageProcessor
from app.services.plate_detector import YOLOPlateDetector
from app.services.plate_formatter import VietnamesePlateFormatter
from app.services.recognition_service import PlateRecognitionService


def _image_to_data_url(image) -> str:
    """Mã hóa ảnh OpenCV thành Data URL để trình duyệt hiển thị trực tiếp."""

    if image is None or not hasattr(image, "size") or image.size == 0:
        raise ValueError("Ảnh crop rỗng hoặc không hợp lệ.")

    success, encoded_image = cv2.imencode(".jpg", image)

    if not success:
        raise ValueError("Không thể mã hóa ảnh crop.")

    encoded_text = base64.b64encode(
        encoded_image.tobytes()
    ).decode("ascii")

    return f"data:image/jpeg;base64,{encoded_text}"


def _decode_uploaded_image(image_file):
    """Đổi file multipart thành ảnh OpenCV."""

    if image_file is None or not image_file.filename:
        return None

    image_bytes = np.frombuffer(
        image_file.read(),
        dtype=np.uint8,
    )
    return cv2.imdecode(
        image_bytes,
        cv2.IMREAD_COLOR,
    )


def create_app() -> Flask:
    """Tạo và cấu hình ứng dụng Flask."""

    app = Flask(__name__)

    config = AppConfig.from_env()
    recognition_service = build_recognition_service(config)
    automatic_scan_service = build_automatic_scan_service(
        config,
        recognition_service,
    )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/v1/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "message": "License plate API is running",
            }
        )

    @app.post("/api/v1/scan")
    def scan():
        # Lấy file từ trường form-data có tên "image"
        image_file = request.files.get("image")

        # Không có file hoặc file không có tên
        if image_file is None or not image_file.filename:
            return jsonify(
                {
                    "success": False,
                    "message": "Hãy gửi ảnh bằng trường có tên image.",
                }
            ), 400

        image = _decode_uploaded_image(image_file)

        # File gửi lên không phải ảnh hợp lệ
        if image is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Không thể đọc nội dung ảnh.",
                }
            ), 400

        try:
            result = recognition_service.recognize(image)
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "status": "PROCESSING_ERROR",
                    "message": str(exc),
                }
            ), 500

        if result is None:
            return jsonify(
                {
                    "success": False,
                    "status": "PLATE_NOT_FOUND",
                    "message": "Không tìm thấy biển số đạt ngưỡng confidence.",
                }
            ), 422

        try:
            crop_image = _image_to_data_url(result.crop)
        except ValueError as exc:
            return jsonify(
                {
                    "success": False,
                    "status": "IMAGE_ENCODING_ERROR",
                    "message": str(exc),
                }
            ), 500

        formatted = result.formatted_plate

        return jsonify(
            {
                "success": True,
                "status": result.status,
                "plate": formatted.display_text,
                "raw_text": formatted.raw_text,
                "is_valid": formatted.is_valid,
                "plate_type": result.detection.class_name,
                "crop_image": crop_image,
                "confidence": round(
                    result.detection.confidence,
                    4,
                ),
            }
        )

    @app.post("/api/v1/auto-scan/start")
    def start_auto_scan():
        """Tạo phiên để nhiều frame của một lượt xe dùng chung FrameSelector."""

        return jsonify(
            {
                "success": True,
                "status": "SCANNING",
                "session_id": automatic_scan_service.start_session(),
            }
        ), 201

    @app.post("/api/v1/auto-scan/frame")
    def scan_auto_frame():
        """Chạy YOLO trên một frame; chỉ OCR khi FrameSelector đã chọn xong."""

        session_id = request.form.get("session_id", "").strip()
        image = _decode_uploaded_image(
            request.files.get("image")
        )

        if not session_id:
            return jsonify(
                {
                    "success": False,
                    "message": "Thiếu session_id của phiên quét.",
                }
            ), 400

        if image is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Frame camera không hợp lệ.",
                }
            ), 400

        try:
            result = automatic_scan_service.observe(
                session_id,
                image,
            )
        except UnknownScanSessionError as exc:
            return jsonify(
                {
                    "success": False,
                    "status": "SESSION_ENDED",
                    "message": str(exc),
                }
            ), 409
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "status": "PROCESSING_ERROR",
                    "message": str(exc),
                }
            ), 500

        payload = _auto_scan_payload(result)

        if result.status in {
            AutoScanStatus.SEARCHING,
            AutoScanStatus.COLLECTING,
        }:
            return jsonify(payload), 202

        if result.status == AutoScanStatus.PLATE_NOT_FOUND:
            return jsonify(payload), 422

        return jsonify(payload)

    @app.post("/api/v1/auto-scan/cancel")
    def cancel_auto_scan():
        data = request.get_json(silent=True) or {}
        session_id = str(data.get("session_id", "")).strip()

        if session_id:
            automatic_scan_service.cancel_session(session_id)

        return jsonify({"success": True})

    return app


def _auto_scan_payload(result) -> dict:
    """Chuyển AutoScanResult thành JSON dành cho giao diện."""

    payload = {
        "success": result.status
        not in {AutoScanStatus.PLATE_NOT_FOUND},
        "status": result.status.value,
        "stable_count": result.stable_count,
        "required_stable_count": result.required_stable_count,
    }

    if result.status == AutoScanStatus.SEARCHING:
        payload["message"] = "Đang tìm biển số..."
        return payload

    if result.status == AutoScanStatus.COLLECTING:
        payload["message"] = (
            "Đã thấy biển số, đang chọn khung hình rõ nhất."
        )
        return payload

    if result.status == AutoScanStatus.PLATE_NOT_FOUND:
        payload["message"] = (
            "Hết thời gian quét nhưng chưa phát hiện được biển số."
        )
        return payload

    payload.update(
        {
            "crop_image": _image_to_data_url(result.crop),
            "plate_type": result.detection.class_name,
            "confidence": round(
                result.detection.confidence,
                4,
            ),
        }
    )

    if result.status == AutoScanStatus.SUCCESS:
        payload.update(
            {
                "plate": result.formatted_plate.display_text,
                "is_valid": True,
                "message": "Đã chọn frame tốt nhất và nhận diện thành công.",
            }
        )
        return payload

    payload.update(
        {
            "plate": "Không đọc được",
            "is_valid": False,
            "reason": result.reason,
            "message": _retry_message(result.reason),
        }
    )
    return payload


def _retry_message(reason: str | None) -> str:
    """Giải thích vì sao cần quét lại mà không lưu dữ liệu."""

    messages = {
        "LOW_IMAGE_QUALITY": (
            "Đã thấy biển số nhưng ảnh còn mờ hoặc chưa ổn định. "
            "Hãy giữ xe đứng yên và quét lại."
        ),
        "OCR_NO_TEXT": (
            "Đã chọn ảnh tốt nhất nhưng OCR không đọc được ký tự. "
            "Hãy làm sạch biển, tăng ánh sáng và quét lại."
        ),
        "OCR_INVALID_FORMAT": (
            "OCR đã đọc được ký tự nhưng chưa đúng định dạng biển số. "
            "Hãy điều chỉnh vị trí camera và quét lại."
        ),
    }
    return messages.get(
        reason,
        "Chưa nhận diện được biển số đáng tin cậy. Hãy quét lại.",
    )


def build_recognition_service(
        config: AppConfig,
    ) -> PlateRecognitionService:
        """Khởi tạo pipeline nhận diện ảnh tĩnh."""

        return PlateRecognitionService(
            detector=YOLOPlateDetector(
                model_path=config.model_path,
                preview_confidence=config.detection_preview_threshold,
            ),
            image_processor=PlateImageProcessor(
                padding_ratio=config.crop_padding_ratio,
                square_plate_labels=config.square_plate_labels,
            ),
            ocr=GoogleVisionOCR(
                config.google_credentials_path,
            ),
            formatter=VietnamesePlateFormatter(),
            detection_threshold=config.detection_threshold,
        )


def build_automatic_scan_service(
    config: AppConfig,
    recognition_service: PlateRecognitionService,
) -> AutomaticScanService:
    """Tạo pipeline nhiều frame riêng cho camera trên web."""

    return AutomaticScanService(
        recognition_service=recognition_service,
        frame_selector_factory=lambda: FrameSelector(
            stable_frame_count=config.stable_frame_count,
            # Phiên web đã có SCAN_TIMEOUT_SECONDS quản lý vòng đời, nên
            # không để cửa sổ ngắn reset selector giữa các request mạng.
            candidate_window_seconds=config.scan_timeout_seconds,
            min_sharpness_score=config.min_sharpness_score,
            max_center_shift_ratio=config.max_center_shift_ratio,
        ),
        scan_timeout_seconds=config.scan_timeout_seconds,
    )


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False,
    )
