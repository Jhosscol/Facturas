# Sistema de Extracción Automática de Datos de Facturas (OCR + NLP)

Este es un proyecto universitario diseñado para automatizar la extracción de datos clave de facturas y documentos financieros en formato de imagen o PDF usando técnicas de Visión Computacional (OpenCV) y Procesamiento de Lenguaje Natural (NLP).

## 🚀 Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

1. **Python 3.8+**
2. **Tesseract OCR**:
   - Descárgalo para Windows desde [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
   - Instálalo en la ruta por defecto: `C:\Program Files\Tesseract-OCR\tesseract.exe` (si utilizas otra ruta, actualízala en `config.py`).
   - Asegúrate de instalar el paquete de idioma español (`spa`).
3. **Poppler** (Solo si vas a procesar archivos PDF):
   - Descarga para Windows desde [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) y añade el directorio `bin` a tu variable de entorno PATH.

## 🛠️ Instalación

1. Clona o ubícate en la carpeta del proyecto:
   ```bash
   cd d:/Noveno_Semestre/Procesamiento_Lenguaje_Natural/Facturas
   ```

2. Instala las dependencias de Python:
   ```bash
   pip install -r requirements.txt
   ```

3. Descarga el modelo en español para **spaCy**:
   ```bash
   python -m spacy download es_core_news_sm
   ```

## 📂 Estructura de la Fase 1

- `config.py`: Parámetros centrales del sistema (rutas, constantes de IGV y Tesseract).
- `src/preprocessing.py`: Módulo de Visión Computacional con OpenCV (escala de grises, binarización adaptativa, deskew y denoising).
- `src/ocr_engine.py`: Interfaz con Tesseract OCR para digitalizar texto y calcular métricas de confianza.
- `src/entity_extractor.py`: Reglas heurísticas Regex + Inteligencia spaCy para extraer números de factura, fechas, RUCs, razón social y montos financieros.
- `src/validator.py`: Validador lógico que verifica que `Subtotal + IGV == Total` y comprueba RUCs y fechas.
- `src/exporter.py`: Utilidades para exportar los resultados estructurados a archivos JSON o CSV.
- `src/pipeline.py`: El orquestador principal que une todos los pasos en un flujo automatizado.

## 💻 Cómo Ejecutar

### 1. Procesar una sola factura
Coloca una imagen o PDF de prueba en cualquier directorio (por ejemplo, en `data/input/`) y ejecuta:
```bash
python src/pipeline.py data/input/mi_factura.jpg
```
Esto imprimirá el resumen estructurado en la consola y guardará el resultado formateado en un archivo `.json` dentro de `data/output/`.

### 2. Procesar un lote de facturas
Coloca múltiples facturas en `data/input/` y ejecuta:
```bash
python src/pipeline.py --lote
```
Esto procesará cada uno de los archivos encontrados, guardará sus respectivos archivos `.json` individuales y generará un archivo consolidado `.csv` en `data/output/` para que puedas abrirlo directamente en Excel.
