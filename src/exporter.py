import json
import os
import sys
import io
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

def exportar_json(datos: dict):
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    fname = "output_" + datos.get("archivo_origen", "factura") + ".json"
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)

def generar_excel(facturas: list) -> io.BytesIO:
    # Preprocesar alertas para unirlas con comas
    for fact in facturas:
        if "alertas" in fact and isinstance(fact["alertas"], list):
            fact["alertas"] = ", ".join(fact["alertas"])
            
    # Convert list of dicts to DataFrame
    df = pd.DataFrame(facturas)
    
    # We want a cleaner Excel with user-friendly headers
    columnas_deseadas = {
        "numero_factura": "Número de factura",
        "fecha_emision": "Fecha",
        "proveedor_ruc": "RUC emisor",
        "cliente_nombre": "Cliente",
        "total": "Total",
        "igv": "IGV"
    }
    
    # Filter to keep only desired columns that actually exist in df
    cols_to_keep = [col for col in columnas_deseadas.keys() if col in df.columns]
    df_filtrado = df[cols_to_keep].copy()
    
    # Rename columns to user-friendly Spanish names
    df_filtrado.rename(columns={col: columnas_deseadas[col] for col in cols_to_keep}, inplace=True)
    
    output = io.BytesIO()
    try:
        # Try writing as excel (.xlsx)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Facturas")
    except Exception as e:
        # Fallback to CSV if excel writer fails (e.g. missing openpyxl or error)
        # Using utf-8-sig to make Excel open it with correct Spanish accents and characters
        output = io.BytesIO()
        df_filtrado.to_csv(output, index=False, sep=";", encoding="utf-8-sig")
        
    output.seek(0)
    return output
