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
