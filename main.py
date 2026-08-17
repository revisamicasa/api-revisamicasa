import io
import os
import gc
import re
import logging
import traceback
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError, ImageOps
from google import genai
from google.genai import types, errors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS PARA RENDER (Nivel DEBUG)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("RevisaMiCasaAPI")

app = FastAPI(
    title="Super API - Revisa Mi Casa",
    description="Servicio profesional de diagnóstico técnico e inspección de viviendas con IA.",
    version="2.0.7"
)

# Interceptor global para registrar excepciones en los logs de Render
@app.middleware("http")
async def log_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(f"--- EXCEPCIÓN NO CONTROLADA EN {request.url.path} ---")
        logger.error(f"Detalle del error: {str(exc)}")
        logger.error(traceback.format_exc())
        logger.error("-----------------------------------------------------")
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor", "error_log": str(exc)}
        )

# Límite de entrada por archivo (10 MB)
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def optimizar_para_gemini(imagen_bytes: bytes, max_dim: int = 600) -> bytes:
    """Valida, corrige orientación EXIF, convierte espacios de color y comprime la imagen."""
    try:
        logger.debug("Iniciando procesamiento de imagen con Pillow...")
        with Image.open(io.BytesIO(imagen_bytes)) as img:
            logger.debug(f"Formato original: {img.format}, Modo: {img.mode}, Tamaño: {img.size}")

            # Rotación automática según metadatos EXIF de la cámara/celular
            img = ImageOps.exif_transpose(img)

            if img.mode in ("RGBA", "P", "CMYK"):
                logger.debug(f"Convirtiendo espacio de color de {img.mode} a RGB...")
                img = img.convert("RGB")

            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buffer_salida = io.BytesIO()
            img.save(buffer_salida, format="JPEG", quality=60, optimize=True)
            res_bytes = buffer_salida.getvalue()
            logger.debug(f"Imagen optimizada exitosamente. Tamaño final: {len(res_bytes)} bytes")
            return res_bytes
    except UnidentifiedImageError as uie:
        logger.error(f"Error Pillow: Archivo no identificado como imagen válida. {str(uie)}")
        raise ValueError("El archivo enviado no es una imagen válida o está dañado.")
    except Exception as e:
        logger.error(f"Error inesperado al optimizar imagen: {str(e)}")
        raise ValueError(f"Error al procesar la imagen: {str(e)}")


def sanitizar_texto_para_pdf(texto: str) -> str:
    """Limpia caracteres especiales para evitar colapsos en ReportLab."""
    if not texto:
        return "Sin observaciones registradas."

    texto = re.sub(r'```(?:json)?', '', texto)
    texto = texto.replace('```', '')
    texto = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return texto.strip()


def generar_pdf_informe(texto_diagnostico: str, imagenes_bytes: List[bytes]) -> bytes:
    """Compila el informe PDF en memoria garantizando una fila uniforme."""
    logger.debug("Iniciando generación de PDF con ReportLab...")
    buffer = io.BytesIO()
    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        story = []
        styles = getSampleStyleSheet()

        titulo_style = ParagraphStyle(
            'TituloHeader',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F2942"),
            spaceAfter=4
        )

        subtitulo_style = ParagraphStyle(
            'SubTituloHeader',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#5A6B7C"),
            spaceAfter=15
        )

        cuerpo_style = ParagraphStyle(
            'CuerpoDoc',
            parent=styles['BodyText'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2C3E50"),
            spaceAfter=8
        )

        story.append(Paragraph("<b>REVISA MI CASA</b>", titulo_style))
        story.append(Paragraph("Informe Técnico de Inspección Preventiva | www.revisamicasa.cl", subtitulo_style))
        story.append(Spacer(1, 10))

        if imagenes_bytes:
            elementos_img = []
            for idx, img_bytes in enumerate(imagenes_bytes):
                try:
                    img_stream = io.BytesIO(img_bytes)
                    elementos_img.append(RLImage(img_stream, width=220, height=165))
                except Exception as img_err:
                    logger.warning(f"Error al adjuntar foto #{idx+1} al PDF: {img_err}")

            if elementos_img:
                num_columnas = len(elementos_img)
                tabla_fotos = Table([elementos_img], colWidths=[240] * num_columnas)
                tabla_fotos.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ]))
                story.append(tabla_fotos)
                story.append(Spacer(1, 10))

        story.append(Paragraph("<b>Evaluación y Recomendaciones del Inspector:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))

        texto_limpio = sanitizar_texto_para_pdf(texto_diagnostico)
        parrafos = texto_limpio.split('\n')

        for p in parrafos:
            linea = p.strip()
            if linea:
                linea = re.sub(r'^[*\-•]\s*', '', linea)
                story.append(Paragraph(linea, cuerpo_style))

        doc.build(story)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        logger.debug(f"PDF generado correctamente. Tamaño: {len(pdf_data)} bytes")
        return pdf_data
    except Exception as pdf_e:
        logger.error(f"Fallo crítico al ensamblar el PDF en ReportLab: {str(pdf_e)}")
        logger.error(traceback.format_exc())
        raise pdf_e
    finally:
        buffer.close()


def consultar_gemini_api(api_key: str, imagenes_optimizadas: List[bytes]) -> str:
    """Consulta la API usando el SDK oficial de Google GenAI."""
    logger.debug("Conectando con la API de Gemini...")
    client = genai.Client(api_key=api_key)

    prompt = (
        "Eres un inspector técnico de viviendas experto en edificación y normativa en Chile. "
        "Analiza las imágenes adjuntas y redacta un diagnóstico técnico profesional, estructurado en:\n"
        "1. Hallazgo / Falla Detectada\n"
        "2. Causa Probable\n"
        "3. Recomendación Técnica de Reparación\n\n"
        "Sé preciso, conciso (máximo 3 párrafos en total) y profesional. NO utilices formato JSON ni bloques de código."
    )

    config = types.GenerateContentConfig(
        max_output_tokens=450,
        temperature=0.2
    )

    partes = [types.Part.from_bytes(data=img, mime_type='image/jpeg') for img in imagenes_optimizadas]
    partes.append(prompt)

    logger.debug("Enviando petición de generación de contenido a gemini-2.0-flash...")
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=partes,
        config=config
    )

    if response and response.text:
        logger.debug("Respuesta recibida exitosamente desde Gemini.")
        return response.text

    logger.error("Gemini no devolvió texto en la respuesta.")
    raise RuntimeError("La API de Gemini no devolvió texto en el diagnóstico.")


@app.get("/", summary="Estado del Servicio")
def read_root():
    logger.info("Consulta al endpoint raíz '/' realizada.")
    return Response(content="Super API Revisa Mi Casa v2.0.7 - Operativa", media_type="text/plain")


@app.post(
    "/diagnostico-gratis",
    summary="Generar Diagnóstico en PDF",
    description="Procesa hasta 2 imágenes enviadas por el usuario, consulta la IA y devuelve un documento PDF descargable."
)
async def diagnostico_gratis(
    fotos: Optional[List[UploadFile]] = File(
        default=None,
        description="[ESTÁNDAR RECOMENDADO] Lista de hasta 2 imágenes asociadas a la inspección."
    ),
    foto: Optional[UploadFile] = File(
        default=None,
        description="[DEPRECADA / LEGADO] Imagen individual enviada por clientes anteriores."
    )
):
    lista_fotos: List[UploadFile] = []
    if fotos:
        lista_fotos.extend(fotos)
    if foto:
        lista_fotos.append(foto)

    logger.info(f"--- NUEVA PETICIÓN EN /diagnostico-gratis --- Archivos recibidos: {len(lista_fotos)}")

    if not lista_fotos:
        logger.warning("Petición rechazada: No se incluyeron fotos.")
        raise HTTPException(
            status_code=400, 
            detail="Debe adjuntar al menos una imagen en el parámetro 'fotos' o 'foto'."
        )

    if len(lista_fotos) > 2:
        logger.warning(f"Petición rechazada: {len(lista_fotos)} fotos enviadas (máximo permitido: 2).")
        raise HTTPException(status_code=400, detail="El límite máximo es de 2 imágenes por consulta.")

    imagenes_optimizadas = []

    try:
        for idx, f in enumerate(lista_fotos):
            logger.info(f"Procesando archivo #{idx+1}: {f.filename} (ContentType: {f.content_type})")
            imagen_bytes = await f.read()

            if len(imagen_bytes) == 0:
                logger.warning(f"Archivo {f.filename} está vacío (0 bytes). Omitiendo.")
                continue

            if len(imagen_bytes) > MAX_IMAGE_SIZE:
                logger.error(f"Archivo {f.filename} excede el tamaño máximo: {len(imagen_bytes)} bytes.")
                raise HTTPException(
                    status_code=400,
                    detail=f"La imagen '{f.filename}' supera el peso máximo permitido (10 MB)."
                )

            try:
                img_opt = await run_in_threadpool(optimizar_para_gemini, imagen_bytes)
                imagenes_optimizadas.append(img_opt)
            except ValueError as ve:
                logger.error(f"Error procesando imagen '{f.filename}': {str(ve)}")
                raise HTTPException(status_code=400, detail=str(ve))
            finally:
                del imagen_bytes

        if not imagenes_optimizadas:
            logger.error("No se obtuvieron imágenes válidas tras la optimización.")
            raise HTTPException(status_code=400, detail="No se enviaron imágenes válidas.")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.critical("VARIABLE DE ENTORNO NO ENCONTRADA: 'GEMINI_API_KEY' no está configurada.")
            raise HTTPException(status_code=500, detail="Error de configuración interna del servidor: Falta API Key.")

        # Consulta a Gemini
        try:
            texto_diagnostico = await run_in_threadpool(
                consultar_gemini_api, api_key, imagenes_optimizadas
            )
        except errors.APIError as api_err:
            logger.error(f"Error específico devuelto por la API de Gemini: {api_err}")
            raise HTTPException(
                status_code=502,
                detail=f"Servicio de IA no disponible: {api_err.message}"
            )
        except Exception as ai_err:
            logger.error(f"Fallo durante la invocación de IA: {str(ai_err)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al analizar la imagen mediante la IA: {str(ai_err)}"
            )

        # Generación del PDF
        try:
            pdf_bytes = await run_in_threadpool(
                generar_pdf_informe, texto_diagnostico, imagenes_optimizadas
            )
        except Exception as pdf_err:
            logger.error(f"Fallo durante la generación del PDF: {str(pdf_err)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar el documento PDF: {str(pdf_err)}"
            )

        logger.info("=== PROCESO COMPLETADO EXITOSAMENTE: PDF Entregado ===")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=Informe_Diagnostico_RevisaMiCasa.pdf"
            }
        )

    finally:
        imagenes_optimizadas.clear()
        gc.collect()
        logger.debug("Recursos en memoria liberados mediante garbage collector.")


if __name__ == "__main__":
    import uvicorn
    # Render asigna el puerto dinámicamente en la variable PORT. Si no existe, usa 8000.
    port_env = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port_env)
