# Ghi chú kiến trúc và trách nhiệm module

## Nguyên tắc tách module

Controller chỉ điều phối luồng. Mỗi module còn lại có một nhóm trách nhiệm, nhờ
đó có thể đổi camera, model hoặc dịch vụ OCR mà không viết lại toàn bộ chương
trình.

| File | Trách nhiệm | Khi nào cần sửa? |
|---|---|---|
| `main.py` | Khởi tạo và kết nối các object | Khi thêm hoặc thay một service |
| `app/config.py` | Đọc `.env`, kiểm tra đường dẫn/ngưỡng | Khi thêm cấu hình |
| `app/domain.py` | Dataclass và trạng thái dùng chung | Khi dữ liệu nghiệp vụ thay đổi |
| `app/interfaces.py` | Hợp đồng chung cho OCR | Khi thêm OCR provider mới |
| `app/controller.py` | Luồng C/R/Q → scan → crop → OCR → hiển thị | Khi quy trình nghiệp vụ đổi |
| `app/services/camera_service.py` | Mở, đọc và đóng camera | Khi đổi webcam sang RTSP |
| `app/services/plate_detector.py` | Chuyển output YOLO thành detection chuẩn | Khi đổi model phát hiện |
| `app/services/image_processor.py` | Padding, crop, ghép BSV, tăng tương phản | Khi cần deskew/perspective |
| `app/services/google_vision_ocr.py` | Gọi Cloud Vision `TEXT_DETECTION` | Khi đổi API hoặc retry policy |
| `app/services/plate_formatter.py` | Làm sạch và định dạng chuỗi Việt Nam | Khi thêm loại biển đặc biệt |
| `app/ui.py` | Vẽ giao diện, hiện kết quả và đọc phím | Khi làm GUI riêng |

## State machine

```text
IDLE
  └─ nhấn C → SCANNING
       ├─ hết thời gian → ERROR
       └─ confidence >= 0.80 → PROCESSING
              ├─ OCR xong → RESULT
              └─ OCR lỗi → ERROR

SCANNING, RESULT hoặc ERROR ─ nhấn R → IDLE
Mọi trạng thái ─ nhấn Q → đóng chương trình
```

Trong `PROCESSING`, controller không chạy YOLO và tạm khóa `R`. Đây là điểm
quan trọng để một xe đứng trước camera không tạo nhiều request Google Vision.

`R` là reload logic: xóa ảnh crop, chuỗi OCR và trạng thái của lần kiểm tra cũ,
sau đó trở về `IDLE`. Chương trình không tải lại model YOLO và không mở lại
camera, nên phản hồi nhanh hơn việc tắt rồi chạy lại Python.

## Luồng dành cho biển vuông BSV

1. YOLO trả nhãn `BSV` và bounding box.
2. `PlateImageProcessor` crop ảnh gốc để hiển thị.
3. Một bản sao được cắt thành nửa trên và nửa dưới rồi ghép ngang.
4. Chỉ bản ghép ngang được gửi lên Google Vision để OCR dễ hơn.
5. `VietnamesePlateFormatter` bỏ xuống dòng, khoảng trắng và dấu cũ.
6. Chuỗi được thêm lại dấu theo định dạng biển Việt Nam.

Ví dụ `50L\n347.98` trở thành `50L34798`, sau đó hiển thị thành
`50L-347.98`.

## Vì sao đã bỏ database và lưu ảnh?

Yêu cầu hiện tại chỉ cần xem ảnh và chuỗi OCR ngay trên màn hình. Vì vậy:

- `app/repositories/sqlite_repository.py` đã được gỡ.
- `app/services/image_storage.py` đã được gỡ.
- Controller không tạo ID, không ghi file và không tạo SQLite.

Việc bỏ hai module này làm luồng thử nghiệm ngắn hơn và tránh tạo dữ liệu không
cần thiết. Khi cần lưu lịch sử trong giai đoạn sau, có thể thêm repository và
storage trở lại mà không phải sửa model YOLO hay Google OCR.

## Cách thêm OCR khác để dự phòng

Tạo class mới có cùng hàm:

```python
class MyOCR:
    def recognize(self, image) -> str:
        return "chuỗi OCR thô"
```

Sau đó đổi object `GoogleVisionOCR(...)` trong `main.py`. Controller không cần
biết OCR phía sau là Google, PaddleOCR hay một API nội bộ.
