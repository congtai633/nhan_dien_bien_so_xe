# Hệ thống nhận diện biển số xe Việt Nam

Prototype sử dụng **YOLOv8** để phát hiện biển số, **OpenCV** để crop và xử lý
ảnh, **FrameSelector** để chọn khung hình rõ và ổn định, sau đó gọi
**Google Cloud Vision OCR** đúng một lần để đọc ký tự.

Phiên bản hiện tại tập trung vào bài toán nhận diện:

- Hỗ trợ hai nhãn của model: `BSD` (biển dài) và `BSV` (biển vuông hai dòng).
- Web tự động thu thập nhiều frame từ camera, không chọn frame đầu tiên vừa đạt
  confidence.
- Giao diện web chỉ có camera trực tiếp; đã bỏ phần chọn ảnh và nút nhận diện
  ảnh thủ công.
- Camera nằm bên trái, ảnh crop và kết quả nằm bên phải trên màn hình desktop.
- Người giám sát chọn `XE VÀO` hoặc `XE RA`; lựa chọn được khóa trong suốt một
  phiên quét và sự kiện thành công được lưu vào MongoDB.
- Chưa lưu ảnh vào/ra, chưa ghép thành một lượt xe hoàn chỉnh và chưa điều khiển
  barrier.

## 1. Vì sao phải chọn nhiều frame?

YOLO có thể phát hiện đúng vị trí biển số với confidence cao trong lúc xe vẫn
đang di chuyển. Tuy nhiên, ảnh crop tại thời điểm đó có thể bị nhòe nên OCR đọc
sai ký tự.

Luồng web hiện tại giải quyết vấn đề này như sau:

```text
Người dùng mở camera
→ chọn chế độ XE VÀO hoặc XE RA
→ backend khóa hướng vào session_id
→ trình duyệt gửi tuần tự nhiều frame về Flask
→ YOLO phát hiện biển số và crop ảnh
→ FrameSelector kiểm tra cùng mục tiêu, độ ổn định và độ nét
→ chọn crop tốt nhất
→ tiền xử lý ảnh BSV/BSD
→ Google Vision OCR đúng một lần
→ chuẩn hóa chuỗi và hiển thị kết quả
→ lưu sự kiện IN/OUT hợp lệ vào MongoDB
```

Nếu hết thời gian:

```text
Chưa từng thấy biển
→ PLATE_NOT_FOUND

Đã thấy biển nhưng ảnh chưa đủ nét/ổn định
→ RETRY_REQUIRED
→ hiển thị crop tốt nhất
→ người dùng điều chỉnh xe hoặc camera rồi quét lại
```

Nếu Google Vision không đọc được chữ hoặc chuỗi không đúng định dạng đang hỗ
trợ, hệ thống cũng trả `RETRY_REQUIRED`. Lỗi credentials, network hoặc Google
Vision API là `PROCESSING_ERROR`, không bị xem nhầm là biển mờ.

## 2. Hai cách chạy

### Giao diện web

Chạy:

```powershell
python flask_app.py
```

Mở `http://127.0.0.1:5000`, cấp quyền camera và bấm **Mở camera**. Frontend tự
gửi các frame tuần tự; không cần bấm chụp hoặc chọn ảnh.

Camera web được mở bởi trình duyệt qua `getUserMedia()`. Vì vậy,
`CAMERA_SOURCE`, `CAMERA_WIDTH` và `CAMERA_HEIGHT` trong `.env` không điều khiển
camera của giao diện web.

### Giao diện OpenCV trên máy tính

Chạy:

```powershell
python main.py
```

Các phím điều khiển:

- `C` — bắt đầu một lượt kiểm tra.
- `R` — xóa kết quả và trở về trạng thái chờ.
- `Q` — đóng chương trình.

Ở luồng này, Python mở camera bằng `CameraService`, nên các biến
`CAMERA_SOURCE`, `CAMERA_WIDTH` và `CAMERA_HEIGHT` có hiệu lực.

## 3. Công nghệ sử dụng

| Công nghệ | Vai trò |
|---|---|
| Python | Ngôn ngữ chính của backend và chương trình OpenCV |
| Ultralytics YOLOv8 | Phát hiện vị trí và loại biển `BSD/BSV` |
| OpenCV | Đọc/crop ảnh, đo độ nét, resize, CLAHE và mã hóa JPEG |
| Google Cloud Vision | OCR ký tự trên ảnh biển số đã chọn |
| Flask | Cung cấp giao diện web và REST API |
| MongoDB và PyMongo | Lưu lịch sử sự kiện nhận diện `IN/OUT` |
| JavaScript | Mở camera trình duyệt, lấy frame và điều khiển phiên quét |
| HTML/CSS | Giao diện camera trái, kết quả phải và responsive |

## 4. Cấu trúc project

```text
nhan_dien_bien_so_xe-main/
├── app/
│   ├── config.py
│   ├── controller.py
│   ├── domain.py
│   ├── interfaces.py
│   ├── ui.py
│   ├── repositories/
│   │   └── mongo_vehicle_access_repository.py
│   └── services/
│       ├── automatic_scan_service.py
│       ├── camera_service.py
│       ├── frame_selector.py
│       ├── google_vision_ocr.py
│       ├── image_processor.py
│       ├── plate_detector.py
│       ├── plate_formatter.py
│       ├── recognition_service.py
│       └── vehicle_access_service.py
├── models/
│   └── best.pt
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   └── index.html
├── .env.example
├── flask_app.py
├── main.py
├── MODULES.md
├── README.md
└── requirements.txt
```

Đọc `MODULES.md` để xem trách nhiệm, input/output và quan hệ giữa từng file.

## 5. Cài đặt trên Windows

Yêu cầu:

- Python 3.10–3.12.
- Model `models/best.pt`.
- Webcam hoạt động.
- Google Cloud project đã bật Cloud Vision API.
- Service account có quyền sử dụng Vision API hoặc Application Default
  Credentials đã được cấu hình.
- MongoDB đang chạy và Flask truy cập được URI đã cấu hình.

Tạo môi trường:

```powershell
cd nhan_dien_bien_so_xe-main
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và sửa đường dẫn credentials:

```env
GOOGLE_APPLICATION_CREDENTIALS=C:/google-credentials/vision-service-account.json
```

Không đặt file JSON bí mật trong source, không commit lên GitHub và không gửi
cho người khác.

Nếu máy đã cấu hình Application Default Credentials bằng Google Cloud CLI, có
thể để trống `GOOGLE_APPLICATION_CREDENTIALS`.

## 6. Cấu hình `.env`

| Biến | Mặc định | Điều kiện | Tác dụng |
|---|---:|---:|---|
| `MODEL_PATH` | `models/best.pt` | File phải tồn tại | Đường dẫn weight YOLO |
| `GOOGLE_APPLICATION_CREDENTIALS` | Trống | File phải tồn tại nếu khai báo | Khóa service account Google Cloud |
| `CAMERA_SOURCE` | `0` | Chỉ số hoặc URL | Nguồn camera của `main.py` |
| `CAMERA_WIDTH` | `1280` | Số nguyên | Chiều rộng camera của `main.py` |
| `CAMERA_HEIGHT` | `720` | Số nguyên | Chiều cao camera của `main.py` |
| `DETECTION_PREVIEW_THRESHOLD` | `0.25` | `(0, DETECTION_THRESHOLD]` | Ngưỡng YOLO trả detection để hiển thị/xét tiếp |
| `DETECTION_THRESHOLD` | `0.80` | `(0, 1]` | Confidence tối thiểu để crop và đưa vào selector |
| `SCAN_TIMEOUT_SECONDS` | `15` | `> 0` | Thời gian tối đa của một lượt quét |
| `CROP_PADDING_RATIO` | `0.08` | `[0, 0.5]` | Phần viền chừa quanh bounding box |
| `SQUARE_PLATE_LABELS` | `BSV` | Danh sách cách nhau bằng dấu phẩy | Nhãn biển hai dòng cần ghép ngang |
| `STABLE_FRAME_COUNT` | `5` | Số nguyên `> 0` | Số detection cùng mục tiêu trước khi chọn ảnh |
| `CANDIDATE_WINDOW_SECONDS` | `1.5` | `> 0` | Cửa sổ theo dõi của luồng `main.py` |
| `MIN_SHARPNESS_SCORE` | `100` | `>= 0` | Ngưỡng độ nét Variance of Laplacian |
| `MAX_CENTER_SHIFT_RATIO` | `0.03` | `[0, 1]` | Độ lệch tâm tối đa so với đường chéo frame |
| `MONGODB_URI` | `mongodb://localhost:27017` | Không được trống | Địa chỉ kết nối MongoDB |
| `MONGODB_DATABASE` | `license_plate_system` | Không được trống | Tên database |
| `STATION_ID` | `GATE_01` | Không được trống | Mã trạm/cổng kiểm soát |
| `CAMERA_ID` | `WEBCAM_TEST_01` | Không được trống | Mã webcam đang dùng |
| `CAMERA_DIRECTION` | `IN` | `IN` hoặc `OUT` | Hướng mặc định khi web không gửi lựa chọn |
| `DUPLICATE_WINDOW_SECONDS` | `10` | Số giây | Chặn lưu lặp cùng biển, camera và hướng |

Lưu ý:

- `MIN_SHARPNESS_SCORE` không phải phần trăm. Giá trị phù hợp phụ thuộc camera,
  ánh sáng và kích thước crop; nên thử trong khoảng `50–300`.
- `FrameSelector` chọn ảnh có sharpness cao nhất. Confidence chỉ được dùng để
  phân thắng thua khi hai ảnh có cùng sharpness; code hiện không dùng công thức
  trọng số `confidence × 0.6 + sharpness × 0.4`.
- Ở web, `AutomaticScanService` dùng `SCAN_TIMEOUT_SECONDS` làm cửa sổ của
  selector để tránh reset chỉ vì mỗi frame phải chờ request mạng. Biến
  `CANDIDATE_WINDOW_SECONDS` đang áp dụng trực tiếp cho luồng `main.py`.

## 7. Cách xử lý BSV và BSD

### BSD — biển dài một dòng

Ảnh crop giữ nguyên bố cục, được phóng lớn nếu chiều cao nhỏ hơn 120 pixel và
tăng tương phản cục bộ bằng CLAHE trước khi OCR.

### BSV — biển vuông hai dòng

```text
Crop BSV
→ chia nửa trên và nửa dưới
→ resize hai phần về cùng chiều cao
→ chèn khoảng trắng
→ ghép ngang
→ phóng lớn và tăng tương phản
→ OCR
```

Ảnh hiển thị trên giao diện là crop gốc. Ảnh gửi Google Vision là bản đã qua
`prepare_for_ocr()`.

Ví dụ OCR trả:

```text
50L
347.98
```

Formatter làm sạch và hiển thị:

```text
50L-347.98
```

## 8. REST API

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/` | Trả giao diện web |
| `GET` | `/api/v1/health` | Kiểm tra Flask đang hoạt động |
| `POST` | `/api/v1/scan` | Nhận diện một ảnh tĩnh từ form-data `image` |
| `POST` | `/api/v1/auto-scan/start` | Nhận JSON `access_mode`, tạo phiên và trả `session_id` |
| `POST` | `/api/v1/auto-scan/frame` | Nhận `session_id` và một frame camera |
| `POST` | `/api/v1/auto-scan/cancel` | Hủy dữ liệu tạm của phiên |

Giao diện hiện tại không dùng `/api/v1/scan`; endpoint này được giữ lại để nhận
diện ảnh tĩnh trực tiếp bằng Postman hoặc ứng dụng khác, nhưng `app.js` không gọi
endpoint này. Ba endpoint `/auto-scan/*` mới là luồng được
`static/js/app.js` sử dụng.

Các trạng thái chính của camera web:

| Status | HTTP thường gặp | Ý nghĩa |
|---|---:|---|
| `SEARCHING` | `202` | Chưa có detection đạt ngưỡng |
| `COLLECTING` | `202` | Đã thấy biển, đang gom frame và đánh giá độ nét |
| `SUCCESS` | `200` | OCR hợp lệ |
| `RETRY_REQUIRED` | `200` | Ảnh mờ, OCR rỗng hoặc sai định dạng |
| `PLATE_NOT_FOUND` | `422` | Hết thời gian nhưng chưa thấy biển |
| `SESSION_ENDED` | `409` | `session_id` không còn tồn tại |
| `PROCESSING_ERROR` | `500` | Lỗi model, xử lý ảnh, credentials hoặc OCR API |

Các `reason` khi cần quét lại:

- `LOW_IMAGE_QUALITY`: đã thấy biển nhưng chưa có crop đủ nét/ổn định.
- `OCR_NO_TEXT`: Google Vision không đọc được ký tự.
- `OCR_INVALID_FORMAT`: OCR có chữ nhưng formatter chưa nhận dạng được mẫu.

## 9. Hoạt động của frontend

`static/js/app.js` thực hiện:

1. Mở camera bằng `navigator.mediaDevices.getUserMedia()`.
2. Đọc lựa chọn `XE VÀO/XE RA` và gọi `/api/v1/auto-scan/start` với JSON
   `{"access_mode": "IN"}` hoặc `{"access_mode": "OUT"}`.
3. Khóa hai radio trong lúc phiên đang quét.
4. Chụp frame JPEG chất lượng `0.92`.
5. Gửi frame tiếp theo sau khi request hiện tại hoàn tất, với độ trễ tối thiểu
   `250 ms`, để tránh các lượt YOLO chạy chồng lên nhau.
6. Cập nhật trạng thái `SEARCHING` hoặc tiến độ `COLLECTING`.
7. Dừng vòng quét khi nhận `SUCCESS`, `RETRY_REQUIRED`,
   `PLATE_NOT_FOUND` hoặc lỗi.
8. Gọi `/api/v1/auto-scan/cancel` khi tắt camera hoặc bắt đầu lượt quét mới.

Giao diện responsive:

- Desktop: camera bên trái, kết quả bên phải.
- Màn hình nhỏ: hai khu vực tự chuyển thành một cột.

## 10. Kiểm tra hệ thống thủ công

Source hiện tại không sử dụng thư mục unit test. Sau khi thay đổi code, cần kiểm
tra thủ công các luồng chính sau:

1. Chạy chương trình web bằng:

   ```powershell
   python flask_app.py
   ```

2. Mở camera và xác nhận trình duyệt gửi frame bình thường.
3. Chọn `XE VÀO`, nhận diện thành công và kiểm tra MongoDB lưu
   `direction: "IN"`.
4. Chọn `XE RA`, nhận diện thành công và kiểm tra MongoDB lưu
   `direction: "OUT"`.
5. Quét lại cùng biển số, camera và hướng trong thời gian chống trùng để xác
   nhận hệ thống không tạo bản ghi mới.
6. Kiểm tra trường hợp không tìm thấy biển, ảnh mờ, OCR thất bại và quét lại.
7. Kiểm tra radio `XE VÀO/XE RA` bị khóa trong lúc phiên đang quét.

Có thể kiểm tra lỗi cú pháp Python trước khi chạy bằng:

```powershell
python -m compileall app flask_app.py main.py
```

## 11. Giới hạn hiện tại

- Mỗi frame chỉ chọn detection có confidence cao nhất đạt ngưỡng.
- `FrameSelector` so sánh nhãn và độ lệch tâm với detection neo; chưa có
  ByteTrack, tracker ID hoặc IoU để theo dõi nhiều xe.
- Luồng desktop reset selector khi một frame không có detection đạt ngưỡng;
  luồng web giữ trạng thái phiên cho đến frame phù hợp tiếp theo hoặc hết thời
  gian.
- Formatter mới hỗ trợ các mẫu biển thông dụng; biển ngoại giao, quân đội hoặc
  định dạng đặc biệt có thể trả `OCR_INVALID_FORMAT`.
- Chưa chỉnh phối cảnh khi camera đặt quá nghiêng.
- Chưa khóa phiên bản package trong `requirements.txt`.
- Flask đang chạy development server tại `127.0.0.1:5000`, chưa phải cấu hình
  triển khai production.
- MongoDB hiện mới lưu từng sự kiện `IN/OUT` trong `vehicle_access_events`.
  Chưa có `vehicle_visits` để ghép lượt vào-ra, chưa lưu hai ảnh đối chiếu,
  chưa có bước người giám sát xác nhận cho ra, tài khoản hoặc barrier.

## 12. Lỗi thường gặp

### Không tìm thấy model

Kiểm tra `MODEL_PATH` và file `models/best.pt`.

### Trình duyệt không mở camera

Kiểm tra quyền camera của trình duyệt, đóng ứng dụng khác đang chiếm webcam và
mở đúng `http://127.0.0.1:5000`.

### Google Vision báo lỗi credentials

Kiểm tra đường dẫn `GOOGLE_APPLICATION_CREDENTIALS`, quyền service account và
Cloud Vision API đã được bật.

### Bộ đếm ổn định thường quay lại từ đầu

Giữ xe đứng yên, đưa biển số vào vùng đủ sáng, giảm
`STABLE_FRAME_COUNT`, tăng `MAX_CENTER_SHIFT_RATIO` hoặc tăng
`CANDIDATE_WINDOW_SECONDS` cho luồng desktop. Chỉ điều chỉnh từng biến sau khi
quan sát kết quả thực tế.
