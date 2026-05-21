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
