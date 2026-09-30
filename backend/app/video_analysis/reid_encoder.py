from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import torch
import torch.nn.functional as F

EXPECTED_PRTREID_MD5 = "9633825232bc89f23a94522c5561650e"
EXPECTED_PRTREID_SHA256 = "1304562c4c930a4a54bbf2d44e221eb911fe31408f6875c5058b2d6ed621cf3b"
DEFAULT_REID_CKPT_PATH = Path("/media/adriano/Windows/runs/reid/prtreid-soccernet-baseline.pth.tar")

# Sports-specific appearance embedding specification
EMBEDDING_DIM: int = 256
INPUT_HEIGHT: int = 256
INPUT_WIDTH: int = 128
IMAGENET_MEAN: tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: tuple[float, float, float] = (0.229, 0.224, 0.225)


def verify_checkpoint_hash(
    path: Path,
    expected_sha256: str = EXPECTED_PRTREID_SHA256,
    expected_md5: str = EXPECTED_PRTREID_MD5,
) -> tuple[str, str]:
    """Verifies SHA-256 and MD5 integrity of the ReID checkpoint."""
    if not path.is_file():
        raise FileNotFoundError(f"ReID checkpoint not found: {path}")

    sha256_hasher = hashlib.sha256()
    md5_hasher = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256_hasher.update(chunk)
            md5_hasher.update(chunk)

    sha256_digest = sha256_hasher.hexdigest()
    md5_digest = md5_hasher.hexdigest()

    if expected_sha256 and sha256_digest != expected_sha256:
        raise ValueError(
            f"PRTReID checkpoint SHA-256 mismatch!\nExpected: {expected_sha256}\nFound:    {sha256_digest}"
        )
    if expected_md5 and md5_digest != expected_md5:
        raise ValueError(
            f"PRTReID checkpoint MD5 mismatch!\nExpected: {expected_md5}\nFound:    {md5_digest}"
        )
    return sha256_digest, md5_digest


def extract_player_crop(
    frame: np.ndarray,
    bbox_xyxy: tuple[float, float, float, float] | list[float],
) -> np.ndarray:
    """
    Extracts a deterministic player crop from an original resolution BGR image.
    Strictly clips coordinates to image bounds. Never uses ground-truth data.
    """
    h_img, w_img = frame.shape[:2]
    x1 = int(round(max(0.0, min(float(w_img - 1), bbox_xyxy[0]))))
    y1 = int(round(max(0.0, min(float(h_img - 1), bbox_xyxy[1]))))
    x2 = int(round(max(0.0, min(float(w_img), bbox_xyxy[2]))))
    y2 = int(round(max(0.0, min(float(h_img), bbox_xyxy[3]))))

    if x2 <= x1 or y2 <= y1:
        # Fallback for degenerate boxes
        x2 = min(w_img, x1 + 1)
        y2 = min(h_img, y1 + 1)

    crop = frame[y1:y2, x1:x2].copy()
    if crop.size == 0:
        crop = np.zeros((INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=np.uint8)
    return crop


class PlayerAppearanceEncoder:
    """
    Sports-specific player appearance embedding model for BoT-SORT.
    Wraps the official SoccerNet baseline PRTReID (BPBReID with HRNet-32 backbone).

    Guarantees:
      - Deterministic eval mode (no dropout, fixed batchnorm)
      - No gradients (requires_grad = False)
      - Batching supported
      - 256-D L2-normalized unit embeddings
      - Strictly ignores role and team classification outputs (appearance ReID only)
    """

    def __init__(
        self,
        checkpoint_path: Path | str = DEFAULT_REID_CKPT_PATH,
        device: str | torch.device | None = None,
        batch_size: int = 32,
        verify_checksum: bool = True,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.batch_size = max(1, batch_size)
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        if verify_checksum:
            self.sha256, self.md5 = verify_checkpoint_hash(self.checkpoint_path)
        else:
            self.sha256, self.md5 = "skipped", "skipped"

        self._mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(1, 1, 3)
        self._std = np.array(IMAGENET_STD, dtype=np.float32).reshape(1, 1, 3)

        self._build_model()

    def _build_model(self) -> None:
        """Loads and builds the PRTReID bpbreid model from checkpoint."""
        try:
            from prtreid import models
        except ImportError as exc:
            raise RuntimeError(
                "Le modèle PRTReID exige le paquet prtreid installé dans .venv-reid."
            ) from exc

        ckpt = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
        cfg = ckpt["config"]

        # bpbreid uses num_classes=1343 from SoccerNet training set for classifier head shape
        use_gpu = self.device.type == "cuda"
        model = models.build_model(
            name="bpbreid",
            num_classes=1343,
            loss="softmax",
            pretrained=False,
            use_gpu=use_gpu,
            config=cfg,
        )

        state_dict = {k.replace("module.", ""): v for k, v in ckpt["state_dict"].items()}
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        for p in model.parameters():
            p.requires_grad = False

        model.to(self.device)
        self.model = model
        self.config = cfg

    def preprocess_crops(self, crops: list[np.ndarray]) -> torch.Tensor:
        """
        Preprocesses a list of BGR player crops into a normalized BCHW PyTorch tensor:
          - BGR -> RGB
          - Resize to (128, 256) via bilinear interpolation
          - ImageNet normalization: (x / 255.0 - mean) / std
          - Channel transpose: (H, W, C) -> (C, H, W)
        """
        tensors = []
        for crop in crops:
            if crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                crop = np.zeros((INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=np.uint8)
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (INPUT_WIDTH, INPUT_HEIGHT), interpolation=cv2.INTER_LINEAR)
            normalized = (resized.astype(np.float32) / 255.0 - self._mean) / self._std
            tensors.append(torch.from_numpy(normalized.transpose(2, 0, 1)))

        batch_tensor = torch.stack(tensors, dim=0)
        return batch_tensor.to(self.device, non_blocking=True)

    @torch.no_grad()
    def encode_crops(self, crops: list[np.ndarray]) -> np.ndarray:
        """
        Encodes a list of BGR image crops into L2-normalized 256-D appearance embeddings.
        Returns a float32 NumPy array of shape (N, 256).
        """
        if not crops:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

        embeddings_list: list[np.ndarray] = []
        n_total = len(crops)

        for start_idx in range(0, n_total, self.batch_size):
            batch_crops = crops[start_idx : start_idx + self.batch_size]
            batch_tensor = self.preprocess_crops(batch_crops)

            out = self.model(batch_tensor)
            # out[0] is dict with 'globl', 'bn_globl', etc.
            globl_features = out[0]["globl"]
            # Apply L2 normalization to unit hypersphere
            normalized_features = F.normalize(globl_features, p=2, dim=-1)
            embeddings_list.append(normalized_features.cpu().numpy().astype(np.float32))

        return np.concatenate(embeddings_list, axis=0)

    def encode_bboxes(
        self,
        frame: np.ndarray,
        bboxes_xyxy: list[tuple[float, float, float, float] | list[float]],
    ) -> np.ndarray:
        """Extracts crops from frame according to xyxy bboxes and encodes them."""
        if not bboxes_xyxy:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        crops = [extract_player_crop(frame, b) for b in bboxes_xyxy]
        return self.encode_crops(crops)

    def as_tracker_encoder(self) -> Callable[[np.ndarray, np.ndarray], list[np.ndarray | None]]:
        """
        Returns a callable conforming to Ultralytics BoT-SORT encoder interface:
          `encoder(img: np.ndarray, dets: np.ndarray) -> list[np.ndarray | None]`
        where dets is shape (N, 5), with first 4 columns being [x_center, y_center, width, height].
        """

        def _encoder(img: np.ndarray, dets: np.ndarray) -> list[np.ndarray | None]:
            if dets is None or len(dets) == 0:
                return []
            # dets[:, :4] is xywh (center_x, center_y, w, h)
            xc = dets[:, 0]
            yc = dets[:, 1]
            w = dets[:, 2]
            h = dets[:, 3]
            x1 = xc - w / 2.0
            y1 = yc - h / 2.0
            x2 = xc + w / 2.0
            y2 = yc + h / 2.0

            bboxes_xyxy = [
                (float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i]))
                for i in range(len(dets))
            ]
            crops = [extract_player_crop(img, b) for b in bboxes_xyxy]
            embeddings = self.encode_crops(crops)
            return [embeddings[i] for i in range(len(embeddings))]

        return _encoder
