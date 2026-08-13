import os
import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from PIL import Image
from google import genai
from google.genai import types

# Librerías para generación de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API para diagnóstico técnico de viviendas y derivación de inspecciones bajo normativa chilena",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar cliente de Gemini usando la variable de entorno
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

PROMPT_NORMATIVA_CHILE = """
Actúa como un Inspector Técnico de Obras (ITO) y Perito Judicial de Edificación en Chile para 'Revisa Mi Casa', con sólidos conocimientos respaldados por la academia y la normativa chilena vigente.

Analiza la fotografía adjunta que muestra una falla, daño o patología en una edificación ubicada en Chile.

Debes evaluar el daño y fundamentar tu diagnóstico aplicando estrictamente:
1. MARCO LEGAL Y NORMATIVO EN CHILE:
   - Ordenanza General de Urbanismo y Construcciones (OGUC).
   - Ley General de Urbanismo y Construcciones (LGUC) respecto a plazos de garantía legal (Ley N° 20.016: 10 años para fallas estructurales, 5 años para instalaciones y 3 años para elementos de terminaciones).
   - Normativa de Seguridad Eléctrica SEC (Pliegos Técnicos RIC) y Normativa Sanitaria/Gasitería (RIDAA).
   - Normativa y Reglamentación Antisísmica en Chile (NCh433, NCh3171).

2. ESTÁNDARES TÉCNICOS Y LITERATURA ESPECIALIZADA:
   - Manuales Técnicos del Ministerio de Vivienda y Urbanismo (MINVU).
   - Principios de ingeniería y patología de la edificación expuestos en "Procesos y técnicas de construcción" (G. Thenoux Z. y H. de Solminihac).
   - Criterios de inspección técnica, patologías constructivas y diagnósticos validados por la investigación académica de las facultades de ingeniería y construcción en Chile (U. de Chile, Pontificia Universidad Católica de Chile, UBB y U. de Valparaíso).

Debes responder EXCLUSIVAMENTE en un objeto JSON válido con la siguiente estructura exacta:
{
    "titulo_diagnostico": "Nombre técnico y preciso de la patología o falla detectada",
    "categoria": "Pintura / Humedad / Estructura / Electricidad / Gasitería / Ventanales / Terminaciones",
    "nivel_gravedad": "Baja / Media / Alta / Crítica",
    "descripcion_problema": "Explicación clara y técnica para el propietario sobre qué ocurre en la imagen",
    "posible_causa": "Origen probable del problema",
    "normativa_chilena_asociada": "Mención explícita de la norma NCh, OGUC, SEC, manual MINVU o garantía de la Ley de Construcción que aplica",
    "reparable_bricolaje": true_o_false,
    "pasos_reparacion": [
        "Paso 1: ...",
        "Paso 2: ..."
    ],
    "requiere_inspector_tecnico": true_o_false,
    "motivo_inspeccion": "Explicación de por qué se requiere inspección presencial de Revisa Mi Casa basándose en el riesgo, la normativa antisísmica/estructural o la pérdida de garantía"
}
"""

@app.get("/")
def home():
    return {
        "status": "online",
        "servicio": "API Revisa Mi Casa - Normativa Chilena",
        "gemini_configurado": GEMINI_KEY is not None
    }


def consultar_gemini(image: Image.Image) -> dict:
    if not client:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY no está configurada en las variables de entorno de Render."
        )

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image, PROMPT_NORMATIVA_CHILE],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)


def construir_pdf_bytes(datos: dict) -> bytes:
    """Genera los bytes binarios de un archivo PDF válido con ReportLab"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0F172A'), spaceAfter=8)
    style_subtitle = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceAfter=12)
    style_body = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#334155'))
    style_bold = ParagraphStyle('BoldStyle', parent=style_body, fontName='Helvetica-Bold')

    elements = []

    # Encabezado
    elements.append(Paragraph("REVISA MI CASA - INFORME TÉCNICO PRELIMINAR", style_title))
    elements.append(Paragraph("Evaluación de Patologías en Edificación según Normativa Chilena (OGUC/LGUC/SEC)", style_subtitle))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12))

    # Tabla
    datos_tabla = [
        [Paragraph("<b>Diagnóstico:</b>", style_body), Paragraph(datos.get("titulo_diagnostico", "N/A"), style_body)],
        [Paragraph("<b>Categoría:</b>", style_body), Paragraph(datos.get("categoria", "N/A"), style_body)],
        [Paragraph("<b>Gravedad:</b>", style_body), Paragraph(f"<b>{datos.get('nivel_gravedad', 'N/A')}</b>", style_body)],
        [Paragraph("<b>Normativa Chilena:</b>", style_body), Paragraph(datos.get("normativa_chilena_asociada", "N/A"), style_body)]
    ]
    
    t = Table(datos_tabla, colWidths=[120, 400])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # Detalle
    elements.append(Paragraph("<b>Descripción del Problema Detectado:</b>", style_bold))
    elements.append(Paragraph(datos.get("descripcion_problema", ""), style_body))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("<b>Posible Causa Técnica:</b>", style_bold))
    elements.append(Paragraph(datos.get("posible_causa", ""), style_body))
    elements.append(Spacer(1, 12))

    if datos.get("requiere_inspector_tecnico"):
        elements.append(Paragraph("<b>RECOMENDACIÓN DE INSPECCIÓN TÉCNICA PRESENCIAL:</b>", ParagraphStyle('AlertTitle', parent=style_bold, textColor=colors.HexColor('#DC2626'))))
        elements.append(Paragraph(datos.get("motivo_inspeccion", ""), style_body))
        elements.append(Spacer(1, 12))

    pasos = datos.get("pasos_reparacion", [])
    if pasos and datos.get("reparable_bricolaje"):
        elements.append(Paragraph("<b>Pasos Sugeridos de Reparación Menor:</b>", style_bold))
        for paso in pasos:
            elements.append(Paragraph(f"• {paso}", style_body))

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
    elements.append(Paragraph("<i>Informe generado de manera automatizada por Revisa Mi Casa. Evaluación preliminar basada en normativas técnicas chilenas (OGUC, LGUC, SEC, RIDAA).</i>", ParagraphStyle('Footer', parent=style_body, fontSize=7, textColor=colors.HexColor('#64748B'))))

    doc.build(elements)
    return buffer.getvalue()


@app.post("/diagnostico")
async def diagnosticar_dano(foto: UploadFile = File(...)):
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo subido debe ser una imagen válida.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        resultado = consultar_gemini(image)

        return {
            "exito": True,
            "evaluacion": resultado
        }
    except Exception as e:
        return {
            "exito": False,
            "error": f"Ocurrió un error al procesar la imagen: {str(e)}"
        }


@app.post("/diagnostico/pdf")
async def generar_reporte_pdf(foto: UploadFile = File(...)):
    """Genera y fuerza la descarga de un archivo PDF válido"""
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo subido debe ser una imagen válida.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        datos = consultar_gemini(image)
        pdf_bytes = construir_pdf_bytes(datos)

        headers = {
            "Content-Disposition": 'attachment; filename="informe_tecnico_revisamicasa.pdf"',
            "Content-Type": "application/pdf"
        }

        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")
