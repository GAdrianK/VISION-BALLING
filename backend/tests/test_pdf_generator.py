import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.pdf import PDFExportRequest, PDFBlock
from app.services.pdf_generator import generate_pdf_report

client = TestClient(app)

@pytest.fixture
def sample_pdf_request() -> PDFExportRequest:
    return PDFExportRequest(
        title="Séance de pressing haut",
        coach="Coach Test",
        date="12/06/2026",
        blocks=[
            PDFBlock(title="Échauffement", content="Rondo 4vs2 en 1 touche de balle."),
            PDFBlock(title="Exercice 1", content="Jeu de transition 6vs4."),
            PDFBlock(title="Exercice 2", content="Match thématique sur grand terrain."),
            PDFBlock(title="Jeu final", content="Étirements et retour au calme.")
        ]
    )

def test_generate_pdf_report_service(sample_pdf_request):
    """
    Vérifie que le service de génération retourne des octets PDF valides (magie %PDF).
    """
    pdf_bytes = generate_pdf_report(sample_pdf_request)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # Les fichiers PDF commencent toujours par le marqueur %PDF
    assert pdf_bytes.startswith(b"%PDF")

def test_export_pdf_endpoint(sample_pdf_request):
    """
    Vérifie que la route API POST /api/export-pdf génère correctement le PDF et le retourne.
    """
    payload = sample_pdf_request.model_dump()
    response = client.post("/api/export-pdf", json=payload)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "Content-Disposition" in response.headers
    assert "attachment; filename=" in response.headers["Content-Disposition"]
    
    # Vérification des données binaires
    content = response.content
    assert isinstance(content, bytes)
    assert len(content) > 0
    assert content.startswith(b"%PDF")
