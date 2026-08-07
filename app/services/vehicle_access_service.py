from datetime import datetime, timedelta, timezone

from app.domain import (
    AccessDirection,
    AutoScanStatus,
    VehicleAccessEvent,
    VehicleVisitStatus,
)


class VehicleAccessService:
    def __init__(
        self,
        repository,
        station_id: str,
        camera_id: str,
        duplicate_window_seconds: float,
    ) -> None:
        self._repository = repository
        self._station_id = station_id
        self._camera_id = camera_id
        self._duplicate_window_seconds = (
            duplicate_window_seconds
        )

    def record_success(
        self,
        scan_id: str,
        result,
        direction: AccessDirection,
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

        open_visit = self._repository.find_open_visit(
            formatted.compact_text
        )

        if direction == AccessDirection.IN and open_visit is not None:
            return {
                "status": "ALREADY_INSIDE",
                **self._visit_time_payload(
                    visit_id=open_visit["visit_id"],
                    visit_status=open_visit["visit_status"],
                    entry_time=open_visit["entry_time"],
                    exit_time=open_visit["exit_time"],
                ),
            }

        if direction == AccessDirection.OUT and open_visit is None:
            return {
                "status": "NOT_INSIDE",
            }

        since = captured_at - timedelta(
            seconds=self._duplicate_window_seconds
        )

        is_duplicate = self._repository.has_recent_event(
            plate_compact=formatted.compact_text,
            camera_id=self._camera_id,
            direction=direction,
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
            direction=direction,
            station_id=self._station_id,
            camera_id=self._camera_id,
            captured_at=captured_at,
        )

        if direction == AccessDirection.IN:
            visit_id = self._repository.create_open_visit(event)

            if visit_id is None:
                return {
                    "status": "ALREADY_INSIDE",
                }

            operation_status = "ENTRY_RECORDED"
            visit_status = VehicleVisitStatus.INSIDE.value
            entry_time = captured_at
            exit_time = None
        else:
            visit_id = self._repository.close_open_visit(event)

            if visit_id is None:
                return {
                    "status": "NOT_INSIDE",
                }

            operation_status = "EXIT_RECORDED"
            visit_status = VehicleVisitStatus.COMPLETED.value
            entry_time = open_visit["entry_time"]
            exit_time = captured_at

        event_id = self._repository.save(event)

        return {
            "status": operation_status,
            "event_id": event_id,
            **self._visit_time_payload(
                visit_id=visit_id,
                visit_status=visit_status,
                entry_time=entry_time,
                exit_time=exit_time,
            ),
        }

    @staticmethod
    def _visit_time_payload(
        visit_id: str,
        visit_status: str,
        entry_time: datetime | None,
        exit_time: datetime | None,
    ) -> dict:
        """Chuẩn hóa giờ MongoDB thành ISO 8601 UTC cho frontend."""

        return {
            "visit_id": visit_id,
            "visit_status": visit_status,
            "entry_time": VehicleAccessService._to_utc_iso(
                entry_time
            ),
            "exit_time": VehicleAccessService._to_utc_iso(
                exit_time
            ),
        }

    @staticmethod
    def _to_utc_iso(value: datetime | None) -> str | None:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc).isoformat()
