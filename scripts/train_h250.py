#!/usr/bin/env python3
"""Lance ou reprend un entraînement YOLO11 sur SoccerNet H250."""

import argparse
from pathlib import Path

from ultralytics import YOLO

from h250_dataset import validate_h250_dataset

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHECKPOINT = (
    ROOT
    / "runs"
    / "detect"
    / "yolo11n_h250_e50_b8"
    / "weights"
    / "last.pt"
)
DEFAULT_DATA_CANDIDATES = [
    ROOT / "data" / "external" / "h250" / "YOLO" / "data.yaml",
    Path("D:/datasets/h250/YOLO/data.yaml"),
    ROOT / "data" / "external" / "h250" / "data.yaml",
    Path("D:/datasets/h250/data.yaml"),
]
DEFAULT_DATA = next((p for p in DEFAULT_DATA_CANDIDATES if p.is_file()), DEFAULT_DATA_CANDIDATES[0])
DEFAULT_PROJECT = Path("D:/runs/detect") if Path("D:/").exists() else ROOT / "runs" / "detect"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Entraîner YOLO11 sur SoccerNet H250 (optimisé détection ballon)"
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
    parser.add_argument(
        "--batch",
        type=int,
        default=4,
        help="Taille de batch (défaut 4, adapté à 6 Go VRAM)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=960,
        help="Taille des images (défaut 960 pour favoriser les petits ballons)",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=15,
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
        default=DEFAULT_PROJECT,
        help="Dossier des résultats (D:/runs/detect si disponible)",
    )
    parser.add_argument("--name", default="yolo11n_h250_e50_imgsz960_b4")
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
    parser.add_argument(
        "--close-mosaic",
        type=int,
        default=10,
        help="Désactiver l'augmentation mosaic sur les N dernières époques",
    )
    parser.add_argument(
        "--box-gain",
        type=float,
        default=7.5,
        help="Pondération de la perte de bounding box (augmenter pour petits objets)",
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

    data_path = args.data
    if not args.resume and not data_path.is_file():
        # Tentative de recherche automatique sur les candidats
        resolved = next((p for p in DEFAULT_DATA_CANDIDATES if p.is_file()), None)
        if resolved:
            data_path = resolved
        else:
            raise FileNotFoundError(
                f"Configuration du dataset introuvable : {args.data}. "
                "Téléchargez d'abord H250 via 'python scripts/download_h250.py'."
            )

    weights_path = resolve_weights(args)
    dataset_summary = validate_h250_dataset(data_path) if not args.resume else None

    print(f"Poids initiaux : {weights_path}")
    print(f"Mode : {'reprise' if args.resume else 'nouvel entraînement'}")
    print(f"Dataset : {data_path}")
    print(f"Résolution : {args.imgsz}x{args.imgsz}, Batch : {args.batch}")
    print(f"Périphérique : {args.device}")
    if dataset_summary:
        split_counts = ", ".join(
            f"{name}={values['images']}"
            for name, values in dataset_summary["splits"].items()
        )
        print(f"Splits H250 validés : {split_counts}")

    model = YOLO(weights_path)
    if args.resume:
        model.train(resume=True, device=args.device)
        return

    train_kwargs = {
        "data": str(data_path),
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "patience": args.patience,
        "device": args.device,
        "workers": args.workers,
        "seed": args.seed,
        "deterministic": args.deterministic,
        "amp": args.amp,
        "cache": False,
        "project": str(args.project),
        "name": args.name,
        "exist_ok": args.exist_ok,
        "close_mosaic": args.close_mosaic,
        "box": args.box_gain,
    }

    model.train(**train_kwargs)


if __name__ == "__main__":
    main()
