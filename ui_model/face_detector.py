# ═══════════════════════════════════════════════════════════════
# model/face_detector.py
# ═══════════════════════════════════════════════════════════════
import cv2
import numpy as np

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    print("⚠️  mediapipe not installed. Run: pip install mediapipe")


class FaceDetector:
    def __init__(self, min_confidence=0.7):
        if not _MP_AVAILABLE:
            raise RuntimeError("Install mediapipe: pip install mediapipe")
        mp_face = mp.solutions.face_detection
        self.detector = mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=min_confidence)

    def detect_and_crop(self, frame_bgr, target_size=224, margin=0.3):
        """
        Input:  full webcam frame (H, W, 3) BGR
        Output: face crop (target_size, target_size, 3) BGR, or None
        """
        h, w = frame_bgr.shape[:2]
        rgb    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Issue 7 fix: try/finally to prevent mediapipe handle leak
        try:
            result = self.detector.process(rgb)
        except Exception as e:
            print(f"[FaceDetector] Error: {e}")
            return None

        if not result.detections:
            return None

        det  = max(result.detections, key=lambda d: d.score[0])
        bbox = det.location_data.relative_bounding_box

        # Convert relative → pixel
        bx = int(bbox.xmin  * w)
        by = int(bbox.ymin  * h)
        bw = int(bbox.width  * w)
        bh = int(bbox.height * h)

        # Issue 6 fix: save original bbox coords BEFORE applying margin
        # so x2/y2 are computed from the unshifted origin
        mx = int(bw * margin)
        my = int(bh * margin)

        x1 = max(0, bx - mx)       # left edge with margin
        y1 = max(0, by - my)        # top edge with margin
        x2 = min(w, bx + bw + mx)  # right edge: uses original bx, not x1
        y2 = min(h, by + bh + my)  # bottom edge: uses original by, not y1

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        return cv2.resize(crop, (target_size, target_size),
                          interpolation=cv2.INTER_LINEAR)

    def close(self):
        self.detector.close()