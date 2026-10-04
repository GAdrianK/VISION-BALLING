#!/usr/bin/env python3
"""VISION-BALLING — Post-Deployment Public Smoke Test Suite.

Automated verification script for public deployments:
- Frontend: Cloudflare Pages (or custom domain)
- Backend: Railway (or custom API domain)

Checks performed:
1. API /health and /api/health endpoints (must return 200 and {"status": "ok"}).
2. Fail-closed public upload gate (POST /api/video-analysis must return 403 Forbidden).
3. Cloudflare Pages SPA routes (/beta, /legal, /privacy, /cookies, /beta-terms) return 200 (not 404).
4. No localhost / 127.0.0.1 leakage in frontend script bundles.
5. Optional BETA intake form submission test (--test-form).

Usage:
  python scripts/smoke_test_public.py --frontend https://vision-balling.pages.dev --api https://api.vision-balling.com
  python scripts/smoke_test_public.py --frontend http://127.0.0.1:5173 --api http://127.0.0.1:8000 --allow-http
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch(
    url: str,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict, str]:
    """Execute HTTP request and return (status_code, headers_dict, body_text)."""
    req_headers = {"User-Agent": "VISION-BALLING-SmokeTest/1.0"}
    if headers:
        req_headers.update(headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            body = resp.read().decode("utf-8", errors="replace")
            return status, resp_headers, body
    except urllib.error.HTTPError as e:
        status = e.code
        resp_headers = dict(e.headers)
        body = e.read().decode("utf-8", errors="replace")
        return status, resp_headers, body
    except Exception as e:
        return 0, {}, str(e)


class SmokeTestRunner:
    def __init__(self, frontend_url: str, api_url: str, allow_http: bool = False, test_form: bool = False):
        self.frontend_url = frontend_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self.allow_http = allow_http
        self.test_form = test_form
        self.failures: list[str] = []
        self.passes: list[str] = []

    def log_pass(self, msg: str) -> None:
        print(f"  [PASS] {msg}")
        self.passes.append(msg)

    def log_fail(self, msg: str) -> None:
        print(f"  [FAIL] {msg}")
        self.failures.append(msg)

    def run_all(self) -> bool:
        print("=" * 65)
        print("VISION-BALLING — Post-Deployment Public Smoke Test")
        print(f"Frontend: {self.frontend_url}")
        print(f"API:      {self.api_url}")
        print("=" * 65)

        # 0. Protocol checks
        self.check_protocols()

        # 1. API Health checks
        self.check_api_health()

        # 2. Video analysis upload rejection check
        self.check_upload_disabled()

        # 3. Frontend root & SPA subroute checks
        self.check_frontend_spa_routes()

        # 4. Frontend bundle inspection for localhost leakage
        self.check_bundle_localhost_leakage()

        # 5. Optional BETA intake form submission test
        if self.test_form:
            self.check_beta_intake_form()

        print("-" * 65)
        print(f"Summary: {len(self.passes)} passed, {len(self.failures)} failed.")
        print("=" * 65)
        return len(self.failures) == 0

    def check_protocols(self) -> None:
        if not self.allow_http:
            if not self.frontend_url.startswith("https://"):
                self.log_fail(f"Frontend URL must use HTTPS in production: {self.frontend_url}")
            else:
                self.log_pass("Frontend uses HTTPS")

            if not self.api_url.startswith("https://"):
                self.log_fail(f"API URL must use HTTPS in production: {self.api_url}")
            else:
                self.log_pass("API uses HTTPS")

    def check_api_health(self) -> None:
        for path in ["/health", "/api/health"]:
            url = f"{self.api_url}{path}"
            status, _, body = fetch(url)
            if status != 200:
                self.log_fail(f"{path} returned status {status} (expected 200): {body}")
                continue

            try:
                data = json.loads(body)
                if data.get("status") == "ok":
                    self.log_pass(f"{path} returned 200 and status 'ok'")
                else:
                    self.log_fail(f"{path} returned unexpected payload: {body}")
            except Exception as e:
                self.log_fail(f"{path} response is not valid JSON: {e}")

    def check_upload_disabled(self) -> None:
        url = f"{self.api_url}/api/video-analysis"
        status, _, body = fetch(url, method="POST", data={})
        if status == 403:
            self.log_pass(f"POST {url} correctly rejected with 403 Forbidden (fail-closed)")
        else:
            self.log_fail(f"POST {url} returned status {status} (expected 403 Forbidden): {body}")

    def check_frontend_spa_routes(self) -> None:
        routes = ["/", "/beta", "/legal", "/privacy", "/cookies", "/beta-terms"]
        for route in routes:
            url = f"{self.frontend_url}{route}"
            status, _, body = fetch(url)
            if status == 200:
                if "VISION-BALLING" in body or "<div id=\"root\">" in body or "<html" in body:
                    self.log_pass(f"Route {route} returned 200 OK (SPA fallback active)")
                else:
                    self.log_fail(f"Route {route} returned 200 but content did not look like VISION-BALLING SPA")
            else:
                self.log_fail(f"Route {route} returned status {status} (expected 200 via _redirects)")

    def check_bundle_localhost_leakage(self) -> None:
        root_url = f"{self.frontend_url}/"
        status, _, body = fetch(root_url)
        if status != 200:
            self.log_fail(f"Failed to fetch {root_url} to locate script bundles")
            return

        # Find script tags: src="/assets/index-xxxx.js"
        script_paths = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', body)
        if not script_paths:
            self.log_fail("No <script> tags found in frontend root HTML")
            return

        for path in script_paths:
            full_script_url = urllib.parse.urljoin(root_url, path)
            sc_status, _, sc_body = fetch(full_script_url)
            if sc_status != 200:
                self.log_fail(f"Could not load asset: {full_script_url}")
                continue

            if "http://localhost:" in sc_body or "http://127.0.0.1:" in sc_body:
                self.log_fail(f"Asset {path} contains leaked localhost reference!")
            else:
                self.log_pass(f"Asset {path} clean (no localhost leakage)")

    def check_beta_intake_form(self) -> None:
        url = f"{self.api_url}/api/beta-requests"
        payload = {
            "name": "Smoke Test Auditor",
            "club": "Smoke Test FC",
            "role": "Analyste vidéo",
            "email": "smoke-test-verify@vision-balling.test",
            "phone": "+33600000000",
            "team_category": "Senior",
            "competition_level": "Régional 1",
            "opponent": "Test Adversaire",
            "video_type": "Match complet",
            "video_url": "https://drive.google.com/file/d/1234567890abcdef/view",
            "analysis_objectives": ["Bloc / compacité", "Pressing", "Transitions"],
            "message": "Automated post-deployment smoke verification",
            "video_authorization_confirmed": True,
            "temporary_storage_consent": True,
            "honeypot": "",
        }
        status, _, body = fetch(url, method="POST", data=payload)
        if status == 201:
            try:
                data = json.loads(body)
                req_id = data.get("id")
                if req_id:
                    self.log_pass(f"BETA intake submission test passed (request_id: {req_id})")
                else:
                    self.log_fail(f"BETA intake returned 201 but no id field: {body}")
            except Exception as e:
                self.log_fail(f"BETA intake returned 201 but invalid JSON: {e}")
        else:
            self.log_fail(f"BETA intake submission returned status {status}: {body}")


def main() -> int:
    parser = argparse.ArgumentParser(description="VISION-BALLING Public Smoke Test Suite")
    parser.add_argument("--frontend", required=True, help="Frontend base URL (e.g. https://vision-balling.pages.dev)")
    parser.add_argument("--api", required=True, help="API base URL (e.g. https://api.vision-balling.com)")
    parser.add_argument("--allow-http", action="store_true", help="Allow HTTP for local development testing")
    parser.add_argument("--test-form", action="store_true", help="Test BETA request creation endpoint")

    args = parser.parse_args()

    runner = SmokeTestRunner(
        frontend_url=args.frontend,
        api_url=args.api,
        allow_http=args.allow_http,
        test_form=args.test_form,
    )
    success = runner.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
