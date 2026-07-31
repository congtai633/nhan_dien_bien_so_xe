const form = document.getElementById("scanForm");
const imageInput = document.getElementById("imageInput");
const previewImage = document.getElementById("previewImage");
const uploadPlaceholder = document.getElementById("uploadPlaceholder");
const scanButton = document.getElementById("scanButton");
const statusMessage = document.getElementById("statusMessage");

const emptyResult = document.getElementById("emptyResult");
const resultContent = document.getElementById("resultContent");

const plateText = document.getElementById("plateText");
const plateType = document.getElementById("plateType");
const confidence = document.getElementById("confidence");
const rawText = document.getElementById("rawText");
const resultStatus = document.getElementById("resultStatus");

const camera = document.querySelector("#camera");
const cameraPlaceholder = document.querySelector("#camera-placeholder");
const openCameraButton = document.querySelector("#open-camera");
const closeCameraButton = document.querySelector("#close-camera");
const message = document.querySelector("#message");

const captureCameraButton = document.querySelector("#capture-camera");
const cameraCanvas = document.querySelector("#camera-canvas");
const previewTitle = document.querySelector("#preview-title");
const cropImage = document.getElementById("cropImage");

let cameraStream = null;
let previewUrl = null;
let selectedImageFile = null;

imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];

    if (!file) {
        return;
    }

    if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
    }

    selectedImageFile = file;
    previewUrl = URL.createObjectURL(file);

    previewImage.src = previewUrl;
    previewImage.hidden = false;
    uploadPlaceholder.hidden = true;
    previewTitle.textContent = "Ảnh đã chọn từ máy";
    scanButton.disabled = false;

    statusMessage.textContent = "";
    resetResult();
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!selectedImageFile) {
        showStatus(
            "Vui lòng chọn ảnh hoặc chụp một khung hình.",
            "error"
        );
        return;
    }

    const formData = new FormData();
    formData.append(
        "image",
        selectedImageFile,
        selectedImageFile.name
    );

    setLoading(true);
    showStatus("Đang nhận diện biển số...", "");

    try {
        const response = await fetch("/api/v1/scan", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.message || "Không thể nhận diện biển số."
            );
        }

        plateText.textContent = data.plate || "Không xác định";
        plateType.textContent = data.plate_type || "--";
        // rawText.textContent = data.raw_text || "--";
        // resultStatus.textContent = data.status || "--";

        const confidencePercent =
            Number(data.confidence || 0) * 100;

        confidence.textContent =
            `${confidencePercent.toFixed(2)}%`;

        if (!data.crop_image) {
            throw new Error("Flask chưa trả về ảnh crop.");
        }

        cropImage.src = data.crop_image.startsWith("data:image/")
            ? data.crop_image
            : `data:image/jpeg;base64,${data.crop_image}`;

        cropImage.hidden = false;   
        emptyResult.hidden = true;
        resultContent.hidden = false;

        showStatus("Nhận diện hoàn tất.", "success");
    } catch (error) {
        showStatus(error.message, "error");
    } finally {
        setLoading(false);
    }
});

function setLoading(isLoading) {
    scanButton.disabled = isLoading;

    scanButton.textContent = isLoading
        ? "Đang xử lý..."
        : "Nhận diện biển số";
}

function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status ${type}`;
}

function resetResult() {
    emptyResult.hidden = false;
    resultContent.hidden = true;
}

openCameraButton.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
        message.textContent =
            "Trình duyệt này không hỗ trợ mở camera.";
        return;
    }

    try {
        message.textContent =
            "Đang yêu cầu quyền sử dụng camera...";

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

        camera.hidden = false;
        cameraPlaceholder.hidden = true;

        openCameraButton.disabled = true;
        captureCameraButton.disabled = false;
        closeCameraButton.disabled = false;

        message.textContent = "Camera đang hoạt động.";
    } catch (error) {
        message.textContent =
            "Không thể mở camera. Hãy kiểm tra quyền camera.";
    }
});

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach((track) => {
            track.stop();
        });
    }

    cameraStream = null;
    camera.srcObject = null;

    camera.hidden = true;
    cameraPlaceholder.hidden = false;

    openCameraButton.disabled = false;
    captureCameraButton.disabled = true;
    closeCameraButton.disabled = true;

    message.textContent = "Camera đã tắt.";
}

closeCameraButton.addEventListener(
    "click",
    stopCamera
);

window.addEventListener(
    "beforeunload",
    stopCamera
);

captureCameraButton.addEventListener("click", () => {
    if (!cameraStream) {
        message.textContent = "Camera chưa được mở.";
        return;
    }

    if (camera.videoWidth === 0 || camera.videoHeight === 0) {
        message.textContent = "Camera chưa tải hình ảnh xong.";
        return;
    }

    cameraCanvas.width = camera.videoWidth;
    cameraCanvas.height = camera.videoHeight;

    const context = cameraCanvas.getContext("2d");

    context.drawImage(
        camera,
        0,
        0,
        cameraCanvas.width,
        cameraCanvas.height
    );

    cameraCanvas.toBlob(
        (blob) => {
            if (!blob) {
                message.textContent =
                    "Không thể tạo ảnh từ camera.";
                return;
            }

            selectedImageFile = new File(
                [blob],
                "camera-capture.jpg",
                { type: "image/jpeg" }
            );

            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }

            previewUrl = URL.createObjectURL(selectedImageFile);
            previewImage.src = previewUrl;
            previewImage.hidden = false;
            uploadPlaceholder.hidden = true;
            previewTitle.textContent = "Ảnh vừa chụp từ camera";
            scanButton.disabled = false;

            resetResult();
            showStatus("", "");
            message.textContent =
                "Đã chụp ảnh. Hãy kiểm tra rồi nhấn Nhận diện biển số.";

            previewImage.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });
        },
        "image/jpeg",
        0.92
    );
});
