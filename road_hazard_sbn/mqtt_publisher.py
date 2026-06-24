"""
MQTT Publisher για road hazard events.
Δημοσιεύει κάθε ανιχνευμένο hazard στο V2X MQTT broker, στο topic "road-safety-data".

Config μέσω environment variables (με fallback σε defaults από το SBN doc):
  MQTT_BROKER_HOST  : IP του MQTT broker (default: V2X broker, 10.143.100.71)
  MQTT_BROKER_PORT  : port του broker (default: 1883)
  MQTT_USERNAME     : username (default: 5gbusnet)
  MQTT_PASSWORD     : password (default: 5gbusnet2026)
  MQTT_TOPIC        : topic στο οποίο γίνεται publish (default: road-safety-data)
  MQTT_CLIENT_ID    : client id (default: road-hazard-publisher)

Σημείωση: Το doc του SBN αναφέρει δύο brokers, έναν γενικό (79.129.11.168, χρήστης
consumer_user, full access σε όλα τα topics) και τον V2X broker (10.143.100.71,
χρήστης 5gbusnet) που είναι αυτός που έχει ρητά αναφερόμενο το topic
"road-safety-data". Αυτό το module χρησιμοποιεί by default τον V2X broker, μιας
και το topic ανήκει εκεί. Αν χρειαστεί τελικά ο άλλος broker, αλλάζει μόνο με τα
env variables, χωρίς αλλαγή κώδικα.
"""

import os
import json
import time
import threading
import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "10.143.100.71")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "5gbusnet")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "5gbusnet2026")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "road-safety-data")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "road-hazard-publisher")
MQTT_CONNECT_TIMEOUT_SEC = float(os.environ.get("MQTT_CONNECT_TIMEOUT_SEC", "5"))

# Mapping από τα δικά μας hazard types στα types που δέχεται το SBN
# (ίδιο mapping με το sbn_client.py, ώστε REST και MQTT να συμφωνούν)
HAZARD_TYPE_MAP = {
    "POTHOLE": "POTHOLE",
    "SLIPPERY_ROAD": "SLIPPERY",
}

_client = None
_client_lock = threading.Lock()
_connected = False


def _utc_timestamp(epoch_seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _build_message(event):
    hazard_type = HAZARD_TYPE_MAP.get(event["type"], event["type"])

    message = {
        "type": hazard_type,
        "timestamp": _utc_timestamp(event["timestamp"]),
        "az": event.get("az"),
        "ax": event.get("ax"),
        "ay": event.get("ay"),
        "roll": event.get("roll"),
        "pitch": event.get("pitch"),
    }

    if event.get("gps_fix") and event.get("lat") is not None and event.get("lon") is not None:
        message["latitude"] = event["lat"]
        message["longitude"] = event["lon"]

    return message


def _get_client():
    """Lazy init, ώστε να μην ανοίγει σύνδεση αν δεν χρειάζεται ποτέ publish."""
    global _client, _connected

    with _client_lock:
        if _client is not None:
            return _client

        client = mqtt.Client(client_id=MQTT_CLIENT_ID)
        if MQTT_USERNAME:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        def _on_connect(c, userdata, flags, rc):
            global _connected
            if rc == 0:
                _connected = True
                print(f"[MQTT] Connected to {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            else:
                _connected = False
                print(f"[MQTT] Connection failed, rc={rc}")

        def _on_disconnect(c, userdata, rc):
            global _connected
            _connected = False
            print(f"[MQTT] Disconnected, rc={rc}")

        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect

        try:
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
            client.loop_start()
        except Exception as e:
            print(f"[MQTT] Could not connect to broker: {e}")
            return None

        _client = client
        return _client


def publish_hazard(event, async_send=True):
    """
    Δημοσιεύει το hazard event στο MQTT topic.

    event       : το dict που επιστρέφει HazardDetector.process()
    async_send  : αν True (default), το publish τρέχει σε ξεχωριστό thread ώστε
                  να μην μπλοκάρει το IMU loop. Βάλε False μόνο για debugging.
    """
    if async_send:
        t = threading.Thread(target=_do_publish, args=(event,), daemon=True)
        t.start()
        return t
    else:
        return _do_publish(event)


def _do_publish(event):
    client = _get_client()
    if client is None:
        print("[MQTT] No client available, skip publish")
        return None

    payload = json.dumps(_build_message(event))

    try:
        result = client.publish(MQTT_TOPIC, payload, qos=1)
        result.wait_for_publish(timeout=MQTT_CONNECT_TIMEOUT_SEC)
        if result.is_published():
            print(f"[MQTT] Published to '{MQTT_TOPIC}': {event['type']}")
        else:
            print(f"[MQTT] Publish did not confirm for: {event['type']}")
        return result
    except Exception as e:
        print(f"[MQTT] Failed to publish: {e}")
        return None
