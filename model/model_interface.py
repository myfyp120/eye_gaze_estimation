import time
import numpy as np

class GazeEstimator:
    def __init__(self):
        self.model_loaded = False
        self._load_model()

    def _load_model(self):
        try:
            # ── When your model is ready, load it here ──
            # from model.gaze_model import GazeModel
            # self.model = GazeModel()
            # self.model.eval()
            # self.model_loaded = True
            pass
        except Exception as e:
            print(f"Model not loaded, running in demo mode: {e}")

    def predict(self, frame):
        if self.model_loaded:
            pass
        else:
            # Fake gaze output — moves in a circle
            t = time.time()
            x = 0.5 + 0.3 * np.sin(t)
            y = 0.5 + 0.3 * np.cos(t)
            return (x, y)