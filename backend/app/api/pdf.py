from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from app.schemas.pdf import PDFExportRequest
from app.services.pdf_generator import generate_pdf_report

router = APIRouter()

@router.post("/api/export-pdf", summary="Exporter un plan d'entraînement tactique en PDF de terrain")
def export_pdf(request: PDFExportRequest):
    """
    Génère une fiche tactique PDF à partir des exercices fournis et la retourne en téléchargement.
    """
    try:
        pdf_bytes = generate_pdf_report(request)
        
        # Formatage du nom de fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fiche_tactique_{timestamp}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération du PDF : {str(e)}"
        )
