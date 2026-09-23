#!/usr/bin/env python3
"""Télécharge et extrait le dataset SoccerNet-v3 H250 depuis Zenodo."""

from __future__ import annotations

import argparse
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from h250_dataset import (
    EXPECTED_ARCHIVE_SHA256,
    H250ValidationError,
    sha256_file,
    validate_h250_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
ZENODO_URL = "https://zenodo.org/records/7808511/files/YOLO.zip"
DEFAULT_DEST = Path("D:/datasets/h250") if Path("D:/").exists() else ROOT / "data" / "external" / "h250"


def download_file_with_resume(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """Télécharge un fichier volumineux avec reprise HTTP (Range) et barre de progression."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing_bytes = dest.stat().st_size if dest.exists() else 0

    headers: dict[str, str] = {}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_range = resp.headers.get("Content-Range")
            total_bytes = None
            if content_range:
                try:
                    total_bytes = int(content_range.split("/")[-1])
                except (ValueError, IndexError):
                    pass
            elif resp.headers.get("Content-Length"):
                total_bytes = existing_bytes + int(resp.headers["Content-Length"])

            mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
            if mode == "wb":
                existing_bytes = 0

            print(f"[*] Téléchargement vers : {dest}")
            if total_bytes:
                total_mb = total_bytes / (1024 * 1024)
                start_mb = existing_bytes / (1024 * 1024)
                print(f"[*] Taille totale : {total_mb:.1f} Mo (Déjà présent : {start_mb:.1f} Mo)")

            downloaded = existing_bytes
            start_time = time.time()
            last_print = start_time

            with open(dest, mode) as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_print >= 5.0:
                        last_print = now
                        elapsed = max(0.1, now - start_time)
                        speed_mb = (downloaded - existing_bytes) / (1024 * 1024 * elapsed)
                        pct = (downloaded / total_bytes * 100) if total_bytes else 0
                        print(f"    Progression : {downloaded / (1024 * 1024):.1f} Mo / {total_mb:.1f} Mo ({pct:.1f}%) à {speed_mb:.2f} Mo/s")

            print(f"[OK] Telechargement termine : {dest} ({downloaded / (1024 * 1024):.1f} Mo)")
    except urllib.error.HTTPError as exc:
        if exc.code == 416:
            print(f"[OK] Fichier deja integralement telecharge ({existing_bytes / (1024 * 1024):.1f} Mo).")
            return
        raise


def extract_zip(archive_path: Path, target_dir: Path) -> None:
    """Extrait l'archive ZIP si elle n'a pas déjà été extraite."""
    print(f"[*] Extraction de {archive_path} vers {target_dir}...")
    start_time = time.time()
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        members = zip_ref.infolist()
        target_root = target_dir.resolve()
        for member in members:
            destination = (target_root / member.filename).resolve()
            try:
                destination.relative_to(target_root)
            except ValueError as error:
                raise H250ValidationError(
                    f"Entrée ZIP hors destination interdite : {member.filename}"
                ) from error
            unix_mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(unix_mode):
                raise H250ValidationError(f"Lien symbolique ZIP interdit : {member.filename}")
        total_files = len(members)
        print(f"[*] Archive contenant {total_files} fichiers.")
        zip_ref.extractall(target_root)
    print(f"[OK] Extraction terminee en {time.time() - start_time:.1f} secondes.")


def verify_dataset_structure(base_dir: Path) -> bool:
    """Vérifie la présence et le nombre d'images/labels du dataset H250."""
    candidates = [
        base_dir / "YOLO" / "data.yaml",
        base_dir / "data.yaml",
    ]
    yaml_path = next((p for p in candidates if p.is_file()), None)
    if not yaml_path:
        print(f"[!] Fichier data.yaml introuvable dans {base_dir}")
        return False

    try:
        summary = validate_h250_dataset(yaml_path)
    except H250ValidationError as error:
        print(f"[!] Dataset invalide : {error}")
        return False
    print(f"[OK] Configuration trouvee : {yaml_path}")
    for split, stats in summary["splits"].items():
        print(
            f"    - Split {split:5s} : {stats['images']} images, "
            f"{stats['labels']} labels"
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharger et extraire SoccerNet H250")
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=DEFAULT_DEST,
        help="Dossier de destination (ex: D:/datasets/h250)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Sauter le téléchargement si l'archive ZIP est déjà présente",
    )
    args = parser.parse_args()

    dest_dir = args.dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "YOLO.zip"

    if not args.skip_download:
        download_file_with_resume(ZENODO_URL, zip_path)

    if zip_path.is_file():
        actual_sha = sha256_file(zip_path)
        if actual_sha != EXPECTED_ARCHIVE_SHA256:
            print(
                "[!] SHA-256 archive invalide : "
                f"expected={EXPECTED_ARCHIVE_SHA256} actual={actual_sha}"
            )
            sys.exit(1)
        print(f"[OK] SHA-256 archive : {actual_sha}")
        if verify_dataset_structure(dest_dir):
            print("[OK] Dataset déjà extrait et valide ; extraction ignorée.")
            return
        extract_zip(zip_path, dest_dir)
    else:
        print(f"[!] Archive {zip_path} introuvable pour extraction.")
        sys.exit(1)

    ok = verify_dataset_structure(dest_dir)
    if ok:
        print("\n[OK] Le dataset SoccerNet-v3 H250 est pret pour l'entrainement et l'evaluation.")
    else:
        print("\n[!] Attention : La structure du dataset semble incomplete.")
        sys.exit(1)


if __name__ == "__main__":
    main()
