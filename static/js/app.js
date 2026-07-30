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

let previewUrl = null;

imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];

    if (!file) {
        return;
    }

    if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
    }

    previewUrl = URL.createObjectURL(file);

    previewImage.src = previewUrl;
    previewImage.hidden = false;
    uploadPlaceholder.hidden = true;
    scanButton.disabled = false;

    statusMessage.textContent = "";
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = imageInput.files[0];

    if (!file) {
        showStatus("Vui lòng chọn một ảnh.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("image", file);

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
        rawText.textContent = data.raw_text || "--";
        resultStatus.textContent = data.status || "--";

        const confidencePercent =
            Number(data.confidence || 0) * 100;

        confidence.textContent =
            `${confidencePercent.toFixed(2)}%`;

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