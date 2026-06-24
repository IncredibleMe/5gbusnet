import sys
import time
import openzen

from gps_reader import GPSReader
from hazard_detector import HazardDetector

# Ports (αλλάζεις αν χρειαστεί)
GPS_PORT  = "/dev/ttyUSB1"
GPS_BAUD  = 115200

def main():
    print("[MAIN] Starting Road Hazard Detection System")
    print("[MAIN] =====================================")

    # 1. Ξεκίνα GPS reader σε background thread
    gps = GPSReader(port=GPS_PORT, baudrate=GPS_BAUD)
    gps.start()

    # 2. Αρχικοποίησε OpenZen για το LPMS UTTL2
    openzen.set_log_level(openzen.ZenLogLevel.Warning)
    error, client = openzen.make_client()
    if error != openzen.ZenError.NoError:
        print("[IMU] Error initializing OpenZen")
        sys.exit(1)

    # Αναζήτηση sensor
    print("[IMU] Scanning for LPMS sensor...")
    client.list_sensors_async()
    sensor_desc = None

    while True:
        event = client.wait_for_next_event()
        if event.event_type == openzen.ZenEventType.SensorFound:
            name = event.data.sensor_found.name
            print(f"[IMU] Found: {name}")
            if "LPMS" in name.upper():
                sensor_desc = event.data.sensor_found
        if event.event_type == openzen.ZenEventType.SensorListingProgress:
            if event.data.sensor_listing_progress.complete > 0:
                break

    if sensor_desc is None:
        print("[IMU] No sensor found. Check USB connection.")
        sys.exit(1)

    # Σύνδεση στο sensor
    error, sensor = client.obtain_sensor(sensor_desc)
    if error != openzen.ZenSensorInitError.NoError:
        print("[IMU] Error connecting to sensor")
        sys.exit(1)
    print("[IMU] Connected to LPMS sensor!")

    imu = sensor.get_any_component_of_type(openzen.component_type_imu)
    if imu is None:
        print("[IMU] No IMU component found")
        sys.exit(1)

    # Sampling rate (200 Hz είναι καλό για pothole detection)
    imu.set_int32_property(openzen.ZenImuProperty.SamplingRate, 200)
    error, freq = imu.get_int32_property(openzen.ZenImuProperty.SamplingRate)
    print(f"[IMU] Sampling rate: {freq} Hz")

    # 3. Αρχικοποίησε Hazard Detector
    detector = HazardDetector(gps_reader=gps)

    # Δώσε λίγο χρόνο στο GPS να πάρει fix
    print("[GPS] Waiting for GPS fix (up to 30s)...")
    for _ in range(30):
        lat, lon, fix = gps.get_position()
        if fix:
            print(f"[GPS] Fix acquired: lat={lat:.6f}, lon={lon:.6f}")
            break
        time.sleep(1)
    else:
        print("[GPS] No fix yet, continuing without GPS (events will show NO GPS FIX)")

    print("\n[MAIN] System running. Drive around to detect hazards!")
    print("[MAIN] Press Ctrl+C to stop.\n")

    # 4. Main loop: διάβαζε IMU events και πέρνα στον detector
    try:
        while True:
            zen_event = client.wait_for_next_event()

            if (zen_event.event_type == openzen.ZenEventType.ImuData and
                zen_event.sensor == imu.sensor and
                zen_event.component.handle == imu.component.handle):

                d = zen_event.data.imu_data
                imu_data = {
                    "timestamp":    d.timestamp,
                    "acceleration": list(d.a),
                    "gyro1":        list(d.g1),
                    "gyro2":        list(d.g2),
                    "magnetometer": list(d.b),
                }
                detector.process(imu_data)

    except KeyboardInterrupt:
        print("\n[MAIN] Stopping...")

    finally:
        gps.stop()
        sensor.release()
        client.close()
        print("[MAIN] Shutdown complete.")

if __name__ == "__main__":
    main()
