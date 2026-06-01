import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

from src.database import inicializar_db, guardar_factura_db, obtener_facturas, obtener_factura_por_id, eliminar_factura_db, obtener_estadisticas
from src.preprocessing import preprocesar
from src.ocr_engine import extraer_texto, calcular_confianza
from src.entity_extractor import extraer_datos
from src.validator import validar
from src.exporter import exportar_json, generar_excel

@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_db()
    print("[API] Servidor listo")
    yield
    print("[API] Servidor detenido.")

app = FastAPI(title="Sistema OCR Facturas", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Servir el frontend
app.mount("/app", StaticFiles(directory=os.path.join(config.BASE_DIR, "frontend"), html=True), name="frontend")

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf"}

@app.get("/")
async def raiz():
    return {"sistema": "OCR Facturas", "version": "1.0.0"}

import io

@app.post("/facturas/")
async def procesar_factura_endpoint(archivo: UploadFile = File(...)):
    # Validate extension
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(400, "Formato no soportado")
    filename = archivo.filename
    ruta_temp = os.path.join(config.INPUT_DIR, archivo.filename)
    with open(ruta_temp, "wb") as f:
        f.write(await archivo.read())
    inicio = time.time()
    imagen = preprocesar(ruta_temp)
    texto_crudo = extraer_texto(imagen)
    confianza = calcular_confianza(imagen)
    datos = extraer_datos(texto_crudo)
    datos["confianza_ocr"] = confianza
    datos["archivo_origen"] = filename
    datos["texto_crudo"] = texto_crudo
    res_val = validar(datos)
    datos.update(res_val)
    datos["tiempo_procesamiento_seg"] = round(time.time() - inicio, 2)

    exportar_json(datos)
    factura_dict = guardar_factura_db(datos)

    return {"mensaje": "Exito", "factura": factura_dict}

@app.get("/facturas/")
async def listar_facturas():
    facturas = obtener_facturas()
    return {"total": len(facturas), "facturas": [f.to_dict() for f in facturas]}

@app.get("/estadisticas/")
async def estadisticas():
    return {"estadisticas": obtener_estadisticas()}

@app.get("/facturas/exportar/excel/")
async def exportar_facturas_excel(ids: str = Query(..., description="IDs de facturas separadas por comas")):
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    except Exception:
        raise HTTPException(400, "IDs inválidos")
        
    if not id_list:
        raise HTTPException(400, "Debe proporcionar al menos un ID de factura")
        
    db_facturas = []
    for fid in id_list:
        factura = obtener_factura_por_id(fid)
        if factura:
            db_facturas.append(factura.to_dict())
            
    if not db_facturas:
        raise HTTPException(404, "No se encontraron facturas con los IDs proporcionados")
        
    excel_io = generar_excel(db_facturas)
    
    headers = {
        'Content-Disposition': 'attachment; filename="facturas_exportadas.xlsx"'
    }
    return StreamingResponse(
        excel_io,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
