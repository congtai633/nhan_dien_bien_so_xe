import base64

import cv2
import numpy as np

from flask import Flask, jsonify, render_template, request
from app.config import AppConfig
from app.services.google_vision_ocr import GoogleVisionOCR
from app.services.image_processor import PlateImageProcessor
from app.services.plate_detector import YOLOPlateDetector
from app.services.plate_formatter import VietnamesePlateFormatter
from app.services.recognition_service import PlateRecognitionService


def _image_to_data_url(image) -> str:
    """Chuyển ảnh OpenCV thành chuỗi mà trình duyệt hiển thị được."""

    if image is None or not hasattr(image, "size") or image.size == 0:
        raise ValueError("Ảnh crop rỗng hoặc không hợp lệ.")

    success, encoded_image = cv2.imencode(".jpg", image)

    if not success:
        raise ValueError("Không thể mã hóa ảnh crop.")

    encoded_text = base64.b64encode(
        encoded_image.tobytes()
    ).decode("ascii")

    return f"data:image/jpeg;base64,{encoded_text}"

def create_app() -> Flask:
    """Tạo và cấu hình ứng dụng Flask."""

    app = Flask(__name__)

    config = AppConfig.from_env()
    recognition_service = build_recognition_service(config)

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

        # Đọc dữ liệu file thành mảng byte
        image_bytes = np.frombuffer(
            image_file.read(),
            dtype=np.uint8,
        )

        # Chuyển mảng byte thành ảnh OpenCV
        image = cv2.imdecode(
            image_bytes,
            cv2.IMREAD_COLOR,
        )

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

    return app

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

app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False,
    )