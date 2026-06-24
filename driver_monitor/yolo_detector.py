from ultralytics import YOLO
import cv2

# Φορτώνουμε το μικρότερο μοντέλο για real-time απόδοση
model = YOLO("yolov8n-pose.pt")

# Κατώφλι εμπιστοσύνης
CONFIDENCE_THRESHOLD = 0.5

def is_head_down(keypoints):
    try:
        nose       = keypoints[0]
        l_shoulder = keypoints[5]
        r_shoulder = keypoints[6]

        if nose[2] < CONFIDENCE_THRESHOLD:
            return False

        shoulder_avg_y = (l_shoulder[1] + r_shoulder[1]) / 2
        nose_y         = nose[1]
        distance       = shoulder_avg_y - nose_y

        print(f"[DEBUG] nose_y={nose_y:.3f} | distance={distance:.3f}")

        # Λιποθυμία: μύτη πολύ χαμηλά
        if nose_y > 900:
            return True, "MEDICAL_EMERGENCY"

        # Κεφάλι σκυμμένο (νύσταγμα κλπ)
        if distance > 350:
            return True, "HEAD_DOWN"

        return False, "NORMAL"

    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        return False, "NORMAL"

class YoloDetector:
    def __init__(self):
        self.model = model

    def process(self, frame):
        """
        Επιστρέφει dict με:
          - person_detected: bool
          - head_down: bool
          - abnormal_posture: bool
          - confidence: float
        """
        results = self.model(frame, verbose=False)

        if not results or len(results[0].boxes) == 0:
            return {"person_detected": False, "head_down": False,
                    "abnormal_posture": False, "confidence": 0.0}

        # Παίρνουμε το πρώτο άτομο με την υψηλότερη εμπιστοσύνη
        boxes = results[0].boxes
        best_idx = int(boxes.conf.argmax())
        confidence = float(boxes.conf[best_idx])

        if confidence < CONFIDENCE_THRESHOLD:
            return {"person_detected": False, "head_down": False,
                    "abnormal_posture": False, "confidence": confidence}

        head_down = False
        if results[0].keypoints is not None:
            kps = results[0].keypoints.data[best_idx].cpu().numpy()
            # head_down = is_head_down(kps)

        head_down, posture_type = is_head_down(kps)

        return {
            "person_detected": True,
            "head_down": head_down,
            "posture_type": posture_type,
            "abnormal_posture": head_down,
            "confidence": confidence
        }
