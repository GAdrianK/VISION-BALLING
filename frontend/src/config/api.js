/**
 * Resolves the backend API base URL for VISION-BALLING.
 *
 * Rules:
 * - In development (import.meta.env.DEV), falls back to local backend if VITE_API_URL is unset.
 * - In production mode, VITE_API_URL is strictly required and cannot point to loopback.
 */
export function getApiBaseUrl() {
  const envUrl = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

  // Dead code eliminated by Vite/Rollup in production builds
  if (import.meta.env.DEV) {
    return envUrl || "http://127.0.0.1:8000";
  }

  // Production validation
  if (!envUrl) {
    throw new Error(
      "Production configuration error: VITE_API_URL is missing. " +
      "Configure VITE_API_URL in Cloudflare Pages environment variables."
    );
  }
  if (envUrl.includes("localhost") || envUrl.includes("127.0.0.1")) {
    throw new Error(
      `Production configuration error: VITE_API_URL cannot point to localhost ('${envUrl}').`
    );
  }
  return envUrl;
}

export const API_BASE = getApiBaseUrl();
