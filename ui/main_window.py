# # from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QLabel)
# # from PyQt6.QtCore import Qt
# # from utils.colors import BG, TEXT_SEC
# # from ui.components.sidebar import Sidebar
# # from ui.screens.home_screen import HomeScreen
# # from ui.screens.settings_screen import SettingsScreen
# # from ui.screens.about_screen import AboutScreen

# # class MainWindow(QMainWindow):
# #     def __init__(self):
# #         super().__init__()
# #         self.setWindowTitle("Through the Iris")
# #         self.setMinimumSize(1000, 650)
# #         self._build_ui()

# #     def _build_ui(self):
# #         central = QWidget()
# #         self.setCentralWidget(central)

# #         layout = QHBoxLayout(central)
# #         layout.setContentsMargins(0, 0, 0, 0)
# #         layout.setSpacing(0)

# #         self.sidebar = Sidebar()
# #         self.sidebar.navigate.connect(self.navigate_to)

# #         self.stack = QStackedWidget()

# #         self.home_screen     = HomeScreen()
# #         self.settings_screen = SettingsScreen()

# #         # Wire settings save to home screen
# #         self.settings_screen.on_save = self._apply_settings

# #         self.stack.addWidget(self.home_screen)       # index 0

# #         dash = QLabel("Dashboard — Coming Soon")
# #         dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
# #         dash.setStyleSheet(f"color: {TEXT_SEC}; font-size: 20px;")
# #         self.stack.addWidget(dash)                   # index 1

# #         calib = QLabel("Calibration — Coming Soon")
# #         calib.setAlignment(Qt.AlignmentFlag.AlignCenter)
# #         calib.setStyleSheet(f"color: {TEXT_SEC}; font-size: 20px;")
# #         self.stack.addWidget(calib)                  # index 2

# #         self.stack.addWidget(self.settings_screen)   # index 3

# #         self.about_screen = AboutScreen()
# #         self.stack.addWidget(self.about_screen)      # index 4

# #         layout.addWidget(self.sidebar)
# #         layout.addWidget(self.stack)

# #         self.setStyleSheet(f"background-color: {BG};")

# #     def _apply_settings(self):
# #         s = self.settings_screen.get_trail_settings()
# #         self.home_screen.apply_trail_settings(
# #             trail_visible = s["trail_visible"],
# #             trail_length  = s["trail_length"],
# #         )
# #         f = self.settings_screen.get_fps_settings()
# #         self.home_screen.apply_fps_settings(
# #             fps_enabled = f["fps_enabled"],
# #             fps_cap     = f["fps_cap"],
# #         )

# #     def navigate_to(self, index):
# #         self.stack.setCurrentIndex(index)

# #     def closeEvent(self, event):
# #         self.home_screen.stop_camera()
# #         event.accept()

# from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout,
#                             QStackedWidget, QLabel)
# from PyQt6.QtCore import Qt
# from utils.colors import BG, TEXT_SEC
# from ui.components.sidebar import Sidebar
# from ui.screens.home_screen import HomeScreen
# from ui.screens.settings_screen import SettingsScreen
# from ui.screens.about_screen import AboutScreen
# from ui.screens.dashboard_screen import DashboardScreen


# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Through the Iris")
#         self.setMinimumSize(1000, 650)
#         self._build_ui()

#     def _build_ui(self):
#         central = QWidget()
#         self.setCentralWidget(central)

#         layout = QHBoxLayout(central)
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(0)

#         self.sidebar = Sidebar()
#         self.sidebar.navigate.connect(self.navigate_to)

#         self.stack = QStackedWidget()

#         self.home_screen      = HomeScreen()
#         self.dashboard_screen = DashboardScreen()
#         self.settings_screen  = SettingsScreen()
#         self.about_screen     = AboutScreen()

#         # Wire home screen camera to dashboard
#         self.home_screen.webcam_thread.frame_ready.connect(
#             self._on_frame
#         )

#         self.settings_screen.on_save = self._apply_settings

#         self.stack.addWidget(self.home_screen)       # index 0
#         self.stack.addWidget(self.dashboard_screen)  # index 1

#         calib = QLabel("Calibration — Coming Soon")
#         calib.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         calib.setStyleSheet(f"color: {TEXT_SEC}; font-size: 20px;")
#         self.stack.addWidget(calib)                  # index 2

#         self.stack.addWidget(self.settings_screen)   # index 3
#         self.stack.addWidget(self.about_screen)      # index 4

#         layout.addWidget(self.sidebar)
#         layout.addWidget(self.stack)

#         self.setStyleSheet(f"background-color: {BG};")

#     def _on_frame(self, frame):
#         # Push gaze data to dashboard from each frame
#         from model.model_interface import GazeEstimator
#         gaze_x, gaze_y = self.home_screen.estimator.predict(frame)
#         self.dashboard_screen.update_gaze(gaze_x, gaze_y)
#         # Sync FPS
#         fps_text = self.home_screen.fps_card.value_lbl.text()
#         try:
#             self.dashboard_screen.update_fps(float(fps_text))
#         except ValueError:
#             pass
#         # Sync duration
#         dur = self.home_screen.duration_card.value_lbl.text()
#         if ":" in dur:
#             parts = dur.split(":")
#             self.dashboard_screen.update_duration(int(parts[0]), int(parts[1]))

#     def _apply_settings(self):
#         s = self.settings_screen.get_trail_settings()
#         self.home_screen.apply_trail_settings(
#             trail_visible=s["trail_visible"],
#             trail_length=s["trail_length"],
#         )
#         f = self.settings_screen.get_fps_settings()
#         self.home_screen.apply_fps_settings(
#             fps_enabled=f["fps_enabled"],
#             fps_cap=f["fps_cap"],
#         )

#     def navigate_to(self, index):
#         self.stack.setCurrentIndex(index)

#     def closeEvent(self, event):
#         self.home_screen.stop_camera()
#         self.dashboard_screen.stop_session()
#         event.accept()

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QStackedWidget)
from PyQt6.QtCore import Qt
from utils.colors import BG
from ui.components.sidebar import Sidebar
from ui.screens.home_screen import HomeScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.about_screen import AboutScreen
from ui.screens.dashboard_screen import DashboardScreen
from ui.screens.calibration_screen import CalibrationScreen


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Through the Iris")
        self.setMinimumSize(1000, 650)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigate_to)

        self.stack = QStackedWidget()

        self.home_screen        = HomeScreen()
        self.dashboard_screen   = DashboardScreen()
        self.calibration_screen = CalibrationScreen()
        self.settings_screen    = SettingsScreen()
        self.about_screen       = AboutScreen()

        # Wire session start/stop to dashboard
        self.home_screen.on_session_start = self.dashboard_screen.start_session
        self.home_screen.on_session_stop  = self.dashboard_screen.stop_session

        # Wire gaze updates to dashboard
        self.home_screen.on_gaze_update = self._on_gaze_update

        # Wire calibration done signal
        self.calibration_screen.calibration_done.connect(
            self._on_calibration_done
        )

        self.settings_screen.on_save = self._apply_settings

        self.stack.addWidget(self.home_screen)          # index 0
        self.stack.addWidget(self.dashboard_screen)     # index 1
        self.stack.addWidget(self.calibration_screen)   # index 2
        self.stack.addWidget(self.settings_screen)      # index 3
        self.stack.addWidget(self.about_screen)         # index 4

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)

        self.setStyleSheet(f"background-color: {BG};")

    def _on_gaze_update(self, gaze_x, gaze_y, fps):
        self.dashboard_screen.update_gaze(gaze_x, gaze_y)
        self.dashboard_screen.update_fps(fps)
        dur = self.home_screen.duration_card.value_lbl.text()
        if ":" in dur:
            parts = dur.split(":")
            try:
                self.dashboard_screen.update_duration(
                    int(parts[0]), int(parts[1])
                )
            except ValueError:
                pass

    def _on_calibration_done(self, result):
        """Called when user clicks Done on the results screen."""
        # Store calibration result — wire to model later
        # self.home_screen.estimator.set_calibration(
        #     self.calibration_screen.get_manager()
        # )
        print(f"[Calibration] Done — accuracy: {result.accuracy}%")
        self.navigate_to(0)  # Go back to home
        self.sidebar.set_active(0)

    def _apply_settings(self):
        s = self.settings_screen.get_trail_settings()
        self.home_screen.apply_trail_settings(
            trail_visible=s["trail_visible"],
            trail_length=s["trail_length"],
        )
        f = self.settings_screen.get_fps_settings()
        self.home_screen.apply_fps_settings(
            fps_enabled=f["fps_enabled"],
            fps_cap=f["fps_cap"],
        )

    def navigate_to(self, index):
        self.stack.setCurrentIndex(index)

    def closeEvent(self, event):
        self.home_screen.stop_camera()
        self.dashboard_screen.stop_session()
        event.accept()