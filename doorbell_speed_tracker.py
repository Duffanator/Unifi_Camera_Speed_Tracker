"""
RTSP Camera Vehicle Speed Tracker with MQTT Integration
-------------------------------------------------------
Tracks moving vehicles across two virtual tripwires using OpenCV background
subtraction, calculates speed in MPH, saves a timestamped screenshot, and
publishes JSON payloads to an MQTT broker (ideal for Home Assistant).
"""

import os
import time
import json
import logging
from datetime import datetime
import cv2
import paho.mqtt.client as mqtt

# Force OpenCV to use TCP for RTSP streams to reduce packet loss/artifacting
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# ==========================================
# CONFIGURATION
# ==========================================

# --- Video Stream (RTSP / RTSPS) ---
# Example UniFi Protect URL: "rtsps://192.168.1.1:7441/YOUR_STREAM_TOKEN?enableSrtp"
# (Note: For UniFi Protect, try port 7447 with rtsp:// if 7441 rtsps:// fails)
RTSP_URL = os.getenv("RTSP_URL", "rtsps://YOUR_CAMERA_IP:7441/YOUR_STREAM_TOKEN?enableSrtp")

# --- Output Directories & Logging ---
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "./screenshots")
ENABLE_DEBUG_LOGGING = True
LOG_FILE = "speed_tracker.log"

# --- MQTT Broker Settings ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "YOUR_MQTT_BROKER_IP")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "your_mqtt_username")
MQTT_PASS = os.getenv("MQTT_PASS", "your_mqtt_password")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/doorbell_camera/speed")

# --- Speed & Tripwire Calibration ---
# Measure the real-world distance (in feet) between Line A and Line B on the road
REAL_WORLD_DISTANCE_FEET = 40.0

# X-coordinates for the vertical tripwire lines (within the 1280x720 window)
# Tip: Run the script and click on the video feed to print X/Y coordinates in the console!
LINE_A_X = 553   # Left tripwire (Green)
LINE_B_X = 1004  # Right tripwire (Red)
TRIPWIRE_TOLERANCE = 10  # Pixel buffer (+/-) on either side of the tripwire line

# Time bounds (in seconds) to filter out false triggers or stopped vehicles
MIN_VALID_SECONDS = 0.5
MAX_VALID_SECONDS = 10.0

# --- Region of Interest (ROI) & Digital Zoom ---
# Crop percentages to digitally zoom into the center of the frame (0.15 = 15% off each side)
CROP_X_PERCENT = 0.15  # Cuts left and right edges
CROP_Y_PERCENT = 0.25  # Cuts top and bottom edges

# Vertical Y-coordinates (within the 1280x720 resized window) to watch for motion
# Restricts detection to the street, ignoring sky/trees above and porch/sidewalk below
ROI_Y_START = 240
ROI_Y_END = 500

# Minimum pixel area required to classify a moving contour as a vehicle
MIN_CONTOUR_AREA = 1000
# ==========================================


# Ensure the screenshot directory exists before starting
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)
    print(f"Created screenshot directory at: {SCREENSHOT_DIR}")

# Configure Logging
if ENABLE_DEBUG_LOGGING:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
else:
    logging.basicConfig(level=logging.CRITICAL + 1)

logging.info("=== STARTING SPEED TRACKER SCRIPT ===")

# Setup MQTT Client
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    logging.info(f"Connected to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"Warning: Could not connect to MQTT Broker ({e}). Continuing without MQTT...")
    logging.error(f"MQTT Connection failed: {e}")


def click_event(event, x, y, flags, param):
    """Prints the X and Y coordinates in the console when the user clicks the video feed."""
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"--> MOUSE CLICKED: X={x}, Y={y} <--")


def record_speed_event(elapsed_time, direction_label, direction_code, frame):
    """Calculates MPH, logs the event, publishes to MQTT, and saves a screenshot."""
    speed_fps = REAL_WORLD_DISTANCE_FEET / elapsed_time
    mph = round(speed_fps * 0.681818, 1)

    msg = f"Vehicle detected ({direction_code})! Speed: {mph} MPH (Elapsed time: {round(elapsed_time, 2)}s)"
    print(msg)
    logging.info(msg)

    # Publish JSON payload to MQTT
    payload = json.dumps({"speed": mph, "direction": direction_label})
    client.publish(MQTT_TOPIC, payload)

    # Save timestamped screenshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{mph}mph.jpg"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    cv2.imwrite(filepath, frame)
    logging.info(f"Saved screenshot to {filepath}")


# Setup Video Capture & Background Subtractor
cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
object_detector = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=40)
tracking_data = {}
prev_frame_time = 0

print("Starting video stream...")
print("Tip: Click anywhere on the video window to print X/Y coordinates in this console.")
print("Press 'q' in the video window to quit.")

cv2.namedWindow("Doorbell Speed Tracker")
cv2.setMouseCallback("Doorbell Speed Tracker", click_event)

while True:
    ret, frame = cap.read()

    # Handle stream drops gracefully
    if not ret:
        print("Failed to grab frame. Reconnecting in 5 seconds...")
        logging.warning("Stream dropped. Failed to grab frame. Reconnecting in 5 seconds...")
        cap.release()
        time.sleep(5)
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

        # Reset background subtractor and clear partial tracks after a reconnect
        object_detector = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=40)
        tracking_data.clear()
        continue

    # ---------------------------------------------------------
    # 1. Digital Zoom & Standardize Resolution
    # ---------------------------------------------------------
    h, w = frame.shape[:2]
    crop_x = int(w * CROP_X_PERCENT)
    crop_y = int(h * CROP_Y_PERCENT)

    if crop_x > 0 or crop_y > 0:
        frame = frame[crop_y : h - crop_y, crop_x : w - crop_x]

    frame = cv2.resize(frame, (1280, 720))

    # ---------------------------------------------------------
    # 2. On-Screen Diagnostics (FPS & Status)
    # ---------------------------------------------------------
    new_frame_time = time.time()
    time_diff = new_frame_time - prev_frame_time
    calc_fps = 1 / time_diff if time_diff > 0 else 0
    prev_frame_time = new_frame_time

    cv2.putText(frame, f"FPS: {int(calc_fps)}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "Status: Connected", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

    # ---------------------------------------------------------
    # 3. Region of Interest (ROI) & Motion Detection
    # ---------------------------------------------------------
    # Draw horizontal ROI boundary lines (Cyan)
    cv2.line(frame, (0, ROI_Y_START), (1280, ROI_Y_START), (255, 255, 0), 1)
    cv2.line(frame, (0, ROI_Y_END), (1280, ROI_Y_END), (255, 255, 0), 1)

    # Draw vertical Tripwire lines (Line A = Green, Line B = Red)
    cv2.line(frame, (LINE_A_X, 0), (LINE_A_X, 720), (0, 255, 0), 2)
    cv2.line(frame, (LINE_B_X, 0), (LINE_B_X, 720), (0, 0, 255), 2)

    roi = frame[ROI_Y_START:ROI_Y_END, :]
    mask = object_detector.apply(roi)
    _, mask = cv2.threshold(mask, 254, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > MIN_CONTOUR_AREA:
            x, y_roi, w_box, h_box = cv2.boundingRect(cnt)
            y_frame = y_roi + ROI_Y_START
            cx = int(x + (w_box / 2))
            cy = int(y_frame + (h_box / 2))

            logging.debug(f"Large Object Detected - Area: {int(area)} | Center: ({cx}, {cy})")

            # Draw bounding box and center point
            cv2.rectangle(frame, (x, y_frame), (x + w_box, y_frame + h_box), (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(frame, f"Area: {int(area)}", (x, y_frame - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # ---------------------------------------------------------
            # 4. Bidirectional Tripwire Logic
            # ---------------------------------------------------------
            # Crossed Line A (Left Tripwire)
            if LINE_A_X - TRIPWIRE_TOLERANCE < cx < LINE_A_X + TRIPWIRE_TOLERANCE:
                logging.debug(f"Object crossed Line A at X: {cx}")

                if "car" in tracking_data and tracking_data["car"]["start_line"] == "B":
                    elapsed_time = time.time() - tracking_data["car"]["start_time"]

                    if MIN_VALID_SECONDS < elapsed_time <= MAX_VALID_SECONDS:
                        record_speed_event(elapsed_time, "Right_to_Left", "R->L", frame)
                        tracking_data.clear()
                        logging.debug("Tracking data cleared.")
                    else:
                        logging.warning(f"Timeout exceeded for Line B trigger ({round(elapsed_time, 2)}s). Overwriting with new Line A start.")
                        tracking_data["car"] = {"start_time": time.time(), "start_line": "A"}
                else:
                    logging.info("Initiated new track: Started at Line A (Left-to-Right).")
                    tracking_data["car"] = {"start_time": time.time(), "start_line": "A"}

            # Crossed Line B (Right Tripwire)
            elif LINE_B_X - TRIPWIRE_TOLERANCE < cx < LINE_B_X + TRIPWIRE_TOLERANCE:
                logging.debug(f"Object crossed Line B at X: {cx}")

                if "car" in tracking_data and tracking_data["car"]["start_line"] == "A":
                    elapsed_time = time.time() - tracking_data["car"]["start_time"]

                    if MIN_VALID_SECONDS < elapsed_time <= MAX_VALID_SECONDS:
                        record_speed_event(elapsed_time, "Left_to_Right", "L->R", frame)
                        tracking_data.clear()
                        logging.debug("Tracking data cleared.")
                    else:
                        logging.warning(f"Timeout exceeded for Line A trigger ({round(elapsed_time, 2)}s). Overwriting with new Line B start.")
                        tracking_data["car"] = {"start_time": time.time(), "start_line": "B"}
                else:
                    logging.info("Initiated new track: Started at Line B (Right-to-Left).")
                    tracking_data["car"] = {"start_time": time.time(), "start_line": "B"}

    cv2.imshow("Doorbell Speed Tracker", frame)

    # Exit conditions: press 'q' or close the window
    if cv2.waitKey(30) & 0xFF == ord("q"):
        msg = "Quit key 'q' pressed. Shutting down..."
        print(msg)
        logging.info(msg)
        break

    if cv2.getWindowProperty("Doorbell Speed Tracker", cv2.WND_PROP_VISIBLE) < 1:
        msg = "Window closed by user. Shutting down..."
        print(msg)
        logging.info(msg)
        break

print("Releasing camera and closing connections...")
logging.info("=== SHUTTING DOWN SPEED TRACKER SCRIPT ===")
cap.release()
cv2.destroyAllWindows()
client.loop_stop()
