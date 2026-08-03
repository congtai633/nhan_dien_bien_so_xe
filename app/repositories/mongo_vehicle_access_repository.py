from datetime import datetime

from pymongo import ASCENDING, DESCENDING, MongoClient

from app.domain import AccessDirection, VehicleAccessEvent


class MongoVehicleAccessRepository:
    def __init__(
        self,
        uri: str,
        database_name: str,
    ) -> None:
        self._client = MongoClient(uri)

        database = self._client[database_name]

        self._collection = database["vehicle_access_events"]

        self._collection.create_index(
            "scan_id",
            unique=True,
        )

        self._collection.create_index(
            [
                ("plate_compact", ASCENDING),
                ("camera_id", ASCENDING),
                ("direction", ASCENDING),
                ("captured_at", DESCENDING),
            ]
        )

    def has_recent_event(
        self,
        plate_compact: str,
        camera_id: str,
        direction: AccessDirection,
        since: datetime,
    ) -> bool:
        document = self._collection.find_one(
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

        result = self._collection.insert_one(document)

        return str(result.inserted_id)