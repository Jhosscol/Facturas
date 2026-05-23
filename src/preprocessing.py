import cv2
import numpy as np

def preprocesar(ruta: str) -> np.ndarray:
    img = cv2.imread(ruta)
    if img is None:
        raise FileNotFoundError(ruta)
    
    # 1. Convertir a escala de grises (esencial para OCR de Tesseract)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. Reescalado adaptativo: si la imagen es muy pequeña (ancho < 1200px),
    # la redimensionamos usando interpolación cúbica para evitar que las letras se pixelen.
    h, w = gray.shape[:2]
    if w < 1200:
        scale_factor = 2000.0 / w
        gray = cv2.resize(gray, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)
        
    # NOTA: Retiramos medianBlur y binarizaciones OTSU agresivas por defecto.
    # Las imágenes digitales y los escaneos de alta calidad conservan mucho mejor
    # los detalles finos y la legibilidad de fuentes antialiased sin filtros destructivos.
    return gray
