import cv2
import time
import json
import base64
import threading
import os
import paho.mqtt.client as mqtt

from eye_tracker   import EyeTracker
from yolo_detector import YoloDetector

# --- CONFIG από environment variables ---
CAMERA_INDEX  = int(os.getenv("CAMERA_INDEX", 0))
MQTT_BROKER   = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT     = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC    = os.getenv("MQTT_TOPIC", "busnet/driver/alert")

EYES_CLOSED_THRESHOLD = 2.5   # sec
FACE_MISSING_TIMEOUT  = 3.0   # sec

# --- STATE ---
state = {
    "current":             "NORMAL",
    "eyes_closed_since":   None,
    "face_missing_since":  None,
    "last_alert_state":    None,
}

# --- MQTT ---
mqtt_client = mqtt.Client()
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"[MQTT] Could not connect: {e}. Running without MQTT.")

def publish_alert(alert_state, frame):
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    snapshot  = base64.b64encode(buffer).decode('utf-8')
    payload   = json.dumps({
        "event_type": alert_state,
        "timestamp":  int(time.time()),
        "snapshot":   snapshot
    })
    try:
        mqtt_client.publish(MQTT_TOPIC, payload, qos=1)
        print(f"[ALERT] Published: {alert_state}")
    except Exception as e:
        print(f"[ALERT] MQTT publish failed: {e}")

# --- MAIN LOOP ---
def main():
    print(f"[Driver Monitor] Starting camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("[ERROR] Cannot open camera. Exiting.")
        return

    eye_tracker   = EyeTracker()
    yolo_detector = YoloDetector()

    print("[Driver Monitor] Running. Press Ctrl+C to stop.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Frame read failed.")
            break

        frame = cv2.flip(frame, 1)

        # --- EYE TRACKER ---
        eye_result  = eye_tracker.process(frame)

        # --- YOLO DETECTOR (τρέχει στο ίδιο frame) ---
        yolo_result = yolo_detector.process(frame)

        # --- STATE MACHINE ---
        face_detected = eye_result.get("face_detected", False) or yolo_result.get("person_detected", False)

        if face_detected:
            state["face_missing_since"] = None

            if not eye_result.get("calibrated"):
                state["current"] = "CALIBRATING"
            elif eye_result.get("eyes_closed") or yolo_result.get("head_down"):
                if state["eyes_closed_since"] is None:
                    state["eyes_closed_since"] = time.time()
                else:
                    elapsed = time.time() - state["eyes_closed_since"]
                    if elapsed > EYES_CLOSED_THRESHOLD:
                        alert_type = yolo_result.get("posture_type", "SLEEPING_ALERT")
                        new_state  = alert_type
                        print(f"[DEBUG MAIN] posture_type={alert_type} | current={state['current']}")
                        if state["current"] != new_state:
                            state["current"] = new_state
                            publish_alert(new_state, frame)
                        else:
                            state["eyes_closed_since"] = None
                            state["current"] = "NORMAL"
        else:
            state["eyes_closed_since"] = None
            if state["face_missing_since"] is None:
                state["face_missing_since"] = time.time()
            elif (time.time() - state["face_missing_since"]) > FACE_MISSING_TIMEOUT:
                new_state = "FACE_NOT_DETECTED"
                if state["current"] != new_state:
                    state["current"] = new_state
                    publish_alert(new_state, frame)

        # --- LOGGING ---
        print(f"[STATUS] {state['current']} | "
              f"EAR: {eye_result.get('ear', 0):.3f} | "
              f"HeadDown: {yolo_result.get('head_down')} | "
              f"PersonConf: {yolo_result.get('confidence', 0):.2f}",
              end='\r')
        

        

        time.sleep(0.03)  # ~30fps

    cap.release()
    print("\n[Driver Monitor] Stopped.")

if __name__ == "__main__":
    main()
