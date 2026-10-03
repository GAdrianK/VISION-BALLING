from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RESULT_PREFIX = "BROWSER_VIDEO_RESULT="


def probe_browser(browser: Path, video: Path, timeout_seconds: float = 20) -> dict:
    browser = browser.resolve()
    video = video.resolve()
    if not browser.is_file():
        raise FileNotFoundError(f"Navigateur introuvable : {browser}")
    if not video.is_file() or video.stat().st_size == 0:
        raise FileNotFoundError(f"Vidéo absente ou vide : {video}")

    with tempfile.TemporaryDirectory(
        prefix="vision-balling-browser-", dir=video.parent
    ) as temporary:
        root = Path(temporary)
        page = root / "probe.html"
        profile = root / "profile"
        video_uri = json.dumps(video.as_uri())
        page.write_text(
            f"""<!doctype html>
<html><head><meta charset="utf-8"><title>pending</title></head>
<body><video id="probe" muted playsinline preload="auto"></video>
<pre id="result">{RESULT_PREFIX}{{"status":"PENDING"}}</pre>
<script>
const video = document.getElementById("probe");
const result = document.getElementById("result");
let finished = false;
let metadataLoaded = false;
function finish(status, details) {{
  if (finished) return;
  finished = true;
  const payload = Object.assign({{status, metadataLoaded}}, details || {{}});
  result.textContent = {json.dumps(RESULT_PREFIX)} + JSON.stringify(payload);
  document.title = status;
}}
video.addEventListener("loadedmetadata", () => {{
  metadataLoaded = true;
  if (!(video.videoWidth > 0 && video.videoHeight > 0)) {{
    finish("FAIL", {{reason: "invalid dimensions", width: video.videoWidth,
      height: video.videoHeight}});
  }}
}});
video.addEventListener("loadeddata", () => finish("PASS", {{
  width: video.videoWidth,
  height: video.videoHeight,
  duration: video.duration,
  readyState: video.readyState
}}));
video.addEventListener("error", () => finish("FAIL", {{
  reason: "decode error",
  errorCode: video.error ? video.error.code : null,
  errorMessage: video.error ? video.error.message : null
}}));
setTimeout(() => finish("FAIL", {{reason: "timeout"}}), 6000);
video.src = {video_uri};
video.load();
</script></body></html>""",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--allow-file-access-from-files",
                "--autoplay-policy=no-user-gesture-required",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=8000",
                "--dump-dom",
                page.as_uri(),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    rendered = html.unescape(completed.stdout)
    match = re.search(rf"{RESULT_PREFIX}(\{{[^<]+\}})", rendered)
    if match is None:
        return {
            "status": "FAIL",
            "reason": "result marker missing",
            "browser_exit_code": completed.returncode,
            "stderr": completed.stderr[-1000:],
        }
    payload = json.loads(match.group(1))
    payload["browser_exit_code"] = completed.returncode
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe a pipeline MP4 in an installed Chromium browser."
    )
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    args = parser.parse_args()
    result = probe_browser(args.browser, args.video)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
