import unittest

from app.controller import LicensePlateController
from app.domain import AppState


class _Config:
    detection_threshold = 0.80


class _Camera:
    def __init__(self):
        self.opened = False
        self.released = False

    def open(self):
        self.opened = True

    def read(self):
        return object()

    def release(self):
        self.released = True


class _Display:
    def __init__(self):
        self.clear_result_calls = 0
        self.next_keys = []
        self.closed = False

    def clear_result(self):
        self.clear_result_calls += 1

    def render(self, **kwargs):
        pass

    def show_result(self, image, plate_text):
        pass

    def read_key(self):
        return self.next_keys.pop(0) if self.next_keys else None

    def close(self):
        self.closed = True

class _FrameSelector:
    def reset(self):
        pass

class ControllerControlTests(unittest.TestCase):
    def setUp(self):
        self.camera = _Camera()
        self.display = _Display()
        self.controller = LicensePlateController(
            config=_Config(),
            camera=self.camera,
            detector=object(),
            image_processor=object(),
            ocr=object(),
            formatter=object(),
            display=self.display,
            frame_selector=_FrameSelector()
        )

    def tearDown(self):
        self.controller._executor.shutdown(wait=True, cancel_futures=True)

    def test_c_starts_a_check(self):
        self.controller._start_check()

        self.assertEqual(self.controller.state, AppState.SCANNING)
        self.assertGreater(self.controller.scan_started_at, 0)

    def test_c_requires_reload_after_a_result(self):
        self.controller.state = AppState.RESULT

        self.controller._start_check()

        self.assertEqual(self.controller.state, AppState.RESULT)
        self.assertIn("Press R to reload", self.controller.message)

    def test_r_reloads_to_idle_and_clears_old_result(self):
        self.controller.state = AppState.RESULT
        self.controller.latest_crop = object()
        self.controller.latest_plate_text = "50L-347.98"

        self.controller._reload()

        self.assertEqual(self.controller.state, AppState.IDLE)
        self.assertIsNone(self.controller.latest_crop)
        self.assertEqual(self.controller.latest_plate_text, "")
        self.assertEqual(self.display.clear_result_calls, 1)

    def test_r_waits_when_ocr_is_processing(self):
        self.controller.state = AppState.PROCESSING

        self.controller._reload()

        self.assertEqual(self.controller.state, AppState.PROCESSING)
        self.assertIn("OCR is processing", self.controller.message)
        self.assertEqual(self.display.clear_result_calls, 0)

    def test_q_exits_and_releases_the_camera(self):
        self.display.next_keys = ["q"]

        self.controller.run()

        self.assertTrue(self.camera.opened)
        self.assertTrue(self.camera.released)
        self.assertTrue(self.display.closed)


if __name__ == "__main__":
    unittest.main()
