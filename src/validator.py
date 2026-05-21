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
