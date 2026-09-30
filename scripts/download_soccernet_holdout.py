#!/usr/bin/env python3
"""
Downloads and extracts designated SoccerNet Tracking 2023 holdout sequences
directly from the official HuggingFace train.zip archive using HTTP range streaming.
"""

from __future__ import annotations

import os
import struct
import sys
import time
import urllib.request
import zlib
from pathlib import Path
from remotezip import RemoteZip

HF_TRAIN_ZIP_URL = "https://huggingface.co/datasets/SoccerNet/SN-Tracking-2023/resolve/main/train.zip"
TARGET_DIR = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
TARGET_SEQUENCES = ["SNMOT-069", "SNMOT-070", "SNMOT-071"]


def download_and_extract_sequence(rzip: RemoteZip, seq_name: str, target_root: Path) -> None:
    print(f"\n================================================================================")
    print(f"[*] Processing sequence: {seq_name}")
    print(f"================================================================================")
    
    seq_target_dir = target_root / seq_name
    if (seq_target_dir / "img1" / "000750.jpg").is_file() and (seq_target_dir / "gt" / "gt.txt").is_file():
        print(f"[✓] {seq_name} already fully extracted at {seq_target_dir}. Skipping.")
        return

    info_list = [i for i in rzip.infolist() if f"/{seq_name}/" in i.filename or i.filename.startswith(f"{seq_name}/")]
    if not info_list:
        raise ValueError(f"No files found for {seq_name} in remote archive!")

    info_sorted = sorted(info_list, key=lambda x: x.header_offset)
    min_off = info_sorted[0].header_offset
    last_item = info_sorted[-1]
    
    # Calculate exact end offset
    end_off = last_item.header_offset + 30 + len(last_item.filename) + len(last_item.extra) + last_item.compress_size + 1024
    total_bytes = end_off - min_off

    print(f"[*] Byte range for {seq_name}: {min_off} to {end_off} ({total_bytes / 1024 / 1024:.2f} MB)")
    print(f"[*] Total entries to extract: {len(info_sorted)}")

    t0 = time.time()
    req = urllib.request.Request(HF_TRAIN_ZIP_URL, headers={"Range": f"bytes={min_off}-{end_off}"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    dl_time = time.time() - t0
    print(f"[✓] Downloaded {len(data) / 1024 / 1024:.2f} MB in {dl_time:.2f} s ({len(data) / 1024 / 1024 / max(dl_time, 0.001):.2f} MB/s)")

    # Unpack entries sequentially
    t_unpack0 = time.time()
    extracted_count = 0
    pos = 0

    while pos < len(data) - 30:
        if data[pos:pos+4] != b"PK\x03\x04":
            pos += 1
            continue
        sig, ver, flag, method, mtime, mdate, crc, comp_size, uncomp_size, fn_len, extra_len = struct.unpack(
            "<IHHHHHIIIHH", data[pos:pos+30]
        )
        fn = data[pos+30:pos+30+fn_len].decode("utf-8", errors="replace")
        pos += 30 + fn_len + extra_len
        payload = data[pos:pos+comp_size]
        pos += comp_size

        if not fn or fn.endswith("/"):
            # Directory entry
            continue

        # Target relative path inside target_root
        # E.g. fn = "train/SNMOT-069/img1/000001.jpg"
        parts = fn.split("/")
        if seq_name in parts:
            rel_idx = parts.index(seq_name)
            rel_path = Path(*parts[rel_idx:])
        else:
            continue

        dest_file = target_root / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if method == 8:
            decomp = zlib.decompressobj(-zlib.MAX_WBITS).decompress(payload)
        elif method == 0:
            decomp = payload
        else:
            print(f"[!] Unsupported compression method {method} for {fn}")
            continue

        dest_file.write_bytes(decomp)
        extracted_count += 1

    unpack_time = time.time() - t_unpack0
    print(f"[✓] Extracted {extracted_count} files for {seq_name} in {unpack_time:.2f} s")
    
    # Validation
    gt_file = seq_target_dir / "gt" / "gt.txt"
    last_frame = seq_target_dir / "img1" / "000750.jpg"
    gameinfo = seq_target_dir / "gameinfo.ini"
    print(f"[*] Validation: gt.txt exists={gt_file.is_file()} (size={gt_file.stat().st_size if gt_file.is_file() else 0} bytes)")
    print(f"[*] Validation: 000750.jpg exists={last_frame.is_file()}")
    print(f"[*] Validation: gameinfo.ini exists={gameinfo.is_file()}")
    if not (gt_file.is_file() and last_frame.is_file() and gameinfo.is_file()):
        raise RuntimeError(f"Extraction validation failed for {seq_name}!")


def main() -> None:
    print(f"Connecting to remote archive: {HF_TRAIN_ZIP_URL}...")
    with RemoteZip(HF_TRAIN_ZIP_URL) as rzip:
        for seq in TARGET_SEQUENCES:
            download_and_extract_sequence(rzip, seq, TARGET_DIR)
    print("\n[✓] All holdout sequences downloaded and extracted successfully!")


if __name__ == "__main__":
    main()
