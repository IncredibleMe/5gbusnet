# Road Hazard Detection (SBN Integration)

Sensor based road hazard detection for the 5G-BusNET system, with the addition of automatic alarm reporting to the SchoolBusNet (SBN) telematics platform. The program reads motion data from an LPMS IMU and position data from a GPS receiver, flags two kinds of road hazards in real time (potholes and slippery road conditions), tags each one with GPS coordinates, and sends it to SBN as a telematics alarm.

This folder is a standalone version of the `road_hazard` module. The original `road_hazard` folder is untouched, this one adds the SBN reporting layer on top of the same detection logic.

## What each file does

`gps_reader_sbn.py` runs a background thread that opens the serial GPS, reads NMEA sentences, and parses the GNRMC and GPRMC messages with pynmea2. It keeps the most recent latitude, longitude and fix status behind a lock so the rest of the program can ask for the current position at any time.

`hazard_detector_sbn.py` takes one IMU sample at a time and decides whether a hazard occurred. A pothole is a sharp spike on the vertical (Z) axis compared to a short rolling baseline. A slippery road is strong sideways acceleration combined with a sudden gyro rotation. A cooldown stops the same event from firing many times in a row. When a hazard fires, it pulls the current GPS position, prints a formatted event, and calls `sbn_client.send_alarm()` to report it to SBN.

`sbn_client.py` builds the alarm payload (mapping the internal hazard type to the type SBN expects, converting the timestamp to UTC, including lat/lon only when a GPS fix is available) and sends it as a POST request to the SBN telematics alarm endpoint. The send happens on a separate thread by default, so a slow network call never blocks the IMU loop.

`main_sbn.py` ties everything together. It starts the GPS reader, initialises OpenZen for the LPMS sensor at 200 Hz, waits up to 30 seconds for a GPS fix, then loops on incoming IMU events and passes each one to the detector.

`libOpenZen.so` and `openzen.cpython-311-x86_64-linux-gnu.so` are the native OpenZen bindings needed to talk to the LPMS sensor. They need to sit in the same folder as `main_sbn.py` (see Configuration below).

## Hardware

You need two devices connected over USB:

1. An LPMS IMU (the code targets the LPMS family, for example the UTTL2). This is read through OpenZen.
2. A GPS receiver that outputs NMEA sentences on a serial port at 115200 baud (Quectel LC76G in this project).

## Requirements

Python 3.11 is recommended, matching the bundled OpenZen binary (`cpython-311`). The Python packages used are:

```
pyserial
pynmea2
requests
openzen
```

Install with pip:

```bash
pip install -r requirements.txt
```

OpenZen is the sensor library from LP-Research and is not a plain pip install in every environment. The `.so` files in this folder are the manually built bindings already matched to this project's setup, so as long as they stay alongside `main_sbn.py`, `import openzen` should work without a separate install.

## Configuration

Three things usually need adjusting for your setup: the serial ports, the detection thresholds, and the SBN credentials.

### Serial ports

The GPS port and baud rate are set near the top of `main_sbn.py`:

```python
GPS_PORT  = "/dev/ttyUSB1"
GPS_BAUD  = 115200
```

On Linux the GPS usually shows up as `/dev/ttyUSB0`, `/dev/ttyUSB1` and so on. On macOS it looks more like `/dev/tty.usbserial-XXXX` or `/dev/tty.usbmodemXXXX`. Change `GPS_PORT` to match the device you actually have. To list available ports on Linux you can run `ls /dev/ttyUSB*`, and on macOS `ls /dev/tty.*`.

The IMU is found automatically by OpenZen, so it does not need a port. The program scans for any sensor whose name contains "LPMS" and connects to it.

### Detection thresholds

The thresholds live at the top of `hazard_detector_sbn.py` and are meant to be tuned with live data:

```python
POTHOLE_Z_THRESHOLD     = 1.1   # g, vertical spike
SLIPPERY_XY_THRESHOLD   = 0.6   # g, lateral acceleration
SLIPPERY_GYRO_THRESHOLD = 4.0   # deg/s, sudden rotation
COOLDOWN_SEC            = 1.0   # seconds between events
```

Raise a threshold if you get false positives, lower it if real hazards are missed.

### SBN credentials

Set these environment variables before running:

```bash
export SBN_AUTH_TOKEN="<bearer token from SBN, without the leading 'Bearer '>"
export SBN_VEHICLE_ID="<the vehicleId SBN assigned to this PoC vehicle>"
```

Optional, with sensible defaults if left unset:

```bash
export SBN_API_URL="https://5g.schoolbusnet.net/SBN-telematics-ws/telematicsapi/services/telematicsalarm"
export SBN_TIMEOUT_SEC="3"
```

If `SBN_AUTH_TOKEN` is not set, the client prints a warning and skips sending (it does not crash the rest of the system).

### Hazard type mapping

| Internal type | SBN type |
|---|---|
| `POTHOLE` | `POTHOLE` |
| `SLIPPERY_ROAD` | `SLIPPERY` |

## Running it locally

OpenZen needs the current directory on the library path to find `libOpenZen.so`, so run it like this from inside the project folder:

```bash
LD_LIBRARY_PATH=. python3 main_sbn.py
```

What you should see on startup:

1. The GPS reader thread starts.
2. OpenZen scans for the LPMS sensor and connects to it. Scanning picks up every serial device, IMU and GPS alike, so the code filters by name and only connects to the one containing "LPMS".
3. The program waits for a GPS fix (up to 30 seconds). If no fix arrives it keeps going, and events will show "NO GPS FIX" instead of coordinates.
4. The main loop starts. Drive around (or shake the IMU) to trigger detections, each one is printed locally and also sent to SBN.

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

followed by a line confirming whether the SBN alarm was sent successfully, for example:

```
[SBN] Alarm sent OK (201): POTHOLE
```

## Troubleshooting

If OpenZen reports no sensor found, check the USB connection and that `import openzen` works on its own (with `LD_LIBRARY_PATH=.` set). If the GPS never gets a fix, confirm the correct port in `main_sbn.py`, make sure the antenna has a clear view of the sky, and remember that a cold start can take a minute or more outdoors. If you see a "Cannot open port" message, another program may already be holding the serial port, or your user may not have permission to read it (on Linux, adding your user to the `dialout` group usually fixes the permission case).

If alarms are not reaching SBN, check that `SBN_AUTH_TOKEN` is actually set in the shell you are running from (it does not persist across terminal sessions unless added to your shell profile), and watch the console for `[SBN]` log lines describing the failure (rejected status code, network error, or missing token).

## Security note

Never commit `SBN_AUTH_TOKEN` or any SBN console credentials into this repo, in code or in documentation. Always use environment variables, or a `.env` file excluded via `.gitignore`.
