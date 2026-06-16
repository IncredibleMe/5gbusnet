# Driver Monitoring System

Real time driver monitoring for the 5G-BusNET system. The program reads the driver camera and watches for signs of drowsiness or a medical problem. It combines two methods on every frame: eye tracking with MediaPipe to measure how open the eyes are, and pose detection with YOLO to read head and body posture. When something looks wrong for long enough, it raises an alert and (optionally) publishes it over MQTT with a snapshot.

These notes cover running everything locally with plain Python. Docker is not used here, so the broker and the container setup are skipped for now.

## What each file does

`eye_tracker.py` uses MediaPipe Face Mesh to find the eyes and compute the Eye Aspect Ratio (EAR). It calibrates for the first 100 frames to learn your normal open eye value, then sets the closed eye threshold at 60 percent of that average. After calibration it reports whether the eyes are closed on each frame.

`yolo_detector.py` runs the `yolov8n-pose.pt` model to find the person and their pose keypoints. From the nose and shoulder positions it decides between three states: NORMAL, HEAD_DOWN (head dropped, for example dozing off) and MEDICAL_EMERGENCY (nose very low in the frame, which suggests slumping or fainting).

`main.py` is the loop that runs the camera, calls both detectors on each frame, and runs the state machine. If eyes are closed or the head is down for longer than the threshold, it fires the matching alert. If no face or person is seen for too long, it fires FACE_NOT_DETECTED. Alerts are published over MQTT when a broker is reachable.

`anoymaly_detection.py` is a separate MQTT subscriber for IMU data. It is not part of the camera pipeline and is not needed to run the driver monitor.

`requirements.txt` lists the Python packages. The Docker files (`Dockerfile`, `docker-compose.yml`, `mosquitto.conf`) are for the containerised setup and are not used in the local workflow described here.

## Requirements

Python 3.10 or 3.11 works well. Create a virtual environment, then install the packages:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` contains:

```
opencv-python-headless==4.9.0.80
mediapipe==0.10.14
ultralytics==8.2.0
paho-mqtt==2.1.0
numpy==1.26.4
```

One extra step matters. Ultralytics pulls in PyTorch, and newer PyTorch versions break with this Ultralytics version. Pin PyTorch to 2.5.1 to avoid the model loading error:

```bash
pip install torch==2.5.1
```

The YOLO weights file `yolov8n-pose.pt` should sit next to `yolo_detector.py` so the model loads on startup.

## Selecting the camera

This is the part you asked about. The camera is chosen by an index number. The relevant lines in `main.py` are:

```python
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
...
cap = cv2.VideoCapture(CAMERA_INDEX)
```

Index `0` is almost always the built in webcam. An external USB camera usually shows up as index `1`, and if you have more than one extra camera you might also try `2`.

You have two ways to switch cameras.

Option 1, no code change. Set the environment variable when you launch:

```bash
CAMERA_INDEX=1 python main.py
```

Option 2, change the default in the code. Edit the line in `main.py` and replace the `0` with the index you want:

```python
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))   # default to the external camera
```

A note for macOS (Apple Silicon included): camera indices can be inconsistent, so if index 1 does not open, try 2, then 0. On a Mac you can also force the AVFoundation backend, which sometimes behaves better:

```python
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
```

If you are not sure which index maps to which camera, the quickest check is to open each index in turn and see which feed appears. The first time you run it, macOS will also ask for camera permission, so allow it for your terminal or IDE.

## MQTT (optional for local runs)

The program tries to connect to a broker on startup, but it does not need one. If the connection fails it prints a message and keeps running without publishing, so you can do all the detection work locally with no broker at all.

The broker settings come from environment variables, with these defaults in `main.py`:

```python
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "busnet/driver/alert")
```

The default broker name `mqtt_broker` only resolves inside the Docker network. For a local run you have two choices. Either ignore MQTT entirely (detection still works and alerts just print to the console), or run a local broker and point the program at it:

```bash
# install and start mosquitto locally, then:
MQTT_BROKER=localhost python main.py
```

## Running it locally

With the virtual environment active and the camera chosen:

```bash
python main.py
```

The first 100 frames are calibration, so look at the camera with your eyes open and normal for a few seconds. After that the threshold is set and monitoring begins.

You can combine the camera and broker settings on one line:

```bash
CAMERA_INDEX=1 MQTT_BROKER=localhost python main.py
```

Press Ctrl+C to stop.

## Tuning the detection

A few values control how sensitive the system is.

In `main.py`:

```python
EYES_CLOSED_THRESHOLD = 2.5   # seconds eyes must stay closed before an alert
FACE_MISSING_TIMEOUT  = 3.0   # seconds with no face before FACE_NOT_DETECTED
```

In `eye_tracker.py` the closed eye threshold is set during calibration as `avg * 0.60`. Lower the multiplier to make it less likely to flag closed eyes, raise it to make it more sensitive.

In `yolo_detector.py` the posture decision uses the nose position in the frame:

```python
if nose_y > 900:        # very low, treated as MEDICAL_EMERGENCY
if distance > 350:      # head dropped relative to shoulders, treated as HEAD_DOWN
```

These pixel values depend on your camera resolution and how the driver sits, so calibrate them with the live debug output. The detector already prints `nose_y` and `distance` on each frame, which makes it easy to read off the right numbers for your camera and seating position.

## Status output

While running, the program prints a one line status that updates in place:

```
[STATUS] NORMAL | EAR: 0.312 | HeadDown: False | PersonConf: 0.91
```

When an alert fires you will also see lines such as `[ALERT] Published: HEAD_DOWN` if a broker is connected.

## Troubleshooting

If the camera will not open, the index is the usual cause, so work through the camera selection steps above. If you get a PyTorch or model loading error from Ultralytics, confirm that torch is pinned to 2.5.1. If MediaPipe fails to install, check that your Python version is 3.10 or 3.11, since the pinned MediaPipe build does not cover every newer version. If MQTT prints a connection warning, that is expected on a local run without a broker and it does not stop detection.
