const emptyResult = document.getElementById("emptyResult");
const resultContent = document.getElementById("resultContent");
const plateText = document.getElementById("plateText");
const plateType = document.getElementById("plateType");
const confidence = document.getElementById("confidence");
const entryTime = document.getElementById("entryTime");
const exitTime = document.getElementById("exitTime");
const cropImage = document.getElementById("cropImage");
const statusMessage = document.getElementById("statusMessage");
const resultStatusBadge = document.getElementById("result-status-badge");

const camera = document.getElementById("camera");
const cameraPlaceholder = document.getElementById("camera-placeholder");
const cameraStatusBadge = document.getElementById("camera-status-badge");
const scanIndicator = document.getElementById("scan-indicator");
const openCameraButton = document.getElementById("open-camera");
const restartScanButton = document.getElementById("restart-scan");
const closeCameraButton = document.getElementById("close-camera");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraOverlay = document.getElementById("camera-overlay");
const message = document.getElementById("message");
const accessModeInputs = document.querySelectorAll(
    'input[name="access_mode"]'
);

const AUTO_SCAN_DELAY_MS = 250;

let cameraStream = null;
let autoScanSessionId = null;
let autoScanTimer = null;
let autoScanBusy = false;
let autoScanStopped = true;
let lastDetectionData = null;

openCameraButton.addEventListener("click", openCamera);
restartScanButton.addEventListener("click", restartAutomaticScan);
closeCameraButton.addEventListener("click", stopCamera);
window.addEventListener("beforeunload", stopCamera);
window.addEventListener("resize", redrawBoundingBox);

async function openCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
        message.textContent =
            "Trình duyệt này không hỗ trợ mở camera.";
        setBadge(cameraStatusBadge, "Không hỗ trợ", "error");
        showStatus(
            "Hãy sử dụng trình duyệt có hỗ trợ camera.",
            "error"
        );
        return;
    }

    openCameraButton.disabled = true;
    message.textContent = "Đang yêu cầu quyền sử dụng camera...";
    setBadge(cameraStatusBadge, "Đang kết nối", "active");

    try {
        cameraStream =
            await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: {
                        ideal: "environment",
                    },
                },
                audio: false,
            });

        camera.srcObject = cameraStream;
        await camera.play();

        camera.hidden = false;
        cameraPlaceholder.hidden = true;
        resizeCameraOverlay();
        closeCameraButton.disabled = false;
        restartScanButton.hidden = true;

        setBadge(cameraStatusBadge, "Đang mở", "success");
        resetResult();

        try {
            await startAutomaticScan();
        } catch (error) {
            finishAutomaticScan();
            restartScanButton.hidden = false;
            message.textContent =
                "Camera đã mở nhưng chưa thể bắt đầu quét.";
            setBadge(resultStatusBadge, "Lỗi quét", "error");
            showStatus(error.message, "error");
        }
    } catch (error) {
        releaseCameraStream();
        camera.srcObject = null;
        camera.hidden = true;
        cameraPlaceholder.hidden = false;

        openCameraButton.disabled = false;
        closeCameraButton.disabled = true;
        message.textContent =
            "Không thể mở camera. Hãy kiểm tra quyền camera.";

        setBadge(cameraStatusBadge, "Kết nối lỗi", "error");
        showStatus(
            "Trình duyệt chưa được cấp quyền sử dụng camera.",
            "error"
        );
    }
}

async function restartAutomaticScan() {
    if (!cameraStream) {
        message.textContent = "Camera chưa được mở.";
        setBadge(cameraStatusBadge, "Chưa kết nối", "idle");
        return;
    }

    restartScanButton.hidden = true;
    resetResult();

    try {
        await startAutomaticScan();
    } catch (error) {
        finishAutomaticScan();
        restartScanButton.hidden = false;
        message.textContent =
            "Không thể bắt đầu lượt quét mới.";
        setBadge(resultStatusBadge, "Lỗi quét", "error");
        showStatus(error.message, "error");
    }
}

async function startAutomaticScan() {
    await stopAutomaticScan(true);

    setBadge(resultStatusBadge, "Đang khởi tạo", "active");
    setScanning(true);

    const response = await fetch("/api/v1/auto-scan/start", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            access_mode: getSelectedAccessMode(),
        }),
    });
    const data = await readJsonResponse(response);

    if (!response.ok || !data.success) {
        throw new Error(
            data.message || "Không thể bắt đầu phiên quét."
        );
    }

    autoScanSessionId = data.session_id;
    autoScanStopped = false;

    message.textContent =
        "Camera đang tự động tìm biển số...";
    setBadge(resultStatusBadge, "Đang quét", "active");
    showStatus(
        "Giữ phương tiện trong khung hình để hệ thống chọn ảnh rõ nhất.",
        ""
    );

    scheduleNextAutoFrame(0);
}

async function scanNextCameraFrame() {
    if (
        autoScanStopped ||
        autoScanBusy ||
        !autoScanSessionId ||
        !cameraStream
    ) {
        return;
    }

    autoScanBusy = true;

    try {
        const frameFile = await captureCurrentCameraFrame(
            "auto-camera-frame.jpg"
        );
        const formData = new FormData();

        formData.append("session_id", autoScanSessionId);
        formData.append("image", frameFile, frameFile.name);

        const response = await fetch("/api/v1/auto-scan/frame", {
            method: "POST",
            body: formData,
        });
        const data = await readJsonResponse(response);

        if (
            response.status === 202 &&
            ["SEARCHING", "COLLECTING"].includes(data.status)
        ) {
            updateBoundingBox(data);
            updateScanningProgress(data);
            scheduleNextAutoFrame();
            return;
        }

        if (
            response.status === 422 &&
            data.status === "PLATE_NOT_FOUND"
        ) {
            finishAutomaticScan();
            clearBoundingBox();
            restartScanButton.hidden = false;

            message.textContent =
                "Chưa thấy biển số. Điều chỉnh vị trí xe rồi quét lại.";
            setBadge(resultStatusBadge, "Chưa tìm thấy", "warning");
            showStatus(
                data.message || "Không tìm thấy biển số.",
                "error"
            );
            return;
        }

        if (!response.ok || !data.success) {
            throw new Error(
                data.message || "Quét camera thất bại."
            );
        }

        finishAutomaticScan();
        clearBoundingBox();
        renderRecognitionResult(data);
        restartScanButton.hidden = false;

        if (data.status === "SUCCESS") {
            renderAccessResult(data);
            return;
        }

        if (data.status === "RETRY_REQUIRED") {
            message.textContent =
                "Ảnh chưa đủ rõ. Điều chỉnh xe hoặc camera rồi quét lại.";
            setBadge(resultStatusBadge, "Cần quét lại", "warning");
            showStatus(
                data.message || "Chưa thể đọc chính xác biển số.",
                "error"
            );
        }
    } catch (error) {
        finishAutomaticScan();
        restartScanButton.hidden = false;

        message.textContent =
            "Quá trình tự động nhận diện đã dừng.";
        setBadge(resultStatusBadge, "Có lỗi", "error");
        showStatus(error.message, "error");
    } finally {
        autoScanBusy = false;
    }
}

function updateScanningProgress(data) {
    if (data.status === "SEARCHING") {
        message.textContent = "Đang tìm biển số trong khung hình...";
        setBadge(resultStatusBadge, "Đang tìm", "active");
        return;
    }

    message.textContent =
        `Đang kiểm tra độ ổn định ${data.stable_count}/` +
        `${data.required_stable_count} khung hình...`;
    setBadge(resultStatusBadge, "Đang chọn ảnh", "active");
}

function scheduleNextAutoFrame(delay = AUTO_SCAN_DELAY_MS) {
    if (autoScanStopped) {
        return;
    }

    window.clearTimeout(autoScanTimer);
    autoScanTimer = window.setTimeout(
        scanNextCameraFrame,
        delay
    );
}

function finishAutomaticScan() {
    autoScanStopped = true;
    autoScanSessionId = null;
    setScanning(false);

    if (autoScanTimer !== null) {
        window.clearTimeout(autoScanTimer);
        autoScanTimer = null;
    }
}

async function stopAutomaticScan(cancelServer) {
    const sessionId = autoScanSessionId;
    finishAutomaticScan();

    if (cancelServer && sessionId) {
        try {
            await fetch("/api/v1/auto-scan/cancel", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    session_id: sessionId,
                }),
            });
        } catch (error) {
            // Camera vẫn phải tắt nếu request hủy phiên gặp lỗi.
        }
    }
}

function stopCamera() {
    void stopAutomaticScan(true);
    releaseCameraStream();
    clearBoundingBox();

    camera.srcObject = null;
    camera.hidden = true;
    cameraPlaceholder.hidden = false;

    openCameraButton.disabled = false;
    restartScanButton.hidden = true;
    closeCameraButton.disabled = true;

    message.textContent = "Camera đã tắt.";
    setBadge(cameraStatusBadge, "Chưa kết nối", "idle");
}

function releaseCameraStream() {
    if (cameraStream) {
        cameraStream.getTracks().forEach((track) => {
            track.stop();
        });
    }

    cameraStream = null;
}

function captureCurrentCameraFrame(fileName) {
    if (
        !cameraStream ||
        camera.videoWidth === 0 ||
        camera.videoHeight === 0
    ) {
        return Promise.reject(
            new Error("Camera chưa có khung hình.")
        );
    }

    cameraCanvas.width = camera.videoWidth;
    cameraCanvas.height = camera.videoHeight;

    const context = cameraCanvas.getContext("2d");

    if (!context) {
        return Promise.reject(
            new Error("Không thể đọc khung hình camera.")
        );
    }

    context.drawImage(
        camera,
        0,
        0,
        cameraCanvas.width,
        cameraCanvas.height
    );

    return new Promise((resolve, reject) => {
        cameraCanvas.toBlob(
            (blob) => {
                if (!blob) {
                    reject(
                        new Error(
                            "Không thể tạo ảnh từ camera."
                        )
                    );
                    return;
                }

                resolve(
                    new File(
                        [blob],
                        fileName,
                        { type: "image/jpeg" }
                    )
                );
            },
            "image/jpeg",
            0.92
        );
    });
}

function renderRecognitionResult(data) {
    if (!data.crop_image) {
        throw new Error("Flask chưa trả về ảnh crop.");
    }

    cropImage.src = data.crop_image.startsWith("data:image/")
        ? data.crop_image
        : `data:image/jpeg;base64,${data.crop_image}`;
    cropImage.hidden = false;

    plateText.textContent =
        data.plate || "Không xác định";
    plateType.textContent =
        data.plate_type || "--";

    const confidencePercent =
        Number(data.confidence || 0) * 100;

    confidence.textContent =
        `${confidencePercent.toFixed(2)}%`;

    entryTime.textContent = formatVisitTime(data.entry_time);
    exitTime.textContent = data.exit_time
        ? formatVisitTime(data.exit_time)
        : data.visit_status === "INSIDE"
            ? "Chưa ra"
            : "--";

    emptyResult.hidden = true;
    resultContent.hidden = false;
}

function renderAccessResult(data) {
    const status = data.storage_status;

    if (["ENTRY_RECORDED", "EXIT_RECORDED"].includes(status)) {
        message.textContent =
            status === "ENTRY_RECORDED"
                ? "Đã ghi nhận xe vào bãi."
                : "Đã ghi nhận xe ra khỏi bãi.";
        setBadge(resultStatusBadge, "Đã ghi nhận", "success");
        showStatus(data.message, "success");
        return;
    }

    if (status === "ALREADY_INSIDE") {
        message.textContent =
            "Xe đã vào trước đó và chưa có lượt ra.";
        setBadge(resultStatusBadge, "Xe đã ở trong bãi", "warning");
        showStatus(data.message, "warning");
        return;
    }

    if (status === "NOT_INSIDE") {
        message.textContent =
            "Không tìm thấy lượt vào để thực hiện xe ra.";
        setBadge(resultStatusBadge, "Không có lượt vào", "warning");
        showStatus(data.message, "warning");
        return;
    }

    if (status === "DUPLICATE") {
        message.textContent = "Lượt quét trùng nên không lưu thêm.";
        setBadge(resultStatusBadge, "Dữ liệu trùng", "warning");
        showStatus(data.message, "warning");
        return;
    }

    if (status === "ERROR") {
        message.textContent =
            "Nhận diện thành công nhưng lưu dữ liệu thất bại.";
        setBadge(resultStatusBadge, "Lỗi lưu dữ liệu", "error");
        showStatus(data.message, "error");
        return;
    }

    message.textContent =
        "Đã chọn và crop khung hình biển số rõ nhất.";
    setBadge(resultStatusBadge, "Thành công", "success");
    showStatus(data.message || "Nhận diện hoàn tất.", "success");
}

function resetResult() {
    clearBoundingBox();
    emptyResult.hidden = false;
    resultContent.hidden = true;

    cropImage.removeAttribute("src");
    cropImage.hidden = true;
    plateText.textContent = "--";
    plateType.textContent = "--";
    confidence.textContent = "--";
    entryTime.textContent = "--";
    exitTime.textContent = "--";

    setBadge(resultStatusBadge, "Đang chờ", "idle");
    showStatus("", "");
}

function formatVisitTime(value) {
    if (!value) {
        return "--";
    }

    const parsedTime = new Date(value);

    if (Number.isNaN(parsedTime.getTime())) {
        return "--";
    }

    const time = parsedTime.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    });
    const date = parsedTime.toLocaleDateString("vi-VN");

    return `${time} ${date}`;
}

function updateBoundingBox(data) {
    if (!data.bounding_box || !data.frame_size) {
        clearBoundingBox();
        return;
    }

    lastDetectionData = data;
    drawBoundingBox(data);
}

function redrawBoundingBox() {
    resizeCameraOverlay();

    if (lastDetectionData) {
        drawBoundingBox(lastDetectionData);
    }
}

function resizeCameraOverlay() {
    const width = camera.clientWidth;
    const height = camera.clientHeight;
    const pixelRatio = window.devicePixelRatio || 1;

    cameraOverlay.width = Math.max(
        Math.round(width * pixelRatio),
        1
    );
    cameraOverlay.height = Math.max(
        Math.round(height * pixelRatio),
        1
    );
}

function drawBoundingBox(data) {
    const context = cameraOverlay.getContext("2d");
    const sourceWidth = Number(data.frame_size.width);
    const sourceHeight = Number(data.frame_size.height);
    const displayWidth = camera.clientWidth;
    const displayHeight = camera.clientHeight;

    if (
        !context ||
        sourceWidth <= 0 ||
        sourceHeight <= 0 ||
        displayWidth <= 0 ||
        displayHeight <= 0
    ) {
        clearBoundingBox();
        return;
    }

    resizeCameraOverlay();

    const pixelRatio = window.devicePixelRatio || 1;
    context.setTransform(
        pixelRatio,
        0,
        0,
        pixelRatio,
        0,
        0
    );
    context.clearRect(0, 0, displayWidth, displayHeight);

    // Video dùng object-fit: cover, vì vậy cần tính cả phần ảnh bị cắt.
    const scale = Math.max(
        displayWidth / sourceWidth,
        displayHeight / sourceHeight
    );
    const offsetX = (displayWidth - sourceWidth * scale) / 2;
    const offsetY = (displayHeight - sourceHeight * scale) / 2;
    const box = data.bounding_box;
    const x = Number(box.x1) * scale + offsetX;
    const y = Number(box.y1) * scale + offsetY;
    const width = (Number(box.x2) - Number(box.x1)) * scale;
    const height = (Number(box.y2) - Number(box.y1)) * scale;

    if (width <= 0 || height <= 0) {
        clearBoundingBox();
        return;
    }

    const lineWidth = 3;
    const label =
        `${data.plate_type || "Biển số"} ` +
        `${(Number(data.confidence || 0) * 100).toFixed(1)}%`;

    context.lineWidth = lineWidth;
    context.strokeStyle = "#22c55e";
    context.shadowColor = "rgb(0 0 0 / 45%)";
    context.shadowBlur = 4;
    context.strokeRect(x, y, width, height);
    context.shadowBlur = 0;

    context.font =
        "700 13px Inter, ui-sans-serif, system-ui, sans-serif";
    const labelPaddingX = 8;
    const labelHeight = 26;
    const labelWidth =
        context.measureText(label).width + labelPaddingX * 2;
    const labelY = Math.max(y - labelHeight, 0);

    context.fillStyle = "#16a34a";
    context.fillRect(x, labelY, labelWidth, labelHeight);
    context.fillStyle = "#ffffff";
    context.textBaseline = "middle";
    context.fillText(
        label,
        x + labelPaddingX,
        labelY + labelHeight / 2
    );
}

function clearBoundingBox() {
    lastDetectionData = null;
    const context = cameraOverlay.getContext("2d");

    if (context) {
        context.clearRect(
            0,
            0,
            cameraOverlay.width,
            cameraOverlay.height
        );
    }
}

function setBadge(element, text, state) {
    element.textContent = text;
    element.className =
        `status-badge status-badge--${state}`;
}

function setScanning(isScanning) {
    scanIndicator.hidden = !isScanning;

    accessModeInputs.forEach((input) => {
        input.disabled = isScanning;
    });
}

function getSelectedAccessMode() {
    const selected = document.querySelector(
        'input[name="access_mode"]:checked'
    );

    return selected?.value || "IN";
}

function showStatus(statusText, type) {
    statusMessage.textContent = statusText;
    statusMessage.className =
        `result-message ${type}`.trim();
}

async function readJsonResponse(response) {
    try {
        return await response.json();
    } catch (error) {
        throw new Error(
            "Máy chủ trả về dữ liệu không hợp lệ."
        );
    }
}
