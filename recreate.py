import os

src_dir = r"d:\Noveno_Semestre\Procesamiento_Lenguaje_Natural\Facturas\src"
os.makedirs(src_dir, exist_ok=True)

files = {}

files["__init__.py"] = ""

files["api.py"] = """
import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

from src.database import inicializar_db, guardar_factura_db, obtener_facturas, obtener_factura_por_id, eliminar_factura_db, obtener_estadisticas
from src.preprocessing import preprocesar
from src.ocr_engine import extraer_texto, calcular_confianza
from src.entity_extractor import extraer_datos
from src.validator import validar
from src.exporter import exportar_json

@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_db()
    print("[API] Servidor listo")
    yield
    print("[API] Servidor detenido.")

app = FastAPI(title="Sistema OCR Facturas", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf"}

@app.get("/")
async def raiz():
    return {"sistema": "OCR Facturas", "version": "1.0.0"}

@app.post("/facturas/")
async def procesar_factura_endpoint(archivo: UploadFile = File(...)):
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(400, "Formato no soportado")

    ruta_temp = os.path.join(config.INPUT_DIR, archivo.filename)
    with open(ruta_temp, "wb") as f:
        f.write(await archivo.read())

    inicio = time.time()
    imagen = preprocesar(ruta_temp)
    texto_crudo = extraer_texto(imagen)
    confianza = calcular_confianza(imagen)

    datos = extraer_datos(texto_crudo)
    datos["confianza_ocr"] = confianza
    datos["archivo_origen"] = archivo.filename
    datos["texto_crudo"] = texto_crudo

    res_val = validar(datos)
    datos.update(res_val)
    datos["tiempo_procesamiento_seg"] = round(time.time() - inicio, 2)

    exportar_json(datos)
    factura = guardar_factura_db(datos)

    return {"mensaje": "Exito", "factura": factura.to_dict()}

@app.get("/facturas/")
async def listar_facturas():
    facturas = obtener_facturas()
    return {"total": len(facturas), "facturas": [f.to_dict() for f in facturas]}

@app.get("/estadisticas/")
async def estadisticas():
    return {"estadisticas": obtener_estadisticas()}
"""

files["database.py"] = """
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Factura(Base):
    __tablename__ = "facturas"
    id = Column(Integer, primary_key=True, index=True)
    numero_factura = Column(String, nullable=True)
    fecha_emision = Column(String, nullable=True)
    proveedor_ruc = Column(String, nullable=True)
    proveedor_nombre = Column(String, nullable=True)
    subtotal = Column(Float, nullable=True)
    igv = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    confianza_ocr = Column(Float, nullable=True)
    archivo_origen = Column(String, unique=True, index=True)
    texto_crudo = Column(Text, nullable=True)
    es_valido = Column(Boolean, default=False)
    estado = Column(String, default="ERROR_OCR")
    tiempo_procesamiento_seg = Column(Float, nullable=True)
    fecha_procesamiento = Column(DateTime, default=datetime.utcnow)
    alertas = relationship("Alerta", back_populates="factura", cascade="all, delete-orphan")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c.table.columns in self.__table__.columns}
        d["alertas"] = [a.descripcion for a in self.alertas]
        if d["fecha_procesamiento"]: d["fecha_procesamiento"] = d["fecha_procesamiento"].isoformat()
        return d

class Alerta(Base):
    __tablename__ = "alertas"
    id = Column(Integer, primary_key=True, index=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"))
    descripcion = Column(String)
    factura = relationship("Factura", back_populates="alertas")

def inicializar_db():
    Base.metadata.create_all(bind=engine)

def guardar_factura_db(datos: dict) -> Factura:
    db = SessionLocal()
    try:
        factura = db.query(Factura).filter(Factura.archivo_origen == datos["archivo_origen"]).first()
        if not factura:
            factura = Factura(archivo_origen=datos["archivo_origen"])
        
        factura.numero_factura = datos.get("numero_factura")
        factura.fecha_emision = datos.get("fecha_emision")
        factura.proveedor_ruc = datos.get("proveedor_ruc")
        factura.proveedor_nombre = datos.get("proveedor_nombre")
        factura.subtotal = datos.get("subtotal")
        factura.igv = datos.get("igv")
        factura.total = datos.get("total")
        factura.confianza_ocr = datos.get("confianza_ocr")
        factura.texto_crudo = datos.get("texto_crudo")
        factura.es_valido = datos.get("es_valido", False)
        factura.estado = datos.get("estado", "ERROR_OCR")
        factura.tiempo_procesamiento_seg = datos.get("tiempo_procesamiento_seg")
        
        db.query(Alerta).filter(Alerta.factura_id == factura.id).delete()
        db.add(factura)
        db.flush()
        
        for desc in datos.get("alertas", []):
            db.add(Alerta(factura_id=factura.id, descripcion=desc))
            
        db.commit()
        db.refresh(factura)
        return factura
    finally:
        db.close()

def obtener_facturas():
    db = SessionLocal()
    try:
        return db.query(Factura).all()
    finally:
        db.close()

def obtener_factura_por_id(id: int):
    db = SessionLocal()
    try:
        return db.query(Factura).filter(Factura.id == id).first()
    finally:
        db.close()

def eliminar_factura_db(id: int):
    db = SessionLocal()
    try:
        f = db.query(Factura).filter(Factura.id == id).first()
        if f:
            db.delete(f)
            db.commit()
            return True
        return False
    finally:
        db.close()

def obtener_estadisticas():
    db = SessionLocal()
    try:
        facturas = db.query(Factura).all()
        return {
            "total": len(facturas),
            "exitosas": sum(1 for f in facturas if f.estado == "EXITO"),
            "monto_total": sum(f.total for f in facturas if f.total)
        }
    finally:
        db.close()
"""

files["preprocessing.py"] = """
import cv2
import numpy as np

def preprocesar(ruta: str) -> np.ndarray:
    img = cv2.imread(ruta)
    if img is None: raise FileNotFoundError(ruta)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh
"""

files["ocr_engine.py"] = """
import pytesseract

def extraer_texto(imagen) -> str:
    return pytesseract.image_to_string(imagen, lang='spa')

def calcular_confianza(imagen) -> float:
    data = pytesseract.image_to_data(imagen, lang='spa', output_type=pytesseract.Output.DICT)
    confs = [int(c) for c in data['conf'] if int(c) != -1]
    return sum(confs) / len(confs) if confs else 0.0
"""

files["entity_extractor.py"] = """
import re

def extraer_datos(texto: str) -> dict:
    datos = {
        "numero_factura": None,
        "fecha_emision": None,
        "proveedor_ruc": None,
        "proveedor_nombre": None,
        "subtotal": None,
        "igv": None,
        "total": None
    }
    
    # RUC
    ruc_match = re.search(r'RUC.*?(\d{11})', texto, re.IGNORECASE)
    if ruc_match: datos["proveedor_ruc"] = ruc_match.group(1)
    
    # Total
    total_match = re.search(r'TOTAL.*?(\d+[.,]\d{2})', texto, re.IGNORECASE)
    if total_match:
        try:
            datos["total"] = float(total_match.group(1).replace(',', '.'))
        except: pass
        
    # Subtotal
    sub_match = re.search(r'SUBTOTAL.*?(\d+[.,]\d{2})', texto, re.IGNORECASE)
    if sub_match:
        try:
            datos["subtotal"] = float(sub_match.group(1).replace(',', '.'))
        except: pass
        
    return datos
"""

files["validator.py"] = """
def validar(datos: dict) -> dict:
    alertas = []
    es_valido = True
    
    if not datos.get("proveedor_ruc"):
        alertas.append("Falta RUC")
        es_valido = False
        
    if not datos.get("total"):
        alertas.append("Falta Total")
        es_valido = False
        
    return {
        "es_valido": es_valido,
        "alertas": alertas,
        "estado": "EXITO" if es_valido else "REVISION_MANUAL"
    }
"""

files["exporter.py"] = """
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

def exportar_json(datos: dict):
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    fname = "output_" + datos.get("archivo_origen", "factura") + ".json"
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
"""

files["pipeline.py"] = """
import os
import sys
import time
from src.preprocessing import preprocesar
from src.ocr_engine import extraer_texto, calcular_confianza
from src.entity_extractor import extraer_datos
from src.validator import validar
from src.exporter import exportar_json
from src.database import inicializar_db, guardar_factura_db

def procesar_factura(ruta: str):
    inicializar_db()
    inicio = time.time()
    imagen = preprocesar(ruta)
    texto = extraer_texto(imagen)
    conf = calcular_confianza(imagen)
    datos = extraer_datos(texto)
    datos["confianza_ocr"] = conf
    datos["archivo_origen"] = os.path.basename(ruta)
    datos["texto_crudo"] = texto
    
    val = validar(datos)
    datos.update(val)
    datos["tiempo_procesamiento_seg"] = time.time() - inicio
    
    exportar_json(datos)
    guardar_factura_db(datos)
    print("Factura procesada:", datos)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        procesar_factura(sys.argv[1])
"""

for fname, content in files.items():
    with open(os.path.join(src_dir, fname), "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Recreated {fname}")

