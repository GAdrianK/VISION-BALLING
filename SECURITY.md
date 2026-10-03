# VISION-BALLING Security Policy

## 1. Supported Versions

Security updates and vulnerability patches are actively maintained for the following versions:

| Version | Status | Supported |
| :--- | :--- | :--- |
| **v0.9.0-rc2** | **Active Release Candidate** | **Yes** |
| < v0.9.0-rc2 | Obsolete / Diagnostic Prototypes | No |

---

## 2. Reporting a Vulnerability

We welcome responsible security disclosures. If you discover a security vulnerability in VISION-BALLING:

1. **Do NOT open a public GitHub issue.**
2. Send a detailed report to the security contact: `security@vision-balling.com` (or private security advisory via GitHub).
3. Include:
   - Vulnerability category (e.g., IDOR, RCE, Model Poisoning, XSS, Insecure Deserialization).
   - Step-by-step reproduction steps or proof-of-concept.
   - Affected endpoints or files.
   - Potential impact assessment.
4. You will receive an acknowledgment within 48 hours.

---

## 3. Core Security Principles & Architecture

### 3.1. Fail-Closed by Design
VISION-BALLING enforces strict **Fail-Closed** security across all layers:
- If preflight checks (GPU, CUDA, FFmpeg, model weights) fail, the pipeline **fails loudly** and halts immediately.
- If video artifacts or tactical evidence are missing for a real uploaded sequence, endpoints return **HTTP 404**; they **never silently fall back to public demo or mock data**.
- In `APP_ENV=production`, wildcard CORS (`*`), empty origins, and unauthenticated diagnostics are strictly prohibited at startup.

### 3.2. Capability-Based Access Control (IDOR Prevention)
- Public demo sequences (`SNMOT-068`, `SNMOT-069`, `GOLDEN-01-BROADCAST`) are immutable and public read-only.
- Real user video uploads (`REAL_UPLOAD`) generate a cryptographically random capability token (`access_token`, 32 bytes entropy) upon creation.
- Only the SHA-256 hash of this token is stored server-side (`access_token_hash`).
- All subsequent inspection, artifact streaming, grounded queries, and summary endpoints require `Authorization: Bearer <token>`, `X-Analysis-Token`, or `?token=<token>`.

### 3.3. Input & Upload Validation
- Videos undergo container magic byte inspection (verifying MP4, MOV, MKV, WebM, AVI signatures) prior to parser execution.
- Maximum duration, resolution, disk space, and file size limits are enforced.
- Directory traversal defenses sanitize file paths and prevent access outside isolated analysis session directories.

### 3.4. Read-Only Database & Prompt Injection Hardening
- Legacy natural-language SQL analysis is disabled by default in production (`ENABLE_LEGACY_SQL_API=false`).
- When activated, database connections use read-only SQLite mode (`mode=ro`), and queries are restricted to parameterized `SELECT` statements with prohibited keywords (`DROP`, `DELETE`, `ATTACH`, etc.).
- The Grounded Tactical RAG engine treats external retrieved knowledge strictly as contextual data, preventing prompt injection from overriding verified match evidence.

### 3.5. Commercial Deployment License Gate
`COMMERCIAL_DEPLOYMENT_LICENSE_REVIEW_REQUIRED=true`  
Any public or commercial deployment requires formal license auditing of underlying third-party datasets and checkpoints.
