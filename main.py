from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
import io
from reportlab.pdfgen import canvas

app = FastAPI()

def generar_pdf_reportlab(datos: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "Informe Técnico - Revisa Mi Casa")
    c.drawString(100, 730, f"Resultado: {datos.get('resultado_preliminar', '')}")
    c.drawString(100, 710, f"Tipo de falla: {datos.get('tipo_falla', '')}")
    c.drawString(100, 690, f"Mensaje: {datos.get('mensaje', '')}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

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
    # Validar que se suba un archivo
    if not foto:
        raise HTTPException(status_code=400, detail="Debe subir una imagen en el campo 'foto'.")

    # Validar que sea imagen
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen válida.")

    # Aquí iría tu lógica de diagnóstico, por ahora simulo datos
    datos = {
        "resultado_preliminar": "Evaluación preliminar completada",
        "tipo_falla": "Requiere revisión detallada",
        "mensaje": "Hemos detectado una posible falla en revestimiento/estructura."
    }

    # Generar PDF
    pdf_bytes = generar_pdf_reportlab(datos)

    # Retornar PDF como descarga
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=Informe_RevisaMiCasa.pdf"
        }
    )
