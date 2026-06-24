# Road Hazard Detection

Sensor based road hazard detection for the 5G-BusNET system. The program reads motion data from an LPMS IMU and position data from a GPS receiver, then flags two kinds of road hazards in real time: potholes and slippery road conditions. Each detected hazard is tagged with the GPS coordinates where it happened.

## What each file does

`gps_reader.py` runs a background thread that opens the serial GPS, reads NMEA sentences, and parses the GNRMC and GPRMC messages with pynmea2. It keeps the most recent latitude, longitude and fix status behind a lock so the rest of the program can ask for the current position at any time.

`hazard_detector.py` takes one IMU sample at a time and decides whether a hazard occurred. A pothole is a sharp spike on the vertical (Z) axis compared to a short rolling baseline. A slippery road is strong sideways acceleration combined with a sudden gyro rotation. A cooldown stops the same event from firing many times in a row. When a hazard fires, it pulls the current GPS position and prints a formatted event.

`main.py` ties everything together. It starts the GPS reader, initialises OpenZen for the LPMS sensor at 200 Hz, waits up to 30 seconds for a GPS fix, then loops on incoming IMU events and passes each one to the detector.

## Hardware

You need two devices connected over USB:

1. An LPMS IMU (the code targets the LPMS family, for example the UTTL2). This is read through OpenZen.
2. A GPS receiver that outputs NMEA sentences on a serial port at 115200 baud.

## Requirements

Python 3.9 or newer is recommended. The Python packages used are:

```
pyserial
pynmea2
openzen
```

Install the first two with pip:

```bash
pip install pyserial pynmea2
```

OpenZen is the sensor library from LP-Research and is not a plain pip install in every environment. Use the OpenZen Python bindings from the official OpenZen releases and make sure `import openzen` works before running the program.

## Configuration

Two things usually need adjusting for your setup: the serial ports and the detection thresholds.

### Serial ports

The GPS port and baud rate are set near the top of `main.py`:

```python
GPS_PORT  = "/dev/ttyUSB1"
GPS_BAUD  = 115200
```

On Linux the GPS usually shows up as `/dev/ttyUSB0`, `/dev/ttyUSB1` and so on. On macOS it looks more like `/dev/tty.usbserial-XXXX` or `/dev/tty.usbmodemXXXX`. Change `GPS_PORT` to match the device you actually have. To list available ports on Linux you can run `ls /dev/ttyUSB*`, and on macOS `ls /dev/tty.*`.

The IMU is found automatically by OpenZen, so it does not need a port. The program scans for any sensor whose name contains "LPMS" and connects to it.

### Detection thresholds

The thresholds live at the top of `hazard_detector.py` and are meant to be tuned with live data:

```python
POTHOLE_Z_THRESHOLD     = 1.1   # g, vertical spike
SLIPPERY_XY_THRESHOLD   = 0.6   # g, lateral acceleration
SLIPPERY_GYRO_THRESHOLD = 4.0   # deg/s, sudden rotation
COOLDOWN_SEC            = 1.0   # seconds between events
```

Raise a threshold if you get false positives, lower it if real hazards are missed.

## Running it locally

From the project folder:

```bash
python main.py
```

What you should see on startup:

1. The GPS reader thread starts.
2. OpenZen scans for the LPMS sensor and connects to it.
3. The program waits for a GPS fix (up to 30 seconds). If no fix arrives it keeps going, and events will show "NO GPS FIX" instead of coordinates.
4. The main loop starts. Drive around (or shake the IMU) to trigger detections.

Press Ctrl+C to stop. On shutdown the GPS reader stops and the sensor and OpenZen client are released cleanly.

## Output

Each hazard prints a block like this:

```
=======================================================
  *** HAZARD DETECTED: POTHOLE ***
  Time      : 14:32:07
  Location  : lat=37.983810, lon=23.727539
  Accel Z   : +2.340 g
  Accel X/Y : +0.120 / +0.080 g
  Gyro R/P  : +1.200 / +0.900 deg/s
=======================================================
```

## Troubleshooting

If OpenZen reports no sensor found, check the USB connection and that `import openzen` works on its own. If the GPS never gets a fix, confirm the correct port in `main.py`, make sure the antenna has a clear view of the sky, and remember that a cold start can take a minute or more outdoors. If you see a "Cannot open port" message, another program may already be holding the serial port, or your user may not have permission to read it (on Linux, adding your user to the `dialout` group usually fixes the permission case).
