# Hệ thống nhận diện biển số Việt Nam

Hệ thống sử dụng YOLO để phát hiện biển số từ camera, theo dõi biển số qua nhiều
frame để chọn ảnh rõ và ổn định, sau đó gửi đúng một ảnh lên Google Cloud Vision
để OCR. Kết quả được chuẩn hóa theo định dạng biển số Việt Nam và hiển thị trực
tiếp trên màn hình.

Phiên bản hiện tại không lưu ảnh, không sử dụng database và chưa điều khiển
barrier.

## Luồng xử lý

```text
Camera chờ
→ nhấn C
→ YOLO phát hiện BSV/BSD tại máy
→ lọc detection có confidence >= DETECTION_THRESHOLD
→ crop biển số
→ FrameSelector kiểm tra vị trí qua nhiều frame và đo độ nét
→ chọn ảnh đạt yêu cầu có sharpness cao nhất
→ xử lý ảnh BSV/BSD
→ Google Vision OCR đúng một lần
→ chuẩn hóa chuỗi
→ hiển thị ảnh crop và biển số
```

Ví dụ Google Vision trả về:

```text
50L
347.98
```

Hệ thống làm sạch và hiển thị:

```text
50L-347.98
```

## Cách chạy trên Windows

Yêu cầu Python 3.10–3.12 và webcam hoạt động.

```powershell
cd nhan_dien_bien_so_xe-main
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và sửa đường dẫn khóa Google Cloud:

```env
GOOGLE_APPLICATION_CREDENTIALS=C:/duong-dan/toi/service-account.json
```

File JSON là khóa service account có quyền gọi Cloud Vision API. Không đưa khóa
này vào project, GitHub hoặc gửi cho người khác.

Chạy chương trình:

```powershell
python main.py
```

## Phím điều khiển

- `C` — **Check**: bắt đầu một lượt kiểm tra biển số.
- `R` — **Reload**: xóa kết quả và trở về trạng thái chờ.
- `Q` — **Quit**: đóng chương trình.

Sau khi nhấn `R`, camera và model vẫn được giữ trong bộ nhớ nhưng chương trình
không tự quét. Nhấn `C` để kiểm tra xe tiếp theo.

Khi request OCR đang được xử lý, `R` tạm thời không có hiệu lực nhằm tránh tạo
request thứ hai. Chờ kết quả xuất hiện rồi nhấn `R`.

## Kết quả hiển thị

Hệ thống mở hai cửa sổ:

- Cửa sổ camera: hình trực tiếp, bounding box, confidence, trạng thái và tiến độ
  ổn định, ví dụ `3/5`.
- Cửa sổ kết quả: ảnh biển số được chọn và chuỗi OCR đã chuẩn hóa.

Khi nhấn `R` hoặc thoát chương trình, kết quả trên màn hình được xóa.

## Cấu hình trong `.env`

| Biến | Mặc định | Khoảng hợp lệ trong code | Tác dụng |
|---|---:|---:|---|
| `CAMERA_SOURCE` | `0` | Chỉ số camera hoặc URL | Chọn webcam, camera khác hoặc RTSP |
| `DETECTION_PREVIEW_THRESHOLD` | `0.25` | `(0, DETECTION_THRESHOLD]` | Ngưỡng YOLO trả box để hiển thị |
| `DETECTION_THRESHOLD` | `0.80` | `(0, 1]` | Ngưỡng confidence tối thiểu để xét chọn ảnh |
| `SCAN_TIMEOUT_SECONDS` | `15` | `> 0` | Thời gian tối đa của một lượt nhấn `C` |
| `CROP_PADDING_RATIO` | `0.08` | `[0, 0.5]` | Chừa viền quanh bounding box |
| `SQUARE_PLATE_LABELS` | `BSV` | Danh sách nhãn | Nhãn biển hai dòng cần ghép ngang |
| `STABLE_FRAME_COUNT` | `5` | Số nguyên `> 0` | Số frame cùng mục tiêu cần theo dõi |
| `CANDIDATE_WINDOW_SECONDS` | `1.5` | `> 0` | Thời gian tối đa để gom đủ frame ổn định |
| `MIN_SHARPNESS_SCORE` | `100` | `>= 0` | Điểm nét Laplacian tối thiểu để lưu ứng viên |
| `MAX_CENTER_SHIFT_RATIO` | `0.03` | `[0, 1]` | Độ lệch tâm tối đa so với frame bắt đầu |

Các giá trị nên dùng thử trong thực tế:

| Biến | Khoảng nên thử |
|---|---:|
| `DETECTION_THRESHOLD` | `0.60–0.95` |
| `STABLE_FRAME_COUNT` | `3–10` frame |
| `CANDIDATE_WINDOW_SECONDS` | `0.5–3.0` giây |
| `MIN_SHARPNESS_SCORE` | `50–300` |
| `MAX_CENTER_SHIFT_RATIO` | `0.01–0.05` |

`MIN_SHARPNESS_SCORE` không phải phần trăm. Giá trị này phụ thuộc camera, ánh
sáng và kích thước ảnh crop, nên cần quan sát log thực tế trước khi điều chỉnh.

Nếu bộ đếm thường quay lại `1/5`, mục tiêu có thể đang di chuyển quá giới hạn,
YOLO bị mất detection hoặc `CANDIDATE_WINDOW_SECONDS` quá ngắn so với tốc độ xử
lý của máy.

## Chạy test

Test không bắt buộc để mở camera và chạy `main.py`, nhưng nên được giữ để kiểm
tra nhanh sau mỗi lần sửa controller, formatter hoặc service:

```powershell
python -m unittest discover -s tests -v
```

Các unit test hiện có không cần webcam thật và không gọi Google Vision thật.

## Giới hạn hiện tại

- Mỗi frame chỉ theo dõi detection có confidence cao nhất đạt ngưỡng.
- `FrameSelector` nhận diện cùng mục tiêu bằng nhãn và độ lệch tâm so với frame
  bắt đầu; chưa sử dụng tracker ID hoặc IoU.
- Nếu một frame không có detection đạt ngưỡng, quá trình gom frame ổn định được
  đặt lại.
- Chưa có danh sách xe được phép/từ chối, database và điều khiển barrier.
- Formatter mới hỗ trợ một số dạng biển thông dụng; biển ngoại giao, quân đội
  hoặc định dạng đặc biệt có thể chưa được nhận ra.
- Nếu camera nghiêng nhiều, nên bổ sung chỉnh phối cảnh trước OCR.

Đọc `MODULES.md` để hiểu trách nhiệm của từng file và vị trí cần sửa khi mở rộng
hệ thống.
