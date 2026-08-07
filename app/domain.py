"""Các kiểu dữ liệu dùng chung; không phụ thuộc camera, YOLO hay Google OCR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from datetime import datetime

class AppState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    RESULT = "RESULT"
    ERROR = "ERROR"


class AutoScanStatus(str, Enum):
    """Các trạng thái trả về trong một phiên camera tự động."""

    SEARCHING = "SEARCHING"
    COLLECTING = "COLLECTING"
    SUCCESS = "SUCCESS"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    PLATE_NOT_FOUND = "PLATE_NOT_FOUND"


class AccessDirection(str, Enum):
    """Hướng di chuyển của xe trong một phiên quét."""

    IN = "IN"
    OUT = "OUT"


class VehicleVisitStatus(str, Enum):
    """Trạng thái của một lượt xe từ lúc vào đến lúc ra."""

    INSIDE = "INSIDE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class PlateDetection:
    box: BoundingBox
    class_name: str
    confidence: float

@dataclass(frozen=True)
class FrameCandidate:
    crop: object
    detection: PlateDetection
    sharpness_score: float


@dataclass(frozen=True)
class AutoScanResult:
    """Kết quả của một lần gửi frame trong phiên camera tự động."""

    status: AutoScanStatus
    crop: object | None = None
    detection: PlateDetection | None = None
    frame_width: int = 0
    frame_height: int = 0
    formatted_plate: FormattedPlate | None = None
    stable_count: int = 0
    required_stable_count: int = 0
    sharpness_score: float = 0.0
    reason: str | None = None
    access_direction: AccessDirection | None = None

@dataclass(frozen=True)
class FormattedPlate:
    raw_text: str
    compact_text: str
    display_text: str
    is_valid: bool


@dataclass(frozen=True)
class ProcessingResult:
    display_image: object
    status: str
    formatted_plate: FormattedPlate | None = None
    error_message: str | None = None

@dataclass(frozen=True)
class RecognitionResult:
    """Kết quả nhận diện biển số từ một ảnh tĩnh."""

    crop: object
    detection: PlateDetection
    formatted_plate: FormattedPlate
    status: str

@dataclass(frozen=True)
class VehicleAccessEvent:
    scan_id: str
    plate_compact: str
    plate_display: str
    raw_text: str
    plate_type: str
    confidence: float
    direction: AccessDirection
    station_id: str
    camera_id: str
    captured_at: datetime
