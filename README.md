# Sistema de Extracción Automática de Facturas — OCR + OpenAI + ERP

Sistema inteligente para la digitalización, extracción y gestión de datos de facturas peruanas. Combina visión computacional (OpenCV + Tesseract), un LLM (OpenAI GPT) y heurísticas Regex/spaCy en un motor híbrido de alta tolerancia a errores OCR. Incluye una interfaz web completa y un módulo de integración simulada con ERP.

---

## 🚀 Requisitos Previos

1. **Python 3.8+**
2. **Tesseract OCR** — [Descargar para Windows (UB-Mannheim)](https://github.com/UB-Mannheim/tesseract/wiki)
   - Instalar en `C:\Program Files\Tesseract-OCR\` (o ajustar ruta en `config.py`)
   - Instalar el paquete de idioma **español (`spa`)**
3. **Poppler** — solo necesario para procesar PDFs de múltiples páginas

---

## 🛠️ Instalación

```bash
# 1. Instalar dependencias Python
pip install -r requirements.txt

# 2. Descargar modelo NLP en español
python -m spacy download es_core_news_sm
```

### Configurar API Key de OpenAI

Crear archivo `.env` en la raíz del proyecto:
```env
OPENAI_ENABLED=True
OPENAI_API_KEY=sk-...tu_clave_aqui...
```

---

## ▶️ Ejecución

```bash
uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

Acceder en el navegador: **[http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/)**
Documentación API interactiva: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 📂 Estructura del Proyecto

```
Facturas/
├── config.py                  # Configuración central y variables de entorno
├── requirements.txt
├── .env                       # API keys (NO subir a GitHub)
├── src/
│   ├── api.py                 # Servidor FastAPI — endpoints principales
│   ├── database.py            # Modelos SQLAlchemy + SQLite + lógica ERP
│   ├── preprocessing.py       # Preprocesamiento de imagen con OpenCV
│   ├── ocr_engine.py          # Interfaz con Tesseract OCR
│   ├── openai_extractor.py    # Motor híbrido OpenAI + Regex (principal)
│   ├── entity_extractor.py    # Motor Regex + spaCy (fallback/complemento)
│   ├── validator.py           # Validación algebraica SUNAT (IGV 18%)
│   └── exporter.py            # Generación de archivos Excel/CSV
└── frontend/
    ├── index.html             # Interfaz web principal
    ├── styles.css             # Estilos (glassmorphism, dark mode)
    └── app.js                 # Lógica frontend (fetch, tabla dinámica, ERP)
```

---

## 🔌 Endpoints Principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/facturas/` | Subir y procesar una factura |
| `GET`  | `/facturas/` | Listar todas las facturas procesadas |
| `GET`  | `/estadisticas/` | Totales y monto acumulado |
| `GET`  | `/facturas/exportar/excel/?ids=1,2,3` | Exportar seleccionadas a `.xlsx` |
| `POST` | `/erp/sincronizar/{id}` | Enviar factura al ERP simulado |
| `GET`  | `/erp/registros/` | Ver todos los registros enviados al ERP |
| `GET`  | `/docs` | Documentación interactiva (Swagger) |
