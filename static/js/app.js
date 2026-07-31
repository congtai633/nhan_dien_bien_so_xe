const emptyResult = document.getElementById("emptyResult");
const resultContent = document.getElementById("resultContent");
const plateText = document.getElementById("plateText");
const plateType = document.getElementById("plateType");
const confidence = document.getElementById("confidence");
const cropImage = document.getElementById("cropImage");
const statusMessage = document.getElementById("statusMessage");
const resultStatusBadge = document.getElementById(
    "result-status-badge"
);

const camera = document.getElementById("camera");
const cameraPlaceholder = document.getElementById(
    "camera-placeholder"
);
const cameraStatusBadge = document.getElementById(
    "camera-status-badge"
);
const scanIndicator = document.getElementById("scan-indicator");
const openCameraButton = document.getElementById("open-camera");
const restartScanButton = document.getElementById("restart-scan");
const closeCameraButton = document.getElementById("close-camera");
const cameraCanvas = document.getElementById("camera-canvas");
const message = document.getElementById("message");

const AUTO_SCAN_DELAY_MS = 250;

let cameraStream = null;
let autoScanSessionId = null;
let autoScanTimer = null;
let autoScanBusy = false;
let autoScanStopped = true;

openCameraButton.addEventListener("click", openCamera);
restartScanButton.addEventListener("click", restartAutomaticScan);
closeCameraButton.addEventListener("click", stopCamera);
window.addEventListener("beforeunload", stopCamera);

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
            updateScanningProgress(data);
            scheduleNextAutoFrame();
            return;
        }

        if (
            response.status === 422 &&
            data.status === "PLATE_NOT_FOUND"
        ) {
            finishAutomaticScan();
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
        renderRecognitionResult(data);
        restartScanButton.hidden = false;

        if (data.status === "SUCCESS") {
            message.textContent =
                "Đã chọn và crop khung hình biển số rõ nhất.";
            setBadge(resultStatusBadge, "Thành công", "success");
            showStatus(
                data.message || "Nhận diện hoàn tất.",
                "success"
            );
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

    emptyResult.hidden = true;
    resultContent.hidden = false;
}

function resetResult() {
    emptyResult.hidden = false;
    resultContent.hidden = true;

    cropImage.removeAttribute("src");
    cropImage.hidden = true;
    plateText.textContent = "--";
    plateType.textContent = "--";
    confidence.textContent = "--";

    setBadge(resultStatusBadge, "Đang chờ", "idle");
    showStatus("", "");
}

function setBadge(element, text, state) {
    element.textContent = text;
    element.className =
        `status-badge status-badge--${state}`;
}

function setScanning(isScanning) {
    scanIndicator.hidden = !isScanning;
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
