import os
import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image
from google import genai
from google.genai import types

# Librerías para generación de PDF nativo con ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API para diagnóstico técnico de viviendas bajo normativa chilena",
    version="3.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

PROMPT_NORMATIVA_CHILE = """
Actúa como un Inspector Técnico de Obras (ITO) y Perito Judicial de Edificación en Chile para 'Revisa Mi Casa'.
Analiza la fotografía adjunta que muestra una falla, daño o patología en una edificación ubicada en Chile.

Debes responder EXCLUSIVAMENTE en un objeto JSON válido con la siguiente estructura exacta:
{
    "titulo_diagnostico": "Nombre técnico de la falla",
    "categoria": "Pintura / Humedad / Estructura / Electricidad / Gasitería / Ventanales / Terminaciones",
    "nivel_gravedad": "Baja / Media / Alta / Crítica",
    "descripcion_problema": "Explicación clara y técnica para el propietario",
    "posible_causa": "Origen probable del problema",
    "normativa_chilena_asociada": "Mención explícita de norma NCh, OGUC, SEC, MINVU o LGUC",
    "reparable_bricolaje": true,
    "pasos_reparacion": ["Paso 1", "Paso 2"],
    "requiere_inspector_tecnico": true,
    "motivo_inspeccion": "Justificación de la inspección presencial"
}
"""


def generar_pdf_reportlab(datos: dict) -> bytes:
    """Genera un archivo PDF binario perfecto usando ReportLab"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2563eb'),
        fontName='Helvetica-Bold'
    )
    
    label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )
    
    val_style = ParagraphStyle(
        'FieldValue',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155'),
        fontName='Helvetica'
    )
    
    section_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold',
        spaceAfter=4
    )

    story = []

    # Encabezado
    story.append(Paragraph("REVISA MI CASA - INFORME TÉCNICO PRELIMINAR", title_style))
    story.append(Paragraph("Evaluación de Patologías según Normativa Chilena (OGUC / LGUC / SEC)", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=12))

    # Resumen Ficha Técnica (Tabla)
    table_data = [
        [Paragraph("Diagnóstico:", label_style), Paragraph(str(datos.get("titulo_diagnostico", "N/A")), val_style)],
        [Paragraph("Categoría:", label_style), Paragraph(str(datos.get("categoria", "N/A")), val_style)],
        [Paragraph("Gravedad:", label_style), Paragraph(str(datos.get("nivel_gravedad", "N/A")), val_style)],
        [Paragraph("Normativa:", label_style), Paragraph(str(datos.get("normativa_chilena_asociada", "N/A")), val_style)]
    ]

    t = Table(table_data, colWidths=[110, 430])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Descripción y Causa
    story.append(Paragraph("Descripción del Problema Detectado:", section_title))
    story.append(Paragraph(str(datos.get("descripcion_problema", "")), val_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Posible Causa Técnica:", section_title))
    story.append(Paragraph(str(datos.get("posible_causa", "")), val_style))
    story.append(Spacer(1, 10))

    # Recomendación de Inspección
    if datos.get("requiere_inspector_tecnico"):
        alert_style = ParagraphStyle(
            'AlertTitle',
            parent=section_title,
            textColor=colors.HexColor('#dc2626')
        )
        story.append(Paragraph("RECOMENDACIÓN DE INSPECCIÓN PRESENCIAL:", alert_style))
        story.append(Paragraph(str(datos.get("motivo_inspeccion", "")), val_style))
        story.append(Spacer(1, 10))

    # Pasos de Reparación
    pasos = datos.get("pasos_reparacion", [])
    if pasos and datos.get("reparable_bricolaje"):
        story.append(Paragraph("Pasos Sugeridos de Reparación Menor:", section_title))
        for paso in pasos:
            story.append(Paragraph(f"• {paso}", val_style))
            story.append(Spacer(1, 2))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@app.get("/")
def home():
    return {
        "status": "online",
        "servicio": "API Revisa Mi Casa - Normativa Chilena",
        "gemini_configurado": GEMINI_KEY is not None
    }


@app.post("/diagnostico")
async def diagnosticar_dano(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Debe cargar una imagen válida.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_NORMATIVA_CHILE],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return {"exito": True, "evaluacion": json.loads(response.text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/diagnostico/pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Retorna el informe técnico en formato PDF descargable.",
        }
    },
    summary="Generar Informe Técnico en PDF",
    description="Analiza la imagen enviada y genera un archivo PDF binario descargable."
)
async def generar_reporte_pdf(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Debe cargar una imagen válida.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_NORMATIVA_CHILE],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos_json = json.loads(response.text)
        
        # Generar bytes con ReportLab
        pdf_bytes = generar_pdf_reportlab(datos_json)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=informe_revisamicasa.pdf",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la generación del PDF: {str(e)}")
