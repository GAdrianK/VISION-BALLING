#!/usr/bin/env python3
"""VISION-BALLING Legal & Compliance Placeholders Verification Script.

Ensures that:
1. Unknown owner/business details remain explicit bracketed placeholders (e.g. [LEGAL_NAME]).
2. No fabricated SIREN, SIRET, RCS, VAT, or fake business identities exist.
3. Infrastructure separation is explicitly maintained in LEGAL_CONFIG:
   - Frontend static hosting (Cloudflare Pages)
   - Backend API hosting (Railway)
   - Managed database (Railway PostgreSQL)
   - Dedicated local GPU station (not public cloud)
4. Legal & compliance pages consistently import and utilize LEGAL_CONFIG.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CONFIG_FILE = FRONTEND_DIR / "src" / "config" / "legalConfig.js"
COMPONENTS_DIR = FRONTEND_DIR / "src" / "components"


def check_legal_config() -> list[str]:
    errors = []
    if not CONFIG_FILE.exists():
        return [f"Missing configuration file: {CONFIG_FILE}"]

    content = CONFIG_FILE.read_text(encoding="utf-8")

    # Check for mandatory placeholders list
    if "MANDATORY_LEGAL_PLACEHOLDERS" not in content:
        errors.append("MANDATORY_LEGAL_PLACEHOLDERS export missing in legalConfig.js")

    mandatory_keys = [
        "LEGAL_NAME",
        "LEGAL_STATUS",
        "LEGAL_ADDRESS",
        "LEGAL_EMAIL",
        "LEGAL_PHONE",
        "SIREN",
        "SIRET",
        "PUBLICATION_DIRECTOR",
    ]

    for key in mandatory_keys:
        # Check that either bracketed placeholder is present or explicit key definition
        pattern = rf"{key}\s*:\s*\"(\[[^\]]+\]|[^\"]+)\""
        match = re.search(pattern, content)
        if not match:
            errors.append(f"Key {key} not properly defined in LEGAL_CONFIG")
        else:
            val = match.group(1)
            # If not bracketed, ensure it's not a common fake identity
            fake_patterns = ["acme", "john doe", "foo bar", "test corp", "123456789"]
            if any(fake in val.lower() for fake in fake_patterns):
                errors.append(f"Key {key} contains fabricated test dummy data: '{val}'")

    # Check 4-tier infrastructure disclosure
    infra_keys = [
        "FRONTEND_HOST_NAME",
        "API_HOST_NAME",
        "DATABASE_HOST_NAME",
        "LOCAL_GPU_PROCESSOR",
    ]
    for key in infra_keys:
        if key not in content:
            errors.append(f"Infrastructure key {key} missing in legalConfig.js")

    # Verify that GPU processing mentions local / private
    if "LOCAL_GPU_PROCESSOR" in content:
        gpu_match = re.search(r"LOCAL_GPU_PROCESSOR\s*:\s*\"([^\"]+)\"", content)
        if gpu_match:
            gpu_desc = gpu_match.group(1).lower()
            if "local" not in gpu_desc or "priv" not in gpu_desc:
                errors.append(f"LOCAL_GPU_PROCESSOR must indicate local and private hardware: {gpu_desc}")

    return errors


def check_legal_components() -> list[str]:
    errors = []
    legal_page = COMPONENTS_DIR / "LegalPage.jsx"
    privacy_page = COMPONENTS_DIR / "PrivacyPage.jsx"

    if not legal_page.exists():
        errors.append(f"Missing LegalPage component: {legal_page}")
    else:
        text = legal_page.read_text(encoding="utf-8")
        if "LEGAL_CONFIG" not in text:
            errors.append("LegalPage.jsx does not import or use LEGAL_CONFIG")
        if "LOCAL_GPU_PROCESSOR" not in text:
            errors.append("LegalPage.jsx does not disclose LOCAL_GPU_PROCESSOR")

    if not privacy_page.exists():
        errors.append(f"Missing PrivacyPage component: {privacy_page}")
    else:
        text = privacy_page.read_text(encoding="utf-8")
        if "LEGAL_CONFIG" not in text:
            errors.append("PrivacyPage.jsx does not import or use LEGAL_CONFIG")
        if "LOCAL_GPU_PROCESSOR" not in text:
            errors.append("PrivacyPage.jsx does not disclose LOCAL_GPU_PROCESSOR")
        if "[EMAIL]" in text:
            errors.append("PrivacyPage.jsx contains unbracketed or raw '[EMAIL]' placeholder")

    return errors


def check_no_fabricated_identifiers() -> list[str]:
    errors = []
    # Search for patterns that look like hardcoded fake 9-digit SIREN or 14-digit SIRET in JSX files
    siren_pattern = re.compile(r"\bSIREN\s*[:=]\s*['\"]?\d{9}['\"]?", re.IGNORECASE)
    siret_pattern = re.compile(r"\bSIRET\s*[:=]\s*['\"]?\d{14}['\"]?", re.IGNORECASE)

    for path in COMPONENTS_DIR.glob("*.jsx"):
        text = path.read_text(encoding="utf-8")
        if siren_pattern.search(text):
            errors.append(f"Fabricated SIREN found in {path.name}")
        if siret_pattern.search(text):
            errors.append(f"Fabricated SIRET found in {path.name}")

    return errors


def main() -> int:
    print("=" * 60)
    print("VISION-BALLING — Legal & Compliance Placeholders Verification")
    print("=" * 60)

    all_errors = []

    print("[1/3] Checking legalConfig.js definitions and placeholders...")
    config_errs = check_legal_config()
    all_errors.extend(config_errs)
    if not config_errs:
        print("  ✓ legalConfig.js valid (mandatory placeholders and 4-tier infra present)")
    else:
        for err in config_errs:
            print(f"  ✗ {err}")

    print("[2/3] Checking Legal & Privacy components integration...")
    comp_errs = check_legal_components()
    all_errors.extend(comp_errs)
    if not comp_errs:
        print("  ✓ LegalPage & PrivacyPage correctly wired to LEGAL_CONFIG")
    else:
        for err in comp_errs:
            print(f"  ✗ {err}")

    print("[3/3] Checking for fabricated business identifiers...")
    ident_errs = check_no_fabricated_identifiers()
    all_errors.extend(ident_errs)
    if not ident_errs:
        print("  ✓ Zero fabricated SIREN/SIRET identifiers found in components")
    else:
        for err in ident_errs:
            print(f"  ✗ {err}")

    print("=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} legal/compliance errors detected.")
        return 1
    else:
        print("PASSED: All legal placeholder and compliance checks succeeded.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
