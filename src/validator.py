def validar(datos: dict) -> dict:
    """Valida reglas de negocio contables para asegurar la calidad de los datos."""
    alertas = []
    es_valido = True
    
    # 1. Regla de RUC (Peru)
    ruc = datos.get("proveedor_ruc")
    if not ruc:
        alertas.append("⚠️ Falta RUC del proveedor")
        es_valido = False
    elif not (len(ruc) == 11 and (ruc.startswith("10") or ruc.startswith("20"))):
        alertas.append(f"❌ RUC mal detectado o inválido ({ruc})")
        es_valido = False
    
    # 2. Regla Matemática (Consistencia Contable)
    subtotal = datos.get("subtotal") or 0
    igv = datos.get("igv") or 0
    total = datos.get("total") or 0
    
    if total > 0:
        calculado = round(subtotal + igv, 2)
        if abs(calculado - total) > 0.10: # Tolerancia de 10 céntimos por redondeo
            alertas.append(f"🧮 Error matemático: {subtotal} + {igv} != {total}")
            # No bloqueamos el guardado, pero pedimos revisión
            if es_valido: es_valido = False
    else:
        alertas.append("⚠️ No se detectó el Monto Total")
        es_valido = False

    # 3. Datos mínimos para ERP
    if not datos.get("numero_factura"):
        alertas.append("📄 Falta Serie/Correlativo")
        es_valido = False
    if not datos.get("fecha_emision"):
        alertas.append("📅 Falta Fecha de Emisión")
        es_valido = False
        
    return {
        "es_valido": es_valido,
        "alertas": alertas,
        "estado": "EXITO" if es_valido else "REVISION_MANUAL"
    }
