import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
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
