import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from src.database import SessionLocal, Factura

class FiltroQuery(BaseModel):
    """Esquema para extraer los filtros de la pregunta del usuario."""
    fecha_inicio: Optional[str] = Field(None, description="Fecha de inicio en formato YYYY-MM-DD")
    fecha_fin: Optional[str] = Field(None, description="Fecha de fin en formato YYYY-MM-DD")
    proveedor: Optional[str] = Field(None, description="Nombre o RUC del proveedor")
    monto_min: Optional[float] = Field(None, description="Monto total mínimo")
    monto_max: Optional[float] = Field(None, description="Monto total máximo")
    orden: Optional[str] = Field(None, description="Campo por el cual ordenar, ej: 'total', 'fecha_emision'")
    orden_desc: Optional[bool] = Field(True, description="Si es True, orden descendente (mayor a menor).")
    limite: Optional[int] = Field(None, description="Cantidad máxima de resultados a retornar")

def parse_fecha_es(fecha_str: str):
    if not fecha_str:
        return None
    f = fecha_str.lower().strip()
    
    # 1. Tratar "15 de octubre del 2013"
    meses = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'setiembre': 9, 'octubre': 10,
        'noviembre': 11, 'diciembre': 12
    }
    match_texto = re.search(r'(\d{1,2})\s*de\s*([a-z]+)\s*(?:del|de)\s*(\d{4})', f)
    if match_texto:
        dia = int(match_texto.group(1))
        mes = meses.get(match_texto.group(2), 1)
        anio = int(match_texto.group(3))
        try:
            return datetime(anio, mes, dia).date()
        except:
            pass
            
    # 2. Formato dd/mm/yyyy o dd-mm-yyyy o dd-mm-yy
    match_num = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', f)
    if match_num:
        dia = int(match_num.group(1))
        mes = int(match_num.group(2))
        anio = int(match_num.group(3))
        if anio < 100:
            anio += 2000
        try:
            return datetime(anio, mes, dia).date()
        except:
            pass
            
    # Fallback genérico
    try:
        from dateutil import parser
        return parser.parse(f, dayfirst=True).date()
    except:
        return None

def traducir_pregunta_a_filtro(pregunta: str) -> Optional[FiltroQuery]:
    if not getattr(config, 'GEMINI_API_KEY', None):
        print("[NL2SQL] Falta GEMINI_API_KEY en config.py")
        return None
        
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("[NL2SQL] Librería google-genai no está instalada.")
        return None
        
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    prompt = f"""Eres un asistente que convierte preguntas en lenguaje natural sobre facturas en un filtro estructurado para una base de datos.
Pregunta del usuario: "{pregunta}"
Extrae los parámetros de búsqueda de la pregunta."""
    
    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FiltroQuery,
                temperature=0.0
            )
        )
        return FiltroQuery.model_validate_json(response.text)
    except Exception as e:
        print(f"[NL2SQL] Error al extraer filtro con Gemini: {e}")
        return None

def ejecutar_consulta(filtro: FiltroQuery) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(Factura)
        
        if filtro.proveedor:
            termino = f"%{filtro.proveedor}%"
            query = query.filter((Factura.proveedor_nombre.ilike(termino)) | (Factura.proveedor_ruc.ilike(termino)))
            
        if filtro.monto_min is not None:
            query = query.filter(Factura.total >= filtro.monto_min)
            
        if filtro.monto_max is not None:
            query = query.filter(Factura.total <= filtro.monto_max)
            
        # Filtros de fecha removidos de SQL, se harán en memoria.
            
        if filtro.orden:
            # Validar que el campo exista en Factura para evitar inyección/errores
            campo = getattr(Factura, filtro.orden, Factura.total)
            if filtro.orden_desc:
                query = query.order_by(campo.desc())
            else:
                query = query.order_by(campo.asc())
        else:
            query = query.order_by(Factura.fecha_emision.desc())
            
        if filtro.limite and not filtro.fecha_inicio and not filtro.fecha_fin:
            query = query.limit(filtro.limite)
            
        facturas_db = query.all()
        resultados = []
        
        # Procesamiento dinámico de fechas en memoria
        if filtro.fecha_inicio or filtro.fecha_fin:
            fecha_ini_dt, fecha_fin_dt = None, None
            try:
                if filtro.fecha_inicio: fecha_ini_dt = datetime.strptime(filtro.fecha_inicio, "%Y-%m-%d").date()
                if filtro.fecha_fin: fecha_fin_dt = datetime.strptime(filtro.fecha_fin, "%Y-%m-%d").date()
            except:
                pass
                
            for fac in facturas_db:
                f_dt = parse_fecha_es(fac.fecha_emision)
                if not f_dt: continue
                if fecha_ini_dt and f_dt < fecha_ini_dt: continue
                if fecha_fin_dt and f_dt > fecha_fin_dt: continue
                resultados.append(fac.to_dict())
                
            if filtro.limite:
                resultados = resultados[:filtro.limite]
        else:
            resultados = [f.to_dict() for f in facturas_db]
            
        return resultados
    finally:
        db.close()

def generar_respuesta_natural(pregunta: str, resultados: List[Dict[str, Any]]) -> str:
    if not getattr(config, 'GEMINI_API_KEY', None):
        return f"Se encontraron {len(resultados)} facturas."
        
    try:
        from google import genai
    except ImportError:
        return f"Se encontraron {len(resultados)} facturas."

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    # Resumir resultados para no exceder tokens
    resumen = []
    
    # Calcular sumatoria para aportar más valor en la respuesta
    suma_total = sum(f.get('total', 0) for f in resultados if f.get('total'))
    
    for f in resultados[:10]: # Máximo 10 para el prompt
        resumen.append(f"- Factura: {f.get('numero_factura')}, Prov: {f.get('proveedor_nombre')}, Total: {f.get('total')} {f.get('moneda')}, Fecha: {f.get('fecha_emision')}")
    
    contexto = "\n".join(resumen) if resumen else "No se encontraron facturas con esos criterios."
    if len(resultados) > 10:
        contexto += f"\n(Hay {len(resultados) - 10} facturas más no listadas aquí)."
        
    prompt = f"""El usuario preguntó: "{pregunta}"
Los resultados de la base de datos arrojaron {len(resultados)} registros, sumando un total de {suma_total:.2f}.
Detalle de algunas facturas:
{contexto}

Redacta una respuesta concisa, amable y natural en español al usuario respondiendo a su pregunta basándote únicamente en estos datos.
No agregues información que no esté en los resultados. Si los resultados están vacíos, indícalo amablemente."""

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"[NL2SQL] Error al generar respuesta con Gemini: {e}")
        return "Hubo un error al generar la respuesta en lenguaje natural."

def consultar_facturas_nl(pregunta: str) -> Dict[str, Any]:
    filtro = traducir_pregunta_a_filtro(pregunta)
    if not filtro:
        return {"respuesta": "No pude entender tu pregunta para convertirla en filtros. ¿Podrías reformularla indicando fechas, proveedor o montos?", "datos": []}
        
    resultados = ejecutar_consulta(filtro)
    respuesta_txt = generar_respuesta_natural(pregunta, resultados)
    
    return {
        "respuesta": respuesta_txt,
        "datos": resultados,
        "filtro_interpretado": filtro.model_dump() if hasattr(filtro, 'model_dump') else {}
    }
