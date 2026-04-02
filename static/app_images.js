const imageGrid = document.getElementById("imageGrid");
const imageModal = document.getElementById("imageModal");
const modalImage = document.getElementById("modalImage");
const modalTimestamp = document.getElementById("modalTimestamp");
const modalDevice = document.getElementById("modalDevice");
const imageDownload = document.getElementById("imageDownload");

let currentImageName = null;
let currentDeviceId = null;
function populateImages(images) {
    imageGrid.innerHTML = "";
    Object.keys(images).toReversed().forEach((key) => {
        const timestamp = transformTimestamp(key.slice(0, -4));
        const deviceName = images[key]["name"];
        const deviceID = images[key]["id"];
        const imageUrl = `/api/image?device=${deviceID}&name=${key}`

        const card = document.createElement("div");
        card.className = "image-card";

        const img = document.createElement("img");
        img.src = imageUrl;
        img.alt = "Capture";

        card.appendChild(img);

        card.addEventListener("click", () => {
            openImageModal(imageUrl, timestamp, deviceName, deviceID, key);
            currentImageName = key;
            currentDeviceId = images[key]["id"];
        });

        imageGrid.appendChild(card);
    });
}
function openImageModal(src, timestamp, deviceName, deviceID, imageName) {
    modalImage.src = src;
    modalTimestamp.textContent = "📅 " + timestamp;
    modalDevice.textContent = "📷 " + deviceName;
    imageModal.style.display = "flex";

    imageDownload.href=`/api/download-image?device=${deviceID}&name=${imageName}`
}
function closeImageModal() {
    imageModal.style.display = "none";
}
imageModal.onclick = function(e) {
    if (e.target === imageModal) closeImageModal();
}

async function deleteCurrentImage() {
    if (!currentImageName || !currentDeviceId) return;

    if (!confirm("Are you sure you want to delete this image?")) return;

    try {
        const response = await fetch(`/api/image?device=${currentDeviceId}&name=${currentImageName}`, {
            method: "DELETE"
        });
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        closeImageModal();
        refreshPage();
    } catch (error) {
        showError(error.toString());
    }
}