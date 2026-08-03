from datetime import datetime, timedelta, timezone

from app.domain import (
    AccessDirection,
    AutoScanStatus,
    VehicleAccessEvent,
)


class VehicleAccessService:
    def __init__(
        self,
        repository,
        station_id: str,
        camera_id: str,
        direction: AccessDirection,
        duplicate_window_seconds: float,
    ) -> None:
        self._repository = repository
        self._station_id = station_id
        self._camera_id = camera_id
        self._direction = direction
        self._duplicate_window_seconds = (
            duplicate_window_seconds
        )

    def record_success(
        self,
        scan_id: str,
        result,
    ) -> dict:
        formatted = result.formatted_plate
        detection = result.detection

        if (
            result.status != AutoScanStatus.SUCCESS
            or formatted is None
            or not formatted.is_valid
            or detection is None
        ):
            return {
                "status": "SKIPPED",
            }

        captured_at = datetime.now(timezone.utc)

        since = captured_at - timedelta(
            seconds=self._duplicate_window_seconds
        )

        is_duplicate = self._repository.has_recent_event(
            plate_compact=formatted.compact_text,
            camera_id=self._camera_id,
            direction=self._direction,
            since=since,
        )

        if is_duplicate:
            return {
                "status": "DUPLICATE",
            }

        event = VehicleAccessEvent(
            scan_id=scan_id,
            plate_compact=formatted.compact_text,
            plate_display=formatted.display_text,
            raw_text=formatted.raw_text,
            plate_type=detection.class_name,
            confidence=detection.confidence,
            direction=self._direction,
            station_id=self._station_id,
            camera_id=self._camera_id,
            captured_at=captured_at,
        )

        event_id = self._repository.save(event)

        return {
            "status": "SAVED",
            "event_id": event_id,
        }