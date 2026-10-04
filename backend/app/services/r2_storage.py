from __future__ import annotations

import datetime
import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.parse

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
    k_date = _sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region_name)
    k_service = _sign(k_region, service_name)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing


class R2StorageService:
    """S3-compatible Cloudflare R2 client using standard SigV4 signing.
    
    Provides:
    - Pure Python AWS SigV4 presigned URL generation (with Range 206 support)
    - File upload and download via httpx
    - Transparent local directory fallback when R2 credentials are not set (for local dev/tests).
    """

    def __init__(self, cfg: Optional[Settings] = None, local_storage_dir: Optional[Path] = None) -> None:
        self.cfg = cfg or settings
        self.account_id = self.cfg.R2_ACCOUNT_ID.strip()
        self.bucket_name = self.cfg.R2_BUCKET_NAME.strip()
        self.access_key_id = self.cfg.R2_ACCESS_KEY_ID.strip()
        self.secret_access_key = self.cfg.R2_SECRET_ACCESS_KEY.strip()
        self.region = "auto"
        self.service_name = "s3"

        if self.cfg.R2_ENDPOINT_URL.strip():
            self.endpoint_url = self.cfg.R2_ENDPOINT_URL.strip().rstrip("/")
        elif self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        else:
            self.endpoint_url = ""

        # Local storage fallback directory
        self.local_dir = local_storage_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "r2_mock")
        self.local_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        """Returns True if full R2 credentials and bucket are provided."""
        return bool(
            self.endpoint_url
            and self.bucket_name
            and self.access_key_id
            and self.secret_access_key
        )

    def generate_presigned_url(
        self,
        method: str,
        s3_key: str,
        expires_in_seconds: int = 300,
        content_type: Optional[str] = None,
    ) -> str:
        """Generates an AWS SigV4 presigned URL for GET or PUT.
        
        CRUCIAL FOR VIDEO STREAMING:
        The 'range' header is NOT included in signed_headers, allowing browsers
        to issue HTTP 206 partial content range requests without invalidating
        the signature.
        """
        clean_key = s3_key.lstrip("/")
        if not self.is_configured:
            # Fallback for local testing / development
            return f"/api/video-analysis/mock-storage/{clean_key}"

        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        parsed_url = urllib.parse.urlparse(self.endpoint_url)
        host = parsed_url.netloc
        canonical_uri = f"/{self.bucket_name}/{urllib.parse.quote(clean_key, safe='-_.~/')}"

        credential_scope = f"{date_stamp}/{self.region}/{self.service_name}/aws4_request"
        canonical_headers = f"host:{host}\n"
        signed_headers = "host"

        query_params: Dict[str, str] = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.access_key_id}/{credential_scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_in_seconds),
            "X-Amz-SignedHeaders": signed_headers,
        }

        # Sort query params lexicographically
        canonical_query = urllib.parse.urlencode(sorted(query_params.items()))

        # Payload is UNSIGNED-PAYLOAD for presigned URLs
        payload_hash = "UNSIGNED-PAYLOAD"

        canonical_request = (
            f"{method.upper()}\n"
            f"{canonical_uri}\n"
            f"{canonical_query}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        string_to_sign = (
            f"AWS4-HMAC-SHA256\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        signing_key = _get_signature_key(
            self.secret_access_key, date_stamp, self.region, self.service_name
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return f"{self.endpoint_url}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"

    def upload_file(self, local_path: Path, s3_key: str, content_type: str = "application/octet-stream") -> bool:
        """Uploads a local file to R2 (or copies to mock directory if not configured)."""
        clean_key = s3_key.lstrip("/")
        if not self.is_configured:
            dest = self.local_dir / clean_key
            dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(local_path, dest)
            return True

        upload_url = self.generate_presigned_url("PUT", clean_key, expires_in_seconds=900)
        with open(local_path, "rb") as f:
            data = f.read()

        with httpx.Client(timeout=120.0) as client:
            resp = client.put(upload_url, content=data, headers={"Content-Type": content_type})
            resp.raise_for_status()
            return True

    def put_object_bytes(self, s3_key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """Puts in-memory bytes into R2."""
        clean_key = s3_key.lstrip("/")
        if not self.is_configured:
            dest = self.local_dir / clean_key
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            return True

        upload_url = self.generate_presigned_url("PUT", clean_key, expires_in_seconds=300)
        with httpx.Client(timeout=60.0) as client:
            resp = client.put(upload_url, content=data, headers={"Content-Type": content_type})
            resp.raise_for_status()
            return True

    def get_object_bytes(self, s3_key: str) -> bytes:
        """Retrieves object bytes from R2 or local mock storage."""
        clean_key = s3_key.lstrip("/")
        if not self.is_configured:
            target = self.local_dir / clean_key
            if not target.is_file():
                raise FileNotFoundError(f"Object {clean_key} not found in local mock R2 storage.")
            with open(target, "rb") as f:
                return f.read()

        download_url = self.generate_presigned_url("GET", clean_key, expires_in_seconds=300)
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(download_url)
            resp.raise_for_status()
            return resp.content

    def download_file(self, s3_key: str, local_path: Path) -> Path:
        """Downloads an object from R2 to a local destination."""
        data = self.get_object_bytes(s3_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        return local_path

    def exists(self, s3_key: str) -> bool:
        """Checks if an object exists in R2 or local mock storage."""
        clean_key = s3_key.lstrip("/")
        if not self.is_configured:
            return (self.local_dir / clean_key).is_file()

        download_url = self.generate_presigned_url("GET", clean_key, expires_in_seconds=60)
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.head(download_url)
                return resp.status_code == 200
        except Exception:
            return False


_global_r2_storage: Optional[R2StorageService] = None


def get_r2_storage() -> R2StorageService:
    global _global_r2_storage
    if _global_r2_storage is None:
        _global_r2_storage = R2StorageService()
    return _global_r2_storage
