# Kiến trúc và trách nhiệm các module

Tài liệu này mô tả source hiện tại của hệ thống nhận diện biển số xe Việt Nam.
Project có hai điểm khởi động:

- `main.py`: chương trình desktop dùng OpenCV và phím `C/R/Q`.
- `flask_app.py`: ứng dụng web dùng camera của trình duyệt và tự động gửi nhiều
  frame.

Cả hai cùng tái sử dụng detector YOLO, bộ xử lý ảnh, Google Vision OCR,
formatter và `FrameSelector`.

## 1. Nguyên tắc kiến trúc

Source được chia theo ba nhóm chính:

1. **Domain**: trạng thái và kiểu dữ liệu dùng chung, không phụ thuộc thư viện
   bên ngoài.
2. **Services**: mỗi service giải quyết một trách nhiệm như camera, YOLO, chọn
   frame, xử lý ảnh hoặc OCR.
3. **Entry point/điều phối**: `main.py`, `controller.py` và `flask_app.py` kết
   nối các service thành luồng hoàn chỉnh.

Hệ thống sử dụng **composition** và **dependency injection**:

- `main.py` và `flask_app.py` là nơi tạo object thật.
- Controller/service nhận dependency qua constructor.
- Logic điều phối không tự khởi tạo YOLO hoặc Google Vision.

## 2. Kiến trúc desktop

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

`main.py` chỉ cấu hình và truyền dependency. `LicensePlateController` sở hữu
state machine `C/R/Q`, nhưng không biết chi tiết YOLO được nạp thế nào hoặc
Google Vision tạo client ra sao.

## 3. Kiến trúc web

```text
index.html + style.css
→ app.js mở camera trình duyệt
→ Flask REST API
→ AutomaticScanService
   ├─ một FrameSelector và hướng IN/OUT cho mỗi session_id
   └─ PlateRecognitionService
      ├─ YOLOPlateDetector
      ├─ PlateImageProcessor
      ├─ GoogleVisionOCR
      └─ VietnamesePlateFormatter
→ VehicleAccessService
→ MongoVehicleAccessRepository
→ MongoDB collection vehicle_access_events
```

Camera web do trình duyệt mở bằng `getUserMedia()`. Backend Flask không dùng
`CameraService` và không đọc `CAMERA_SOURCE` cho luồng này.

## 4. Trách nhiệm từng file

### File gốc và backend

| File | Trách nhiệm | Khi nào cần sửa? |
|---|---|---|
| `main.py` | Khởi tạo pipeline desktop và chạy controller | Khi thêm/thay dependency của desktop |
| `flask_app.py` | Tạo Flask app, khởi tạo pipeline web, khai báo API và chuyển kết quả thành JSON | Khi đổi endpoint hoặc contract frontend/backend |
| `app/config.py` | Đọc `.env`, chuyển kiểu, đổi đường dẫn và validate cấu hình | Khi thêm tham số cấu hình |
| `app/domain.py` | Chứa enum và dataclass dùng chung | Khi trạng thái hoặc dữ liệu nghiệp vụ thay đổi |
| `app/interfaces.py` | Khai báo hợp đồng `OCRProvider` | Khi thay đổi interface chung của OCR |
| `app/controller.py` | Điều phối state `C/R/Q`, chọn frame, chạy OCR bất đồng bộ và cập nhật kết quả | Khi đổi luồng desktop |
| `app/ui.py` | Vẽ camera, bounding box, trạng thái, ảnh crop và đọc bàn phím | Khi đổi giao diện OpenCV |

### Services

| File | Trách nhiệm | Không chịu trách nhiệm |
|---|---|---|
| `camera_service.py` | Mở, đọc và đóng webcam/RTSP cho `main.py` | Không dùng trong camera web |
| `plate_detector.py` | Chạy YOLO và đổi output thành `PlateDetection` | Không crop, không OCR |
| `frame_selector.py` | Theo dõi nhiều detection, đo sharpness và chọn crop tốt nhất | Không gọi YOLO hoặc OCR |
| `image_processor.py` | Crop có padding, xử lý BSV hai dòng, resize và CLAHE | Không đọc ký tự |
| `google_vision_ocr.py` | Mã hóa JPEG và gọi Google Vision `TEXT_DETECTION` | Không định dạng biển số |
| `plate_formatter.py` | Làm sạch, sửa ký tự dễ nhầm theo vị trí, thêm dấu và kiểm tra Regex | Không gọi Google Vision |
| `recognition_service.py` | Cung cấp ranh giới `detect_candidate()` và `recognize_candidate()` | Không giữ phiên nhiều frame |
| `automatic_scan_service.py` | Giữ session web, đưa frame qua selector, quyết định lúc OCR và đóng phiên | Không lưu database hoặc ảnh |
| `vehicle_access_service.py` | Kiểm tra kết quả hợp lệ, chống trùng và tạo sự kiện theo hướng của session | Không nhận diện ảnh hoặc quyết định cho xe ra |

### Repository

| File | Trách nhiệm |
|---|---|
| `mongo_vehicle_access_repository.py` | Tạo index, kiểm tra sự kiện gần nhất và lưu `VehicleAccessEvent` vào MongoDB |

### Frontend

| File | Trách nhiệm |
|---|---|
| `templates/index.html` | Khung giao diện, radio `XE VÀO/XE RA`, nút mở/tắt/quét lại |
| `static/css/style.css` | Bố cục, màu trạng thái, animation quét và responsive |
| `static/js/app.js` | Gửi hướng khi tạo session, khóa radio trong lúc quét, gửi frame và hủy session |

Giao diện hiện tại không còn input chọn file, preview ảnh upload hoặc nút nhận
diện ảnh thủ công. API ảnh tĩnh `/api/v1/scan` vẫn tồn tại để nhận diện ảnh trực
tiếp bằng Postman hoặc ứng dụng khác, nhưng `app.js` không gọi endpoint này.

## 5. Các kiểu dữ liệu trong `app/domain.py`

| Kiểu | Ý nghĩa |
|---|---|
| `AppState` | State của chương trình desktop |
| `AutoScanStatus` | Status của phiên camera web |
| `AccessDirection` | Hướng `IN` hoặc `OUT` của phiên/sự kiện |
| `BoundingBox` | Tọa độ `x1, y1, x2, y2` |
| `PlateDetection` | Bounding box, nhãn `BSD/BSV` và confidence |
| `FrameCandidate` | Crop, detection và sharpness |
| `FormattedPlate` | Chuỗi thô, chuỗi làm sạch, chuỗi hiển thị và cờ hợp lệ |
| `ProcessingResult` | Kết quả worker OCR trả về controller desktop |
| `RecognitionResult` | Kết quả nhận diện một ảnh/crop |
| `AutoScanResult` | Kết quả sau mỗi frame, kèm hướng đã khóa của phiên web |
| `VehicleAccessEvent` | Dữ liệu một lần nhận diện hợp lệ được lưu vào MongoDB |

`domain.py` dùng `object` cho ảnh để không buộc tầng domain phải import
`numpy` hoặc OpenCV.

## 6. Dữ liệu truyền qua pipeline

| Bước | Input | Output |
|---|---|---|
| Camera | Webcam/RTSP hoặc `getUserMedia()` | Frame hình ảnh |
| Decode web | JPEG multipart | Ảnh BGR `numpy.ndarray` |
| Detector | Frame BGR | `list[PlateDetection]` |
| Crop | Frame + `BoundingBox` | Ảnh biển số gốc |
| Frame selector | Crop + detection + kích thước frame | `None` hoặc `FrameCandidate` |
| Image processor | Crop + loại `BSD/BSV` | Ảnh đã chuẩn bị cho OCR |
| OCR | Ảnh xử lý | Chuỗi thô |
| Formatter | Chuỗi thô | `FormattedPlate` |
| Flask/UI | Kết quả | JSON hoặc hình ảnh/trạng thái hiển thị |

## 7. `PlateRecognitionService`

Trước khi có camera tự động, một hàm có thể chạy toàn bộ:

```text
YOLO → crop → tiền xử lý → OCR → format
```

Source hiện tách thành ba hàm:

### `recognize(image)`

Luồng tiện ích dành cho một ảnh tĩnh. Hàm gọi `detect_candidate()` rồi
`recognize_candidate()`.

### `detect_candidate(image)`

Chỉ thực hiện:

1. Kiểm tra ảnh hợp lệ.
2. Chạy detector.
3. Lấy detection đầu tiên đạt `DETECTION_THRESHOLD`.
4. Crop ảnh.
5. Trả `(crop, detection)`.

Hàm này **không gọi OCR**, nên `AutomaticScanService` có thể kiểm tra nhiều
frame mà không phát sinh một request Google Vision cho mỗi frame.

### `recognize_candidate(crop, detection)`

Chỉ được gọi sau khi đã có crop cần OCR:

1. `PlateImageProcessor.prepare_for_ocr()`.
2. `OCRProvider.recognize()`.
3. `VietnamesePlateFormatter.format()`.
4. Trả `SUCCESS`, `NO_TEXT` hoặc `INVALID_FORMAT`.

## 8. `FrameSelector`

`FrameSelector` là bộ chọn frame theo quy tắc, chưa phải tracker nhiều đối tượng
như ByteTrack.

### Xác định cùng mục tiêu

Hai detection được xem là cùng mục tiêu khi:

- Cùng nhãn `BSD` hoặc `BSV`.
- Khoảng cách giữa hai tâm không vượt
  `MAX_CENTER_SHIFT_RATIO × đường chéo frame`.

Detection hiện tại được so với detection neo đầu tiên
`_anchor_detection`, không phải frame ngay trước đó.

### Đo độ nét

Độ nét được tính bằng **Variance of Laplacian**:

```python
cv2.Laplacian(gray, cv2.CV_64F).var()
```

Giá trị lớn thường cho biết ảnh có nhiều cạnh rõ hơn. Đây không phải phần trăm
và phụ thuộc camera, ánh sáng, kích thước crop.

### Quy tắc chọn

1. Detection đầu tiên tạo track mới và `stable_count = 1`.
2. Detection cùng mục tiêu làm bộ đếm tăng.
3. Chỉ crop đạt `MIN_SHARPNESS_SCORE` mới vào danh sách ứng viên đủ nét.
4. Khi đủ `STABLE_FRAME_COUNT`, chọn ứng viên có sharpness cao nhất.
5. Nếu sharpness bằng nhau, chọn ảnh có confidence cao hơn.
6. Selector reset sau khi trả ứng viên.

Code hiện không dùng công thức trọng số confidence/sharpness. Sharpness là tiêu
chí chính; confidence chỉ là tie-breaker.

Track bắt đầu lại khi:

- Hết `candidate_window_seconds`.
- Nhãn biển thay đổi.
- Tâm biển lệch quá giới hạn.
- Luồng desktop không có detection đạt ngưỡng.
- Người dùng bắt đầu lượt quét desktop mới.

Trong luồng web, `AutomaticScanService` tạo selector với cửa sổ bằng
`SCAN_TIMEOUT_SECONDS` và không reset chỉ vì một request frame không có
detection. Session kết thúc khi thành công, retry, không tìm thấy biển, bị hủy
hoặc phát sinh lỗi.

## 9. `AutomaticScanService`

### Vì sao cần `session_id`?

HTTP không tự nhớ frame nào thuộc cùng một lượt quét. `start_session()` sinh
`session_id` bằng UUID và tạo `_ScanSession` riêng, nhờ đó:

- Frame của hai trình duyệt không bị trộn.
- Quét lại không dùng dữ liệu của lượt cũ.
- Mỗi session có hướng `IN/OUT`, một `FrameSelector`, thời gian bắt đầu và ứng
  viên tốt nhất.
- Người dùng không thể đổi hướng của phiên đang chạy giữa các frame.

### Luồng `observe()`

```text
Nhận session_id + frame
→ detect_candidate()
   ├─ chưa thấy biển và chưa timeout → SEARCHING
   ├─ chưa thấy biển và timeout → PLATE_NOT_FOUND
   └─ thấy biển
      → FrameSelector.observe()
         ├─ chưa chọn xong → COLLECTING
         ├─ đủ ổn định + có ảnh nét → OCR một lần
         │  ├─ hợp lệ → SUCCESS
         │  └─ rỗng/sai định dạng → RETRY_REQUIRED
         └─ timeout trước khi đủ điều kiện
            → RETRY_REQUIRED + crop tốt nhất
```

`best_candidate` lưu crop tốt nhất đã nhìn thấy, kể cả chưa đạt ngưỡng nét, để
giao diện có ảnh minh họa khi trả `LOW_IMAGE_QUALITY`. Dữ liệu chỉ nằm trong bộ
nhớ và bị xóa khi session kết thúc.

### Bảo đảm OCR không bị gọi lặp

- Frontend gửi request tuần tự.
- Mỗi `_ScanSession` có `Lock` để chống hai request cùng session chạy đồng thời.
- `_finish_with_ocr()` là điểm duy nhất trong luồng web gọi
  `recognize_candidate()`.
- Session được đánh dấu `finished` và xóa ngay sau OCR.
- Request dùng lại session cũ nhận `SESSION_ENDED`.

## 10. State machine camera web

| Status | Ý nghĩa | Hành động frontend |
|---|---|---|
| `SEARCHING` | Chưa thấy biển đạt ngưỡng | Tiếp tục gửi frame |
| `COLLECTING` | Đã thấy biển, đang kiểm tra ổn định/độ nét | Hiện tiến độ và tiếp tục |
| `SUCCESS` | OCR hợp lệ | Hiện crop, biển số, loại và confidence |
| `RETRY_REQUIRED` | Ảnh mờ, OCR rỗng hoặc sai format | Hiện crop tốt nhất và nút Quét lại |
| `PLATE_NOT_FOUND` | Hết thời gian mà chưa thấy biển | Báo điều chỉnh vị trí và quét lại |

`SESSION_ENDED` và `PROCESSING_ERROR` được Flask tạo ở tầng API; chúng không
thuộc enum `AutoScanStatus`.

## 11. REST API trong `flask_app.py`

| Endpoint | Input | Output chính |
|---|---|---|
| `GET /` | Không | `index.html` |
| `GET /api/v1/health` | Không | Trạng thái Flask |
| `POST /api/v1/scan` | form-data `image` | Kết quả nhận diện một ảnh |
| `POST /api/v1/auto-scan/start` | JSON `access_mode`: `IN` hoặc `OUT` | `session_id`, `access_mode`, HTTP `201` |
| `POST /api/v1/auto-scan/frame` | form-data `session_id`, `image` | Trạng thái phiên và kết quả nếu có |
| `POST /api/v1/auto-scan/cancel` | JSON `session_id` | Xác nhận hủy |

`_decode_uploaded_image()` đổi JPEG multipart thành ảnh BGR.
`_image_to_data_url()` đổi crop thành Data URL để trình duyệt hiển thị trực
tiếp; source không ghi file ảnh xuống ổ đĩa.

## 12. Frontend camera tự động

### `templates/index.html`

Chứa hai panel:

- Bên trái: chọn `XE VÀO/XE RA`, camera, badge và nút mở/tắt/quét lại.
- Bên phải: crop tốt nhất, biển số, loại biển và confidence.

Không còn form upload ảnh.

### `static/js/app.js`

Luồng chính:

1. `openCamera()` xin quyền camera.
2. `startAutomaticScan()` gửi hướng đã chọn và tạo session.
3. `captureCurrentCameraFrame()` vẽ video lên canvas và tạo JPEG.
4. `scanNextCameraFrame()` gửi frame đến Flask.
5. Request tiếp theo chỉ được lên lịch sau khi request hiện tại hoàn tất.
6. `renderRecognitionResult()` hiển thị Data URL và thông tin kết quả.
7. `stopAutomaticScan()` hủy session khi cần.

`AUTO_SCAN_DELAY_MS = 250` là thời gian chờ tối thiểu sau một response. Chu kỳ
thực tế còn bao gồm thời gian YOLO và thời gian truyền request.

### `static/css/style.css`

- Desktop dùng grid hai cột, camera rộng hơn kết quả.
- Badge có màu riêng cho idle, active, success, warning và error.
- Có animation cho trạng thái đang quét.
- Dưới `780px`, giao diện chuyển thành một cột.

## 13. Luồng xử lý BSV/BSD

### BSD

Giữ bố cục một dòng, resize khi ảnh quá nhỏ và tăng tương phản CLAHE.

### BSV

1. Chia crop thành nửa trên và nửa dưới.
2. Resize hai phần về cùng chiều cao.
3. Chèn khoảng trắng 12 pixel.
4. Ghép ngang theo thứ tự đọc.
5. Resize và tăng tương phản.

Ảnh crop gốc dùng để hiển thị. Bản ghép/tăng tương phản chỉ dùng cho OCR.

## 14. `OCRProvider` và `GoogleVisionOCR`

`OCRProvider` là `Protocol`:

```python
class OCRProvider(Protocol):
    def recognize(self, image: object) -> str:
        ...
```

`GoogleVisionOCR` không cần kế thừa trực tiếp. Python sử dụng structural typing:
object nào có `recognize(image) -> str` đúng hợp đồng đều có thể được truyền vào
controller hoặc recognition service.

Hiện tại `main.py` và `flask_app.py` truyền `GoogleVisionOCR`, vì vậy lời gọi:

```python
self.ocr.recognize(image)
```

thực tế chạy phương thức của `GoogleVisionOCR`. Muốn thay bằng PaddleOCR hoặc
Tesseract, tạo adapter có cùng hàm `recognize()` và đổi object tại entry point;
logic điều phối không cần sửa.

`GoogleVisionOCR`:

1. Mã hóa ảnh JPEG chất lượng 95.
2. Gọi `text_detection(..., timeout=15)`.
3. Ném lỗi nếu API trả lỗi.
4. Trả chuỗi rỗng nếu không có text annotation.
5. Trả nội dung annotation đầu tiên nếu thành công.

## 15. State machine desktop

```text
IDLE
  └─ nhấn C → SCANNING
       ├─ timeout → ERROR
       └─ FrameSelector chọn được crop → PROCESSING
            ├─ OCR hợp lệ → RESULT
            ├─ OCR có chữ nhưng sai format → RESULT
            └─ OCR rỗng/API lỗi → ERROR

SCANNING, RESULT hoặc ERROR ─ nhấn R → IDLE
PROCESSING ─ R bị khóa đến khi OCR hoàn tất
Mọi trạng thái ─ nhấn Q → đóng chương trình
```

OCR desktop chạy trong `ThreadPoolExecutor(max_workers=1)` để cửa sổ camera
không bị đứng. Controller chuyển sang `PROCESSING` trước khi submit job, nên
frame tiếp theo không thể gửi OCR lần hai.

## 16. Phạm vi lưu dữ liệu

Project hiện có MongoDB để lưu từng sự kiện nhận diện thành công, nhưng chưa có
`ManualCaseService`, API manual case, thư mục lưu ảnh hoặc collection ghép lượt
xe vào-ra.

`AutomaticScanService` chỉ giữ tạm:

- `session_id`.
- Thời điểm bắt đầu.
- `FrameSelector`.
- Crop tốt nhất.
- Hướng `IN/OUT` đã chọn.

Dữ liệu bị xóa khi phiên thành công, cần quét lại, hết thời gian, bị hủy hoặc
gặp lỗi. Nút **Quét lại** chỉ tạo phiên mới, không tạo hồ sơ.

## 17. Nên sửa file nào khi mở rộng?

| Nhu cầu | File chính cần xem |
|---|---|
| Thay model hoặc thay cách lọc YOLO | `plate_detector.py`, `config.py` |
| Điều chỉnh tiêu chí chọn frame | `frame_selector.py`, `.env` |
| Thay đổi vòng đời phiên web | `automatic_scan_service.py`, `flask_app.py` |
| Thêm loại biển/Regex | `plate_formatter.py` |
| Cải thiện ảnh nghiêng hoặc ánh sáng | `image_processor.py` |
| Thay Google Vision bằng OCR khác | Tạo adapter mới và đổi dependency ở entry point |
| Đổi API | `flask_app.py`, sau đó đồng bộ `static/js/app.js` |
| Đổi bố cục web | `index.html`, `style.css` |
| Đổi hành vi camera web | `app.js` |
| Ghép lượt vào-ra và đối chiếu ảnh | Thêm `vehicle_visits` và service nghiệp vụ; giữ detector/OCR độc lập |

Sau mỗi thay đổi, nên kiểm tra lỗi cú pháp:

```powershell
python -m compileall app flask_app.py main.py
```

Sau đó chạy lại chương trình và kiểm tra thủ công luồng camera, YOLO,
FrameSelector, OCR, định dạng biển số, lựa chọn `IN/OUT` và dữ liệu được lưu
trong MongoDB.
