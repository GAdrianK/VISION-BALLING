from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def download_soccernet_tracking(
    dest_dir: Path,
    split: str = "train",
    task: str = "tracking",
) -> Path:
    """
    Downloads SoccerNet Tracking dataset annotations using official SoccerNet package.
    Stops and reports instructions if authentication or license approval is required.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Initialisation du téléchargement SoccerNet ({task=}, {split=})...")
    print(f"[*] Destination : {dest_dir.resolve()}")

    try:
        from SoccerNet.Downloader import SoccerNetDownloader
    except ImportError:
        print("[!] Le package SoccerNet n'est pas installé dans l'environnement Python.")
        print("    Veuillez exécuter : pip install SoccerNet")
        sys.exit(1)

    try:
        downloader = SoccerNetDownloader(LocalDirectory=str(dest_dir))
        # Attempt to download tracking annotations only (without full video matches)
        downloader.downloadDataTask(
            task=task,
            split=[split],
            verbose=True,
        )
        print(f"[✓] Téléchargement réussi du split '{split}' dans {dest_dir}")
        return dest_dir
    except Exception as err:  # noqa: BLE001
        err_msg = str(err)

        print("\n[!] Attention : Le téléchargement SoccerNet a été interrompu.")
        print(f"    Message d'erreur : {err_msg}\n")
        print("=== Démarche pour le téléchargement SoccerNet Tracking ===")
        print("1. Créez un compte ou inscrivez-vous sur le portail officiel SoccerNet : https://www.soccer-net.org/")
        print("2. Acceptez les conditions d'utilisation / licence de recherche non-commerciale.")
        print("3. Si un mot de passe ou un jeton HuggingFace est requis, fournissez-le via le paramètre --password ou la variable d'environnement SOCCERNET_PASSWORD.")
        print("4. Relancez la commande avec les accès appropriés.")
        return dest_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement optionnel de SoccerNet Tracking train split")
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=ROOT / "data" / "external" / "soccernet",
        help="Répertoire de destination (exclu de Git)",
    )
    parser.add_argument(
        "--split",
        default="train",
        choices=["train", "valid", "test", "challenge"],
        help="Split du dataset à télécharger",
    )
    args = parser.parse_args()
    download_soccernet_tracking(args.dest_dir, split=args.split)


if __name__ == "__main__":
    main()
