function goBack() {
    window.location.href = "/";
}



var deviceID;
function getDeviceIdFromURL() {
    const params = new URLSearchParams(window.location.search);
    return params.get("id");
}

async function fetchDeviceInfo() {
    try {
        const response = await fetch(`/api/device-information?device=${deviceID}`);
        if (!response.ok) {
            if (response.status == 404)
                window.location.href = "/404";
            else {
                json = await response.json();
                throw new Error(json["result"]);
            }
        }

        const data = await response.json();
        document.title = data["name"];
        document.getElementById("deviceName").textContent = data["name"];
        document.getElementById("deviceStatus").className = "device-status status-" + data["status"];
        document.getElementById("deviceId").textContent = "ID: " + deviceID;
        document.getElementById("deviceIp").textContent = "IP: " + data["ipAddress"];
        document.getElementById("deviceLastSeen").textContent = "Last seen: " + transformTimestamp(data["lastSeen"]);
    } catch (error) {
        showError(error.toString());
    }
}

const temperatureBadge = document.getElementById("temperatureBadge");
async function updateDeviceTemperature() {
    try {
        const response = await fetch(`/api/temperature?device=${deviceID}&latest=1`);
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        keys = Object.keys(data);
        if (keys[0])
            temperatureBadge.textContent = `${data[keys[0]]} °C`;
        else
            temperatureBadge.textContent = "NaN";
    } catch (error) {
        showError(error.toString());
        temperatureBadge.textContent = "NaN";
    }
}



var currentPage = 0;
var totalPages = 0;
const selectPageButton = document.getElementById("selectPageBtn");
async function fetchTotalPages() {
    try {
        const response = await fetch(`/api/image-pages?device=${deviceID}`);
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        totalPages = data["pages"];
        if (currentPage >= totalPages)
            currentPage = totalPages - 1;
        else if (currentPage < 0)
            currentPage = 0;
        selectPageButton.textContent = `Page ${currentPage + 1} of ${totalPages}`;
    } catch (error) {
        showError(error.toString());
        selectPageButton.textContent = "Page 1 of 1";
    }
}
async function fetchImages() {
    try {
        const response = await fetch(`/api/images?device=${deviceID}&page=${currentPage}`);
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



const logModal = document.getElementById("logModal");
const logContent = document.getElementById("logContent");
function openLogModal() {
    loadLog();
    logModal.style.display = "flex";
}
function closeLogModal() {
    logModal.style.display = "none";
}
async function loadLog() {
    logContent.innerHTML = "";
    try {
        const response = await fetch(`/api/log?device=${deviceID}&latest=5`);
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();
        Object.keys(data).forEach(key => {
            const text = document.createElement("p");
            text.textContent = `${key}: "${data[key]}"`;
            logContent.appendChild(text);
        });
    } catch (error) {
        showError(error.toString());
    }
}
logModal.onclick = function(e) {
    if (e.target === logModal) closeLogModal();
}



function pageUp() {
    currentPage++;
    refreshPage();
}
function pageDown() {
    currentPage--;
    refreshPage();
}
function selectPage() {
    let page = Number(prompt("Please enter a page number:", "1"));
    if (!isNaN(page)) {
        currentPage = page - 1;
        refreshPage();
    } else {
        showWarning("Input must be a number!");
    }
}



const waitForDeviceModal = document.getElementById("waitDeviceModal");
const abortDeviceWaitBtn = document.getElementById("abortWaitBtn");
function openWaitForDeviceModal() {
    waitForDeviceModal.style.display = "flex";
}
function closeWaitForDeviceModal() {
    waitForDeviceModal.style.display = "none";
}
async function waitForDeviceOnline() {
    openWaitForDeviceModal();

    let aborted = false;
    waitForDeviceModal.onclick = (e) => {
        if (e.target === waitForDeviceModal) {
            aborted = true;
            closeWaitForDeviceModal();
        }
    };
    abortDeviceWaitBtn.onclick = () => {
        aborted = true;
        closeWaitForDeviceModal();
    };
    

    while (!aborted) {
        try {
            const response = await fetch(`/api/device-status?device=${deviceID}`);

            if (!response.ok) {
                const json = await response.json();
                throw new Error(json["result"]);
            }

            if (!aborted) {
                const data = await response.json();

                if (data["status"] === "online") {
                    closeWaitForDeviceModal();
                    return true;
                }
            } else break;
        } catch (error) {
            showError(error.toString());
        }

        await delay(2500);
    }

    closeWaitForDeviceModal();
    return false;
}



const streamModal = document.getElementById("streamModal");
const streamImage = document.getElementById("streamImage");
async function openStreamModal() {
    const online = await waitForDeviceOnline();
    if (!online) return;

    streamImage.style.display = "block";
    streamImage.src = `/api/stream?device=${deviceID}`;

    streamModal.style.display = "flex";
}
function closeStreamModal() {
    streamModal.style.display = "none";
    streamImage.src = "";
    streamImage.style.display = "none";
}
streamModal.onclick = function(e) {
    if (e.target === streamModal) closeStreamModal();
}



function openSettings() {
    loadSettings();
    openSettingsModal();
}
async function loadSettings() {
    try {
        const response = await fetch(`/api/device-settings?device=${deviceID}`);
        if (!response.ok) {
            const json = await response.json();
            throw new Error(json["result"]);
        }

        const data = await response.json();

        // general settings
        document.getElementById("deviceNameInput").value = data["displayName"];

        document.getElementById("enableMovementWakeup").checked = data["settings"]["enableMovementWakeup"];
        document.getElementById("enablePictureOnTimer").checked = data["settings"]["pictureOnTimerWakeup"];
        document.getElementById("enableTemperatureRead").checked = data["settings"]["enableTemperatureRead"];

        document.getElementById("ledBrightness").value = data["settings"]["ledBrightness"];
        document.getElementById("deepSleepTime").value = data["settings"]["deepSleepTime"];

        // camera settings
        document.getElementById("snapshotResolution").value = data["settings"]["snapshotFramesize"];
        document.getElementById("snapshotQuality").value = data["settings"]["snapshotQuality"];

        document.getElementById("streamingResolution").value = data["settings"]["streamingFramesize"];
        document.getElementById("streamingQuality").value = data["settings"]["streamingQuality"];

        document.getElementById("contrast").value = data["settings"]["contrast"];
        document.getElementById("brightness").value = data["settings"]["brightness"];

        document.getElementById("saturation").value = data["settings"]["saturation"];
        document.getElementById("autoExposureLevel").value = data["settings"]["autoExposureLevel"];

        document.getElementById("gainceiling").value = data["settings"]["gainceiling"];
        document.getElementById("autoWhiteBalance").checked = data["settings"]["autoWhiteBalance"];

        document.getElementById("nightMode").checked = data["settings"]["aec2"];
        document.getElementById("lensCorrection").checked = data["settings"]["lensCorrection"];
        
        document.getElementById("horizontalFlip").checked = data["settings"]["horizontalFlip"];
        document.getElementById("verticalFlip").checked = data["settings"]["verticalFlip"];
    } catch (error) {
        showError(error.toString());
    }
}

function saveGeneralSettings() {
    let generalSettings = {};

    generalSettings["displayName"] = document.getElementById("deviceNameInput").value.trim();
    generalSettings["enableMovementWakeup"] = document.getElementById("enableMovementWakeup").checked;
    generalSettings["pictureOnTimerWakeup"] = document.getElementById("enablePictureOnTimer").checked;
    generalSettings["enableTemperatureRead"] = document.getElementById("enableTemperatureRead").checked;

    generalSettings["ledBrightness"] = safeClamp(document.getElementById("ledBrightness").value, 0, 255);
    generalSettings["deepSleepTime"] = safeClamp(document.getElementById("deepSleepTime").value, 0, 120);

    saveSettings(generalSettings, false).then(() => { refreshPage(); });
}
function saveCameraSettings(toAll) {
    let cameraSettings = {};

    cameraSettings["snapshotFramesize"] = safeClamp(document.getElementById("snapshotResolution").value, 0, 19);
    cameraSettings["snapshotQuality"] = safeClamp(document.getElementById("snapshotQuality").value, 4, 63);

    cameraSettings["streamingFramesize"] = safeClamp(document.getElementById("streamingResolution").value, 0, 19);
    cameraSettings["streamingQuality"] = safeClamp(document.getElementById("streamingQuality").value, 4, 63);

    cameraSettings["contrast"] = safeClamp(document.getElementById("contrast").value, -2, 2);
    cameraSettings["brightness"] = safeClamp(document.getElementById("brightness").value, -2, 2);
    
    cameraSettings["saturation"] = safeClamp(document.getElementById("saturation").value, -2, 2);
    cameraSettings["autoExposureLevel"] = safeClamp(document.getElementById("autoExposureLevel").value, -2, 2);

    cameraSettings["gainceiling"] = safeClamp(document.getElementById("gainceiling").value, 0, 6);
    cameraSettings["autoWhiteBalance"] = document.getElementById("autoWhiteBalance").checked;
    
    cameraSettings["aec2"] = document.getElementById("nightMode").checked;
    cameraSettings["lensCorrection"] = document.getElementById("lensCorrection").checked;
    
    cameraSettings["horizontalFlip"] = document.getElementById("horizontalFlip").checked;
    cameraSettings["verticalFlip"] = document.getElementById("verticalFlip").checked;

    saveSettings(cameraSettings, toAll);
}
async function saveSettings(jsonData, toAll) {
    const url = toAll ? "/api/device-settings" : `/api/device-settings?device=${deviceID}`;
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(jsonData)
        });
        if (!response.ok) {
            const json = await response.json();
            throw new Error(json["result"]);
        }
        
        showSuccess("Successfully updated settings!");
    } catch (error) {
        showError(error.toString());
    }
}

const firmwareFile = document.getElementById("firmwareFile");
async function uploadFirmware() {
    if (!firmwareFile.files.length) {
        showWarning("Please select a file!");
        return;
    }

    const online = await waitForDeviceOnline();
    if (!online) return;

    const formData = new FormData();
    formData.append("firmware", firmwareFile.files[0]);
    
    try {
        const response = await fetch(`/api/firmware?device=${deviceID}`, {
            method: "POST",
            body: formData
        });
        if (!response.ok) {
            const json = await response.json();
            throw new Error(json["result"]);
        }

        showSuccess("Firmware flashed successfully!");
    } catch (error) {
        showError(error.toString());
    }
}

async function deleteDeviceData() {
    if (!confirm("Are you sure you want to delete all data of this device?")) return;

    try {
        const response = await fetch(`/api/delete-data?device=${deviceID}`, {
            method: "DELETE"
        });
        if (!response.ok) {
            json = await response.json();
            throw new Error(json["result"]);
        }
        
        showSuccess("Successfully deleted device data!");
        goBack();
    } catch (error) {
        showError(error.toString());
    }
}



function refreshPage() {
    fetchDeviceInfo(deviceID);
    fetchTotalPages().then(() => {
        fetchImages();
    });
    updateDeviceTemperature();
}
document.addEventListener("DOMContentLoaded", () => {
    deviceID = getDeviceIdFromURL();
    if (!deviceID) {
        goBack();
        return;
    }

    document.getElementById("downloadAll").href = `/api/download?device=${deviceID}&type=all`;
    document.getElementById("downloadImages").href = `/api/download?device=${deviceID}&type=images`;
    document.getElementById("downloadTemperatures").href = `/api/download?device=${deviceID}&type=temperatures`;
    document.getElementById("downloadLog").href = `/api/download?device=${deviceID}&type=logs`;

    refreshPage();

    setInterval(() => {
        refreshPage();
    }, 60000);
});