import serial
import threading
import pynmea2
import time

class GPSReader:
    def __init__(self, port="/dev/ttyUSB1", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.lat = None
        self.lon = None
        self.fix = False
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"[GPS] Reader started on {self.port}")

    def stop(self):
        self._running = False

    def get_position(self):
        with self._lock:
            return self.lat, self.lon, self.fix

    def _read_loop(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            while self._running:
                try:
                    line = ser.readline().decode("ascii", errors="replace").strip()
                    if line.startswith("$GNRMC") or line.startswith("$GPRMC"):
                        msg = pynmea2.parse(line)
                        if msg.status == "A":  # A = valid fix
                            with self._lock:
                                self.lat = msg.latitude
                                self.lon = msg.longitude
                                self.fix = True
                        else:
                            with self._lock:
                                self.fix = False
                except pynmea2.ParseError:
                    pass
                except Exception as e:
                    print(f"[GPS] Read error: {e}")
                    time.sleep(0.5)
        except serial.SerialException as e:
            print(f"[GPS] Cannot open port {self.port}: {e}")
