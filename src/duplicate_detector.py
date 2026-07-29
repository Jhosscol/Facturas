import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from src.database import SessionLocal, Factura

_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[Duplicados] Cargando modelo paraphrase-multilingual-MiniLM-L12-v2...")
            _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        except ImportError:
            print("[Duplicados] Librería sentence-transformers no instalada.")
            return None
    return _model

def verificar_duplicado(texto_nuevo: str, proveedor_ruc: str) -> dict:
    """
    Compara el texto crudo de la nueva factura con las anteriores del mismo proveedor
    usando sentence-transformers para encontrar duplicados semánticos.
    """
    if not texto_nuevo or not proveedor_ruc:
        return {"es_duplicado": False}
        
    model = get_model()
    if not model:
        return {"es_duplicado": False}
        
    db = SessionLocal()
    try:
        # Traer facturas recientes del mismo proveedor para comparar
        facturas_previas = db.query(Factura).filter(
            Factura.proveedor_ruc == proveedor_ruc
        ).order_by(Factura.fecha_procesamiento.desc()).limit(30).all()
        
        if not facturas_previas:
            return {"es_duplicado": False}
            
        from sentence_transformers import util
        import torch
        
        # Calcular embedding para la nueva factura
        emb_nuevo = model.encode(texto_nuevo, convert_to_tensor=True)
        
        max_score = 0.0
        id_original = None
        
        for f in facturas_previas:
            if not f.texto_crudo:
                continue
                
            emb_previo = model.encode(f.texto_crudo, convert_to_tensor=True)
            cosine_scores = util.cos_sim(emb_nuevo, emb_previo)
            score = cosine_scores[0][0].item()
            
            if score > max_score:
                max_score = score
                id_original = f.id
                
        umbral = getattr(config, 'UMBRAL_SIMILITUD_DUPLICADOS', 0.85)
        
        if max_score > umbral:
            return {
                "es_duplicado": True, 
                "score": max_score, 
                "factura_original_id": id_original
            }
            
        return {"es_duplicado": False}
        
    except Exception as e:
        print(f"[Duplicados] Error al verificar duplicados: {e}")
        import traceback
        traceback.print_exc()
        return {"es_duplicado": False}
    finally:
        db.close()
