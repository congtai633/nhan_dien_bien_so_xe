"""Adapter chạy model YOLO và chuyển output sang PlateDetection."""

from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

from app.domain import BoundingBox, PlateDetection


class YOLOPlateDetector:
    def __init__(self, model_path: Path, preview_confidence: float) -> None:
        self._model = YOLO(str(model_path))
        self._preview_confidence = preview_confidence

    def detect(self, frame) -> list[PlateDetection]:
        """Phát hiện tất cả biển số trong frame, chưa gọi OCR."""
        height, width = frame.shape[:2]
        result = self._model.predict(
            source=frame,
            conf=self._preview_confidence,
            verbose=False,
        )[0]

        detections: list[PlateDetection] = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
            class_id = int(box.cls[0].item())

            detections.append(
                PlateDetection(
                    box=BoundingBox(
                        x1=max(0, min(width - 1, int(x1))),
                        y1=max(0, min(height - 1, int(y1))),
                        x2=max(0, min(width, int(x2))),
                        y2=max(0, min(height, int(y2))),
                    ),
                    class_name=str(self._model.names[class_id]),
                    confidence=float(box.conf[0].item()),
                )
            )

        return sorted(detections, key=lambda item: item.confidence, reverse=True)
