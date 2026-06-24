"""
SBN Telematics Alarm Client
Στέλνει telematics alarms (potholes, slippery road, κλπ) στο SchoolBusNet API.

Config μέσω environment variables (με fallback σε defaults για local testing):
  SBN_API_URL      : endpoint του telematics alarm API
  SBN_AUTH_TOKEN    : bearer token (χωρίς το πρόθεμα "Bearer ")
  SBN_VEHICLE_ID    : vehicleId όπως αναγνωρίζεται στο SBN
  SBN_TIMEOUT_SEC   : timeout για το HTTP request (default 3s, μην το αφήσεις μεγάλο
                       γιατί μπλοκάρει το IMU processing loop αν καλείται synchronous)
"""

import os
import time
import threading
import requests

SBN_API_URL = os.environ.get(
    "SBN_API_URL",
    "https://5g.schoolbusnet.net/SBN-telematics-ws/telematicsapi/services/telematicsalarm",
)
SBN_AUTH_TOKEN = os.environ.get("SBN_AUTH_TOKEN", "")
SBN_VEHICLE_ID = os.environ.get("SBN_VEHICLE_ID", "NCC-1701-A")
SBN_TIMEOUT_SEC = float(os.environ.get("SBN_TIMEOUT_SEC", "3"))

# Mapping από τα δικά μας hazard types στα types που δέχεται το SBN
HAZARD_TYPE_MAP = {
    "POTHOLE": "POTHOLE",
    "SLIPPERY_ROAD": "SLIPPERY",
}


def _utc_timestamp(epoch_seconds):
    """Μετατρέπει unix timestamp σε UTC string τύπου YYYY-MM-DDTHH:mm:ssZ"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _build_payload(event, notes=None):
    sbn_type = HAZARD_TYPE_MAP.get(event["type"], event["type"])

    payload = {
        "vehicleId": SBN_VEHICLE_ID,
        "type": sbn_type,
        "resolved": False,
        "notes": notes or f"Auto detected by 5G BusNET Module B (az={event.get('az')}, ax={event.get('ax')}, ay={event.get('ay')})",
        "timestamp": _utc_timestamp(event["timestamp"]),
    }

    # lat/lon είναι optional στο SBN, οπότε τα στέλνουμε μόνο αν έχουμε fix
    if event.get("gps_fix") and event.get("lat") is not None and event.get("lon") is not None:
        payload["latitude"] = event["lat"]
        payload["longitude"] = event["lon"]

    return payload


def send_alarm(event, notes=None, async_send=True):
    """
    Στέλνει το hazard event στο SBN ως telematics alarm.

    event       : το dict που επιστρέφει HazardDetector.process()
    notes       : προαιρετικό custom μήνυμα (default περιγραφή με τα accel values)
    async_send  : αν True (default), το POST τρέχει σε ξεχωριστό thread ώστε
                  να μην μπλοκάρει το IMU loop. Βάλε False μόνο για debugging.
    """
    if not SBN_AUTH_TOKEN:
        print("[SBN] Warning: SBN_AUTH_TOKEN δεν έχει οριστεί, skip alarm send")
        return None

    payload = _build_payload(event, notes=notes)

    if async_send:
        t = threading.Thread(target=_post_alarm, args=(payload,), daemon=True)
        t.start()
        return t
    else:
        return _post_alarm(payload)


def _post_alarm(payload):
    headers = {
        "Authorization": f"Bearer {SBN_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            SBN_API_URL, json=payload, headers=headers, timeout=SBN_TIMEOUT_SEC
        )
        if resp.status_code in (200, 201, 202):
            print(f"[SBN] Alarm sent OK ({resp.status_code}): {payload['type']}")
        else:
            print(f"[SBN] Alarm rejected ({resp.status_code}): {resp.text[:200]}")
        return resp
    except requests.exceptions.RequestException as e:
        print(f"[SBN] Failed to send alarm: {e}")
        return None
