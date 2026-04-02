from flask import Flask, request, jsonify, render_template, send_file, Response
from datetime import datetime, timedelta
import zipstream
import requests
import shutil
import json
import os

VERSION = "1.0.0"
DOWNLOAD_FILENAME = "BirdhouseCameraSystem"

ERROR_MISSING_DEVICE_ID = "Missing device ID!"
ERROR_DEVICE_NOT_FOUND = "Device not found!"
ERROR_MISSING_IP_ADDRESS = "Missing IP address!"
ERROR_MISSING_DATA = "Missing data!"
ERROR_DEVICE_OFFLINE = "Device is offline!"
ERROR_EXTENSTION_NOT_ALLOWED = "Extension not allowed!"
ERROR_ESP_FLASH_ERROR = "ESP reported flash failure!"
ERROR_ESP_UNKNOWN_ERROR = "Unexpected ESP response!"
ERROR_TIMEOUT = "Request timed out!"
ERROR_CONNECTION_FAILURE = "Could not connect to device!"
ERROR_NO_IMAGES_FOUND = "No images found!"
ERROR_MISSING_ARGUMENTS = "Missing arguments!"
ERROR_INVALID_FILE_NAME = "Invalid file name!"
ERROR_MISSING_TYPE = "Missing type!"
ERROR_INVALID_TYPE = "Invalid type!"

MAXIMUM_STORAGE_CAPACITY = 10000 # in MB; max storage can be exceeded, just an indicator
IMAGES_PER_PAGE = 24
LATEST_IMAGES_AMOUNT = 32

STATIC_DIR = "./static"
DATA_DIR = "./data"
IMG_DIR = os.path.join(DATA_DIR, "images")
TEMP_DIR = os.path.join(DATA_DIR, "temperatures")
LOG_DIR = os.path.join(DATA_DIR, "logs")
DEVICE_FILE = os.path.join(DATA_DIR, "devices.json")

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = Flask(__name__)

last_seen = {}



# --------------------------------------------------
# Utility Functions
# --------------------------------------------------

def is_json_file(file_name):
    return '.' in file_name and file_name.rsplit('.', 1)[1].lower() == "json"

def is_bin_file(file_name):
    return '.' in file_name and file_name.rsplit('.', 1)[1].lower() == "bin"

def get_size(start_path):
    total_size = 0
    for path, directories, files in os.walk(start_path):
        for f in files:
            file_path = os.path.join(path, f)
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)
    return total_size

def paginate_array(array, entries_per_page, page_index):
    total_entries = len(array)
    total_pages = (total_entries + entries_per_page - 1) // entries_per_page

    if total_entries < entries_per_page:
        return array[:]

    if page_index < 0:
        page_index = 0
    elif page_index >= total_pages:
        page_index = total_pages - 1

    start_index = page_index * entries_per_page
    end_index = start_index + entries_per_page

    return array[start_index:end_index]

def read_csv_last_n_lines(file_path, n):
    with open(file_path) as f:
        lines = f.readlines()
        if n != 0:
            last_n_lines = lines[-n:]
        else:
            last_n_lines = lines

    dict = {}
    for line in last_n_lines:
        timestamp, value = line.strip().split(',', 1)
        dict.update({timestamp: value.strip().strip('"')})
    
    return dict


def load_devices():
    if not os.path.exists(DEVICE_FILE):
        return {}
    with open(DEVICE_FILE, "r") as f:
        return json.load(f)

def save_devices(devices):
    with open(DEVICE_FILE, "w") as f:
        json.dump(devices, f, indent=4, ensure_ascii=False)

def create_device_if_not_exist(device_id, ip_address = "", display_name = ""):
    devices = load_devices()
    if device_id not in devices:
        devices[device_id] = {
            "version": 1,
            "ipAddress": ip_address,
            "displayName": display_name,
            "settings": { # don't expose every field to avoid overwhelming the user
                "ledBrightness": 255,
                "enableMovementWakeup": True,
                "pictureOnTimerWakeup": False,
                "deepSleepTime": 60,
                "enableTemperatureRead": False, # doesn't matter atm, functionality removed
                
                # 6: QVGA 320x240, 8: CIF 400x296, 10: VGA 640x480, 16: FHD 1920x1080
                "snapshotFramesize": 10,
                "streamingFramesize": 10,

                "snapshotQuality" : 8,
                "streamingQuality": 20,

                "contrast": 0,
                "brightness": 1,
                "saturation": 0,

                "horizontalFlip": False,
                "verticalFlip": True, # OV3660 module: image is flipped

                "autoExposureLevel": 0,
                "gainceiling": 1,

                "whiteBalanceMode": 0,
                "autoWhiteBalance": True,

                "aec2": True, # night mode for OV3660

                "autoExposureControl": True,
                "autoExposureControlValue": 490, # manual aec

                "autoGainControl": True,
                "autoGainControlValue": 1, # manual agc

                "lensCorrection": True
            }
        }
        save_devices(devices)
    elif devices[device_id]["ipAddress"] != ip_address:
        devices[device_id]["ipAddress"] = ip_address
        save_devices(devices)
    set_last_seen_time(device_id)

def set_last_seen_time(device_id):
    now = datetime.now()
    if device_id not in last_seen:
        last_seen.update({device_id: now})
    else:
        last_seen[device_id] = now

def get_last_seen_time(device_id):
    if device_id not in last_seen:
        set_last_seen_time(device_id)
    return last_seen[device_id]


def get_device_name(device_id):
    devices = load_devices()
    if device_id in devices:
        if devices[device_id]["displayName"] != "":
            return devices[device_id]["displayName"]
    return device_id

def get_device_status(device_id):
    now = datetime.now()

    # error: last seen one day ago
    time_difference = now - get_last_seen_time(device_id)
    if time_difference > timedelta(days=1):
        return "error"

    # warning: there is a log this day
    device_dir = os.path.join(LOG_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d")}.csv")
    if os.path.isfile(file):
        return "warning"

    # ok: everything is running as expected
    return "ok"

def get_device_ip(device_id):
    devices = load_devices()
    if device_id in devices:
        return devices[device_id]["ipAddress"]
    return ""

def get_device_version(device_id):
    devices = load_devices()
    if device_id in devices:
        return devices[device_id]["version"]
    return 0



# --------------------------------------------------
# ESP32 Camera Node - API endpoints 
# --------------------------------------------------

# POST /devices/log
@app.route("/devices/log", methods=["POST"])
def device_post_log():
    device_id = request.headers.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    create_device_if_not_exist(device_id, request.remote_addr)

    data = request.get_json(force=True)

    if not data or "message" not in data:
        return {"result": ERROR_MISSING_DATA}, 400
    message = data["message"]

    device_dir = os.path.join(LOG_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)

    now = datetime.now()
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d")}.csv")

    with open(file, "a") as f:
        f.write(f"{now.strftime("%Y-%m-%d %H:%M:%S")},\"{message}\"\n")

    return {"result": "ok"}, 200

# POST /devices/temperature
@app.route("/devices/temperature", methods=["POST"])
def device_post_temperature():
    device_id = request.headers.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    create_device_if_not_exist(device_id, request.remote_addr)

    data = request.get_json(force=True)

    if not data or "temperature" not in data:
        return {"result": ERROR_MISSING_DATA}, 400
    temperature = data["temperature"]

    device_dir = os.path.join(IMG_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)

    now = datetime.now()
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d")}.csv")

    with open(file, "a") as f:
        f.write(f"{now.strftime("%Y-%m-%d %H:%M:%S")},{temperature}\n")

    return {"result": "ok"}, 200

# POST /devices/image
@app.route("/devices/image", methods=["POST"])
def device_post_image():
    device_id = request.headers.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    create_device_if_not_exist(device_id, request.remote_addr)

    if not request.data:
        return {"result": ERROR_MISSING_DATA}, 400

    device_dir = os.path.join(IMG_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)

    now = datetime.now()
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d_%H%M%S")}.jpg")

    with open(file, "wb") as f:
        f.write(request.data)

    return {"result": "ok"}, 200

# GET /devices/settings?device=
@app.route("/devices/settings", methods=["GET"])
def device_get_settings():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    create_device_if_not_exist(device_id, request.remote_addr)

    devices = load_devices()

    return jsonify({
        "version": devices[device_id]["version"],
        "settings": devices[device_id]["settings"]
    }), 200



# --------------------------------------------------
# Device - API endpoints
# --------------------------------------------------

# GET /api/devices
@app.route("/api/devices", methods=["GET"])
def get_devices():
    devices = load_devices()
    device_list = {}
    for id in devices.keys():
        device_list.update({f"{id}": {
            "name": get_device_name(id),
            "ipAddress": get_device_ip(id),
            "status": get_device_status(id),
            "lastSeen": get_last_seen_time(id).strftime("%Y%m%d_%H%M%S")
        }})
    return jsonify(device_list), 200

# GET /api/device-information?device=
@app.route("/api/device-information", methods=["GET"])
def get_device_information():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    return jsonify({
        "name": get_device_name(device_id),
        "ipAddress": get_device_ip(device_id),
        "status": get_device_status(device_id),
        "version": get_device_version(device_id),
        "lastSeen": get_last_seen_time(device_id).strftime("%Y%m%d_%H%M%S")
    }), 200

# GET /api/log?device=&latest=
@app.route("/api/log", methods=["GET"])
def get_log():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    latest = request.args.get("latest", default=0, type=int)

    device_dir = os.path.join(LOG_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)

    now = datetime.now()
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d")}.csv")

    if not os.path.isfile(file):
        return jsonify({}), 200

    return jsonify(read_csv_last_n_lines(file, latest)), 200

# GET /api/temperature?device=&latest=
@app.route("/api/temperature", methods=["GET"])
def get_temperature():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    latest = request.args.get("latest", default=0, type=int)

    device_dir = os.path.join(TEMP_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)

    now = datetime.now()
    file = os.path.join(device_dir, f"{now.strftime("%Y%m%d")}.csv")

    if not os.path.isfile(file):
        return jsonify({}), 200

    return jsonify(read_csv_last_n_lines(file, latest)), 200

# GET /api/device-status?device=
@app.route("/api/device-status", methods=["GET"])
def get_device_online():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    if devices[device_id]["ipAddress"] == "":
        return {"result": ERROR_MISSING_IP_ADDRESS}, 404

    try:
        requests.get(f"http://{devices[device_id]["ipAddress"]}", timeout=2)
        return jsonify({"status": "online"}), 200
    except:
        return jsonify({"status": "offline"}), 200

# GET /api/stream?device=
@app.route("/api/stream", methods=["GET"])
def get_stream():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    if devices[device_id]["ipAddress"] == "":
        return {"result": ERROR_MISSING_IP_ADDRESS}, 404
    
    esp_url = f"http://{devices[device_id]["ipAddress"]}/stream"

    try:
        stream = requests.get(esp_url, stream=True, timeout=5)
        return Response(stream.iter_content(chunk_size=1024), content_type=stream.headers["Content-Type"])
    except requests.exceptions.RequestException:
        return {"result": ERROR_DEVICE_OFFLINE}, 503

# GET /api/device-settings?device=
@app.route("/api/device-settings", methods=["GET"])
def get_device_settings():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    return jsonify(devices[device_id]), 200

# POST /api/device-settings?device=
@app.route("/api/device-settings", methods=["POST"])
def post_device_settings():
    device_id = request.args.get("device")
    
    devices = load_devices()
    if device_id:
        if device_id not in devices:
            return {"result": ERROR_DEVICE_NOT_FOUND}, 404
        selected_devices = [device_id]
    else:
        selected_devices = devices.keys()
    
    data = request.get_json(force=True)
    if not data:
        return {"result": ERROR_MISSING_DATA}, 400
    
    for device in selected_devices:
        for key in data.keys():
            if key in devices[device]:
                devices[device][key] = data[key]
            elif key in devices[device]["settings"]:
                devices[device]["settings"][key] = data[key]
        devices[device]["version"] += 1

    save_devices(devices)
    return {"result": "ok"}, 200

# POST /api/firmware?device=
@app.route("/api/firmware", methods=["POST"])
def post_firmware():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    firmware = request.files.get("firmware")
    if not firmware:
        return {"result": ERROR_MISSING_DATA}, 400
    
    if not is_bin_file(firmware.filename):
        return {"result": ERROR_EXTENSTION_NOT_ALLOWED}, 400

    device_ip = devices[device_id]["ipAddress"]
    if device_ip == "":
        return {"result": ERROR_MISSING_IP_ADDRESS}, 404

    try:
        response = requests.post(
            f"http://{device_ip}/update",
            files={"firmware": (firmware.filename, firmware.stream)},
            timeout=120
        )

        esp_reply = response.text.strip()
        if esp_reply == "OK":
            return jsonify({"result": "ok"}), 200
        elif esp_reply == "FAIL":
            return jsonify({"result": ERROR_ESP_FLASH_ERROR}), 500
        else:
            return jsonify({"result": ERROR_ESP_UNKNOWN_ERROR}), 500
    except requests.exceptions.Timeout:
        return jsonify({"result": ERROR_TIMEOUT}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"result": ERROR_CONNECTION_FAILURE}), 503



# --------------------------------------------------
# Image - API endpoints
# --------------------------------------------------

# GET /api/images?device=&page=
@app.route("/api/images", methods=["GET"])
def get_images_pagiate():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    page = request.args.get("page", default=0, type=int)

    device_dir = os.path.join(IMG_DIR, device_id)
    if not os.path.isdir(device_dir):
        return {"result": ERROR_NO_IMAGES_FOUND}, 404

    images = [f for f in os.listdir(device_dir) if os.path.isfile(os.path.join(device_dir, f))]
    images.reverse() # latest images first
    
    image_list = {}
    for image in paginate_array(images, IMAGES_PER_PAGE, page):
        image_list.update({image: {"id": device_id, "name": get_device_name(device_id)} })

    return jsonify(image_list), 200

# GET /api/image-pages?device=
@app.route("/api/image-pages", methods=["GET"])
def get_images_page():
    device_id = request.args.get("device")
    if not device_id:
        return {"result": ERROR_MISSING_DEVICE_ID}, 400
    
    device_dir = os.path.join(IMG_DIR, device_id)
    if not os.path.isdir(device_dir):
        return jsonify({"pages": 1}), 200

    images = [f for f in os.listdir(device_dir) if os.path.isfile(os.path.join(device_dir, f))]
    total_pages = (len(images) + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
    
    return jsonify({"pages": total_pages}), 200

# GET /api/latest-images
@app.route("/api/latest-images", methods=["GET"])
def get_latest_images():
    devices = load_devices()

    image_array = []

    for device_id in devices.keys():
        device_dir = os.path.join(IMG_DIR, device_id)

        if not os.path.isdir(device_dir):
            continue

        for file in os.listdir(device_dir):
            full_path = os.path.join(device_dir, file)
            if os.path.isfile(full_path):
                image_array.append({
                    "file": file,
                    "id": device_id,
                    "timestamp": os.path.splitext(file)[0]
                })

    image_array.sort(key=lambda x: x["timestamp"], reverse=True)
    latest = image_array[:LATEST_IMAGES_AMOUNT]

    result = {}
    for entry in latest:
        result.update({entry["file"]: {"id": entry["id"], "name": get_device_name(entry["id"])}})

    return jsonify(result), 200

# GET /api/image?device=&name=
@app.route("/api/image", methods=["GET"])
def get_image():
    device_id = request.args.get("device")
    image_name = request.args.get("name")
    if not device_id or not image_name:
        return send_file(os.path.join(STATIC_DIR, "MissingImage.png"), mimetype='image/png'), 200
    
    devices = load_devices()
    if device_id not in devices:
        return send_file(os.path.join(STATIC_DIR, "MissingImage.png"), mimetype='image/png'), 200
    
    path = os.path.join(IMG_DIR, device_id, image_name)
    if not os.path.exists(path) or not os.path.isfile(path):
        return send_file(os.path.join(STATIC_DIR, "MissingImage.png"), mimetype='image/png'), 200
    
    return send_file(path, mimetype='image/jpg'), 200

# DELETE /api/image?device=&name=
@app.route("/api/image", methods=["DELETE"])
def delete_image():
    device_id = request.args.get("device")
    image = request.args.get("name")

    if not device_id or not image:
        return {"result": ERROR_MISSING_ARGUMENTS}, 400

    if ".." in image or "/" in image:
        return {"result": ERROR_INVALID_FILE_NAME}, 400

    image_path = os.path.join(IMG_DIR, device_id, image)

    if not os.path.exists(image_path) or not os.path.isfile(image_path):
        return {"result": ERROR_NO_IMAGES_FOUND}, 404

    os.remove(image_path)

    return {"result": "ok"}, 200

# Get /api/download-image?device=&name=
@app.route("/api/download-image", methods=["GET"])
def download_image():
    device_id = request.args.get("device")
    image_name = request.args.get("name")
    if not device_id or not image_name:
        return {"result": ERROR_MISSING_ARGUMENTS}, 400
    
    devices = load_devices()
    if device_id not in devices:
        return {"result": ERROR_DEVICE_NOT_FOUND}, 404
    
    path = os.path.join(IMG_DIR, device_id, image_name)
    if not os.path.exists(path) or not os.path.isfile(path):
        return {"result": ERROR_NO_IMAGES_FOUND}, 404
    
    file_name = f"{get_device_name(device_id)}_{image_name}"
    return send_file(path, as_attachment=True, download_name=file_name), 200



# --------------------------------------------------
# Main - API endpoints
# --------------------------------------------------

# GET /api/storage-usage
@app.route("/api/storage-usage", methods=["GET"])
def get_storage_usage():
    size = get_size(DATA_DIR) / 1048576
    if size > MAXIMUM_STORAGE_CAPACITY:
        size = MAXIMUM_STORAGE_CAPACITY
    return jsonify({
        "used": int(size),
        "total": int(MAXIMUM_STORAGE_CAPACITY),
        "range": round(size / MAXIMUM_STORAGE_CAPACITY, 3)
    }), 200

# GET /api/version
@app.route("/api/version", methods=["GET"])
def get_server_version():
    return jsonify({"version": VERSION}), 200

# GET /api/download?device=&type=
@app.route("/api/download", methods=["GET"])
def download_data():
    device_id = request.args.get("device")
    data_type = request.args.get("type")
    if not data_type:
        return {"result": ERROR_MISSING_TYPE}, 400

    if data_type not in ["images", "temperatures", "logs", "all"]:
        return {"result": ERROR_INVALID_TYPE}, 400

    now = datetime.now()
    devices = load_devices()
    if device_id:
        if device_id not in devices:
            return {"result": ERROR_DEVICE_NOT_FOUND}, 404
        selected_devices = [device_id]
        zip_name = f"{now.strftime("%Y%m%d_%H%M%S")}_{DOWNLOAD_FILENAME}_{get_device_name(device_id)}_{data_type}.zip"
    else:
        selected_devices = devices.keys()
        zip_name = f"{now.strftime("%Y%m%d_%H%M%S")}_{DOWNLOAD_FILENAME}_{data_type}.zip"

    z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)

    for id in selected_devices:
        name = get_device_name(id)

        types_to_include = (["images", "temperatures", "logs"] if data_type == "all" else [data_type])
        for type in types_to_include:
            folder_path = os.path.join("data", type, id)

            if not os.path.exists(folder_path):
                continue

            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, folder_path)
                    archive_path = os.path.join(name, type, rel_path)
                    z.write(abs_path, archive_path)

    return Response(
        z,
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_name}"}
    )

# GET /api/settings
@app.route("/api/settings", methods=["GET"])
def get_settings():
    now = datetime.now()
    file_name = f"{now.strftime("%Y%m%d_%H%M%S")}_{DOWNLOAD_FILENAME}_Settings.json"
    return send_file(DEVICE_FILE, as_attachment=True, download_name=file_name), 200

# POST /api/settings
@app.route("/api/settings", methods=["POST"])
def upload_settings():
    settings = request.files.get("settings")
    if not settings:
        return {"result": ERROR_MISSING_DATA}, 400
    
    if not is_json_file(settings.filename):
        return {"result": ERROR_EXTENSTION_NOT_ALLOWED}, 400

    settings.save(DEVICE_FILE)
    return {"result": "ok"}, 200

# DELETE /api/delete-data?device=
@app.route("/api/delete-data", methods=["DELETE"])
def delete_data():
    device_id = request.args.get("device")

    global last_seen
    devices = load_devices()
    if device_id:
        if device_id in devices:
            del devices[device_id]
        if device_id in last_seen:
            del last_seen[device_id]
    else:
        devices = {}
        last_seen = {}
    save_devices(devices)

    try:
        for category_path in [IMG_DIR, TEMP_DIR, LOG_DIR]:
            if not os.path.isdir(category_path):
                continue

            if device_id:
                path = os.path.join(category_path, device_id)
                if not os.path.isdir(path):
                    continue
                shutil.rmtree(path)
            else:
                for device in os.listdir(category_path):
                    path = os.path.join(category_path, device)

                    if os.path.isdir(path):
                        shutil.rmtree(path)

        return jsonify({"result": "ok"}), 200
    except Exception as e:
        return jsonify({"result": str(e)}), 500



# --------------------------------------------------
# Render Webpage
# --------------------------------------------------

@app.route("/")
def index_html():
    return render_template('index.html')

@app.route("/device")
def device_html():
    return render_template('device.html')

@app.errorhandler(404)
def page_not_found(error):
    print(error)
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    print(error)
    return render_template("500.html"), 500



if __name__ == "__main__":
    devices = load_devices()
    for device in devices:
        set_last_seen_time(device)

    app.run()