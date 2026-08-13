import os
import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image
from google import genai
from google.genai import types
from fpdf import FPDF

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API para diagnóstico técnico de viviendas y derivación de inspecciones bajo normativa chilena",
    version="2.3.0"
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
    "reparable_bricolaje": true,
    "pasos_reparacion": [
        "Paso 1: ...",
        "Paso 2: ..."
    ],
    "requiere_inspector_tecnico": true,
    "motivo_inspeccion": "Explicación de por qué se requiere inspección presencial de Revisa Mi Casa basándose en el riesgo, la normativa antisísmica/estructural o la pérdida de garantía"
}
"""

class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 8, 'REVISA MI CASA - INFORME TÉCNICO PRELIMINAR', new_x="LMARGIN", new_y="NEXT", align='L')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(37, 99, 235)
        self.cell(0, 6, 'Evaluación de Patologías según Normativa Chilena (OGUC / LGUC / SEC)', new_x="LMARGIN", new_y="NEXT", align='L')
        self.set_draw_color(37, 99, 235)
        self.set_line_width(0.8)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, 'Informe automatizado preliminar por Revisa Mi Casa. Basado en OGUC, LGUC y normativas chilenas.', align='C')

def generar_pdf_bytes(datos: dict) -> bytes:
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Cuadro Resumen
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(10, pdf.get_y(), 190, 38, style='DF')
    
    start_y = pdf.get_y() + 3
    pdf.set_xy(12, start_y)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(15, 23, 42)
    
    fields = [
        ("Diagnóstico:", str(datos.get("titulo_diagnostico", "N/A"))),
        ("Categoría:", str(datos.get("categoria", "N/A"))),
        ("Nivel de Gravedad:", str(datos.get("nivel_gravedad", "N/A"))),
        ("Normativa Asociada:", str(datos.get("normativa_chilena_asociada", "N/A")))
    ]
    
    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(40, 7, label, new_x="RIGHT", new_y="TOP")
        pdf.set_font('Helvetica', '', 9)
        # Limpiar texto para prevenir encoding errors en FPDF
        val_clean = val.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(145, 7, val_clean, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(12)

    pdf.set_y(start_y + 38)
    pdf.ln(5)

    # Detalle Técnico
    sections = [
        ("Descripción del Problema Detectado:", datos.get("descripcion_problema", "")),
        ("Posible Causa Técnica:", datos.get("posible_causa", "")),
    ]

    for title, content in sections:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        content_clean = str(content).encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, content_clean)
        pdf.ln(3)

    if datos.get("requiere_inspector_tecnico"):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(0, 6, "RECOMENDACIÓN DE INSPECCIÓN PRESENCIAL:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        motivo = str(datos.get("motivo_inspeccion", "")).encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, motivo)
        pdf.ln(3)

    pasos = datos.get("pasos_reparacion", [])
    if pasos and datos.get("reparable_bricolaje"):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "Pasos Sugeridos de Reparación Menor:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        for paso in pasos:
            paso_clean = str(paso).encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, f"- {paso_clean}")

    return bytes(pdf.output())


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
        raise HTTPException(status_code=400, detail="Debe ser una imagen válida.")

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
        return {"exito": False, "error": str(e)}


@app.post("/diagnostico/pdf")
async def generar_reporte_pdf(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Debe ser una imagen válida.")

    try:
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_NORMATIVA_CHILE],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos = json.loads(response.text)
        pdf_bytes = generar_pdf_bytes(datos)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="informe_revisamicasa.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la generación: {str(e)}")
