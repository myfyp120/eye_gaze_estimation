

# ═══════════════════════════════════════════════════════════════
# model/gaze_predictor.py
# Place in the UI repo's model/ folder
# ═══════════════════════════════════════════════════════════════
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as T
import numpy as np
import math
import sys
import os

ETH_REPO = "C:/Users/aqsam/eye_gaze_estimation/repo/ETH-XGaze"  

sys.path.insert(0, ETH_REPO)

try:
    from model import gaze_network
except ImportError as e:
    raise ImportError(
        f"Cannot import gaze_network from {ETH_REPO}.\n"
        f"Make sure ETH_REPO points to your cloned ETH-XGaze repo.\n"
        f"Original error: {e}")


class GazePredictor:
    """
    Real-time gaze predictor with few-shot FC fine-tuning calibration.

    FC layer in gaze_network:
        self.model.gaze_fc = nn.Sequential(nn.Linear(2048, 2))
        Parameters: 2×2048 weights + 2 biases = 4,098 total

    Few-shot calibration:
        Freezes all ResNet-50 backbone (25,557,032 params).
        Fine-tunes ONLY gaze_fc (4,098 params) on 9 face-gaze pairs.
        50 Adam steps at lr=1e-5. Takes ~5-10 seconds on CPU.
        Reduces MAE by ~1-3° for the specific person.
    """

    def __init__(self, ckpt_path, device=None):
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device    = torch.device(device)
        self.ckpt_path = ckpt_path

        # Load model
        self.model = gaze_network().to(self.device)

        # Issue 2 fix: try/except with clear error message
        try:
            ckpt = torch.load(ckpt_path, map_location=self.device,
                              weights_only=False)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Checkpoint not found: {ckpt_path}\n"
                f"Download best_mpii_ckpt.pth.tar from Google Drive.")

        if 'model_state' not in ckpt:
            available = list(ckpt.keys())
            raise KeyError(
                f"'model_state' not in checkpoint. "
                f"Available keys: {available}")

        self.model.load_state_dict(ckpt['model_state'])
        self.model.eval()

        # Save original FC weights for reset_calibration()
        self._save_original_fc()

        # Issue 3 fix: T.Resize added defensively even though
        # FaceDetector already returns 224x224. Protects against
        # any future change to detect_and_crop's target_size.
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
        ])

        self.is_calibrated = False
        print(f"[GazePredictor] Loaded | device={device} | "
              f"calibrated={self.is_calibrated}")

    def _save_original_fc(self):
        """Store original FC weights so reset_calibration() can restore them."""
        # gaze_fc is nn.Sequential(nn.Linear(2048, 2))
        fc = self.model.gaze_fc[0]  # the Linear layer inside Sequential
        self._orig_weight = fc.weight.data.clone()
        self._orig_bias   = fc.bias.data.clone()

    def _preprocess(self, face_bgr_224):
        """numpy (224,224,3) BGR uint8 → tensor (1,3,224,224) on device"""
        img = face_bgr_224[:, :, [2, 1, 0]].copy()  # BGR → RGB
        return self.transform(img).unsqueeze(0).to(self.device)

    def predict(self, face_bgr_224):
        """
        Input:  numpy (224,224,3) BGR uint8 face crop
        Output: (pitch, yaw) in radians
        If calibrated, gaze_fc is already adapted — result is corrected.
        """
        self.model.eval()
        tensor = self._preprocess(face_bgr_224)
        with torch.no_grad():
            out = self.model(tensor).cpu().numpy()[0]
        return float(out[0]), float(out[1])

    def predict_screen(self, face_bgr_224,
                        screen_w, screen_h,
                        dist_cm=60,
                        screen_w_cm=34,
                        screen_h_cm=19):
        """
        Input:  face crop + screen dimensions
        Output: (x_px, y_px) on screen where user is looking

        dist_cm:       eye-to-screen distance (measure with ruler)
        screen_w_cm:   physical screen width in cm
        screen_h_cm:   physical screen height in cm
        """
        pitch, yaw = self.predict(face_bgr_224)
        x_cm = dist_cm * math.tan(yaw)
        y_cm = dist_cm * math.tan(-pitch)  # flip: pitch up = y up
        x_px = int(screen_w / 2 + x_cm * (screen_w / screen_w_cm))
        y_px = int(screen_h / 2 + y_cm * (screen_h / screen_h_cm))
        x_px = max(0, min(screen_w - 1, x_px))
        y_px = max(0, min(screen_h - 1, y_px))
        return x_px, y_px

    def calibrate(self, face_crops_bgr, dot_positions_px,
                   screen_w, screen_h,
                   dist_cm=60, screen_w_cm=34, screen_h_cm=19,
                   epochs=50, lr=1e-5):
        """
        Few-shot FC fine-tuning calibration.

        Steps:
          1. Convert each dot pixel position → (pitch, yaw) ground truth
          2. Stack face crops into batch tensor
          3. Freeze ALL backbone parameters
          4. Unfreeze ONLY gaze_fc (4,098 parameters)
          5. Run 50 Adam steps minimizing L1 loss on those N samples
          6. Freeze everything, restore eval mode

        Parameters:
            face_crops_bgr  : list of (224,224,3) BGR numpy arrays
            dot_positions_px: list of (x_px, y_px) dot screen positions
            epochs          : fine-tuning steps (50 is enough for 9 samples)
            lr              : learning rate (keep at 1e-5 — very small)
        """
        assert len(face_crops_bgr) == len(dot_positions_px), \
            "Mismatch: face crops and dot positions must have same length"
        assert len(face_crops_bgr) >= 3, \
            f"Need at least 3 points, got {len(face_crops_bgr)}"

        # Issue 5 fix: initialize loss before loop
        loss = torch.tensor(0.0)

        # Step 1: convert dot pixels → gaze angles
        true_gazes = []
        for dot_x, dot_y in dot_positions_px:
            x_cm  = (dot_x - screen_w/2) * (screen_w_cm / screen_w)
            y_cm  = (dot_y - screen_h/2) * (screen_h_cm / screen_h)
            pitch = -math.atan2(y_cm, dist_cm)
            yaw   =  math.atan2(x_cm, dist_cm)
            true_gazes.append([pitch, yaw])

        # Step 2: prepare tensors
        imgs   = torch.cat([self._preprocess(f)
                            for f in face_crops_bgr])   # (N,3,224,224)
        labels = torch.tensor(true_gazes,
                              dtype=torch.float32).to(self.device)  # (N,2)

        # Step 3: freeze all parameters
        for param in self.model.parameters():
            param.requires_grad = False

        # Step 4: unfreeze ONLY gaze_fc
        # gaze_fc is nn.Sequential(nn.Linear(2048,2))
        for param in self.model.gaze_fc.parameters():
            param.requires_grad = True

        # Step 5: fine-tune
        self.model.train()
        optimizer = optim.Adam(
            self.model.gaze_fc.parameters(), lr=lr)
        criterion = nn.L1Loss()

        print(f"[Calibration] Fine-tuning FC on "
              f"{len(face_crops_bgr)} samples, {epochs} steps...")

        # Issue 4 fix: torch.enable_grad() guarantees gradients even
        # if this method is called from within a no_grad context
        with torch.enable_grad():
            for step in range(epochs):
                preds = self.model(imgs)
                loss  = criterion(preds, labels)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                if step % 10 == 0:
                    print(f"  step {step:3d}/{epochs} | "
                          f"loss: {loss.item():.5f}")

        # Step 6: restore eval mode, freeze everything
        for param in self.model.parameters():
            param.requires_grad = False
        self.model.eval()

        self.is_calibrated = True
        print(f"[Calibration] Done! Final loss: {loss.item():.5f}")

    def reset_calibration(self):
        """Restores original FC weights — undoes calibration."""
        fc = self.model.gaze_fc[0]
        fc.weight.data.copy_(self._orig_weight)
        fc.bias.data.copy_(self._orig_bias)
        self.is_calibrated = False
        print("[Calibration] Reset to pre-calibration weights")