import cv2
import mediapipe as mp
import math

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

LEFT_EYE  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def euclidean_distance(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def calculate_ear(landmarks):
    def eye_aspect_ratio(eye_indices):
        v1 = euclidean_distance(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        v2 = euclidean_distance(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        h  = euclidean_distance(landmarks[eye_indices[0]], landmarks[eye_indices[3]])
        return (v1 + v2) / (2.0 * h) if h != 0 else 0
    return (eye_aspect_ratio(LEFT_EYE) + eye_aspect_ratio(RIGHT_EYE)) / 2.0

class EyeTracker:
    def __init__(self):
        self.is_calibrated    = False
        self.calibration_frames = 0
        self.total_ear_sum    = 0.0
        self.EAR_THRESHOLD    = 0.0
        self.CALIBRATION_LIMIT = 100

    def process(self, frame):
        """
        Επιστρέφει dict με:
          - ear: float
          - eyes_closed: bool
          - calibrated: bool
          - face_detected: bool
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            return {"face_detected": False, "eyes_closed": False,
                    "ear": 0.0, "calibrated": self.is_calibrated}

        landmarks = results.multi_face_landmarks[0].landmark
        ear = calculate_ear(landmarks)

        if not self.is_calibrated:
            self.total_ear_sum += ear
            self.calibration_frames += 1
            if self.calibration_frames >= self.CALIBRATION_LIMIT:
                avg = self.total_ear_sum / self.CALIBRATION_LIMIT
                self.EAR_THRESHOLD = avg * 0.60
                self.is_calibrated = True
                print(f"[EyeTracker] Calibrated. Threshold: {self.EAR_THRESHOLD:.3f}")
            return {"face_detected": True, "eyes_closed": False,
                    "ear": ear, "calibrated": False}

        eyes_closed = ear < self.EAR_THRESHOLD
        return {"face_detected": True, "eyes_closed": eyes_closed,
                "ear": ear, "calibrated": True}
