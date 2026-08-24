#!/usr/bin/env python3
"""
Script de reprise et d'amélioration d'entraînement YOLO11 sur dataset SoccerNet-v3 H250.
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHECKPOINT = ROOT / "runs" / "detect" / "yolo11n_h250_e50_b8" / "weights" / "last.pt"
DEFAULT_BEST_CHECKPOINT = ROOT / "runs" / "detect" / "yolo11n_h250_e50_b8" / "weights" / "best.pt"
DEFAULT_DATA = ROOT / "data" / "external" / "h250" / "YOLO" / "data.yaml"

def main():
    parser = argparse.ArgumentParser(description="Reprendre ou affiner l'entraînement du modèle de vision YOLO11 H250")
    parser.add_argument("--weights", type=Path, default=DEFAULT_CHECKPOINT, help="Chemin du checkpoint (.pt)")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Chemin du fichier data.yaml")
    parser.add_argument("--epochs", type=int, default=50, help="Nombre total d'époques")
    parser.add_argument("--batch", type=int, default=8, help="Taille de batch")
    parser.add_argument("--imgsz", type=int, default=1280, help="Taille des images")
    parser.add_argument("--patience", type=int, default=20, help="Patience pour le early stopping")
    parser.add_argument("--device", default="cpu", help="Device (cpu, 0, etc.)")
    parser.add_argument("--project", default=str(ROOT / "runs" / "detect"), help="Dossier de projet des résultats")
    parser.add_argument("--name", default="yolo11n_h250_resume", help="Nom de l'expérience")
    parser.add_argument("--resume", action="store_true", help="Reprendre proprement l'entraînement depuis le checkpoint")

    args = parser.parse_args()

    weights_path = str(args.weights)
    if not Path(weights_path).exists() and DEFAULT_BEST_CHECKPOINT.exists():
        weights_path = str(DEFAULT_BEST_CHECKPOINT)
        print(f"👉 Checkpoint principal introuvable. Bascule sur best.pt : {weights_path}")

    print("==================================================")
    print("      VISION FOOT - ENTRAÎNEMENT YOLOV11 (H250)    ")
    print("==================================================")
    print(f"Poids initiaux : {weights_path}")
    print(f"Dataset        : {args.data}")
    if args.resume:
        print("Mode           : REPRISE (Resume)")
        print(f"Époques Cibles : {args.epochs}")
    else:
        print("Mode           : NOUVEAU/FINE-TUNING (New/Fine-tuning)")
        print(f"Époques        : {args.epochs}")
        print(f"Batch Size     : {args.batch}")
        print(f"Image Size     : {args.imgsz}")
    print(f"Device         : {args.device}")
    print("==================================================\n")

    model = YOLO(weights_path)
    if args.resume:
        model.train(
            resume=True,
            device=args.device,
            epochs=args.epochs
        )
    else:
        model.train(
            data=str(args.data),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            patience=args.patience,
            device=args.device,
            project=args.project,
            name=args.name,
            exist_ok=True
        )

if __name__ == "__main__":
    main()
