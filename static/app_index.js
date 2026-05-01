const storageText = document.getElementById("storageText");
const storageFill = document.getElementById("storageFill");
async function fetchStorageUsage() {
    try {
        const response = await fetch("/api/storage-usage");
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        updateStorageUI(data);
    } catch (error) {
        showError(error.toString());
        storageText.textContent = "Used Storage: -- MB / -- MB";
        storageFill.style.width = "0%"
    }
}
function updateStorageUI(data) {
    const { used, total, range } = data;

    storageText.textContent = `Used Storage: ${used} MB / ${total} MB`;
    storageFill.style.width = `${range * 100}%`;

    if (range < 0.75)
        storageFill.style.background = "#2e7d32";
    else if (range < 0.9)
        storageFill.style.background = "#f9a825";
    else
        storageFill.style.background = "#c62828";
}

async function fetchImages() {
    try {
        const response = await fetch("/api/latest-images");
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }
        
        const data = await response.json();
        populateImages(data);
    } catch (error) {
        showError(error.toString());
    }
}
async function fetchDevices() {
    try {
        const response = await fetch("/api/devices");
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        renderDevices(data);
    } catch (error) {
        showError(error.toString());
    }
}

const deviceGrid = document.getElementById("deviceGrid");
function renderDevices(devices) {
    deviceGrid.innerHTML = "";

    sorted = Object.entries(devices);
    sorted.sort((a, b) => {
        const nameA = a[1]["name"].toLowerCase();
        const nameB = b[1]["name"].toLowerCase();
        return nameA < nameB ? -1 : nameA > nameB ? 1 : 0;
    });

    sorted.forEach(device => {
        const card = document.createElement("div");
        card.className = "device-card";

        card.innerHTML = `
            <span>${device[1]["name"]}</span>
            <div class="device-status status-${device[1]["status"]}"></div>
        `;

        card.addEventListener("click", () => {
            window.location.href = `/device?id=${device[0]}`;
        });

        deviceGrid.appendChild(card);
    });
}



function openSettings() {
    fetchVersion();
    openSettingsModal();
}

const versionIndicator = document.getElementById("versionIndicator");
async function fetchVersion() {
    try {
        const response = await fetch("/api/version");
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        versionIndicator.textContent = "Version: " + data.version;
    } catch (error) {
        showError(error.toString());
        versionIndicator.textContent = "";
    }
}

const settingsFile = document.getElementById("settingsUpload");
async function uploadSettings() {
    if (!settingsFile.files.length) {
        showWarning("Please select a file!");
        return;
    }

    const formData = new FormData();
    formData.append("settings", settingsFile.files[0]);

    try {
        const response = await fetch("/api/settings", { 
            method: "POST",
            body: formData
        });
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        showSuccess("Successfully replaced device settings!");
        closeSettingsModal();
        refreshPage();
    } catch(error) {
        showError(error.toString());
    }
}

async function deleteData(type) {
    if (!confirm("Are you sure?")) return;

    var endpoint = "/api/delete-data";
    if (type) {
        endpoint += `?type=${type}`;
    }

    try {
        const response = await fetch(endpoint, {
            method: "DELETE"
        });
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }
        
        showSuccess("Successfully deleted data!");
        closeSettingsModal();
        refreshPage();
    } catch (error) {
        showError(error.toString());
    }
}



function refreshPage() {
    fetchStorageUsage();
    fetchImages();
    fetchDevices();
}
document.addEventListener("DOMContentLoaded", () => {
    refreshPage();
    
    setInterval(() => { refreshPage() }, 60000);
});