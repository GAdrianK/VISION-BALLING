/**
 * VISION-BALLING — Central Legal & Hosting Configuration
 *
 * Unknown owner-specific values remain explicit bracketed placeholders.
 * Do NOT invent any legal details (names, addresses, SIREN, SIRET, etc.).
 *
 * Hosting and infrastructure explicitly distinguish:
 * 1. Frontend static hosting (Cloudflare Pages)
 * 2. Backend API hosting (Railway)
 * 3. Database processing (Railway PostgreSQL)
 * 4. Video processing & computer vision inference (private local GPU station)
 */

export const LEGAL_CONFIG = {
  // Owner & Publisher Identification (LCEN Art. 6-III-1)
  LEGAL_NAME: "[LEGAL_NAME]",
  BUSINESS_NAME: "[BUSINESS_NAME]",
  LEGAL_STATUS: "[LEGAL_STATUS]",
  LEGAL_ADDRESS: "[PROFESSIONAL_ADDRESS]",
  // Professional Contact Email (canonical OVH mailbox: contact@vision-balling.fr, replaces [EMAIL])
  LEGAL_EMAIL: "contact@vision-balling.fr",
  LEGAL_PHONE: "[PHONE]",
  SIREN: "[SIREN]",
  SIRET: "[SIRET]",
  RNE: "[RNE]",
  RCS: "[RCS_IF_APPLICABLE]",
  VAT_NUMBER: "[VAT_NUMBER_IF_APPLICABLE]",
  PUBLICATION_DIRECTOR: "[NAME]",

  // DPO / GDPR Privacy Contact (canonical OVH mailbox: contact@vision-balling.fr)
  DPO_CONTACT_EMAIL: "contact@vision-balling.fr",

  // Hosting Disclosures (replaces generic [HOST_NAME] with 4-tier separation)
  // 1. Frontend Static Hosting (Cloudflare Pages)
  FRONTEND_HOST_NAME: "Cloudflare, Inc. (Cloudflare Pages)",
  FRONTEND_HOST_LEGAL_ENTITY: "Cloudflare, Inc.",
  FRONTEND_HOST_ADDRESS: "101 Townsend St, San Francisco, CA 94107, USA (Réseau de diffusion de contenu mondial & points de présence en France/UE)",
  FRONTEND_HOST_PHONE: "+1 (888) 993-5273",
  FRONTEND_HOST_URL: "https://pages.cloudflare.com",

  // 2. Backend API Hosting (Railway)
  API_HOST_NAME: "Railway Corp. (Railway Platform)",
  API_HOST_LEGAL_ENTITY: "Railway Corp.",
  API_HOST_ADDRESS: "2261 Market St #4008, San Francisco, CA 94114, USA (Déploiement conteneurisé CPU - région Europe disponible)",
  API_HOST_PHONE: "[API_HOST_PHONE]",
  API_HOST_URL: "https://railway.app",

  // 3. Managed Database Processing (Railway PostgreSQL)
  DATABASE_HOST_NAME: "Railway Managed PostgreSQL",
  DATABASE_HOST_LEGAL_ENTITY: "Railway Corp.",
  DATABASE_HOST_ADDRESS: "San Francisco, CA, USA (Instance managée PostgreSQL)",
  DATABASE_HOST_URL: "https://railway.app",

  // 4. Dedicated Local Private GPU Infrastructure
  LOCAL_GPU_PROCESSOR: "Station de calcul locale dédiée (GPU NVIDIA RTX 4060 privée hors cloud public, non exposée sur Internet)",
};

export const MANDATORY_LEGAL_PLACEHOLDERS = [
  "LEGAL_NAME",
  "LEGAL_STATUS",
  "LEGAL_ADDRESS",
  "LEGAL_EMAIL",
  "LEGAL_PHONE",
  "SIREN",
  "SIRET",
  "PUBLICATION_DIRECTOR",
];
