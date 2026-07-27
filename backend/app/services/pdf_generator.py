import io
from datetime import datetime
from typing import List
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from app.schemas.pdf import PDFExportRequest, PDFBlock

def generate_pdf_report(request: PDFExportRequest) -> bytes:
    """
    Génère un rapport PDF tactique au format A4 en mémoire sous forme de tableau de bord de terrain.
    """
    # 1. Préparation du flux binaire
    buffer = io.BytesIO()
    
    # 2. Configuration du document (Marges de 1.5 cm / 42.5 pt)
    margin = 42.5
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )
    
    # Dimensions utiles
    content_width = A4[0] - (2 * margin)
    
    # 3. Styles
    styles = getSampleStyleSheet()
    
    # Palette de couleurs premium
    color_primary = HexColor("#047857")     # Vert Football
    color_secondary = HexColor("#064e3b")   # Vert foncé
    color_text = HexColor("#1e293b")        # Slate 800
    color_light_bg = HexColor("#f8fafc")    # Slate 50 (fond des cartes)
    color_border = HexColor("#e2e8f0")      # Slate 200
    
    # Custom Paragraph Styles
    style_main_title = ParagraphStyle(
        "PDFMainTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=color_secondary,
        spaceAfter=4
    )
    
    style_subtitle = ParagraphStyle(
        "PDFSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=HexColor("#64748b"),
        textTransform="uppercase",
        spaceAfter=2
    )
    
    style_meta = ParagraphStyle(
        "PDFMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=HexColor("#475569")
    )
    
    style_card_title = ParagraphStyle(
        "PDFCardTitle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=HexColor("#ffffff"),
        spaceBefore=0,
        spaceAfter=0
    )
    
    style_card_content = ParagraphStyle(
        "PDFCardContent",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=color_text,
        spaceAfter=0
    )
    
    story = []
    
    # --- HEADER SECTION ---
    # Date automatique si non fournie
    date_str = request.date if request.date else datetime.now().strftime("%d/%m/%Y")
    
    header_data = [
        [
            Paragraph("FOOTBALL IQ ASSISTANT", style_subtitle),
            Paragraph("FICHE DE TERRAIN", ParagraphStyle("Badge", parent=style_subtitle, alignment=2))
        ],
        [
            Paragraph(request.title, style_main_title),
            Paragraph("⚽ TACTIQUE", ParagraphStyle("SoccerBall", fontName="Helvetica-Bold", fontSize=12, textColor=color_primary, alignment=2))
        ]
    ]
    
    header_table = Table(header_data, colWidths=[content_width * 0.7, content_width * 0.3])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 8))
    
    # Barre métadonnées
    meta_text = f"<b>Entraîneur :</b> {request.coach} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date de séance :</b> {date_str}"
    meta_table_data = [[Paragraph(meta_text, style_meta)]]
    meta_table = Table(meta_table_data, colWidths=[content_width])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#f1f5f9")),
        ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # --- BLOCKS / CARDS ---
    for i, block in enumerate(request.blocks):
        # Remplacement des sauts de ligne pour ReportLab Paragraph
        formatted_content = block.content.replace("\n", "<br/>")
        
        # En-tête de carte (Card Header)
        title_p = Paragraph(f"{block.title.upper()}", style_card_title)
        card_header_table = Table([[title_p]], colWidths=[content_width])
        card_header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_primary),
            ('BOX', (0, 0), (-1, -1), 0.5, color_secondary),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        # Corps de carte (Card Body)
        content_p = Paragraph(formatted_content, style_card_content)
        card_body_table = Table([[content_p]], colWidths=[content_width])
        card_body_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_light_bg),
            ('BOX', (0, 0), (-1, -1), 0.5, color_border),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        # KeepTogether pour éviter de couper la carte en plein milieu du texte d'une page à l'autre
        card_flowable = KeepTogether([
            card_header_table,
            card_body_table,
            Spacer(1, 12)
        ])
        
        story.append(card_flowable)
        
    # --- FOOTER HOOK ---
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HexColor("#64748b"))
        # Ligne de séparation de pied de page
        canvas.setStrokeColor(HexColor("#cbd5e1"))
        canvas.setLineWidth(0.5)
        canvas.line(margin, 35, A4[0] - margin, 35)
        
        # Textes de pied de page
        canvas.drawString(margin, 22, "Football IQ Assistant - Fiche Tactique de Terrain Officielle")
        canvas.drawRightString(A4[0] - margin, 22, f"Page {doc.page}")
        canvas.restoreState()
        
    # Construire le PDF
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    
    # Récupérer les données binaires
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
