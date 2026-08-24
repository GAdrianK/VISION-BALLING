#!/usr/bin/env python3
"""Lance ou reprend un entraînement YOLO11 sur SoccerNet H250."""

import argparse
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHECKPOINT = (
    ROOT
    / "runs"
    / "detect"
    / "yolo11n_h250_e50_b8"
    / "weights"
    / "last.pt"
)
DEFAULT_DATA = ROOT / "data" / "external" / "h250" / "YOLO" / "data.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Entraîner YOLO11 sur SoccerNet H250"
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="Poids initiaux. Par défaut : yolo11n.pt, ou last.pt avec --resume",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help="Chemin du fichier data.yaml",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Nombre total d'époques pour un nouvel entraînement",
    )
    parser.add_argument("--batch", type=int, default=8, help="Taille de batch")
    parser.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="Taille des images",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=20,
        help="Patience pour l'arrêt anticipé",
    )
    parser.add_argument(
        "--device",
        default="0",
        help="Périphérique : 0, cpu, mps, etc.",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--project",
        type=Path,
        default=ROOT / "runs" / "detect",
        help="Dossier des résultats",
    )
    parser.add_argument("--name", default="yolo11n_h250_e50_b8")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reprendre un entraînement interrompu depuis last.pt",
    )
    parser.add_argument(
        "--exist-ok",
        action="store_true",
        help="Autoriser la réutilisation d'un dossier d'expérience existant",
    )
    parser.add_argument(
        "--amp",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--deterministic",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser.parse_args()


def resolve_weights(args: argparse.Namespace) -> str:
    if args.resume:
        checkpoint = args.weights or DEFAULT_CHECKPOINT
        if not checkpoint.is_file():
            raise FileNotFoundError(
                f"Checkpoint de reprise introuvable : {checkpoint}. "
                "Utilisez le fichier last.pt de l'expérience interrompue."
            )
        return str(checkpoint)

    if args.weights is None:
        return "yolo11n.pt"
    if not args.weights.is_file():
        raise FileNotFoundError(f"Poids initiaux introuvables : {args.weights}")
    return str(args.weights)


def main() -> None:
    args = parse_args()

    if not args.resume and not args.data.is_file():
        raise FileNotFoundError(f"Configuration du dataset introuvable : {args.data}")

    weights_path = resolve_weights(args)

    print(f"Poids initiaux : {weights_path}")
    print(f"Mode : {'reprise' if args.resume else 'nouvel entraînement'}")
    print(f"Périphérique : {args.device}")

    model = YOLO(weights_path)
    if args.resume:
        model.train(resume=True, device=args.device)
        return

    model.train(
        data=str(args.data),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        device=args.device,
        workers=args.workers,
        seed=args.seed,
        deterministic=args.deterministic,
        amp=args.amp,
        cache=False,
        project=str(args.project),
        name=args.name,
        exist_ok=args.exist_ok,
    )


if __name__ == "__main__":
    main()
