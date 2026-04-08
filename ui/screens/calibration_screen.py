"""
CalibrationScreen
─────────────────
Fullscreen 9-point gaze calibration UI.

States:
IDLE       → shows intro card with Start button
COUNTDOWN  → 3-2-1 countdown before calibration begins
RUNNING    → shows dots one by one with animated ring
RESULTS    → shows accuracy + per-point breakdown
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtCore    import (Qt, QTimer, QRect, QPointF, QRectF, pyqtSignal)
from PyQt6.QtGui     import (QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient, QFont)
import qtawesome as qta

from model.calibration_manager import CalibrationManager, CALIB_POINTS
from utils.colors import (BG, SURFACE, PANEL, ACCENT, HIGHLIGHT, TEAL, TEXT_PRIMARY, TEXT_SEC)

# ── How long (ms) the user stares at each point ───────────
DWELL_MS      = 3000
TICK_MS       = 16          # ~60 fps animation tick
COUNTDOWN_SEC = 3


class _DotOverlay(QWidget):
    """
    Full-window overlay that draws:
    - dark background
    - animated ring countdown around the active dot
    - small ghost dots at completed positions
    - progress text
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._point_index   = 0
        self._progress      = 0.0    # 0 → 1 over DWELL_MS
        self._completed     = []     # indices of done points
        self._visible       = False

    def show_point(self, index: int):
        self._point_index = index
        self._progress    = 0.0
        self._visible     = True
        self.update()

    def set_progress(self, progress: float):
        self._progress = progress
        self.update()

    def mark_complete(self, index: int):
        if index not in self._completed:
            self._completed.append(index)
        self.update()

    def reset(self):
        self._completed = []
        self._progress  = 0.0
        self._visible   = False
        self.update()

    def _point_px(self, index: int):
        tx, ty = CALIB_POINTS[index]
        x = int(tx * self.width())
        y = int(ty * self.height())
        return x, y

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Semi-dark overlay
        bg = QColor(0, 0, 0, 210)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRect(0, 0, self.width(), self.height())

        if not self._visible:
            painter.end()
            return

        dot_r   = max(10, min(self.width(), self.height()) // 40)
        ring_r  = dot_r * 3

        # ── Completed ghost dots ──────────────────────
        for i in self._completed:
            if i == self._point_index:
                continue
            cx, cy = self._point_px(i)
            ghost  = QColor(TEAL)
            ghost.setAlpha(60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ghost)
            painter.drawEllipse(cx - dot_r//2, cy - dot_r//2,
                                dot_r, dot_r)

        # ── Active dot ────────────────────────────────
        cx, cy = self._point_px(self._point_index)

        # Outer glow
        glow = QRadialGradient(cx, cy, ring_r * 1.5)
        gc   = QColor(HIGHLIGHT)
        gc.setAlpha(40)
        glow.setColorAt(0, gc)
        gc2 = QColor(HIGHLIGHT)
        gc2.setAlpha(0)
        glow.setColorAt(1, gc2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        r_outer = int(ring_r * 1.5)
        painter.drawEllipse(cx - r_outer, cy - r_outer,
                            r_outer * 2, r_outer * 2)

        # Countdown ring (arc)
        pen_w = max(2, dot_r // 3)
        ring_color = QColor(TEAL)
        ring_color.setAlpha(200)
        painter.setPen(QPen(ring_color, pen_w,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span = int(self._progress * 360 * 16)
        rect = QRectF(cx - ring_r, cy - ring_r,
                      ring_r * 2, ring_r * 2)
        painter.drawArc(rect, 90 * 16, -span)

        # Background ring track
        track = QColor(ACCENT)
        track.setAlpha(80)
        painter.setPen(QPen(track, pen_w))
        painter.drawEllipse(rect)

        # Dot center
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(HIGHLIGHT))
        painter.drawEllipse(cx - dot_r, cy - dot_r,
                            dot_r * 2, dot_r * 2)

        # Inner white dot
        painter.setBrush(QColor(255, 255, 255, 220))
        inner = max(3, dot_r // 3)
        painter.drawEllipse(cx - inner, cy - inner,
                            inner * 2, inner * 2)

        # ── Progress text (top-center) ────────────────
        done  = len(self._completed)
        total = len(CALIB_POINTS)
        painter.setPen(QColor(TEXT_SEC))
        f = painter.font()
        f.setPointSize(max(9, min(self.width(), self.height()) // 60))
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            QRect(0, max(20, self.height() // 20), self.width(), 40),
            Qt.AlignmentFlag.AlignHCenter,
            f"Point {done + 1} of {total}  —  keep your eyes on the dot"
        )

        painter.end()


class CalibrationScreen(QWidget):
    """
    Embedded calibration screen (fits inside the main stacked widget).
    Emits `calibration_done` with the CalibrationResult when finished.
    """
    calibration_done = pyqtSignal(object)

    # ── States ────────────────────────────────────────────
    IDLE      = "idle"
    COUNTDOWN = "countdown"
    RUNNING   = "running"
    RESULTS   = "results"

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG};")

        self._manager       = CalibrationManager()
        self._state         = self.IDLE
        self._current_point = 0
        self._elapsed_ms    = 0
        self._countdown_val = COUNTDOWN_SEC
        self._result        = None

        # Animation timer
        self._timer = QTimer()
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

        # Countdown timer
        self._cd_timer = QTimer()
        self._cd_timer.setInterval(1000)
        self._cd_timer.timeout.connect(self._countdown_tick)

        self._build_ui()

    # ── Public API ────────────────────────────────────────
    def get_manager(self) -> CalibrationManager:
        """Return the manager so main_window can pass it to the model."""
        return self._manager

    # ── UI Build ──────────────────────────────────────────
    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setFixedHeight(48)
        self._header.setStyleSheet(f"""
            background-color: {SURFACE};
            border-bottom: 1px solid {ACCENT};
        """)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(20, 0, 20, 0)

        app_icon = QLabel()
        app_icon.setPixmap(
            qta.icon("fa5s.eye", color=HIGHLIGHT).pixmap(48, 48)
        )
        app_icon.setStyleSheet("background: transparent;")

        app_name = QLabel("THROUGH THE IRIS")
        app_name.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)

        self._page_lbl = QLabel("CALIBRATION")
        self._page_lbl.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 11px;
            letter-spacing: 2px;
            background: transparent;
        """)

        hl.addWidget(app_icon)
        hl.addSpacing(8)
        hl.addWidget(app_name)
        hl.addStretch()
        hl.addWidget(self._page_lbl)
        self._outer.addWidget(self._header)

        # Stacked content area
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {BG};")
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._outer.addWidget(self._content, 1)

        # Dot overlay (sits on top, hidden initially)
        self._overlay = _DotOverlay(self._content)
        self._overlay.hide()

        self._show_idle()

    # ── State: IDLE ───────────────────────────────────────
    def _show_idle(self):
        self._state = self.IDLE
        self._clear_content()
        self._overlay.hide()

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.setSpacing(20)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon("fa5s.crosshairs", color=TEAL).pixmap(64, 64)
        )
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")

        # Title
        title = QLabel("Eye Calibration")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: 28px;
            font-weight: bold;
            background: transparent;
        """)

        # Subtitle
        sub = QLabel(
            "Calibration maps your gaze to your screen.\n"
            "You will be shown 9 dots — stare at each one until it completes.\n"
            "Keep your head still and your eyes focused on the dot."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 13px;
            line-height: 1.6;
            background: transparent;
        """)

        # Info cards row
        info_row = QHBoxLayout()
        info_row.setSpacing(16)
        info_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for icon, label in [
            ("fa5s.th",         "9 Points"),
            ("fa5s.clock",      "~18 seconds"),
            ("fa5s.dot-circle", "2s per dot"),
        ]:
            card = self._info_chip(icon, label)
            info_row.addWidget(card)

        # Start button
        start_btn = QPushButton("  Begin Calibration")
        start_btn.setIcon(qta.icon("fa5s.play", color="#ffffff"))
        start_btn.setFixedSize(220, 48)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEAL};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: #00b894;
            }}
            QPushButton:pressed {{
                background-color: #00a381;
            }}
        """)
        start_btn.clicked.connect(self._start_countdown)

        center.addWidget(icon_lbl)
        center.addWidget(title)
        center.addWidget(sub)
        center.addLayout(info_row)
        center.addSpacing(10)
        center.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper.setLayout(center)
        self._content_layout.addWidget(wrapper, 1)

    # ── State: COUNTDOWN ──────────────────────────────────
    def _start_countdown(self):
        self._state         = self.COUNTDOWN
        self._countdown_val = COUNTDOWN_SEC
        self._clear_content()

        self._cd_lbl = QLabel(str(self._countdown_val))
        self._cd_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cd_lbl.setStyleSheet(f"""
            color: {TEAL};
            font-size: 96px;
            font-weight: bold;
            background: transparent;
        """)

        hint = QLabel("Get ready — keep your eyes on the dots")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 14px;
            background: transparent;
        """)

        col = QVBoxLayout()
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(16)
        col.addWidget(self._cd_lbl)
        col.addWidget(hint)

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper.setLayout(col)
        self._content_layout.addWidget(wrapper, 1)

        self._cd_timer.start()

    def _countdown_tick(self):
        self._countdown_val -= 1
        if self._countdown_val <= 0:
            self._cd_timer.stop()
            self._start_calibration()
        else:
            self._cd_lbl.setText(str(self._countdown_val))

    # ── State: RUNNING ────────────────────────────────────
    def _start_calibration(self):
        self._state         = self.RUNNING
        self._current_point = 0
        self._elapsed_ms    = 0
        self._manager.start()

        self._clear_content()

        # Overlay fills the content area
        self._overlay.setGeometry(0, 0, self._content.width(), self._content.height())
        self._overlay.reset()
        self._overlay.show()
        self._overlay.raise_()

        self._advance_point()
        self._timer.start()

    def _advance_point(self):
        self._elapsed_ms = 0
        self._manager.begin_point(self._current_point)
        self._overlay.show_point(self._current_point)

    def _tick(self):
        if self._state != self.RUNNING:
            return

        self._elapsed_ms += TICK_MS

        # Feed a mock sample (replace with real model prediction later)
        # ── WIRE REAL MODEL HERE ──────────────────────────
        # raw_x, raw_y = real_model.predict(current_frame)
        tx, ty = CALIB_POINTS[self._current_point]
        noise_x = (hash((self._current_point, self._elapsed_ms, 1)) % 100 - 50) / 2000
        noise_y = (hash((self._current_point, self._elapsed_ms, 2)) % 100 - 50) / 2000
        mock_raw_x = tx + noise_x
        mock_raw_y = ty + noise_y
        self._manager.add_sample(mock_raw_x, mock_raw_y)
        # ─────────────────────────────────────────────────

        progress = min(1.0, self._elapsed_ms / DWELL_MS)
        self._overlay.set_progress(progress)

        if self._elapsed_ms >= DWELL_MS:
            self._manager.end_point()
            self._overlay.mark_complete(self._current_point)
            self._current_point += 1

            if self._current_point >= len(CALIB_POINTS):
                self._timer.stop()
                result = self._manager.compute()
                self._show_results(result)
            else:
                self._advance_point()

    # ── State: RESULTS ────────────────────────────────────
    def _show_results(self, result):
        self._state  = self.RESULTS
        self._result = result
        self._overlay.hide()
        self._clear_content()

        scroll_col = QVBoxLayout()
        scroll_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_col.setSpacing(20)
        scroll_col.setContentsMargins(40, 30, 40, 30)

        # Icon + title
        if result.success:
            icon_name  = "fa5s.check-circle"
            icon_color = TEAL
            title_text = "Calibration Complete"
        else:
            icon_name  = "fa5s.exclamation-circle"
            icon_color = HIGHLIGHT
            title_text = "Calibration Incomplete"

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon(icon_name, color=icon_color).pixmap(56, 56)
        )
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")

        title_lbl = QLabel(title_text)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: 26px;
            font-weight: bold;
            background: transparent;
        """)

        msg_lbl = QLabel(result.message)
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_lbl.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 13px;
            background: transparent;
        """)

        # Accuracy ring card
        acc_card = self._accuracy_card(result.accuracy)

        # Per-point error grid
        grid_lbl = QLabel("PER-POINT ACCURACY")
        grid_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_lbl.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
        """)

        point_grid = self._point_grid(result.point_errors)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        recalib_btn = QPushButton("  Recalibrate")
        recalib_btn.setIcon(qta.icon("fa5s.redo", color="#ffffff"))
        recalib_btn.setFixedSize(180, 44)
        recalib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        recalib_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border: 1px solid {TEAL}55;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {PANEL};
                border: 1px solid {TEAL};
            }}
        """)
        recalib_btn.clicked.connect(self._show_idle)

        done_btn = QPushButton("  Done")
        done_btn.setIcon(qta.icon("fa5s.check", color="#ffffff"))
        done_btn.setFixedSize(180, 44)
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEAL};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #00b894;
            }}
        """)
        done_btn.clicked.connect(lambda: self.calibration_done.emit(result))

        btn_row.addWidget(recalib_btn)
        btn_row.addWidget(done_btn)

        scroll_col.addWidget(icon_lbl)
        scroll_col.addWidget(title_lbl)
        scroll_col.addWidget(msg_lbl)
        scroll_col.addWidget(acc_card, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_col.addWidget(grid_lbl)
        scroll_col.addWidget(point_grid, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_col.addLayout(btn_row)

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper.setLayout(scroll_col)
        self._content_layout.addWidget(wrapper, 1)

    # ── Helpers ───────────────────────────────────────────
    def _accuracy_card(self, accuracy: float) -> QWidget:
        """Circular accuracy display."""
        class _AccuracyRing(QWidget):
            def __init__(self, pct):
                super().__init__()
                self._pct = pct
                self.setFixedSize(140, 140)

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Background circle
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(PANEL))
                painter.drawEllipse(5, 5, 130, 130)

                # Track
                track = QColor(ACCENT)
                track.setAlpha(80)
                painter.setPen(QPen(track, 10))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(15, 15, 110, 110)

                # Arc
                color = (TEAL if self._pct >= 75
                        else "#f39c12" if self._pct >= 50
                        else HIGHLIGHT)
                painter.setPen(QPen(QColor(color), 10,
                                    Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap))
                span = int(self._pct / 100 * 360 * 16)
                painter.drawArc(QRectF(15, 15, 110, 110), 90*16, -span)

                # Text
                painter.setPen(QColor(color))
                f = painter.font()
                f.setPointSize(22)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(QRect(0, 0, 140, 140), Qt.AlignmentFlag.AlignCenter, f"{int(self._pct)}%")

                painter.end()

        card = QWidget()
        card.setStyleSheet("background: transparent;")
        col  = QVBoxLayout(card)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(6)

        ring = _AccuracyRing(accuracy)
        lbl  = QLabel("ACCURACY")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
        """)
        col.addWidget(ring, alignment=Qt.AlignmentFlag.AlignCenter)
        col.addWidget(lbl)
        return card

    def _point_grid(self, errors) -> QWidget:
        """3x3 grid showing per-point accuracy."""
        class _GridWidget(QWidget):
            def __init__(self, errs):
                super().__init__()
                self._errors = errs
                self.setFixedSize(240, 240)

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                cell  = 80
                pad   = 6
                max_e = max(self._errors) if max(self._errors) > 0 else 0.1

                for i, err in enumerate(self._errors):
                    row = i // 3
                    col = i  % 3
                    x   = col * cell
                    y   = row * cell

                    quality = 1 - min(err / max_e, 1)
                    if quality > 0.7:
                        color = QColor(TEAL)
                    elif quality > 0.4:
                        color = QColor("#f39c12")
                    else:
                        color = QColor(HIGHLIGHT)

                    bg = QColor(color)
                    bg.setAlpha(int(30 + quality * 80))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(bg)
                    painter.drawRoundedRect(x+pad, y+pad,
                                            cell-pad*2, cell-pad*2, 6, 6)

                    painter.setPen(QPen(color, 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(x+pad, y+pad,
                                            cell-pad*2, cell-pad*2, 6, 6)

                    # Dot
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(color)
                    cx = x + cell//2
                    cy = y + cell//2
                    painter.drawEllipse(cx-6, cy-6, 12, 12)

                painter.end()

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        col = QVBoxLayout(w)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(_GridWidget(errors), alignment=Qt.AlignmentFlag.AlignCenter)

        legend_row = QHBoxLayout()
        legend_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legend_row.setSpacing(16)
        for color, label in [(TEAL, "Good"), ("#f39c12", "OK"), (HIGHLIGHT, "Poor")]:
            chip = QLabel(f"● {label}")
            chip.setStyleSheet(f"""
                color: {color};
                font-size: 11px;
                background: transparent;
            """)
            legend_row.addWidget(chip)
        col.addLayout(legend_row)
        return w

    def _info_chip(self, icon_name: str, label: str) -> QWidget:
        chip = QWidget()
        chip.setStyleSheet(f"""
            QWidget {{
                background-color: {PANEL};
                border-radius: 8px;
                border: 1px solid {ACCENT}88;
            }}
        """)
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon(icon_name, color=TEAL).pixmap(14, 14)
        )
        icon_lbl.setStyleSheet("background: transparent; border: none;")

        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: 12px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)
        return chip

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def resizeEvent(self, event):
        self._overlay.setGeometry(0, 0, self._content.width(), self._content.height())
        super().resizeEvent(event)