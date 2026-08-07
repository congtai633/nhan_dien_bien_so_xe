from datetime import datetime

from pymongo import (
    ASCENDING,
    DESCENDING,
    MongoClient,
    ReturnDocument,
)
from pymongo.errors import DuplicateKeyError

from app.domain import (
    AccessDirection,
    VehicleAccessEvent,
    VehicleVisitStatus,
)


class MongoVehicleAccessRepository:
    def __init__(
        self,
        uri: str,
        database_name: str,
    ) -> None:
        self._client = MongoClient(uri)

        database = self._client[database_name]

        self._events = database["vehicle_access_events"]
        self._visits = database["vehicle_visits"]

        self._events.create_index(
            "scan_id",
            unique=True,
        )

        self._events.create_index(
            [
                ("plate_compact", ASCENDING),
                ("camera_id", ASCENDING),
                ("direction", ASCENDING),
                ("captured_at", DESCENDING),
            ]
        )

        # Một biển số chỉ được có tối đa một lượt đang ở trong bãi.
        # Partial unique index vẫn cho phép lưu nhiều lượt COMPLETED cũ.
        self._visits.create_index(
            [("plate_compact", ASCENDING)],
            name="unique_inside_visit_per_plate",
            unique=True,
            partialFilterExpression={
                "status": VehicleVisitStatus.INSIDE.value,
            },
        )

        self._visits.create_index(
            [
                ("plate_compact", ASCENDING),
                ("entry.captured_at", DESCENDING),
            ]
        )

    def has_recent_event(
        self,
        plate_compact: str,
        camera_id: str,
        direction: AccessDirection,
        since: datetime,
    ) -> bool:
        document = self._events.find_one(
            {
                "plate_compact": plate_compact,
                "camera_id": camera_id,
                "direction": direction.value,
                "captured_at": {
                    "$gte": since,
                },
            },
            {
                "_id": 1,
            },
        )

        return document is not None

    def has_open_visit(
        self,
        plate_compact: str,
    ) -> bool:
        """Kiểm tra biển số có lượt vào chưa được đóng hay không."""

        return self.find_open_visit(plate_compact) is not None

    def find_open_visit(
        self,
        plate_compact: str,
    ) -> dict | None:
        """Tìm lượt đang mở và trả dữ liệu giờ vào để hiển thị."""

        document = self._visits.find_one(
            {
                "plate_compact": plate_compact,
                "status": VehicleVisitStatus.INSIDE.value,
            },
            {
                "_id": 1,
                "entry.captured_at": 1,
            },
        )

        if document is None:
            return None

        entry = document.get("entry") or {}

        return {
            "visit_id": str(document["_id"]),
            "visit_status": VehicleVisitStatus.INSIDE.value,
            "entry_time": entry.get("captured_at"),
            "exit_time": None,
        }

    def create_open_visit(
        self,
        event: VehicleAccessEvent,
    ) -> str | None:
        """Tạo lượt xe vào; trả None nếu biển đã có lượt đang mở."""

        document = {
            "plate_compact": event.plate_compact,
            "plate_display": event.plate_display,
            "status": VehicleVisitStatus.INSIDE.value,
            "entry": self._event_details(event),
            "exit": None,
            "created_at": event.captured_at,
            "updated_at": event.captured_at,
        }

        try:
            result = self._visits.insert_one(document)
        except DuplicateKeyError:
            # Unique partial index xử lý trường hợp hai request IN đến
            # gần như đồng thời cho cùng một biển số.
            return None

        return str(result.inserted_id)

    def close_open_visit(
        self,
        event: VehicleAccessEvent,
    ) -> str | None:
        """Đóng lượt đang mở; trả None nếu không có lượt xe vào."""

        document = self._visits.find_one_and_update(
            {
                "plate_compact": event.plate_compact,
                "status": VehicleVisitStatus.INSIDE.value,
            },
            {
                "$set": {
                    "status": VehicleVisitStatus.COMPLETED.value,
                    "exit": self._event_details(event),
                    "updated_at": event.captured_at,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if document is None:
            return None

        return str(document["_id"])

    def save(
        self,
        event: VehicleAccessEvent,
    ) -> str:
        document = {
            "scan_id": event.scan_id,
            "plate_compact": event.plate_compact,
            "plate_display": event.plate_display,
            "raw_text": event.raw_text,
            "plate_type": event.plate_type,
            "confidence": event.confidence,
            "direction": event.direction.value,
            "station_id": event.station_id,
            "camera_id": event.camera_id,
            "captured_at": event.captured_at,
        }

        result = self._events.insert_one(document)

        return str(result.inserted_id)

    @staticmethod
    def _event_details(event: VehicleAccessEvent) -> dict:
        """Dữ liệu nhận diện được nhúng vào entry hoặc exit của lượt xe."""

        return {
            "scan_id": event.scan_id,
            "raw_text": event.raw_text,
            "plate_type": event.plate_type,
            "confidence": event.confidence,
            "station_id": event.station_id,
            "camera_id": event.camera_id,
            "captured_at": event.captured_at,
        }
