# Kiến trúc và trách nhiệm các module

## Kiến trúc tổng thể

Hệ thống sử dụng **composition** và **dependency injection**:

1. `main.py` tạo các object.
2. Các object được truyền vào `LicensePlateController`.
3. Controller chỉ điều phối, không tự khởi tạo YOLO, camera hoặc OCR.
4. Mỗi service xử lý một trách nhiệm riêng.

Nhờ cách tổ chức này, có thể thay camera, model hoặc OCR mà không phải viết lại
toàn bộ hệ thống.

```text
main.py
→ LicensePlateController
   ├─ CameraService
   ├─ YOLOPlateDetector
   ├─ FrameSelector
   ├─ PlateImageProcessor
   ├─ OCRProvider → GoogleVisionOCR
   ├─ VietnamesePlateFormatter
   └─ OpenCVDisplay
```

## Trách nhiệm từng file

| File | Trách nhiệm | Khi nào cần sửa? |
|---|---|---|
| `main.py` | Khởi tạo và truyền các dependency vào controller | Khi thêm hoặc thay service |
| `app/config.py` | Đọc `.env`, chuyển kiểu và kiểm tra cấu hình | Khi thêm tham số cấu hình |
| `app/domain.py` | Chứa state và các dataclass dùng chung | Khi cấu trúc dữ liệu nghiệp vụ đổi |
| `app/interfaces.py` | Khai báo hợp đồng `OCRProvider` | Khi hợp đồng chung của OCR thay đổi |
| `app/controller.py` | Điều phối C/R/Q, state, quét, chọn frame, OCR và kết quả | Khi luồng nghiệp vụ thay đổi |
| `app/services/camera_service.py` | Mở, đọc và đóng camera | Khi đổi webcam sang RTSP hoặc thêm reconnect |
| `app/services/plate_detector.py` | Chạy YOLO và chuyển output thành `PlateDetection` | Khi đổi model hoặc cách lọc detection |
| `app/services/frame_selector.py` | Theo dõi nhiều frame, đo độ nét và chọn crop tốt nhất | Khi đổi quy tắc ổn định/chọn ảnh |
| `app/services/image_processor.py` | Crop có padding, ghép BSV và tăng tương phản | Khi thêm deskew hoặc perspective correction |
| `app/services/google_vision_ocr.py` | Gọi Google Vision `TEXT_DETECTION` | Khi đổi API, timeout hoặc retry |
| `app/services/plate_formatter.py` | Làm sạch và định dạng chuỗi biển số | Khi thêm loại biển hoặc sửa quy tắc ký tự |
| `app/ui.py` | Vẽ box, trạng thái, kết quả và đọc phím | Khi thay OpenCV bằng web/GUI |
| `tests/test_controller_controls.py` | Kiểm tra hành vi C/R/Q của controller | Khi state hoặc constructor controller đổi |
| `tests/test_plate_formatter.py` | Kiểm tra các trường hợp định dạng biển số | Khi quy tắc formatter thay đổi |

## Dữ liệu truyền qua các tầng

| Bước | Input | Output |
|---|---|---|
| Camera | `cv2.VideoCapture` | Frame BGR dạng `numpy.ndarray` |
| Detector | Frame | `list[PlateDetection]` |
| Crop | Frame + `BoundingBox` | Ảnh biển số |
| Frame selector | Crop + detection + kích thước frame | `None` hoặc `FrameCandidate` tốt nhất |
| Image processor | Crop + loại `BSV/BSD` | Ảnh đã chuẩn bị cho OCR |
| OCR | Ảnh xử lý | Chuỗi thô |
| Formatter | Chuỗi thô | `FormattedPlate` |
| Controller | Kết quả xử lý | State, thông báo, ảnh và chuỗi hiển thị |

Các kiểu dữ liệu chính trong `app/domain.py`:

- `AppState`: trạng thái hiện tại của chương trình.
- `BoundingBox`: tọa độ biển số.
- `PlateDetection`: box, nhãn `BSV/BSD` và confidence.
- `FrameCandidate`: crop, detection và điểm sharpness.
- `FormattedPlate`: chuỗi thô, chuỗi làm sạch, chuỗi hiển thị và tính hợp lệ.
- `ProcessingResult`: kết quả được thread OCR trả về controller.

## State machine

```text
IDLE
  └─ nhấn C → SCANNING
       ├─ hết SCAN_TIMEOUT_SECONDS → ERROR
       └─ FrameSelector chọn được ảnh → PROCESSING
              ├─ OCR hợp lệ → RESULT
              ├─ OCR có chữ nhưng sai định dạng → RESULT
              ├─ OCR không thấy chữ → ERROR
              └─ OCR/API lỗi → ERROR

SCANNING, RESULT hoặc ERROR ─ nhấn R → IDLE
PROCESSING ─ R bị khóa cho đến khi OCR hoàn tất
Mọi trạng thái ─ nhấn Q → đóng chương trình
```

Controller đổi sang `PROCESSING` trước khi đưa công việc vào
`ThreadPoolExecutor`. Từ frame tiếp theo, `_scan_frame()` không chạy nữa nên một
lượt kiểm tra không gửi OCR lần hai.

`R` chỉ reset dữ liệu của phiên kiểm tra. Nó không load lại model YOLO và không
mở lại camera.

## Luồng quét và chọn frame

Khi state là `SCANNING`, controller thực hiện:

1. Gọi `YOLOPlateDetector.detect(frame)`.
2. Danh sách detection đã được sắp xếp theo confidence giảm dần.
3. Lấy detection đầu tiên đạt `DETECTION_THRESHOLD`.
4. Crop biển số có padding.
5. Gửi crop và detection vào `FrameSelector.observe()`.
6. Hiển thị `stable_count` và điểm sharpness hiện tại.
7. Nếu selector trả về `None`, tiếp tục đọc frame mới.
8. Nếu selector trả về `FrameCandidate`, gửi đúng ảnh đó sang bước OCR.

Nếu frame hiện tại không có detection đạt ngưỡng, controller gọi
`FrameSelector.reset()`.

## Cách `FrameSelector` hoạt động

`FrameSelector` là bộ chọn frame theo quy tắc, chưa phải tracker nhiều đối tượng
như ByteTrack.

### Xác định cùng mục tiêu

Hai detection được xem là cùng mục tiêu khi:

- Có cùng nhãn `BSV` hoặc `BSD`.
- Độ lệch tâm không vượt `MAX_CENTER_SHIFT_RATIO` nhân với đường chéo frame.

Vị trí hiện tại được so với detection đầu tiên của cửa sổ theo dõi
`_anchor_detection`, không phải detection của frame ngay trước đó.

### Thu thập và chọn ảnh

1. Detection đầu tiên bắt đầu cửa sổ thời gian và có `stable_count = 1`.
2. Mỗi detection cùng mục tiêu làm bộ đếm tăng thêm một.
3. Sharpness được tính bằng Variance of Laplacian.
4. Chỉ crop đạt `MIN_SHARPNESS_SCORE` mới được lưu vào danh sách ứng viên.
5. Khi đủ `STABLE_FRAME_COUNT`, selector chọn ảnh có sharpness cao nhất.
6. Nếu hai ảnh có cùng sharpness, ảnh có confidence cao hơn được ưu tiên.
7. Sau khi chọn, selector tự reset để xóa dữ liệu tạm.

Quá trình bắt đầu lại từ `1` nếu:

- Quá `CANDIDATE_WINDOW_SECONDS`.
- Nhãn detection thay đổi.
- Tâm detection lệch quá giới hạn.
- Controller không thấy detection nào đạt confidence.
- Người dùng bắt đầu lượt kiểm tra mới bằng phím `C`.

Lưu ý: code hiện tại chỉ cần có ít nhất một ứng viên đủ nét trong số các frame
ổn định, không yêu cầu tất cả frame đều đạt ngưỡng sharpness.

## Luồng xử lý biển BSV và BSD

### BSD

Ảnh crop được giữ nguyên bố cục một dòng, phóng lớn nếu cần và tăng tương phản
trước khi OCR.

### BSV

1. Crop biển vuông.
2. Chia ảnh thành nửa trên và nửa dưới.
3. Resize hai phần về cùng chiều cao.
4. Ghép ngang theo thứ tự đọc.
5. Thêm khoảng trắng giữa hai phần.
6. Phóng lớn và tăng tương phản.
7. Gửi bản đã xử lý lên Google Vision.

Ảnh hiển thị cho người dùng vẫn là crop gốc. Ảnh gửi OCR là bản đã qua
`prepare_for_ocr()`.

Ví dụ:

```text
50L
347.98
→ 50L34798
→ 50L-347.98
```

## OCR và xử lý bất đồng bộ

OCR chạy trong `ThreadPoolExecutor(max_workers=1)` để giao diện camera không bị
đứng trong lúc chờ Google Vision.

Worker thực hiện:

```text
GoogleVisionOCR.recognize()
→ VietnamesePlateFormatter.format()
→ ProcessingResult
```

Main thread gọi `_poll_processing_result()` để nhận `ProcessingResult` rồi mới
cập nhật state. Worker không trực tiếp sửa state của controller.

Các status hiện tại:

| Status | Ý nghĩa | State cuối |
|---|---|---|
| `SUCCESS` | Có chữ và đúng định dạng đã hỗ trợ | `RESULT` |
| `INVALID_FORMAT` | Có chữ nhưng formatter chưa nhận dạng | `RESULT` |
| `NO_TEXT` | Google Vision không tìm thấy chữ | `ERROR` |
| `OCR_ERROR` | API, network hoặc xử lý OCR phát sinh lỗi | `ERROR` |

## Vai trò của `OCRProvider`

`OCRProvider` là `Protocol` mô tả hợp đồng:

```python
class OCRProvider(Protocol):
    def recognize(self, image: object) -> str:
        ...
```

`GoogleVisionOCR` không cần kế thừa trực tiếp từ `OCRProvider`. Python sử dụng
structural typing: object nào có hàm `recognize(image) -> str` đúng hợp đồng đều
có thể được truyền vào controller.

Khi chạy hiện tại, `main.py` truyền:

```python
ocr=GoogleVisionOCR(config.google_credentials_path)
```

Vì vậy, lời gọi `self.ocr.recognize(...)` trong controller thực tế chạy hàm của
`GoogleVisionOCR`.

Để thay OCR khác, tạo class có cùng hàm `recognize()` rồi đổi object trong
`main.py`; controller không cần sửa.

## Vì sao chưa có database và lưu ảnh?

Phiên bản hiện tại chỉ cần hiển thị ảnh và chuỗi OCR ngay trên màn hình. Vì vậy,
controller không tạo ID, không ghi ảnh và không lưu database.

Khi cần lưu lịch sử xe vào/ra, có thể thêm repository hoặc service lưu trữ rồi
truyền vào controller mà không phải thay YOLO, `FrameSelector` hoặc OCR.

## Vai trò của thư mục `tests`

Các file test không tham gia khi chạy:

```powershell
python main.py
```

Vì vậy, chúng không bắt buộc đối với việc mở ứng dụng. Tuy nhiên, nên giữ test
trong source phát triển vì chúng giúp:

- Phát hiện lỗi cũ quay lại sau khi sửa code.
- Kiểm tra logic mà không cần camera hoặc gọi Google Vision.
- Xác nhận constructor và dependency của controller vẫn đồng bộ.
- Tự tin hơn khi thay formatter, state machine hoặc `FrameSelector`.

Khi constructor của controller có dependency mới như `frame_selector`, fake
object trong test cũng phải được cập nhật. Ngoài test hiện có, nên bổ sung test
riêng cho `FrameSelector`: đủ số frame, ảnh mờ, mục tiêu di chuyển, hết cửa sổ
thời gian và chọn đúng ảnh nét nhất.
