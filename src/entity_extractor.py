import re


def extraer_datos(texto: str) -> dict:
    """Extrae entidades clave de una factura a partir del texto OCR.
    
    Utiliza múltiples patrones regex para manejar variaciones en el
    texto producido por OCR (errores de reconocimiento, formatos diversos).
    """
    datos = {
        "numero_factura": None,
        "fecha_emision": None,
        "proveedor_ruc": None,
        "proveedor_nombre": None,
        "subtotal": None,
        "igv": None,
        "total": None
    }

    # ── Número de Factura ──
    patrones_factura = [
        r'(?:N[°ºo*.]?\s*(?:DE\s+)?FACTURA|FACTURA\s*N[°ºo*.]?)\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        r'(?:INVOICE|FACTURA)\s*#?\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        r'(?:N[°ºo*.]?\s*COMPROBANTE)\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        r'(?:SERIE\s*[:\-]?\s*)?([A-Z]\d{3})\s*[\-]\s*(\d+)',
    ]
    for pat in patrones_factura:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                datos["numero_factura"] = f"{groups[0]}-{groups[1]}"
            else:
                datos["numero_factura"] = groups[0].strip()
            break

    # ── Fecha de Emisión ──
    patrones_fecha = [
        # DD/MM/YYYY o DD-MM-YYYY o DD.MM.YYYY
        r'(?:FECHA(?:\s+DE\s+EMISI[OÓ]N)?|FECHA\s*EMISI[OÓ]N|FECHA)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        # DDMMYYYY (sin separadores, 8 dígitos)
        r'FECHA\s*[:\-]?\s*(\d{2})(\d{2})(\d{4})',
        # DD de Mes de YYYY
        r'FECHA\s*[:\-]?\s*(\d{1,2}\s+de\s+\w+\s+(?:de\s+)?\d{2,4})',
        # Fecha suelta DD/MM/YYYY en cualquier parte
        r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]
    for pat in patrones_fecha:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 3 and all(g.isdigit() for g in groups):
                # Caso DDMMYYYY
                datos["fecha_emision"] = f"{groups[0]}/{groups[1]}/{groups[2]}"
            else:
                datos["fecha_emision"] = groups[0].strip()
            break

    # ── RUC / NIF / CIF del Proveedor ──
    patrones_ruc = [
        r'R\.?U\.?C\.?\s*[:\-]?\s*(\d{11})',
        r'(?:NIF|CIF|RUC|DNI)\s*[:\-]?\s*([A-Z0-9\-]{8,15})',
        r'(\d{11})',  # Fallback: cualquier secuencia de 11 dígitos
    ]
    for pat in patrones_ruc:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            datos["proveedor_ruc"] = m.group(1).strip()
            break

    # ── Nombre del Proveedor ──
    patrones_nombre = [
        r'(?:RAZ[OÓ]N\s+SOCIAL|PROVEEDOR|EMPRESA|EMITIDO\s+POR|SE[NÑ]OR(?:ES)?)\s*[:\-]?\s*(.+)',
        r'(?:DE|FACTURAR?\s+DE)\s*[:\-]?\s*(.+)',
    ]
    for pat in patrones_nombre:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip()
            # Limpiar nombre: quitar caracteres sueltos
            nombre = re.sub(r'\s{2,}', ' ', nombre)
            if len(nombre) > 2:
                datos["proveedor_nombre"] = nombre[:100]  # Limitar largo
            break

    # Si no encontró nombre, usar la primera línea no vacía como nombre
    if not datos["proveedor_nombre"]:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        for linea in lineas[:5]:
            # Ignorar líneas que son solo "factura" o muy cortas
            if len(linea) > 3 and not re.match(r'^factura$', linea, re.IGNORECASE):
                datos["proveedor_nombre"] = linea[:100]
                break

    # ── Montos: extraer todos los números con formato monetario ──
    def extraer_monto(patron, texto_buscar):
        """Busca un monto asociado a una etiqueta."""
        m = re.search(patron, texto_buscar, re.IGNORECASE)
        if m:
            try:
                valor = m.group(1).replace(',', '.').replace(' ', '')
                return float(valor)
            except (ValueError, IndexError):
                pass
        return None

    # ── Total ──
    patrones_total = [
        r'TOTAL\s*(?:GENERAL|A\s+PAGAR|FACTURA)?\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'TOTAL\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'IMPORTE\s*TOTAL\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
    ]
    for pat in patrones_total:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["total"] = val
            break

    # Si no encontró TOTAL con patrón, buscar la última ocurrencia de un número grande
    if datos["total"] is None:
        # Buscar todos los montos en el texto
        montos = re.findall(r'([\d]+[.,]\d{2})', texto)
        if montos:
            try:
                # El total suele ser el monto más grande o el último
                valores = [float(m.replace(',', '.')) for m in montos]
                if valores:
                    datos["total"] = max(valores)
            except ValueError:
                pass

    # ── Subtotal ──
    patrones_subtotal = [
        r'SUB\s*TOTAL\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'SUBTOTAL\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'BASE\s*IMPONIBLE\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'VALOR\s*(?:DE\s+)?VENTA\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
    ]
    for pat in patrones_subtotal:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["subtotal"] = val
            break

    # ── IGV / IVA ──
    patrones_igv = [
        r'I\.?G\.?V\.?\s*(?:\(?\d+%?\)?)?\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'I\.?V\.?A\.?\s*(?:\(?\d+%?\)?)?\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'IMPUESTO\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
        r'(?:VA|IVA)\s+\d+\s*[.,]?\s*\d*\s*%\s*[:\-]?\s*\$?\s*S?/?\s*([\d]+[.,]\d{2})',
    ]
    for pat in patrones_igv:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["igv"] = val
            break

    # ── Inferencia: si falta subtotal o igv, intentar calcularlo ──
    if datos["total"] and datos["igv"] and not datos["subtotal"]:
        datos["subtotal"] = round(datos["total"] - datos["igv"], 2)
    elif datos["total"] and datos["subtotal"] and not datos["igv"]:
        datos["igv"] = round(datos["total"] - datos["subtotal"], 2)

    return datos
