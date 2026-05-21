"""
config.py — Configuración centralizada del sistema de extracción de facturas.

Centraliza rutas de archivos, parámetros de Tesseract, tasa de impuestos
y cadena de conexión a la base de datos para que el resto de módulos
no tenga valores hardcodeados.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ============================================================
# API Keys
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ============================================================
# Rutas del Proyecto
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

# Crear directorios si no existen
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# Tesseract OCR
# ============================================================
# Ruta al ejecutable de Tesseract en Windows
# Descárgalo de: https://github.com/UB-Mannheim/tesseract/wiki
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Idioma para el OCR (español)
TESSERACT_LANG = "spa"

# Page Segmentation Mode (PSM)
#   4 = Columna de texto variable
#   6 = Bloque uniforme de texto (default recomendado para facturas)
#  11 = Texto disperso sin orden
TESSERACT_PSM = 6

# OCR Engine Mode (OEM)
#   3 = Default (usa LSTM si está disponible)
TESSERACT_OEM = 3

# ============================================================
# Parámetros Financieros (Perú)
# ============================================================
# Tasa del IGV (Impuesto General a las Ventas) — 18%
TASA_IGV = 0.18

# Tolerancia para validación matemática (en soles)
TOLERANCIA_MONTO = 0.50

# ============================================================
# Base de Datos — SQLite
# ============================================================
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'facturas.db')}"

# ============================================================
# Preprocesamiento de Imágenes
# ============================================================
# Umbral para binarización (0-255). Se usa si no se aplica adaptativo.
THRESHOLD_VALUE = 150

# Tamaño del kernel para eliminación de ruido (debe ser impar)
DENOISE_KERNEL = 3
