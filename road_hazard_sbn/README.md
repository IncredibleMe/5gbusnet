# Road Hazard Module (SBN Integration)

Αυτό το folder είναι ένα fork του `road_hazard` module, με προσθήκη integration προς το SchoolBusNet (SBN) Telematics Alarm API. Το αρχικό `road_hazard` folder παραμένει αμετάβλητο, αυτό εδώ είναι ξεχωριστή, ανεξάρτητη έκδοση.

## Τι προσθέτει σε σχέση με το `road_hazard`

- **`sbn_client.py`**: νέο module, στέλνει POST request στο SBN telematics alarm endpoint κάθε φορά που ανιχνεύεται hazard (pothole, slippery road).
- **`hazard_detector.py`**: ίδιο με το αρχικό, με μία επιπλέον κλήση στο `sbn_client.send_alarm()` μετά την ανίχνευση κάθε event.

## Mapping τύπων hazard

| Module B type    | SBN type   |
|-------------------|------------|
| `POTHOLE`         | `POTHOLE`  |
| `SLIPPERY_ROAD`   | `SLIPPERY` |

## Setup

```bash
pip install -r requirements.txt
```

Πριν τρέξεις το `main.py`, όρισε τα παρακάτω environment variables:

```bash
export SBN_AUTH_TOKEN="<το bearer token από το SBN, χωρίς το 'Bearer ' μπροστά>"
export SBN_VEHICLE_ID="<το vehicleId που σου έδωσε το SBN για το PoC όχημα>"
```

Προαιρετικά:

```bash
export SBN_API_URL="https://5g.schoolbusnet.net/SBN-telematics-ws/telematicsapi/services/telematicsalarm"  # default
export SBN_TIMEOUT_SEC="3"   # timeout για το HTTP request, default 3 δευτερόλεπτα
```

## Σημαντικό για ασφάλεια

Το `SBN_AUTH_TOKEN` και τα credentials του SBN console δεν πρέπει ποτέ να μπουν σε commit μέσα στο repo (ούτε σε αυτό README, ούτε σε κώδικα). Χρησιμοποίησε πάντα environment variables ή ένα `.env` αρχείο που είναι στο `.gitignore`.

## Λειτουργία

Η κλήση `sbn_client.send_alarm()` τρέχει σε ξεχωριστό thread by default (`async_send=True`), έτσι ένα αργό network call δεν μπλοκάρει το IMU processing loop (που τρέχει στα 200Hz).

Αν το `SBN_AUTH_TOKEN` δεν έχει οριστεί, ο client απλά τυπώνει warning και κάνει skip το αποστολή, χωρίς να κάνει crash το σύστημα.
