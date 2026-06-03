import pytesseract
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

tessdata_path = os.path.join(config.BASE_DIR, "tessdata")
os.environ["TESSDATA_PREFIX"] = tessdata_path

def extraer_texto(imagen) -> str:
    return pytesseract.image_to_string(imagen, lang='spa')

def extraer_datos_posicionales(imagen) -> list:
    """Retorna una lista de diccionarios con texto y coordenadas [x, y, w, h]."""
    data = pytesseract.image_to_data(imagen, lang='spa', output_type=pytesseract.Output.DICT)
    resultados = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if text:
            resultados.append({
                "text": text,
                "box": [data['left'][i], data['top'][i], data['width'][i], data['height'][i]],
                "conf": data['conf'][i]
            })
    return resultados

def calcular_confianza(imagen) -> float:
    data = pytesseract.image_to_data(imagen, lang='spa', output_type=pytesseract.Output.DICT)
    confs = [int(c) for c in data['conf'] if int(c) != -1]
    return sum(confs) / len(confs) if confs else 0.0
