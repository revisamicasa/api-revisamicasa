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
    description="API de diagnósticos técnicos bajo normativa chilena",
    version="4.2.0"
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

PROMPT_PRELIMINAR = """
Actúa como Inspector Técnico de Obras (ITO) de 'Revisa Mi Casa' en Chile.
Analiza la imagen adjunta y genera un JSON con esta estructura exacta:
{
    "resultado_preliminar": "Evaluación preliminar completada",
    "tipo_falla": "Breve resumen de la falla detectada",
    "mensaje": "Hemos detectado una posible falla en revestimiento/estructura."
}
"""

PROMPT_DETALLADO = """
Actúa como Inspector Técnico de Obras (ITO) y Perito Judicial de Edificación en Chile para 'Revisa Mi Casa'.
Analiza la imagen y genera un JSON con la siguiente estructura:
{
    "titulo_diagnostico": "Nombre técnico de la falla",
    "categoria": "Pintura / Humedad / Estructura / Electricidad / Gasitería / Ventanales / Terminaciones",
    "nivel_gravedad": "Baja / Media / Alta / Crítica",
    "descripcion_problema": "Explicación clara y técnica",
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

    story.append(Paragraph("REVISA MI CASA - INFORME TÉCNICO DETALLADO", title_style))
    story.append(Paragraph("Evaluación Normativa y Guía de Reparación (OGUC / LGUC / SEC / NCh)", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=12))

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

    story.append(Paragraph("Descripción del Problema:", sec_title))
    story.append(Paragraph(str(datos.get("descripcion_problema", "")), val_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Posible Causa Técnica:", sec_title))
    story.append(Paragraph(str(datos.get("posible_causa", "")), val_style))
    story.append(Spacer(1, 8))

    materiales = datos.get("materiales_requeridos", [])
    if materiales:
        story.append(Paragraph("Materiales y Herramientas Sugeridas:", sec_title))
        for mat in materiales:
            story.append(Paragraph(f"• {mat}", val_style))
        story.append(Spacer(1, 8))

    pasos = datos.get("pasos_reparacion", [])
    if pasos:
        story.append(Paragraph("Pasos de Reparación Paso a Paso:", sec_title))
        for idx, paso in enumerate(pasos, 1):
            story.append(Paragraph(f"{idx}. {paso}", val_style))
        story.append(Spacer(1, 8))

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


@app.post("/evaluar-gratis")
async def evaluar_gratis(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))

        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_PRELIMINAR],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos = json.loads(res.text)

        return {
            "resultado_preliminar": datos.get("resultado_preliminar", "Evaluación preliminar completada"),
            "tipo_falla": datos.get("tipo_falla", "Requiere revisión detallada"),
            "mensaje": datos.get("mensaje", "Hemos detectado una posible falla en revestimiento/estructura."),
            "opciones": {
                "informe_detallado_pago": {
                    "precio_clp": 3990,
                    "incluye": "Lista de materiales, paso a paso de reparación y estimación de costos."
                },
                "agendar_inspector": {
                    "recomendado": True,
                    "mensaje": "Si prefieres no reparar tú mismo, podemos enviar un inspector técnico de Revisa Mi Casa."
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/descargar-informe-pago",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Retorna el informe técnico detallado en formato PDF."
        }
    }
)
async def descargar_informe_pago(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))

        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_DETALLADO],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos_detallados = json.loads(res.text)

        pdf_bytes = generar_pdf_reportlab(datos_detallados)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=Informe_Detallado_RevisaMiCasa.pdf",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
