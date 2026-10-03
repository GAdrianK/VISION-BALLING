"""Calibration Adapters for External Football Field Calibrators.

Provides a common interface for football pitch camera calibration while strictly
isolating third-party code and licensing constraints (e.g. GPL-2.0 in PnLCalib).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np

try:
    from app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
        invert_homography,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
        invert_homography,
    )

logger = logging.getLogger(__name__)


class BaseCalibrationAdapter(ABC):
    """Abstract base class for football pitch calibration adapters."""

    def __init__(self, pitch_dimensions: Optional[PitchDimensions] = None) -> None:
        self.pitch_dimensions = pitch_dimensions or PitchDimensions()

    @abstractmethod
    def calibrate_image(
        self,
        image_path: Union[str, Path],
        frame_index: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> PitchCalibrationResult:
        """Calibrate camera on a single image and return PitchCalibrationResult."""
        pass

    @abstractmethod
    def calibrate_batch(
        self,
        image_paths: List[Union[str, Path]],
        frame_indices: Optional[List[int]] = None,
    ) -> List[PitchCalibrationResult]:
        """Calibrate camera on a sequence/batch of images."""
        pass


class PnLCalibAdapter(BaseCalibrationAdapter):
    """Isolated external adapter for PnLCalib (GPL-2.0).

    To maintain licensing separation, PnLCalib is never imported directly into
    VISION-BALLING core modules. All invocations execute in an isolated environment.
    """

    def __init__(
        self,
        pnlcalib_root: Optional[Union[str, Path]] = None,
        weights_kp: Optional[Union[str, Path]] = None,
        weights_lines: Optional[Union[str, Path]] = None,
        python_bin: Optional[Union[str, Path]] = None,
        kp_threshold: float = 0.1,
        line_threshold: float = 0.1,
        max_reproj_err: float = 50.0,
        pitch_dimensions: Optional[PitchDimensions] = None,
    ) -> None:
        super().__init__(pitch_dimensions=pitch_dimensions)
        self.pnlcalib_root = Path(pnlcalib_root or os.getenv("PNLCALIB_ROOT", "/tmp/pnlcalib"))
        self.weights_kp = Path(weights_kp or os.getenv("PNLCALIB_WEIGHTS_KP", "/media/adriano/Windows/runs/calibration/pnlcalib/weights/SV_kp"))
        self.weights_lines = Path(weights_lines or os.getenv("PNLCALIB_WEIGHTS_LINES", "/media/adriano/Windows/runs/calibration/pnlcalib/weights/SV_lines"))
        self.python_bin = Path(python_bin or os.getenv("PNLCALIB_PYTHON_BIN", "/media/adriano/Windows/venvs/vision-balling-pnlcalib/bin/python"))
        self.kp_threshold = kp_threshold
        self.line_threshold = line_threshold
        self.max_reproj_err = max_reproj_err

    def calibrate_image(
        self,
        image_path: Union[str, Path],
        frame_index: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> PitchCalibrationResult:
        results = self.calibrate_batch([image_path], frame_indices=[frame_index] if frame_index is not None else None)
        if results:
            res = results[0]
            if timestamp is not None:
                res.timestamp = timestamp
            return res
        return PitchCalibrationResult(
            frame_index=frame_index,
            timestamp=timestamp,
            valid=False,
            source_calibrator="PnLCalib",
            pitch_dimensions=self.pitch_dimensions,
        )

    def calibrate_batch(
        self,
        image_paths: List[Union[str, Path]],
        frame_indices: Optional[List[int]] = None,
    ) -> List[PitchCalibrationResult]:
        """Calibrate a list of images via the isolated PnLCalib worker."""
        if not image_paths:
            return []

        indices = frame_indices or list(range(len(image_paths)))
        str_paths = [str(p) for p in image_paths]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as req_file:
            req_path = req_file.name
            json.dump({"images": str_paths, "indices": indices}, req_file)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as out_file:
            out_path = out_file.name

        try:
            worker_code = f"""
import sys, os, json, torch, yaml
from PIL import Image
import numpy as np
import torchvision.transforms as T
import torchvision.transforms.functional as f

sys.path.insert(0, '{self.pnlcalib_root}')

from model.cls_hrnet import get_cls_net
from model.cls_hrnet_l import get_cls_net as get_cls_net_l
from utils.utils_heatmap import get_keypoints_from_heatmap_batch_maxpool, get_keypoints_from_heatmap_batch_maxpool_l, coords_to_dict, complete_keypoints
from utils.utils_calib import FramebyFrameCalib

with open('{req_path}') as rf:
    req = json.load(rf)

image_paths = req['images']
indices = req['indices']

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
cfg = yaml.safe_load(open('{self.pnlcalib_root}/config/hrnetv2_w48.yaml'))
cfg_l = yaml.safe_load(open('{self.pnlcalib_root}/config/hrnetv2_w48_l.yaml'))

m_kp = get_cls_net(cfg).to(device)
m_kp.load_state_dict(torch.load('{self.weights_kp}', map_location=device))
m_kp.eval()

m_l = get_cls_net_l(cfg_l).to(device)
m_l.load_state_dict(torch.load('{self.weights_lines}', map_location=device))
m_l.eval()

transform = T.Resize((540, 960))
results = []

for idx, p in zip(indices, image_paths):
    try:
        image = Image.open(p)
        img_t = f.to_tensor(image).float().to(device).unsqueeze(0)
        img_t = img_t if img_t.size()[-1] == 960 else transform(img_t)
        b, c, h, w = img_t.size()

        with torch.no_grad():
            heatmaps = m_kp(img_t)
            heatmaps_l = m_l(img_t)

        kp_coords = get_keypoints_from_heatmap_batch_maxpool(heatmaps[:, :-1, :, :])
        line_coords = get_keypoints_from_heatmap_batch_maxpool_l(heatmaps_l[:, :-1, :, :])
        kp_dict = coords_to_dict(kp_coords, threshold={self.kp_threshold})
        lines_dict = coords_to_dict(line_coords, threshold={self.line_threshold})
        kp_dict, lines_dict = complete_keypoints(kp_dict[0], lines_dict[0], w=w, h=h)

        cam = FramebyFrameCalib(w, h)
        cam.update(kp_dict, lines_dict)
        final_params = cam.heuristic_voting(refine=False, refine_lines=True)

        if final_params and final_params.get('rep_err', 999.0) <= {self.max_reproj_err}:
            cp = final_params['cam_params']
            pos = np.array(cp['position_meters'])
            rot = np.array(cp['rotation_matrix'])
            Q = np.array([[cp['x_focal_length'], 0, cp['principal_point'][0]],
                          [0, cp['y_focal_length'], cp['principal_point'][1]],
                          [0, 0, 1]])
            It = np.eye(4)[:-1]
            It[:, -1] = -pos
            P = Q @ (rot @ It)

            H_pitch2img = P[:, [0, 1, 3]]
            H_img2pitch = np.linalg.inv(H_pitch2img)

            results.append({{
                "frame_index": idx,
                "valid": True,
                "homography_image_to_pitch": H_img2pitch.tolist(),
                "homography_pitch_to_image": H_pitch2img.tolist(),
                "camera_parameters": cp,
                "reprojection_error_px": float(final_params.get('rep_err', 0.0)),
            }})
        else:
            results.append({{
                "frame_index": idx,
                "valid": False,
                "reprojection_error_px": float(final_params.get('rep_err', 999.0)) if final_params else None,
            }})
    except Exception as e:
        results.append({{
            "frame_index": idx,
            "valid": False,
            "error": str(e)
        }})

with open('{out_path}', 'w') as of:
    json.dump(results, of)
"""
            cmd = [str(self.python_bin), "-c", worker_code]
            ret = subprocess.run(cmd, capture_output=True, text=True, check=True)

            with open(out_path) as rf:
                raw_results = json.load(rf)

            parsed: List[PitchCalibrationResult] = []
            for item in raw_results:
                if item.get("valid"):
                    h_i2p = np.array(item["homography_image_to_pitch"], dtype=np.float64)
                    h_p2i = np.array(item["homography_pitch_to_image"], dtype=np.float64)
                    res = PitchCalibrationResult(
                        frame_index=item.get("frame_index"),
                        valid=True,
                        homography_image_to_pitch=h_i2p,
                        homography_pitch_to_image=h_p2i,
                        camera_parameters=item.get("camera_parameters"),
                        reprojection_error_px=item.get("reprojection_error_px"),
                        source_calibrator="PnLCalib",
                        pitch_dimensions=self.pitch_dimensions,
                    )
                else:
                    res = PitchCalibrationResult(
                        frame_index=item.get("frame_index"),
                        valid=False,
                        reprojection_error_px=item.get("reprojection_error_px"),
                        source_calibrator="PnLCalib",
                        pitch_dimensions=self.pitch_dimensions,
                    )
                parsed.append(res)
            return parsed
        finally:
            if os.path.exists(req_path):
                os.remove(req_path)
            if os.path.exists(out_path):
                os.remove(out_path)


class TVCalibAdapter(BaseCalibrationAdapter):
    """Isolated external adapter for TVCalib (MIT)."""

    def __init__(
        self,
        tvcalib_root: Optional[Union[str, Path]] = None,
        checkpoint: Optional[Union[str, Path]] = None,
        python_bin: Optional[Union[str, Path]] = None,
        optim_steps: int = 500,
        pitch_dimensions: Optional[PitchDimensions] = None,
    ) -> None:
        super().__init__(pitch_dimensions=pitch_dimensions)
        self.tvcalib_root = Path(tvcalib_root or os.getenv("TVCALIB_ROOT", "/tmp/tvcalib"))
        self.checkpoint = Path(checkpoint or os.getenv("TVCALIB_CHECKPOINT", "/media/adriano/Windows/runs/calibration/tvcalib/weights/train_59.pt"))
        self.python_bin = Path(python_bin or os.getenv("TVCALIB_PYTHON_BIN", "/media/adriano/Windows/venvs/vision-balling-tvcalib/bin/python"))
        self.optim_steps = optim_steps

    def calibrate_image(
        self,
        image_path: Union[str, Path],
        frame_index: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> PitchCalibrationResult:
        results = self.calibrate_batch([image_path], frame_indices=[frame_index] if frame_index is not None else None)
        if results:
            res = results[0]
            if timestamp is not None:
                res.timestamp = timestamp
            return res
        return PitchCalibrationResult(
            frame_index=frame_index,
            timestamp=timestamp,
            valid=False,
            source_calibrator="TVCalib",
            pitch_dimensions=self.pitch_dimensions,
        )

    def calibrate_batch(
        self,
        image_paths: List[Union[str, Path]],
        frame_indices: Optional[List[int]] = None,
    ) -> List[PitchCalibrationResult]:
        """Calibrate a list of images via the isolated TVCalib worker."""
        if not image_paths:
            return []

        indices = frame_indices or list(range(len(image_paths)))
        str_paths = [str(p) for p in image_paths]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as req_file:
            req_path = req_file.name
            json.dump({"images": str_paths, "indices": indices}, req_file)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as out_file:
            out_path = out_file.name

        try:
            worker_code = f"""
import sys, os, json, torch
from functools import partial
from PIL import Image
import numpy as np
import torchvision.transforms as T

sys.path.insert(0, '{self.tvcalib_root}')

from SoccerNet.Evaluation.utils_calibration import SoccerPitch
from tvcalib.cam_modules import SNProjectiveCamera
from tvcalib.module import TVCalibModule
from tvcalib.cam_distr.tv_main_center import get_cam_distr
from sn_segmentation.src.custom_extremities import generate_class_synthesis, get_line_extremities
from tvcalib.utils.objects_3d import SoccerPitchLineCircleSegments, SoccerPitchSNCircleCentralSplit
from tvcalib.inference import InferenceSegmentationModel, InferenceDatasetCalibration
from tvcalib.sncalib_dataset import custom_list_collate

with open('{req_path}') as rf:
    req = json.load(rf)

image_paths = req['images']
indices = req['indices']

device = 'cuda' if torch.cuda.is_available() else 'cpu'
seg_model = InferenceSegmentationModel('{self.checkpoint}', device)

fn_generate_class_synthesis = partial(generate_class_synthesis, radius=4)
fn_get_line_extremities = partial(get_line_extremities, maxdist=30, width=455, height=256, num_points_lines=4, num_points_circles=8)

tfms = T.Compose([
    T.Resize((256, 455)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

object3d = SoccerPitchLineCircleSegments(device=device, base_field=SoccerPitchSNCircleCentralSplit())
results = []

for idx, p in zip(indices, image_paths):
    try:
        image = Image.open(p).convert('RGB')
        w, h = image.size
        img_t = tfms(image).unsqueeze(0).to(device)

        with torch.no_grad():
            masks = seg_model.inference(img_t)

        mask_np = masks[0].cpu().numpy().astype(np.uint8)
        skeleton = fn_generate_class_synthesis(mask_np)
        keypoints = fn_get_line_extremities(skeleton)

        dataset_calib = InferenceDatasetCalibration([keypoints], w, h, object3d)
        dataloader_calib = torch.utils.data.DataLoader(dataset_calib, batch_size=1, collate_fn=custom_list_collate)
        x_dict = next(iter(dataloader_calib))

        model_calib = TVCalibModule(
            object3d,
            get_cam_distr(1.96, 1, 1),
            None,
            (h, w),
            optim_steps={self.optim_steps},
            device=device,
            log_per_step=False
        )

        per_sample_loss, cam_out, _ = model_calib.self_optim_batch(x_dict)
        h_raster = cam_out.get_homography_raster().detach().cpu().numpy()[0]
        # h_raster is image_to_pitch mapping
        h_p2i = np.linalg.inv(h_raster)
        raw_params = cam_out.get_parameters(1)
        cam_params = {{
            "pan_degrees": float(raw_params["pan_degrees"].item()),
            "tilt_degrees": float(raw_params["tilt_degrees"].item()),
            "roll_degrees": float(raw_params["roll_degrees"].item()),
            "position_meters": raw_params["position_meters"].detach().cpu().numpy().reshape(-1).tolist(),
            "x_focal_length": float(raw_params["x_focal_length"].item()),
            "y_focal_length": float(raw_params["y_focal_length"].item()),
            "principal_point": raw_params["principal_point"].detach().cpu().numpy().reshape(-1).tolist(),
            "radial_distortion": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "tangential_distortion": [0.0, 0.0],
            "thin_prism_distortion": [0.0, 0.0, 0.0, 0.0],
        }}

        results.append({{
            "frame_index": idx,
            "valid": True,
            "homography_image_to_pitch": h_raster.tolist(),
            "homography_pitch_to_image": h_p2i.tolist(),
            "camera_parameters": cam_params,
            "reprojection_error_px": float(per_sample_loss.get("loss_ndc_lines", torch.tensor(0.0)).mean().item() * h),
        }})
    except Exception as e:
        results.append({{
            "frame_index": idx,
            "valid": False,
            "error": str(e)
        }})

with open('{out_path}', 'w') as of:
    json.dump(results, of)
"""
            cmd = [str(self.python_bin), "-c", worker_code]
            ret = subprocess.run(cmd, capture_output=True, text=True, check=True)

            with open(out_path) as rf:
                raw_results = json.load(rf)

            parsed: List[PitchCalibrationResult] = []
            for item in raw_results:
                if item.get("valid"):
                    h_i2p = np.array(item["homography_image_to_pitch"], dtype=np.float64)
                    h_p2i = np.array(item["homography_pitch_to_image"], dtype=np.float64)
                    res = PitchCalibrationResult(
                        frame_index=item.get("frame_index"),
                        valid=True,
                        homography_image_to_pitch=h_i2p,
                        homography_pitch_to_image=h_p2i,
                        camera_parameters=item.get("camera_parameters"),
                        reprojection_error_px=item.get("reprojection_error_px"),
                        source_calibrator="TVCalib",
                        pitch_dimensions=self.pitch_dimensions,
                    )
                else:
                    res = PitchCalibrationResult(
                        frame_index=item.get("frame_index"),
                        valid=False,
                        reprojection_error_px=item.get("reprojection_error_px"),
                        source_calibrator="TVCalib",
                        pitch_dimensions=self.pitch_dimensions,
                    )
                parsed.append(res)
            return parsed
        finally:
            if os.path.exists(req_path):
                os.remove(req_path)
            if os.path.exists(out_path):
                os.remove(out_path)
