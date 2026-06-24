import time
import collections

import sbn_client

class HazardDetector:
    

    # Thresholds (αρχικές τιμές, calibrate με live data)
    POTHOLE_Z_THRESHOLD   = 1.1   # g  (κατακόρυφο spike)
    SLIPPERY_XY_THRESHOLD = 0.6   # g  (πλευρική επιτάχυνση)
    SLIPPERY_GYRO_THRESHOLD = 4.0 # deg/s (απότομη στροφή)

    # Cooldown για να μην πυροδοτούμε συνεχόμενα events για το ίδιο hazard
    COOLDOWN_SEC = 1.0

    def __init__(self, gps_reader):
        self.gps = gps_reader
        self._last_event_time = 0
        self._accel_history = collections.deque(maxlen=10)  # για baseline

    def process(self, imu_data):
        """
        Καλείται για κάθε IMU sample.
        imu_data: dict με keys acceleration, gyro1, gyro2
        Επιστρέφει event dict αν ανιχνευτεί hazard, αλλιώς None.
        """
        accel = imu_data.get("acceleration", [0, 0, 0])
        gyro1 = imu_data.get("gyro1", [0, 0, 0])

        ax, ay, az = accel[0], accel[1], accel[2]
        roll  = gyro1[0]
        pitch = gyro1[1]

        # Κρατάμε ιστορικό για baseline Z (σε ηρεμία ≈ 1g λόγω βαρύτητας)
        self._accel_history.append(az)

        now = time.time()
        if now - self._last_event_time < self.COOLDOWN_SEC:
            return None

        hazard_type = None

        # Pothole: spike στον Z άξονα πάνω από threshold
        # Αφαιρούμε το baseline (≈ μέση τιμή Z σε ηρεμία)
        if len(self._accel_history) >= 5:
            baseline_z = sum(list(self._accel_history)[:-1]) / (len(self._accel_history) - 1)
            z_delta = abs(az - baseline_z)
            if z_delta > self.POTHOLE_Z_THRESHOLD:
                hazard_type = "POTHOLE"

        # Slippery road: έντονη πλευρική επιτάχυνση + gyro spike
        if hazard_type is None:
            lateral_accel = max(abs(ax), abs(ay))
            gyro_spike    = max(abs(roll), abs(pitch))
            if lateral_accel > self.SLIPPERY_XY_THRESHOLD and gyro_spike > self.SLIPPERY_GYRO_THRESHOLD:
                hazard_type = "SLIPPERY_ROAD"

        if hazard_type is None:
            return None

        # Παίρνουμε GPS position
        lat, lon, fix = self.gps.get_position()
        self._last_event_time = now

        event = {
            "type":      hazard_type,
            "timestamp": now,
            "lat":       lat,
            "lon":       lon,
            "gps_fix":   fix,
            "az":        round(az, 4),
            "ax":        round(ax, 4),
            "ay":        round(ay, 4),
            "roll":      round(roll, 4),
            "pitch":     round(pitch, 4),
        }

        self._print_event(event)
        sbn_client.send_alarm(event)
        return event

    def _print_event(self, event):
        ts  = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
        loc = (
            f"lat={event['lat']:.6f}, lon={event['lon']:.6f}"
            if event["gps_fix"]
            else "NO GPS FIX"
        )
        print(f"\n{'='*55}")
        print(f"  *** HAZARD DETECTED: {event['type']} ***")
        print(f"  Time      : {ts}")
        print(f"  Location  : {loc}")
        print(f"  Accel Z   : {event['az']:+.3f} g")
        print(f"  Accel X/Y : {event['ax']:+.3f} / {event['ay']:+.3f} g")
        print(f"  Gyro R/P  : {event['roll']:+.3f} / {event['pitch']:+.3f} deg/s")
        print(f"{'='*55}\n")
