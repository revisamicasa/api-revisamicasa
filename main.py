import os
import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from google import genai
from google.genai import types

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API con visión por IA para diagnóstico de patologías en la construcción",
    version="2.0.0"
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


@app.get("/")
def home():
    return {
        "status": "online",
        "servicio": "API Revisa Mi Casa - Módulo Visión IA",
        "gemini_configurado": GEMINI_KEY is not None
    }


@app.post("/diagnostico")
async def diagnosticar_dano(foto: UploadFile = File(...)):
    """
    Recibe la imagen cargada por el cliente, la analiza mediante Gemini Vision
    y retorna la evaluación técnica preliminar, pasos de solución o recomendación de inspección.
    """
    if not client:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY no está configurada en las variables de entorno de Render."
        )

    # Validar que el archivo sea una imagen
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo subido debe ser una imagen válida.")

    try:
        # Leer la imagen subida
        contents = await foto.read()
        image = Image.open(io.BytesIO(contents))

        # Prompt especializado para Revisa Mi Casa
        prompt = """
        Actúa como un Inspector Técnico de Construcción y Edificación con alta experiencia para 'Revisa Mi Casa'.
        Analiza la fotografía adjunta que muestra una falla, daño o desperfecto en una vivienda.

        Debes responder EXCLUSIVAMENTE en un objeto JSON válido con la siguiente estructura exacta:
        {
            "titulo_diagnostico": "Nombre técnico y breve de la falla detectada",
            "categoria": "Pintura / Humedad / Estructura / Electricidad / Gasitería / Ventanales / Otro",
            "nivel_gravedad": "Baja / Media / Alta / Crítica",
            "descripcion_problema": "Explicación clara para el propietario sobre qué ocurre en la imagen",
            "posible_causa": "Causa probable del origen del problema",
            "reparable_bricolaje": true_o_false,
            "pasos_reparacion": [
                "Paso 1: ...",
                "Paso 2: ..."
            ],
            "requiere_inspector_tecnico": true_o_false,
            "motivo_inspeccion": "Explicación de por qué se recomienda o exige enviar un inspector de Revisa Mi Casa si el problema es grave"
        }
        """

        # Consultar al modelo Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # Parsear la respuesta JSON de Gemini
        resultado = json.loads(response.text)
        return {
            "exito": True,
            "evaluacion": resultado
        }

    except Exception as e:
        return {
            "exito": False,
            "error": f"Ocurrió un error al procesar la imagen: {str(e)}"
        }
