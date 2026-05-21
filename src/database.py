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
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
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
        # Forzar carga de alertas mientras la sesión está abierta
        alertas_desc = [a.descripcion for a in factura.alertas]
        d = {c.name: getattr(factura, c.name) for c in factura.__table__.columns}
        if d["fecha_procesamiento"]:
            d["fecha_procesamiento"] = d["fecha_procesamiento"].isoformat()
        d["alertas"] = alertas_desc
        return d
    except Exception as e:
        db.rollback()
        raise e
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
