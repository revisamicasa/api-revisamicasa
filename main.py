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
    description="API para diagnóstico técnico de viviendas bajo normativa chilena",
    version="3.0.0"
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

def limpiar_texto(texto: str) -> str:
    """Elimina o reemplaza caracteres no soportados por las fuentes estándar de FPDF"""
    if not texto:
        return ""
    
    # Mapeo manual de caracteres comunes en español
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', '°': ' deg ', '“': '"', '”': '"',
        '’': "'", '–': '-', '—': '-', '¿': '', '¡': ''
    }
    for orig, rempl in reemplazos.items():
        texto = texto.replace(orig, rempl)
    
    # Asegurar que solo contenga caracteres latin-1 legibles
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def crear_pdf_binario(datos: dict) -> bytes:
    """Genera el buffer de bytes binarios del PDF"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Encabezado principal
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, 'REVISA MI CASA - INFORME TECNICO PRELIMINAR', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(0, 6, 'Evaluacion de Patologias segun Normativa Chilena (OGUC / LGUC / SEC)', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_draw_color(37, 99, 235)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(8)

    # Resumen Ejecutivo
    fields = [
        ("Diagnostico:", datos.get("titulo_diagnostico", "N/A")),
        ("Categoria:", datos.get("categoria", "N/A")),
        ("Nivel de Gravedad:", datos.get("nivel_gravedad", "N/A")),
        ("Normativa Asociada:", datos.get("normativa_chilena_asociada", "N/A"))
    ]
    
    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 6, label, new_x="RIGHT", new_y="TOP")
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 6, limpiar_texto(str(val)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    pdf.ln(4)

    # Secciones Detalladas
    sections = [
        ("Descripcion del Problema Detectado:", datos.get("descripcion_problema", "")),
        ("Posible Causa Tecnica:", datos.get("posible_causa", "")),
    ]

    for title, content in sections:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 5, limpiar_texto(str(content)))
        pdf.ln(3)

    if datos.get("requiere_inspector_tecnico"):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(0, 6, "RECOMENDACION DE INSPECCION PRESENCIAL:", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 5, limpiar_texto(str(datos.get("motivo_inspeccion", ""))))
        pdf.ln(3)

    pasos = datos.get("pasos_reparacion", [])
    if pasos and datos.get("reparable_bricolaje"):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "Pasos Sugeridos de Reparacion Menor:", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        for paso in pasos:
            pdf.multi_cell(0, 5, f"- {limpiar_texto(str(paso))}")

    # Retorna los bytes directamente
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
        raise HTTPException(status_code=400, detail="Debe cargar una imagen valida.")

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


@app.post("/diagnostico/pdf")
async def generar_reporte_pdf(foto: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no configurada.")
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Debe cargar una imagen valida.")

    try:
        # 1. Leer imagen
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))
        
        # 2. Consultar Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, PROMPT_NORMATIVA_CHILE],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        datos_json = json.loads(response.text)
        
        # 3. Generar PDF binario en memoria
        pdf_bytes = crear_pdf_binario(datos_json)

        # 4. Devolver respuesta de bytes explícita con headers adecuados
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=informe_revisamicasa.pdf",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la generacion del PDF: {str(e)}")
