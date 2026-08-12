from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Revisa Mi Casa API",
    description="API para diagnóstico técnico de viviendas y derivación de inspecciones",
    version="1.0.0"
)

# Permitir que tu sitio web en HostingNet consulte a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se reemplaza por https://revisamicasa.cl
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "status": "online",
        "servicio": "API Revisa Mi Casa",
        "version": "1.0.0"
    }

@app.post("/diagnostico-gratis")
async def diagnostico_gratis(foto: UploadFile = File(...)):
    """
    Endpoint gratuito: Recibe la foto, evalúa gravedad preliminar 
    y sugiere si requiere informe detallado o inspección presencial.
    """
    # Aquí procesaremos la imagen con el modelo de visión por IA
    return {
        "resultado_preliminar": "Evaluación preliminar completada",
        "tipo_falla": "Requiere revisión detallada",
        "mensaje": "Hemos detectado una posible falla en revestimiento/estructura.",
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
