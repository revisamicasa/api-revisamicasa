import os
import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image
from google import genai
from google.genai import types

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API para diagnóstico técnico de viviendas bajo normativa chilena",
    version="5.1.0"
)

# Configuración de CORS
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
    "materiales_requeridos": ["Material 1", "Herramienta 2"],
    "pasos_reparacion": ["Paso 1", "Paso 2"],
    "estimacion_costo_reparacion": "Ej: $20.000 - $45.000 CLP",
    "requiere_inspector_tecnico": true,
    "motivo_inspeccion": "Justificación de la inspección presencial"
}
"""


def generar_pdf_reportlab(datos: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0f172a'), fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#2563eb'), fontName='Helvetica-Bold')
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#0f172a'), fontName='Helvetica-Bold')
    val_style = ParagraphStyle('Val', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#334155'), fontName='Helvetica')
    sec_title = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontSize=11, leading=15, textColor=colors.HexColor('#0f172a'), fontName='Helvetica-Bold', spaceAfter=4)

    story = []

    # Cabecera
    story.append(Paragraph("REVISA MI CASA - INFORME TÉCNICO PRELIMINAR", title_style))
    story.append(Paragraph("Evaluación Normativa y Guía de Reparación (OGUC / LGUC / SEC / NCh)", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=12))

    # Cuadro de Resumen Técnico
    table_data = [
        [Paragraph("Diagnóstico:", label_style), Paragraph(str(datos.get("titulo_diagnostico", "N/A")), val_style)],
        [Paragraph("Categoría:", label_style), Paragraph(str(datos.get("categoria", "N/A")), val_style)],
        [Paragraph("Gravedad:", label_style), Paragraph(str(datos.get("nivel_gravedad", "N/A")), val_style)],
        [Paragraph("Normativa:", label_style), Paragraph(str(datos.get("normativa_chilena_asociada", "N/A")), val_style)],
        [Paragraph("Costo Est. Reparación:", label_style), Paragraph(str(datos.get("estimacion_costo_reparacion", "N/A")), val_style)]
    ]

    t = Table(table_data, colWidths=[120, 420])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Detalle Técnico
    story.append(Paragraph("Descripción del Problema:", sec_title))
    story.append(Paragraph(str(datos.get("descripcion_problema", "")), val_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Posible Causa Técnica:", sec_title))
    story.append(Paragraph(str(datos.get("posible_causa", "")), val_style))
    story.append(Spacer(1, 8))

    # Materiales
    materiales = datos.get("materiales_requeridos", [])
    if materiales:
        story.append(Paragraph("Materiales y Herramientas Sugeridas:", sec_title))
        for mat in materiales:
            story.append(Paragraph(f"• {mat}", val_style))
        story.append(Spacer(1, 8))

    # Pasos
    pasos = datos.get("pasos_reparacion", [])
    if pasos:
        story.append(Paragraph("Pasos de Reparación Recomendados:", sec_title))
        for idx, paso in enumerate(pasos, 1):
            story.append(Paragraph(f"{idx}. {paso}", val_style))
        story.append(Spacer(1, 8))

    # Alerta ITO
    if datos.get("requiere_inspector_tecnico"):
        alert_style = ParagraphStyle('AlertTitle', parent=sec_title, textColor=colors.HexColor('#dc2626'))
        story.append(Paragraph("RECOMENDACIÓN DE INSPECCIÓN PRESENCIAL ITO:", alert_style))
        story.append(Paragraph(str(datos.get("motivo_inspeccion", "")), val_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@app.get("/")
def home():
    return {"status": "online", "servicio": "API Revisa Mi Casa"}


@app.post(
    "/diagnostico-gratis",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Retorna el informe técnico preliminar compilado en PDF."
        }
    }
)
async def diagnostico_gratis(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")
    
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo subido debe ser una imagen válida.")

    try:
        # 1. Procesar la imagen en memoria
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))

        # 2. Obtener respuesta estructurada de Gemini
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_NORMATIVA_CHILE],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos = json.loads(res.text)

        # 3. Construir el binario PDF con ReportLab
        pdf_bytes = generar_pdf_reportlab(datos)

        # 4. Retornar la respuesta como STREAM BINARIO PDF
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=Informe_RevisaMiCasa.pdf",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la solicitud: {str(e)}")
