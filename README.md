# RTSP Doorbell Camera Vehicle Speed Tracker

A lightweight Python & OpenCV vehicle speed estimation tool designed for RTSP/RTSPS security and doorbell cameras (such as UniFi Protect). 

It uses background subtraction within a customizable Region of Interest (ROI) to track vehicles crossing two virtual tripwires, calculates their speed in MPH, saves a timestamped screenshot of the vehicle, and publishes the speed and travel direction to an MQTT broker (perfect for **Home Assistant** dashboards and automations).

---

## Features

* **Bidirectional Speed Tracking:** Automatically detects vehicles moving both Left-to-Right (`L->R`) and Right-to-Left (`R->L`).
* **MQTT Integration:** Publishes real-time JSON payloads (`{"speed": 28.4, "direction": "Left_to_Right"}`) for easy integration with Home Assistant or Node-RED.
* **Automatic Snapshots:** Saves annotated, timestamped `.jpg` screenshots with the calculated MPH in the filename (`YYYYMMDD_HHMMSS_XX.Xmph.jpg`).
* **Digital Zoom & ROI Filtering:** Crops out fisheye edges common on doorbell cameras and restricts motion detection to the street—ignoring swaying trees, clouds, or porch activity.
* **Built-in Click-to-Calibrate Helper:** Click anywhere on the live OpenCV video window to print exact `X, Y` pixel coordinates to the console for effortless tripwire and ROI setup.
* **Auto-Reconnect:** Gracefully handles RTSP stream drops by automatically reconnecting and resetting the background subtractor so the screen doesn't false-trigger.

---

## Prerequisites & Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/doorbell-speed-tracker.git](https://github.com/YOUR_USERNAME/doorbell-speed-tracker.git)
cd doorbell-speed-tracker
```

### 2. Install Dependencies
Python 3.8+ is recommended. Install the required packages using `pip`:
```bash
pip install opencv-python "paho-mqtt>=1.6.1,<2.0.0"
```

---

## Configuration & Calibration Guide

Open `DoorbellCameraSpeed.py` (or `doorbell_speed_tracker.py`) and edit the `CONFIGURATION` section at the top of the file:

### 1. Set Your RTSP Stream & MQTT Broker
Update `RTSP_URL` with your camera's stream address and enter your `MQTT_BROKER` IP and credentials.
* **UniFi Protect Note:** If you are using a UniFi Protect RTSPS URL on port `7441` (`rtsps://...:7441/...?enableSrtp`) and experience connection issues with OpenCV, try changing the protocol to `rtsp://`, the port to `7447`, and removing `?enableSrtp`.

### 2. Adjust Digital Zoom (Optional)
Doorbell cameras often have a wide fisheye field of view. You can digitally zoom into the street by adjusting `CROP_X_PERCENT` and `CROP_Y_PERCENT` (set both to `0.0` to disable cropping).

### 3. Calibrate Your ROI and Tripwires
1. Run the script:
   ```bash
   python DoorbellCameraSpeed.py
   ```
2. A window titled **Doorbell Speed Tracker** will open showing:
   * **Two Horizontal Cyan Lines:** The Region of Interest (`ROI_Y_START` and `ROI_Y_END`). Only motion *between* these two lines is evaluated.
   * **Vertical Green Line (`LINE_A_X`):** Left tripwire.
   * **Vertical Red Line (`LINE_B_X`):** Right tripwire.
3. **Click anywhere on the video window** to print the exact `X` and `Y` pixel coordinates in your terminal:
   ```text
   --> MOUSE CLICKED: X=553, Y=380 <--
   ```
4. Use those coordinates to set:
   * `ROI_Y_START` and `ROI_Y_END`: Frame the road vertically.
   * `LINE_A_X` and `LINE_B_X`: Pick two clear physical landmarks along the road (e.g., two trees, mailbox posts, or driveway edges).
5. Measure the real-world distance (in feet) between those two landmarks along the road and set `REAL_WORLD_DISTANCE_FEET`.

---

## Home Assistant MQTT Configuration

To pull the speed and direction into Home Assistant, add the following to your `configuration.yaml` under the `mqtt:` section:

```yaml
mqtt:
  sensor:
    - name: "Street Vehicle Speed"
      state_topic: "home/doorbell_camera/speed"
      unit_of_measurement: "mph"
      value_template: "{{ value_json.speed }}"
      icon: mdi:speedometer

    - name: "Street Vehicle Direction"
      state_topic: "home/doorbell_camera/speed"
      value_template: "{{ value_json.direction }}"
      icon: mdi:swap-horizontal
```

---

## Recommended `.gitignore`

If you are tracking this project in Git, create a `.gitignore` file in the project folder so your vehicle screenshots and log files aren't uploaded to GitHub:

```gitignore
# Logs and local outputs
*.log
screenshots/
DoorbellCameraScreenshots/

# Environment variables & local configs
.env

# Python cache & virtual environments
__pycache__/
*.py[cod]
venv/
.venv/
```

---

## Usage

Run the script from your terminal:
```bash
python DoorbellCameraSpeed.py
```
Press **`q`** while focused on the video window (or close the window) to cleanly release the camera stream and disconnect from MQTT.
