import re
import spacy

# Cargar modelo en español para NER
try:
    nlp = spacy.load("es_core_news_sm")
except:
    import os
    os.system("python -m spacy download es_core_news_sm")
    nlp = spacy.load("es_core_news_sm")


# ═══════════════════════════════════════════════════════════════════
# Normalización del texto OCR  — corrige errores típicos de Tesseract
# ═══════════════════════════════════════════════════════════════════
def _normalizar_texto_ocr(texto: str) -> str:
    """Pre-normaliza el texto crudo de Tesseract para facilitar regex."""
    norm = texto
    # Tesseract lee «S/» como «si», «sI», «sl», «s/», «Si» etc.
    # Reemplazar variaciones comunes ANTES de buscar montos
    # Patrón: keyword seguido de «si» o «sl» o «s/» pegado al monto
    # GRAVADA si 600.00 → GRAVADA S/ 600.00
    norm = re.sub(r'(GRAVADA\w*)\s+(si|sl|sI|SI)\s+', r'\1 S/ ', norm, flags=re.IGNORECASE)
    norm = re.sub(r'(IGV|1GV|lGV)\s+(si|sl|sI|SI)\s+', r'IGV S/ ', norm, flags=re.IGNORECASE)
    norm = re.sub(r'(TOTAL)\s+(si|sl|sI|SI)\s+', r'TOTAL S/ ', norm, flags=re.IGNORECASE)
    norm = re.sub(r'(SUB\s*TOTAL)\s+(si|sl|sI|SI)\s+', r'\1 S/ ', norm, flags=re.IGNORECASE)
    # «1GV» → «IGV», «lGV» → «IGV»
    norm = re.sub(r'\b1GV\b', 'IGV', norm)
    norm = re.sub(r'\blGV\b', 'IGV', norm)
    # «Totals/» → «TOTAL S/»
    norm = re.sub(r'Totals/', 'TOTAL S/', norm, flags=re.IGNORECASE)
    # «TOTAL A PAGAR» → «TOTAL»
    norm = re.sub(r'TOTAL\s+A\s+PAGAR', 'TOTAL', norm, flags=re.IGNORECASE)
    return norm


# ═══════════════════════════════════════════════════════════════════
# Función auxiliar para parsear un monto numérico de un string
# ═══════════════════════════════════════════════════════════════════
def _parsear_monto(val_str: str) -> float | None:
    """Convierte un string de monto a float, manejando comas y puntos."""
    try:
        val_str = val_str.replace(' ', '').strip()
        if not val_str:
            return None
        # 1,000.00 → 1000.00
        if ',' in val_str and '.' in val_str:
            val_str = val_str.replace(',', '')
        # 600,00 → 600.00 (si hay una sola coma con ≤2 decimales)
        elif ',' in val_str:
            parts = val_str.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                val_str = val_str.replace(',', '.')
            else:
                val_str = val_str.replace(',', '')
        return float(val_str)
    except (ValueError, TypeError):
        return None


def _buscar_monto_en_texto(patrones: list, texto: str) -> float | None:
    """Prueba una lista de regex en orden; devuelve el primer monto encontrado."""
    for pat in patrones:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            val = _parsear_monto(m.group(1))
            if val is not None and val > 0:
                return val
    return None


# ═══════════════════════════════════════════════════════════════════
# Símbolo de moneda — regex tolerante a distorsiones OCR
# ═══════════════════════════════════════════════════════════════════
# Tesseract convierte «S/» en: si, sl, sI, S/, s/, S/., S/
_SYM = r'(?:S/\.?|s[il/]\.?|\$)'  # Símbolo de moneda (tolerante OCR)
_NUM = r'([\d]{1,7}[.,]\d{1,2})'  # Grupo de captura para montos


# ═══════════════════════════════════════════════════════════════════
# Extracción línea-a-línea: busca keyword y monto en la MISMA línea
# o en líneas ADYACENTES (para facturas donde quedan separados)
# ═══════════════════════════════════════════════════════════════════
def _buscar_monto_por_linea(keyword_re: str, lineas: list[str]) -> float | None:
    """
    Busca un keyword en cada línea. Si se encuentra:
     1. Intenta extraer el monto de ESA MISMA línea
     2. Si no hay monto en la línea, busca en la siguiente línea
     3. Si todo falla, busca el ÚLTIMO número de la misma línea
    """
    for i, linea in enumerate(lineas):
        if re.search(keyword_re, linea, re.IGNORECASE):
            # 1) Monto en la misma línea después del keyword
            m = re.search(keyword_re + r'.*?' + _NUM, linea, re.IGNORECASE)
            if m:
                val = _parsear_monto(m.group(1))
                if val and val > 0:
                    return val

            # 2) Cualquier número con decimales en la misma línea
            nums = re.findall(r'(\d{1,7}[.,]\d{1,2})', linea)
            if nums:
                # Tomar el ÚLTIMO número (suele ser el monto, no la cantidad)
                val = _parsear_monto(nums[-1])
                if val and val > 0:
                    return val

            # 3) Buscar en la siguiente línea
            if i + 1 < len(lineas):
                nums_next = re.findall(r'(\d{1,7}[.,]\d{1,2})', lineas[i + 1])
                if nums_next:
                    val = _parsear_monto(nums_next[-1])
                    if val and val > 0:
                        return val
    return None


# ═══════════════════════════════════════════════════════════════════
# Extracción principal
# ═══════════════════════════════════════════════════════════════════
def extraer_datos(texto: str) -> dict:
    print("=" * 60)
    print("TEXTO OCR CRUDO:")
    print("=" * 60)
    print(texto)
    print("=" * 60)
    """Extrae entidades clave usando Regex multi-estrategia + NER (spaCy) + validación cruzada."""
    datos = {
        "numero_factura": None,
        "fecha_emision": None,
        "proveedor_ruc": None,
        "proveedor_nombre": None,
        "subtotal": None,
        "igv": None,
        "total": None,
        "moneda": "SOLES",
        "simbolo_moneda": "S/."
    }

    # Pre-normalizar texto OCR
    texto_norm = _normalizar_texto_ocr(texto)
    lineas = [l.strip() for l in texto_norm.split('\n') if l.strip()]

    # ── 0. Detectar moneda ──
    if re.search(r'\bMONEDA\s*[:\-]?\s*SOLES\b', texto_norm, re.IGNORECASE):
        datos["moneda"] = "SOLES"
        datos["simbolo_moneda"] = "S/."
    elif re.search(r'\bMONEDA\s*[:\-]?\s*D[OÓ]LARES\b', texto_norm, re.IGNORECASE):
        datos["moneda"] = "DOLARES"
        datos["simbolo_moneda"] = "$"
    elif re.search(r'S/\.', texto) or re.search(r'\bSOLES\b', texto, re.IGNORECASE):
        datos["moneda"] = "SOLES"
        datos["simbolo_moneda"] = "S/."

    # ── 1. NER con spaCy ──
    doc = nlp(texto)
    nombres_ner = [ent.text for ent in doc.ents if ent.label_ == "ORG"]

    # ── 2. Número de Factura (SUNAT: F001-000134, E001-123, B001-456) ──
    patrones_factura = [
        r'\b([FfEeBb][A-Za-z0-9]{2,3}[-\s]\d{1,8})\b',
        r'(?:N[°ºo*.]?\s*(?:DE\s+)?FACTURA|FACTURA\s*N[°ºo*.]?)\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        # Formato «Nro 001-0000765»
        r'(?:N[°ºo?.]|NRO?\.?)\s*(\d{3}\s*[-]\s*\d{4,8})',
    ]
    for pat in patrones_factura:
        m = re.search(pat, texto_norm, re.IGNORECASE)
        if m:
            datos["numero_factura"] = m.group(1).strip()
            break

    # ── 3. Fecha de Emisión ──
    patrones_fecha = [
        r'FECHA\s*(?:DE\s+)?EMISI[OÓ]N\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'FECHA\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        # Formato ISO: 2019-05-22
        r'FECHA\s*(?:DE\s+)?EMISI[OÓ]N\s*[:\-]?\s*(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',
        # Formato textual: 15 de octubre del 2013
        r'(\d{1,2}\s+de\s+\w+\s+(?:del?\s+)?\d{4})',
        # Fallback ISO
        r'(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',
        # Fallback dd/mm/yyyy
        r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]
    for pat in patrones_fecha:
        m = re.search(pat, texto_norm, re.IGNORECASE)
        if m:
            datos["fecha_emision"] = m.group(1).strip()
            break

    # ── 4. RUC (11 dígitos, empieza en 10 o 20) ──
    # Buscar TODOS los RUC del texto y preferir el del proveedor (20xxxxxxxxx)
    rucs_20 = re.findall(r'\b(20\d{9})\b', texto_norm)
    rucs_10 = re.findall(r'\b(10\d{9})\b', texto_norm)
    rucs_ruc_label = re.findall(r'R\.?U\.?C\.?\s*[:\-]?\s*(\d{11})', texto_norm, re.IGNORECASE)

    if rucs_ruc_label:
        # Si hay un RUC explícito (acompañado de «RUC:»), preferirlo
        # Priorizar 20xxxxxxxxx (empresa) sobre 10xxxxxxxxx (persona)
        rucs_20_label = [r for r in rucs_ruc_label if r.startswith('20')]
        datos["proveedor_ruc"] = rucs_20_label[0] if rucs_20_label else rucs_ruc_label[0]
    elif rucs_20:
        datos["proveedor_ruc"] = rucs_20[0]
    elif rucs_10:
        datos["proveedor_ruc"] = rucs_10[0]

    # ── 5. Nombre del Proveedor (multi-estrategia) ──
    datos["proveedor_nombre"] = _extraer_nombre_proveedor(texto, texto_norm, lineas, nombres_ner)

    # ══════════════════════════════════════════════════════════════
    #  MONTOS — Enfoque multi-estrategia tolerante a OCR roto
    # ══════════════════════════════════════════════════════════════

    # ── 6. TOTAL ──
    datos["total"] = _extraer_total(texto_norm, lineas)

    # ── 7. SUBTOTAL / GRAVADA (Base Imponible) ──
    datos["subtotal"] = _extraer_subtotal(texto_norm, lineas)

    # ── 8. IGV ──
    datos["igv"] = _extraer_igv(texto_norm, lineas)

    # ── 9. Validación cruzada matemática (IGV = 18% de base) ──
    _validacion_cruzada(datos)

    return datos


# ═══════════════════════════════════════════════════════════════════
# Extracción del nombre del proveedor
# ═══════════════════════════════════════════════════════════════════
def _extraer_nombre_proveedor(texto_orig: str, texto_norm: str, lineas: list, nombres_ner: list) -> str | None:
    """Extrae el nombre del proveedor con múltiples fallbacks."""

    # Estrategia 1: buscar en las primeras líneas la razón social completa
    # (suele estar en las primeras 5 líneas del documento)
    sufijo_re = r'\bS\.?A\.?C\.?\b|\bS\.?R\.?L\.?\b|\bE\.?I\.?R\.?L\.?\b|\bS\.?A\.?\b'
    candidatos_sufijo = []
    for linea in lineas[:15]:  # Buscar en las primeras 15 líneas
        if re.search(sufijo_re, linea, re.IGNORECASE):
            # Limpiar ruidos que se hayan pegado
            linea_limpia = linea.strip()
            if len(linea_limpia) > 5:
                candidatos_sufijo.append(linea_limpia)

    # Estrategia 2: campo explícito «RAZÓN SOCIAL:» o «EMPRESA:»
    razon_social = None
    m_rs = re.search(
        r'(?:RAZ[OÓ]N\s+SOCIAL|EMPRESA|DENOMINACI[OÓ]N)\s*[:\-]?\s*(.+)',
        texto_norm, re.IGNORECASE
    )
    if m_rs:
        # Tomar hasta fin de línea
        candidato = m_rs.group(1).strip()
        # Cortar en el sufijo legal si existe
        m_suf = re.search(sufijo_re, candidato, re.IGNORECASE)
        if m_suf:
            candidato = candidato[:m_suf.end()].strip()
        if len(candidato) > 3:
            razon_social = candidato

    # Estrategia 3: buscar «NOMBRE COMERCIAL:»
    nombre_comercial = None
    m_nc = re.search(
        r'(?:NOMBRE\s+COMERCIAL|COMERCIAL)\s*[:\-]?\s*([^\n]+)',
        texto_norm, re.IGNORECASE
    )
    if m_nc:
        nombre_comercial = m_nc.group(1).strip()

    # Decidir cuál usar
    nombre = None

    # Preferir nombre comercial si existe
    if nombre_comercial and len(nombre_comercial) > 3:
        nombre = nombre_comercial
    # Luego razón social explícita
    elif razon_social and len(razon_social) > 5:
        nombre = razon_social
    # Luego candidatos con sufijo empresarial (tomar el más largo/completo)
    elif candidatos_sufijo:
        nombre = max(candidatos_sufijo, key=len)

    # Fallback: NER de spaCy
    if not nombre and nombres_ner:
        validos = [n for n in nombres_ner if len(n) > 4 and not n.isdigit()]
        if validos:
            nombre = max(validos, key=len)

    # Fallback final: primera línea con texto sustancial
    if not nombre:
        for linea in lineas[:5]:
            if len(linea) > 5 and not re.match(r'^[\d\s\-\.]+$', linea):
                nombre = linea[:150]
                break

    # ── Limpieza del nombre ──
    if nombre:
        # Eliminar ruidos comunes
        ruidos = [
            r'FACTURA\s+ELECTR[OÓ]NICA', r'BOLETA\s+ELECTR[OÓ]NICA',
            r'ELECTR[OÓ]N\s*ICA', r'P[AÁ]GINA\s*\d+',
            r'RUC\s*[:\-]?\s*\d+', r'CRU\s*_',
        ]
        for ruido in ruidos:
            nombre = re.split(ruido, nombre, flags=re.IGNORECASE)[0].strip()

        # Cortar DESPUÉS del sufijo legal para no perder el nombre
        m_suf = re.search(sufijo_re, nombre, re.IGNORECASE)
        if m_suf:
            nombre = nombre[:m_suf.end()].strip()

        nombre = nombre.strip(" -:,\t")

    return nombre if nombre and len(nombre) > 2 else None


# ═══════════════════════════════════════════════════════════════════
# Extracción del TOTAL
# ═══════════════════════════════════════════════════════════════════
def _extraer_total(texto_norm: str, lineas: list) -> float | None:
    # Estrategia 1: regex directo con múltiples formatos
    patrones = [
        # «TOTAL S/ 708.00» o «TOTAL si 708.00»
        r'(?<!SUB\s)(?<!SUB)TOTAL\s*[:\-]?\s*' + _SYM + r'\s*' + _NUM,
        # «TOTAL: 708.00»
        r'(?<!SUB\s)(?<!SUB)TOTAL\s*[:\-]?\s*' + _NUM,
        # «CANCELADO 1,156.40»
        r'CANCELADO\s*[:\-]?\s*' + _NUM,
        # «IMPORTE TOTAL S/ 708.00»
        r'IMPORTE\s*TOTAL\s*[:\-]?\s*' + _SYM + r'?\s*' + _NUM,
    ]
    val = _buscar_monto_en_texto(patrones, texto_norm)
    if val:
        return val

    # Estrategia 2: buscar por línea (keyword + monto pueden estar separados)
    val = _buscar_monto_por_linea(
        r'(?<!SUB\s?)(?<!SUB)TOTAL(?!\s*OPER)',
        lineas
    )
    if val:
        return val

    # Estrategia 3: si hay «CANCELADO», buscar el monto
    val = _buscar_monto_por_linea(r'CANCELADO', lineas)
    if val:
        return val

    # Estrategia 4 (fallback): mayor valor numérico con decimales en el texto
    todos_montos = re.findall(r'\b(\d{1,7}[.,]\d{2})\b', texto_norm)
    if todos_montos:
        valores = []
        for t in todos_montos:
            v = _parsear_monto(t)
            if v and v > 0:
                valores.append(v)
        if valores:
            return max(valores)

    return None


# ═══════════════════════════════════════════════════════════════════
# Extracción del SUBTOTAL / BASE IMPONIBLE / GRAVADA
# ═══════════════════════════════════════════════════════════════════
def _extraer_subtotal(texto_norm: str, lineas: list) -> float | None:
    # Estrategia 1: regex directo
    patrones = [
        r'(?:OP\.?\s*)?GRAVADA\w*\s*[:\-]?\s*' + _SYM + r'\s*' + _NUM,
        r'(?:OP\.?\s*)?GRAVADA\w*\s*[:\-]?\s*' + _NUM,
        r'BASE\s*IMPONIBLE\s*[:\-]?\s*' + _SYM + r'?\s*' + _NUM,
        r'SUB\s*TOTAL\s*[:\-]?\s*' + _SYM + r'?\s*' + _NUM,
        r'Sub\s*Total\s*' + _NUM,
    ]
    val = _buscar_monto_en_texto(patrones, texto_norm)
    if val:
        return val

    # Estrategia 2: buscar por línea
    for keyword in [r'GRAVADA', r'BASE\s*IMPONIBLE', r'SUB\s*TOTAL']:
        val = _buscar_monto_por_linea(keyword, lineas)
        if val:
            return val

    return None


# ═══════════════════════════════════════════════════════════════════
# Extracción del IGV
# ═══════════════════════════════════════════════════════════════════
def _extraer_igv(texto_norm: str, lineas: list) -> float | None:
    # Estrategia 1: «IGV ... S/ 108.00» — el S/ garantiza que capturamos el monto, no el %
    patrones_con_simbolo = [
        r'I\.?G\.?V\.?\s.*?' + _SYM + r'\s*' + _NUM,
    ]
    val = _buscar_monto_en_texto(patrones_con_simbolo, texto_norm)
    if val:
        return val

    # Estrategia 2: buscar por línea — tomará el ÚLTIMO número de la línea del IGV
    # Así evita el porcentaje (18.00) y captura el monto (108.00)
    val = _buscar_monto_por_linea_igv(lineas)
    if val:
        return val

    return None


def _buscar_monto_por_linea_igv(lineas: list) -> float | None:
    """
    Especializada para IGV: encuentra la línea con IGV y extrae
    el ÚLTIMO número con decimales (que es el monto, no el porcentaje).
    
    Ejemplo: «IGV 18.00 % S/ 108.00» → captura 108.00 (no 18.00)
    Ejemplo: «1GV 18 % 176.40»       → captura 176.40 (no 18)
    """
    igv_re = r'\bI\.?G\.?V\.?\b|\b1GV\b|\blGV\b'
    for i, linea in enumerate(lineas):
        if re.search(igv_re, linea, re.IGNORECASE):
            # Buscar todos los números con decimales en la línea
            nums = re.findall(r'(\d{1,7}[.,]\d{1,2})', linea)
            if len(nums) >= 2:
                # Hay múltiples números → el último es el monto
                val = _parsear_monto(nums[-1])
                if val and val > 0:
                    return val
            elif len(nums) == 1:
                # Solo un número → verificar que NO sea un porcentaje
                val = _parsear_monto(nums[0])
                if val and val > 0:
                    # Si hay «%» en la línea y el valor es ≤ 100, probablemente es el %
                    if '%' in linea and val <= 100:
                        # Buscar en la siguiente línea
                        if i + 1 < len(lineas):
                            nums_next = re.findall(r'(\d{1,7}[.,]\d{1,2})', lineas[i + 1])
                            if nums_next:
                                return _parsear_monto(nums_next[-1])
                    else:
                        return val
            else:
                # No hay número con decimales → buscar en la siguiente línea
                if i + 1 < len(lineas):
                    nums_next = re.findall(r'(\d{1,7}[.,]\d{1,2})', lineas[i + 1])
                    if nums_next:
                        return _parsear_monto(nums_next[-1])
    return None


# ═══════════════════════════════════════════════════════════════════
# Validación cruzada — usa regla del 18% para verificar/inferir
# ═══════════════════════════════════════════════════════════════════
def _validacion_cruzada(datos: dict):
    """
    Usa la regla IGV = 18% de Base Imponible para:
    1. Inferir el dato faltante si faltan 1 de los 3 valores
    2. Verificar consistencia si tenemos los 3
    3. Preferir recalcular si los valores extraídos no son consistentes
    """
    total = datos.get("total")
    subtotal = datos.get("subtotal")
    igv = datos.get("igv")

    # Si tenemos total y subtotal, verificar IGV
    if total and subtotal and not igv:
        datos["igv"] = round(total - subtotal, 2)

    # Si tenemos total e IGV, inferir subtotal
    elif total and igv and not subtotal:
        datos["subtotal"] = round(total - igv, 2)

    # Si tenemos subtotal e IGV, inferir total
    elif subtotal and igv and not total:
        datos["total"] = round(subtotal + igv, 2)

    # Si no tenemos ni subtotal ni IGV, pero sí total → calcular con 18%
    elif total and not subtotal and not igv:
        # total = subtotal * 1.18  →  subtotal = total / 1.18
        datos["subtotal"] = round(total / 1.18, 2)
        datos["igv"] = round(total - datos["subtotal"], 2)

    # Si tenemos los 3, verificar consistencia
    if datos["total"] and datos["subtotal"] and datos["igv"]:
        calculado = round(datos["subtotal"] + datos["igv"], 2)
        if abs(calculado - datos["total"]) > 1.0:
            # Los montos extraídos no cuadran — recalcular desde el total
            # (el total suele ser el más fiable porque es el número más grande)
            datos["subtotal"] = round(datos["total"] / 1.18, 2)
            datos["igv"] = round(datos["total"] - datos["subtotal"], 2)


# ═══════════════════════════════════════════════════════════════════
# Vinculación de coordenadas para visualización
# ═══════════════════════════════════════════════════════════════════
def vincular_coordenadas(datos: dict, pos_data: list) -> dict:
    """Intenta encontrar las coordenadas [x, y, w, h] para cada dato extraído."""
    coordenadas = {}

    for campo, valor in datos.items():
        if not valor: continue
        if campo in ("moneda", "simbolo_moneda", "coordenadas"):
            continue

        valor_str = str(valor).lower()

        for item in pos_data:
            txt = item["text"].lower()
            if valor_str in txt or txt in valor_str:
                if campo not in coordenadas:
                    coordenadas[campo] = item["box"]
                else:
                    b1 = coordenadas[campo]
                    b2 = item["box"]
                    x = min(b1[0], b2[0])
                    y = min(b1[1], b2[1])
                    w = max(b1[0] + b1[2], b2[0] + b2[2]) - x
                    h = max(b1[1] + b1[3], b2[1] + b2[3]) - y
                    coordenadas[campo] = [x, y, w, h]

    return coordenadas
