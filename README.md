# Hệ thống nhận diện biển số Việt Nam

Project chuyển các file test YOLO và Google Vision thành một hệ thống hướng đối
tượng, dễ kiểm soát và bảo trì. Phiên bản hiện tại chỉ hiển thị kết quả trực
tiếp, không lưu ảnh và không sử dụng database.

```text
Camera chờ -> nhấn C -> YOLO quét tại máy -> confidence >= 0.80
-> crop biển số -> Google Vision OCR đúng một lần
-> chuẩn hóa -> hiện ảnh crop và chuỗi biển số
```

Ví dụ Google Vision trả về hai dòng:

```text
50L
347.98
```

Hệ thống làm sạch và ghép thành một dòng:

```text
50L-347.98
```

## Cách chạy trên Windows

Yêu cầu Python 3.10–3.12 và webcam hoạt động.

```powershell
cd vietnam_license_plate_system
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
này vào project, GitHub hoặc gửi cho người khác. Sau đó chạy:

```powershell
python main.py
```

## Phím điều khiển

- `C` — **Check**: bắt đầu kiểm tra biển số.
- `R` — **Reload**: xóa ảnh/chuỗi hiện tại và trở về trạng thái chờ.
- `Q` — **Quit**: đóng chương trình.

Sau khi nhấn `R`, chương trình không tự quét. Nhấn `C` khi muốn kiểm tra xe tiếp
theo. `R` chỉ đặt lại trạng thái giao diện và phiên kiểm tra; camera và model vẫn
được giữ trong bộ nhớ để tải lại nhanh, không phải khởi động lại tiến trình
Python.

Khi OCR đang gửi request lên Google Vision, `R` tạm thời chưa có hiệu lực để
tránh tạo request OCR thứ hai. Chờ kết quả xuất hiện rồi nhấn `R`.

## Kết quả hiển thị

Hệ thống mở hai cửa sổ:

- Cửa sổ camera: hình trực tiếp, bounding box, confidence và trạng thái.
- Cửa sổ kết quả: ảnh biển số đã crop và chuỗi OCR đã chuẩn hóa.

Khi nhấn `R` hoặc tắt chương trình, kết quả trên màn hình được bỏ đi.

## Cấu hình thường chỉnh

| Biến trong `.env` | Mặc định | Tác dụng |
|---|---:|---|
| `CAMERA_SOURCE` | `0` | Webcam; đổi thành `1` hoặc URL RTSP nếu cần |
| `DETECTION_THRESHOLD` | `0.80` | Chỉ crop khi confidence đạt ngưỡng này |
| `SCAN_TIMEOUT_SECONDS` | `15` | Dừng kiểm tra nếu không thấy biển đạt ngưỡng |
| `CROP_PADDING_RATIO` | `0.08` | Chừa 8% viền quanh box để không mất ký tự |
| `SQUARE_PLATE_LABELS` | `BSV` | Các nhãn cần cắt hai dòng rồi ghép ngang cho OCR |

`DETECTION_PREVIEW_THRESHOLD=0.25` chỉ giúp thấy các box chưa đủ tốt trên màn
hình; nó không làm hệ thống gửi ảnh có confidence dưới `0.80` lên Google.

## Chạy test không cần camera

```powershell
python -m unittest discover -s tests -v
```

## Giới hạn hiện tại

- Mỗi lần nhấn `C`, hệ thống lấy detection có confidence cao nhất đạt ngưỡng.
- Chưa có danh sách xe được phép/từ chối và chưa điều khiển barrier.
- Chuẩn hóa hỗ trợ các dạng biển thông dụng. Biển ngoại giao, quân đội hoặc định
  dạng đặc biệt có thể được đánh dấu là chưa nhận ra định dạng.
- Nếu góc camera nghiêng nhiều, nên bổ sung chỉnh phối cảnh trước OCR.

Đọc `MODULES.md` để biết trách nhiệm của từng file và vị trí cần sửa khi mở rộng.
