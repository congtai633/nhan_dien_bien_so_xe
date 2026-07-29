"""Các kiểu dữ liệu dùng chung; không phụ thuộc camera, YOLO hay Google OCR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    RESULT = "RESULT"
    ERROR = "ERROR"


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
