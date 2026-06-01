import re

def extraer_datos(texto: str) -> dict:
    """Extrae entidades clave de una factura a partir del texto OCR.
    
    Campos extraídos:
    - numero_factura
    - fecha_emision
    - proveedor_ruc (RUC emisor)
    - proveedor_nombre
    - cliente_nombre (Cliente)
    - subtotal
    - igv
    - total
    """
    datos = {
        "numero_factura": None,
        "fecha_emision": None,
        "proveedor_ruc": None,
        "proveedor_nombre": None,
        "cliente_nombre": None,
        "subtotal": None,
        "igv": None,
        "total": None
    }

    # ── Número de Factura ──
    # Primero buscamos formatos específicos de series de Perú para evitar colisiones
    patrones_factura = [
        r'\b([FB][A-Z0-9]{3})\s*[\-]\s*(\d+)\b',
        r'\b(\d{3,4})\s*[\-]\s*(\d{4,8})\b',
        r'\b(?:N[°ºo*.]?\s*(?:DE\s+)?FACTURA|FACTURA\s*N[°ºo*.]?)\b\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        r'\b(?:INVOICE|FACTURA)\b\s*#?\s*[:\-]?\s*([A-Za-z0-9\-]+)',
        r'\b(?:N[°ºo*.]?\s*COMPROBANTE)\b\s*[:\-]?\s*([A-Za-z0-9\-]+)',
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
        r'(?:FECHA(?:\s+DE\s+EMISI[OÓ.]N)?|FECHA\s*EMISI[OÓ.]N|FECHA)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'FECHA\s*[:\-]?\s*(\d{2})(\d{2})(\d{4})',
        r'FECHA\s*[:\-]?\s*(\d{1,2}\s+de\s+[a-zA-ZáéíóúÁÉÍÓÚ]+\s+(?:del?\s+)?\d{2,4})',
        r'\b(\d{1,2}\s+de\s+[a-zA-ZáéíóúÁÉÍÓÚ]+\s+(?:del?\s+)?\d{2,4})\b',
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

    # ── Cliente (Nombre) ──
    patrones_cliente = [
        # Con documento o dirección intermedia en líneas siguientes (ej: ADQUIRIENTE\nND: 123\nNombre)
        r'(?:SE.OR(?:ES)?|CLIENTE|ADQUIR[IE]*NTE|DENOMINACI.?N)[:\-\s]*(?:(?:ND|RUC|DNI|DOC|DIRECCI.N)[:\-\s\d\-]*\n\s*)+([^\n\r]+)',
        # En la misma línea
        r'(?:SE.OR(?:ES)?|CLIENTE|ADQUIR[IE]*NTE|DENOMINACI.?N|NOMBRES?|RAZ.?N\s+SOCIAL\s+CLIENTE)\s*[:\-]?\s*([^\n\r]+)',
    ]
    for pat in patrones_cliente:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip()
            # Limpiar
            nombre = re.sub(r'(?:R\.?U\.?C\.?|FECHA|DIRECCI[OÓ.]N|TELF|TEL[EÉ]FONO|MONEDA|VENCIMIENTO).*$', '', nombre, flags=re.IGNORECASE)
            nombre = nombre.strip(" -:,*°ºo")
            if len(nombre) > 2:
                datos["cliente_nombre"] = nombre[:100]
                break

    # ── RUCs: Clasificación Inteligente de RUC Emisor y RUC Cliente ──
    rucs_candidatos = re.findall(r'\b(\d{11})\b', texto)
    rucs_unicos = []
    for r in rucs_candidatos:
        if r not in rucs_unicos:
            rucs_unicos.append(r)
            
    cliente_ruc = None
    client_section_match = re.search(r'(?:SE.OR(?:ES)?|CLIENTE|ADQUIRENTE|DENOMINACI.N)[^.]{0,150}?\b(\d{11})\b', texto, re.IGNORECASE | re.DOTALL)
    if client_section_match:
        cliente_ruc = client_section_match.group(1)
        
    for ruc in rucs_unicos:
        if ruc == cliente_ruc:
            continue
        datos["proveedor_ruc"] = ruc
        break
        
    if not datos["proveedor_ruc"] and rucs_unicos:
        if len(rucs_unicos) == 1 and not cliente_ruc:
            datos["proveedor_ruc"] = rucs_unicos[0]
        elif len(rucs_unicos) == 1 and cliente_ruc:
            datos["proveedor_ruc"] = None
        else:
            restantes = [r for r in rucs_unicos if r != cliente_ruc]
            if restantes:
                datos["proveedor_ruc"] = restantes[0]

    # ── Nombre del Proveedor ──
    patrones_nombre = [
        r'(?:RAZ.N\s+SOCIAL|PROVEEDOR|EMPRESA|EMITIDO\s+POR)\s*[:\-]?\s*([^\n\r]+)',
        r'(?:FACTURAR?\s+DE)\s*[:\-]?\s*([^\n\r]+)',
    ]
    for pat in patrones_nombre:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip()
            nombre = re.sub(r'(?:R\.?U\.?C\.?|FECHA|DIRECCI[OÓ.]N|TELF|TEL[EÉ]FONO|MONEDA|VENCIMIENTO).*$', '', nombre, flags=re.IGNORECASE)
            nombre = re.sub(r'\s{2,}', ' ', nombre)
            nombre = nombre.strip(" -:,*°ºo")
            if datos["cliente_nombre"] and nombre.lower() in datos["cliente_nombre"].lower():
                continue
            if len(nombre) > 2:
                datos["proveedor_nombre"] = nombre[:100]
                break

    if not datos["proveedor_nombre"]:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        for linea in lineas[:8]:
            if re.match(r'^factura$', linea, re.IGNORECASE):
                continue
            if datos["cliente_nombre"] and (linea.lower() in datos["cliente_nombre"].lower() or datos["cliente_nombre"].lower() in linea.lower()):
                continue
            limpia = re.sub(r'(?:FECHA|EMISI[OÓ.]N|VENCIMIENTO|N[°ºo*.]?|NRO|N[UÚ]MERO|INVOICE|PEDIDO|R\.?U\.?C\.?|NIF|CIF)[:\s\-]*\d{1,8}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', '', linea, flags=re.IGNORECASE)
            limpia = re.sub(r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b', '', limpia)
            limpia = re.sub(r'(?:FACTURA|INVOICE|PEDIDO|N[°ºo*.]?|NRO)[:\s\-]*[A-Za-z0-9\-]+', '', limpia, flags=re.IGNORECASE)
            limpia = limpia.strip(" -:,*°ºo")
            if len(limpia) > 3:
                datos["proveedor_nombre"] = limpia[:100]
                break

    # ── Montos ──
    def extraer_monto(patron, texto_buscar):
        m = re.search(patron, texto_buscar, re.IGNORECASE)
        if m:
            try:
                valor = m.group(1).replace(' ', '')
                if ',' in valor and '.' in valor:
                    if valor.find(',') < valor.find('.'):
                        valor = valor.replace(',', '')
                    else:
                        valor = valor.replace('.', '').replace(',', '.')
                elif ',' in valor:
                    parts = valor.split(',')
                    if len(parts) == 2 and len(parts[1]) in (1, 2):
                        valor = valor.replace(',', '.')
                    else:
                        valor = valor.replace(',', '')
                return float(valor)
            except (ValueError, IndexError):
                pass
        return None

    patrones_total = [
        r'\b(?<!SUB)TOTAL\s*(?:GENERAL|A\s+PAGAR|FACTURA)?\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'\b(?<!SUB)TOTAL\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'IMPORTE\s*TOTAL\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'PAGAR\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'CANCELADO\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
    ]
    for pat in patrones_total:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["total"] = val
            break

    patrones_subtotal = [
        r'SUB\s*TOTAL\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'SUBTOTAL\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'BASE\s*IMPONIBLE\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'VALOR\s*(?:DE\s+)?VENTA\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
    ]
    for pat in patrones_subtotal:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["subtotal"] = val
            break

    patrones_igv = [
        r'I\.?G\.?V\.?\s*(?:\(?\d+%?\)?)?\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'I\.?V\.?A\.?\s*(?:\(?\d+%?\)?)?\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'IMPUESTO\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
        r'(?:VA|IVA)\s+\d+\s*[.,]?\s*\d*\s*%\s*[:\-]?\s*[\$€S]?[/.]?\s*([\d]+(?:[.,]\d{1,2})?)',
    ]
    for pat in patrones_igv:
        val = extraer_monto(pat, texto)
        if val is not None:
            datos["igv"] = val
            break

    # Validación cruzada e inferencia inteligente
    montos_candidatos = []
    for m in re.findall(r'\b\d+(?:[.,]\d{1,2})\b', texto):
        try:
            val_str = m
            if ',' in val_str:
                parts = val_str.split(',')
                if len(parts) == 2 and len(parts[1]) in (1, 2):
                    val_str = val_str.replace(',', '.')
                else:
                    val_str = val_str.replace(',', '')
            val_float = float(val_str)
            if val_float > 0.01 and val_float not in rucs_unicos:
                montos_candidatos.append(val_float)
        except ValueError:
            pass

    if montos_candidatos:
        montos_candidatos = sorted(list(set(montos_candidatos)))
        
        if not datos["total"]:
            for i in range(len(montos_candidatos)):
                for j in range(i):
                    suma = round(montos_candidatos[i] + montos_candidatos[j], 2)
                    for k in range(len(montos_candidatos)):
                        if abs(montos_candidatos[k] - suma) < 0.05:
                            datos["total"] = montos_candidatos[k]
                            datos["subtotal"] = montos_candidatos[i]
                            datos["igv"] = montos_candidatos[j]
                            break
                            
        if not datos["total"]:
            candidatos_validos = [m for m in montos_candidatos if not datos["subtotal"] or abs(m - datos["subtotal"]) > 0.1]
            if candidatos_validos:
                datos["total"] = max(candidatos_validos)

    if datos["total"] and datos["igv"] and not datos["subtotal"]:
        datos["subtotal"] = round(datos["total"] - datos["igv"], 2)
    elif datos["total"] and datos["subtotal"] and not datos["igv"]:
        datos["igv"] = round(datos["total"] - datos["subtotal"], 2)
    elif datos["subtotal"] and datos["igv"] and not datos["total"]:
        datos["total"] = round(datos["subtotal"] + datos["igv"], 2)
    elif datos["total"] and not datos["subtotal"] and not datos["igv"]:
        datos["subtotal"] = round(datos["total"] / 1.18, 2)
        datos["igv"] = round(datos["total"] - datos["subtotal"], 2)

    return datos

