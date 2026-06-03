"""
openai_extractor.py — Extractor híbrido: OpenAI (primario) + Regex (secundario).

Envía el texto crudo de Tesseract a la API de OpenAI para obtener un JSON
estructurado con los campos de la factura. Luego fusiona el resultado con
el extractor regex existente, tomando lo mejor de cada uno campo por campo.

Si OpenAI falla (API caída, timeout, sin internet), usa el extractor regex
como fallback transparente.
"""

import os
import sys
import json
import traceback

from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

from src.entity_extractor import extraer_datos as extraer_datos_regex


# ═══════════════════════════════════════════════════════════════════
# Esquema Pydantic para la respuesta estructurada de OpenAI
# ═══════════════════════════════════════════════════════════════════
class FacturaOpenAI(BaseModel):
    """Esquema de datos de factura que OpenAI debe devolver."""
    numero_factura: Optional[str] = None
    fecha_emision: Optional[str] = None
    proveedor_ruc: Optional[str] = None
    proveedor_nombre: Optional[str] = None
    cliente_nombre: Optional[str] = None
    subtotal: Optional[float] = None
    igv: Optional[float] = None
    total: Optional[float] = None
    moneda: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# Prompt especializado para facturas peruanas
# ═══════════════════════════════════════════════════════════════════
PROMPT_FACTURA = """Eres un experto en extracción de datos de facturas peruanas (SUNAT).
Se te proporcionará el texto crudo extraído por OCR (Tesseract) de una imagen de factura.
El texto puede contener errores de OCR como:
- "si", "sl", "sI" en lugar de "S/" (símbolo de soles)
- "1GV", "lGV" en lugar de "IGV"
- Caracteres mal reconocidos, espacios extra, líneas desordenadas

Tu tarea es interpretar semánticamente el texto y extraer los datos de la factura.

REGLAS IMPORTANTES:
1. El RUC tiene exactamente 11 dígitos y empieza con 10 (persona) o 20 (empresa).
2. El número de factura sigue el formato SUNAT: letra + 3 dígitos + guión + correlativo (ej: F001-000134, E001-123, B001-456).
3. El IGV en Perú es el 18% de la base imponible (subtotal).
4. TOTAL = SUBTOTAL + IGV (siempre debe cumplirse esta relación).
5. Si dice "GRAVADA" o "BASE IMPONIBLE" o "OP. GRAVADA", ese es el subtotal.
6. La moneda por defecto es "SOLES" a menos que se indique "DÓLARES" o aparezca "$".
7. Para la fecha, usa el formato tal como aparece en el documento.
8. Para el nombre del proveedor, busca la razón social (puede terminar en S.A.C., S.R.L., etc.). Extrae también el nombre del cliente o adquiriente si aparece explícitamente y ponlo en cliente_nombre.
9. Los montos deben ser números decimales (float), no strings.
10. Si no puedes determinar un campo con confianza, déjalo como null.

Texto OCR de la factura:
---
{texto_ocr}
---

Extrae los datos y devuélvelos en formato JSON."""


# ═══════════════════════════════════════════════════════════════════
# Extracción con OpenAI
# ═══════════════════════════════════════════════════════════════════
def _extraer_con_openai(texto_ocr: str) -> dict | None:
    """
    Envía el texto OCR a OpenAI y obtiene un JSON estructurado.
    Retorna None si OpenAI no está disponible o falla.
    """
    if not config.OPENAI_ENABLED:
        print("[OpenAI] Desactivado en config.")
        return None

    if not config.OPENAI_API_KEY:
        print("[OpenAI] No hay API key configurada.")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)

        prompt = PROMPT_FACTURA.format(texto_ocr=texto_ocr)

        response = client.beta.chat.completions.parse(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format=FacturaOpenAI,
        )

        # Parsear la respuesta estructurada
        resultado = response.choices[0].message.parsed
        if resultado:
            datos = resultado.model_dump()
            print(f"[OpenAI] Extracción exitosa: {json.dumps(datos, ensure_ascii=False, indent=2)}")
            return datos
        else:
            print("[OpenAI] Respuesta vacía.")
            return None

    except ImportError:
        print("[OpenAI] Librería 'openai' no instalada. Ejecuta: pip install openai")
        return None
    except Exception as e:
        print(f"[OpenAI] Error en la API: {e}")
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════
# Fusión inteligente de resultados
# ═══════════════════════════════════════════════════════════════════

# Configuración de prioridad por campo:
# "openai"  → preferir OpenAI (mejor para campos semánticos)
# "regex"   → preferir Regex (mejor para campos estructurales)
PRIORIDAD_CAMPOS = {
    "numero_factura":   "regex",    # Patrones SUNAT son deterministas
    "fecha_emision":    "openai",   # OpenAI maneja formatos variados
    "proveedor_ruc":    "regex",    # Regex \b(20\d{9})\b es preciso
    "proveedor_nombre": "openai",   # OpenAI entiende contexto semántico
    "cliente_nombre":   "openai",   # OpenAI cruza la semántica entre comprador/vendedor
    "subtotal":         "openai",   # OpenAI no confunde keywords rotos
    "igv":              "openai",   # OpenAI no confunde % con monto
    "total":            "openai",   # OpenAI interpreta mejor el layout
    "moneda":           "regex",    # Detección directa de S/ o $
    "simbolo_moneda":   "regex",    # Siempre del regex
}


def _fusionar_resultados(openai_dict: dict | None, regex: dict) -> tuple[dict, str]:
    """
    Fusiona los resultados de OpenAI y Regex, tomando lo mejor de cada uno.
    
    Retorna:
        - datos fusionados (dict)
        - método usado: "openai", "regex", o "hybrid"
    """
    # Si OpenAI falló completamente, usar solo regex
    if openai_dict is None:
        regex["metodo_extraccion"] = "regex"
        return regex, "regex"

    fusionado = {}
    campos_openai = 0
    campos_regex = 0

    for campo in ["numero_factura", "fecha_emision", "proveedor_ruc",
                   "proveedor_nombre", "cliente_nombre", "subtotal", "igv", "total",
                   "moneda", "simbolo_moneda"]:

        val_openai = openai_dict.get(campo)
        val_regex = regex.get(campo)
        prioridad = PRIORIDAD_CAMPOS.get(campo, "openai")

        # Normalizar la moneda de OpenAI
        if campo == "moneda" and val_openai:
            val_openai = val_openai.upper()
            if "SOL" in val_openai:
                val_openai = "SOLES"
            elif "DOL" in val_openai or "USD" in val_openai:
                val_openai = "DOLARES"

        # Si OpenAI no devuelve simbolo_moneda, generarlo
        if campo == "simbolo_moneda" and not val_openai:
            moneda_final = fusionado.get("moneda", "SOLES")
            val_openai = "$" if moneda_final == "DOLARES" else "S/."

        # Lógica de selección
        if prioridad == "openai":
            if val_openai is not None and val_openai != "":
                fusionado[campo] = val_openai
                campos_openai += 1
            elif val_regex is not None:
                fusionado[campo] = val_regex
                campos_regex += 1
            else:
                fusionado[campo] = None
        else:  # prioridad == "regex"
            if val_regex is not None and val_regex != "":
                fusionado[campo] = val_regex
                campos_regex += 1
            elif val_openai is not None:
                fusionado[campo] = val_openai
                campos_openai += 1
            else:
                fusionado[campo] = None

    # Determinar el método predominante
    if campos_openai > 0 and campos_regex > 0:
        metodo = "hybrid"
    elif campos_openai > 0:
        metodo = "openai"
    else:
        metodo = "regex"

    fusionado["metodo_extraccion"] = metodo

    print(f"[Fusión] Método: {metodo} (OpenAI: {campos_openai} campos, Regex: {campos_regex} campos)")
    return fusionado, metodo


# ═══════════════════════════════════════════════════════════════════
# Validación cruzada post-fusión (regla del 18%)
# ═══════════════════════════════════════════════════════════════════
def _validacion_cruzada_post(datos: dict):
    """
    Aplica la regla IGV = 18% después de la fusión, 
    igual que entity_extractor pero sobre los datos ya fusionados.
    """
    total = datos.get("total")
    subtotal = datos.get("subtotal")
    igv = datos.get("igv")

    # Si tenemos total y subtotal, verificar/inferir IGV
    if total and subtotal and not igv:
        datos["igv"] = round(total - subtotal, 2)

    elif total and igv and not subtotal:
        datos["subtotal"] = round(total - igv, 2)

    elif subtotal and igv and not total:
        datos["total"] = round(subtotal + igv, 2)

    elif total and not subtotal and not igv:
        datos["subtotal"] = round(total / 1.18, 2)
        datos["igv"] = round(total - datos["subtotal"], 2)

    # Verificar consistencia
    if datos.get("total") and datos.get("subtotal") and datos.get("igv"):
        calculado = round(datos["subtotal"] + datos["igv"], 2)
        if abs(calculado - datos["total"]) > 1.0:
            # Recalcular desde el total (más fiable)
            datos["subtotal"] = round(datos["total"] / 1.18, 2)
            datos["igv"] = round(datos["total"] - datos["subtotal"], 2)


# ═══════════════════════════════════════════════════════════════════
# Función pública — Punto de entrada del extractor híbrido
# ═══════════════════════════════════════════════════════════════════
def extraer_datos_hybrid(texto: str) -> dict:
    """
    Extractor híbrido: ejecuta OpenAI + Regex y fusiona resultados.
    """
    print("=" * 60)
    print("EXTRACCIÓN HÍBRIDA (OpenAI + Regex)")
    print("=" * 60)

    # 1. Ejecutar extractor regex (siempre, como baseline)
    print("\n[1/3] Ejecutando extractor Regex + spaCy...")
    datos_regex = extraer_datos_regex(texto)

    # 2. Ejecutar OpenAI (puede fallar)
    print("\n[2/3] Ejecutando extractor OpenAI...")
    datos_openai = _extraer_con_openai(texto)

    # 3. Fusionar resultados
    print("\n[3/3] Fusionando resultados...")
    datos_fusionados, metodo = _fusionar_resultados(datos_openai, datos_regex)

    # 4. Validación cruzada post-fusión
    _validacion_cruzada_post(datos_fusionados)

    print(f"\n{'=' * 60}")
    print(f"RESULTADO FINAL (método: {metodo}):")
    print(json.dumps(datos_fusionados, ensure_ascii=False, indent=2))
    print(f"{'=' * 60}")

    return datos_fusionados
