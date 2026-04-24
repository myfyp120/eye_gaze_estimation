# ═══════════════════════════════════════════════════════════════
# ui/calibration_screen.py
# ═══════════════════════════════════════════════════════════════
import math
import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QLabel, QProgressBar
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal
from PyQt6.QtGui     import QPainter, QColor, QBrush, QPen


class CalibrationScreen(QWidget):
    calibration_done   = pyqtSignal(list, list)  # (face_crops, dot_positions)
    calibration_failed = pyqtSignal(str)

    DOT_RADIUS = 18
    HOLD_MS    = 1500
    BLINK_MS   = 200

    def __init__(self, face_detector, cap):
        """
        Parameters:
            face_detector: FaceDetector instance (already initialized)
            cap:           existing cv2.VideoCapture from MainWindow
                           (Issue 10 fix: reuse instead of opening new one)
        """
        super().__init__()
        self.face_detector = face_detector
        self.cap           = cap        # shared cap — do NOT release here
        self.face_crops    = []
        self.dot_positions = []
        self.current_idx   = 0
        self.dot_visible   = True

        # Issue 9 fix: initialize dot coords before paintEvent can fire
        self.dot_x = 0
        self.dot_y = 0
        self.grid_positions = []

        self.setWindowTitle("Gaze Calibration")
        self.setStyleSheet("background-color: #1a1a2e;")

        self.label = QLabel("Look at the red dot and hold still", self)
        self.label.setStyleSheet(
            "color: #eee; font-size: 20px; font-family: Arial;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar(self)
        self.progress.setStyleSheet(
            "QProgressBar{background:#333;border-radius:4px;}"
            "QProgressBar::chunk{background:#e94560;}")
        self.progress.setMaximum(9)
        self.progress.setValue(0)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._capture_and_advance)

        self.showFullScreen()
        # Start dot grid after window is shown and slots are connected
        QTimer.singleShot(400, self._start)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.label.setGeometry(w//2 - 300, 20, 600, 40)
        self.progress.setGeometry(w//2 - 200, h - 50, 400, 24)

    def _start(self):
        w, h   = self.width(), self.height()
        margin = 120
        xs     = [margin, w//2, w - margin]
        ys     = [margin, h//2, h - margin]
        self.grid_positions = [(x, y) for y in ys for x in xs]
        self.progress.setMaximum(len(self.grid_positions))
        self._show_next_dot()

    def _show_next_dot(self):
        if self.current_idx >= len(self.grid_positions):
            self._finish()
            return
        self.dot_x, self.dot_y = self.grid_positions[self.current_idx]
        self.dot_visible = True
        self.update()
        self.timer.start(self.HOLD_MS)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1a1a2e"))

        # Guard: only draw if grid has started
        if self.dot_visible and self.grid_positions:
            # Outer ring
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = self.DOT_RADIUS + 6
            painter.drawEllipse(
                self.dot_x - r, self.dot_y - r, 2*r, 2*r)
            # Filled dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#e94560")))
            painter.drawEllipse(
                self.dot_x - self.DOT_RADIUS,
                self.dot_y - self.DOT_RADIUS,
                2*self.DOT_RADIUS, 2*self.DOT_RADIUS)
            # Center
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(self.dot_x-4, self.dot_y-4, 8, 8)
        painter.end()

    def _capture_and_advance(self):
        self.dot_visible = False
        self.update()

        ret, frame = self.cap.read()
        if ret:
            face = self.face_detector.detect_and_crop(frame)
            if face is not None:
                self.face_crops.append(face)
                self.dot_positions.append((self.dot_x, self.dot_y))

        self.current_idx += 1
        self.progress.setValue(self.current_idx)
        QTimer.singleShot(self.BLINK_MS, self._show_next_dot)

    def _finish(self):
        n = len(self.face_crops)
        if n >= 3:
            self.calibration_done.emit(
                self.face_crops, self.dot_positions)
        else:
            # Issue 8 fix: signal is emitted from _finish() which is called
            # via QTimer.singleShot(400,...) — by this point __init__ has
            # returned and slots are already connected. No race condition.
            self.calibration_failed.emit(
                f"Only {n}/9 faces detected. "
                "Ensure good lighting and face the camera directly.")
        self.close()

    # Do NOT release self.cap here — it belongs to MainWindow
    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)