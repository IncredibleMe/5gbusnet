# 5G-BusNET

A demonstration of a 5G enabled smart school bus monitoring system. The project is split into two independent modules that watch different things during a trip. One keeps an eye on the driver, the other keeps an eye on the road. Each module runs on its own and has its own setup guide.

## Modules

### Driver Monitoring System

Watches the driver through a camera and looks for drowsiness or a medical problem. It measures how open the eyes are with MediaPipe and reads head and body posture with a YOLO pose model, then raises an alert when something stays wrong for too long. Alerts can be published over MQTT with a snapshot.

Setup and run instructions: [driver_monitor/README.md](driver_monitor/README.md)

### Road Hazard Detection

Watches the road through motion and position sensors. It reads an LPMS IMU and a GPS receiver, then flags potholes and slippery road conditions in real time and tags each event with the coordinates where it happened.

Setup and run instructions: [road_hazard/README.md](road_hazard/README.md)

## Repository layout

```
5g-busnet/
├── README.md                  (this file)
├── road_hazard/
│   ├── README.md
│   ├── gps_reader.py
│   ├── hazard_detector.py
│   └── main.py
└── driver_monitor/
    ├── README.md
    ├── eye_tracker.py
    ├── yolo_detector.py
    ├── main.py
    ├── requirements.txt
    └── yolov8n-pose.pt
```

## Getting started

The two modules are separate programs with separate dependencies, so pick the one you want to run and follow its README. As a quick summary:

The Driver Monitoring System needs a camera and the packages in `driver_monitor/requirements.txt`, plus PyTorch pinned to 2.5.1. It runs with `python main.py` from inside the `driver_monitor` folder.

The Road Hazard Detection module needs an LPMS IMU and a GPS receiver over USB, along with pyserial, pynmea2 and the OpenZen bindings. It runs with `python main.py` from inside the `road_hazard` folder.

## Status

Both modules run locally with plain Python. The driver monitor can publish alerts over MQTT when a broker is available, but it also runs fine on its own and just prints to the console. The Docker files included with the driver monitor are for a containerised setup and are not required for the local workflow.
