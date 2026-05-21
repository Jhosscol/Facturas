import cv2
import numpy as np

def preprocesar(ruta: str) -> np.ndarray:
    img = cv2.imread(ruta)
    if img is None: raise FileNotFoundError(ruta)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh
