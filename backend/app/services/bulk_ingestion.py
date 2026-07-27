import time
import random
import logging
from sqlalchemy.orm import Session
from app.services.extractor_engine import FootballScraperEngine

logger = logging.getLogger(__name__)

def run_bulk_ingestion(match_list: list[dict], db_sql: Session) -> dict:
    """
    Ingère une liste de matches avec un délai d'attente aléatoire pour éviter le blocage.
    Chaque match_dict doit contenir 'url' et 'match_id'.
    """
    scraper = FootballScraperEngine()
    results = []
    success_count = 0
    failed_count = 0

    for i, match in enumerate(match_list, 1):
        url = match.get("url")
        match_id = match.get("match_id")
        if not url or not match_id:
            msg = f"Match {i} invalide : 'url' et 'match_id' requis."
            results.append({"match_id": match_id, "status": "failed", "message": msg})
            failed_count += 1
            continue

        logger.info(f"[BulkScrape] Début ingestion match {i}/{len(match_list)} : {match_id}")
        
        # Ingestion
        res_msg = scraper.fetch_and_save_match_stats(url, match_id, db_sql)
        
        if res_msg.startswith("Succès"):
            results.append({"match_id": match_id, "status": "success", "message": res_msg})
            success_count += 1
        else:
            results.append({"match_id": match_id, "status": "failed", "message": res_msg})
            failed_count += 1

        # Délai d'attente aléatoire (entre 3 et 6 secondes) entre chaque requête HTTP (sauf la dernière)
        # Uniquement si la source est une URL distante (pour ne pas ralentir les fichiers locaux en test)
        if i < len(match_list) and (url.startswith("http://") or url.startswith("https://")):
            sleep_time = random.uniform(3.0, 6.0)
            logger.info(f"[BulkScrape] Attente de {sleep_time:.2f} secondes avant le prochain match...")
            time.sleep(sleep_time)

    report = {
        "total": len(match_list),
        "success": success_count,
        "failed": failed_count,
        "details": results
    }
    logger.info(f"[BulkScrape] Ingestion de masse terminée. Résultat : {report}")
    return report
