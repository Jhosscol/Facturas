# Informe Técnico — Sistema de Extracción Automática de Facturas

---

## 1. Descripción General

El sistema es una aplicación web que automatiza la digitalización y extracción de información estructurada a partir de imágenes y PDFs de facturas peruanas. Utiliza un pipeline de tres capas: preprocesamiento visual, extracción inteligente con LLM, y validación algebraica según normativa SUNAT. Los datos extraídos se almacenan en una base de datos local, pueden exportarse a Excel y enviarse a un sistema ERP simulado.

---

## 2. Arquitectura Tecnológica

| Capa | Tecnología | Rol |
|------|-----------|-----|
| Frontend | HTML5 + CSS3 + JavaScript | Interfaz web (subida, visualización, exportación) |
| Backend | FastAPI (Python) | API REST que orquesta todo el pipeline |
| Persistencia | SQLite + SQLAlchemy | Almacenamiento de facturas y registros ERP |
| OCR | Tesseract + OpenCV | Digitalización del documento físico/escaneado |
| IA Semántica | OpenAI GPT (API) | Extracción inteligente de campos con comprensión contextual |
| NLP Estructural | spaCy + Regex | Extracción determinista de RUC, N° factura, fechas |
| Exportación | pandas + openpyxl | Generación de archivos Excel/CSV |

---

## 3. Pipeline de Procesamiento

Cuando el usuario sube una factura, el sistema ejecuta los siguientes pasos en secuencia:

### Paso 1 — Preprocesamiento Visual (`preprocessing.py`)
- **Conversión a escala de grises** para reducir ruido de color
- **Binarización adaptativa** (umbralización de Otsu) para mejorar contraste texto/fondo
- **Deskew** (corrección de inclinación) para alinear documentos fotografiados en ángulo
- **Denoising** con filtros de OpenCV para eliminar manchas y artefactos

### Paso 2 — OCR con Tesseract (`ocr_engine.py`)
- Tesseract convierte la imagen preprocesada a texto plano
- Se calcula la **confianza OCR promedio** (0–100%) como métrica de calidad por palabra reconocida
- Se extraen también las coordenadas posicionales de cada palabra para vincularlas a los campos extraídos

### Paso 3 — Extracción Híbrida (`openai_extractor.py` + `entity_extractor.py`)

El sistema opera con **dos motores en paralelo** que luego se fusionan:

**Motor Semántico — OpenAI GPT:**
- Recibe el texto OCR crudo mediante un Prompt especializado en facturas SUNAT
- El esquema de salida es un JSON Pydantic estricto que obliga a devolver solo los campos requeridos
- El Prompt instruye al LLM sobre: formato de RUC peruano (11 dígitos), formato de número de factura SUNAT, relación IGV 18%, tratamiento de distorsiones OCR típicas (ej. "si" → "S/", "1GV" → "IGV")
- Campos objetivo: `numero_factura`, `fecha_emision`, `proveedor_ruc`, `proveedor_nombre`, `cliente_nombre`, `subtotal`, `igv`, `total`, `moneda`

**Motor Determinista — Regex + spaCy:**
- Aplica más de 30 expresiones regulares multi-estrategia tolerantes a errores OCR
- spaCy NER identifica nombres de organizaciones (ORG) como respaldo para el nombre del proveedor
- Especialmente preciso para RUC (patrón `\b(20\d{9})\b`) y número de factura (patrón SUNAT `F001-000134`)

**Fusión de resultados:**
- Cada campo tiene una prioridad configurable (`"openai"` o `"regex"`)
- Campos semánticos (proveedor, cliente, montos) → prioridad OpenAI
- Campos estructurales (RUC, N° factura, moneda) → prioridad Regex
- Si el campo prioritario es `null`, se usa el otro motor como respaldo

### Paso 4 — Validación SUNAT (`validator.py`)
- Verifica que `Subtotal + IGV == Total` (tolerancia ±1 sol)
- Si faltan campos, los **infiere matemáticamente**: ej. si hay Total e IGV, calcula `Subtotal = Total - IGV`
- Si los tres valores existen pero son inconsistentes, recalcula desde el Total (el dato más fiable)
- Genera alertas descriptivas que se muestran en la interfaz

---

## 4. Campos Extraídos

| Campo | Descripción |
|-------|-------------|
| `numero_factura` | Serie y correlativo (ej. F001-00000998) |
| `fecha_emision` | Fecha del comprobante |
| `proveedor_ruc` | RUC del emisor (11 dígitos) |
| `proveedor_nombre` | Razón social del emisor |
| `cliente_nombre` | Nombre del adquiriente/cliente |
| `subtotal` | Base imponible (sin IGV) |
| `igv` | Impuesto General a las Ventas (18%) |
| `total` | Monto total a pagar |
| `moneda` | SOLES o DOLARES |
| `confianza_ocr` | Precisión del reconocimiento (0–100%) |
| `metodo_extraccion` | `hybrid`, `openai` o `regex` |

---

## 5. Funcionalidades del Sistema

### Interfaz Web
- Subida de archivos por **drag & drop** o selector (`.jpg`, `.png`, `.pdf`)
- **Vista previa** del documento subido (imagen o PDF incrustado)
- Panel de resultados con todos los campos extraídos en tiempo real
- Barra de confianza OCR visual con color indicador
- Sección de alertas de validación con detalle de inconsistencias

### Gestión de Historial
- Tabla dinámica con todas las facturas procesadas en sesión
- Checkboxes de selección individual y global
- Estadísticas en tiempo real: total procesadas, exitosas, monto acumulado

### Exportación
- Botón **"Añadir a lista de exportación"** enlaza la última factura procesada a la selección de exportación
- Exportación de facturas seleccionadas a **Excel `.xlsx`** (con fallback a `.csv` si falla openpyxl)
- El Excel incluye: N° factura, Fecha, RUC emisor, Cliente, Total, IGV — con encabezados en español

### Integración ERP Simulada
- Botón **"🚀 Enviar a ERP"** disponible tras cada procesamiento exitoso
- Llama al endpoint `POST /erp/sincronizar/{id}` que registra el payload estructurado en la tabla `registro_erp` de la BD
- El payload enviado contiene **solo los campos de negocio** (excluye texto OCR crudo y coordenadas):
  ```json
  {
    "numero_factura": "BE01-00000007",
    "fecha_emision": "18-04-2022",
    "proveedor_ruc": "20490190334",
    "proveedor_nombre": "GRILL RESTAURANT",
    "cliente_nombre": "FERNANDO HOLGADO SANCHEZ",
    "subtotal": 9.32,
    "igv": 1.68,
    "total": 11.0,
    "moneda": "SOLES",
    "confianza_ocr": 80.83,
    "metodo_extraccion": "hybrid",
    "estado": "EXITO"
  }
  ```
- Los registros son consultables en `GET /erp/registros/`, demostrando la trazabilidad de envíos
- La arquitectura del endpoint permite reemplazar el almacenamiento local por una llamada HTTP real a un ERP externo sin modificar el frontend

---

## 6. API REST — Endpoints

| Método | Ruta | Función |
|--------|------|---------|
| `POST` | `/facturas/` | Procesar y guardar factura |
| `GET`  | `/facturas/` | Listar historial completo |
| `GET`  | `/estadisticas/` | Contadores y monto total |
| `GET`  | `/facturas/exportar/excel/?ids=1,2` | Exportar selección a Excel |
| `POST` | `/erp/sincronizar/{id}` | Registrar factura en ERP simulado |
| `GET`  | `/erp/registros/` | Ver historial de envíos ERP |

---

## 7. Base de Datos

Dos tablas principales en SQLite:

**`facturas`** — Almacena cada documento procesado con todos sus campos extraídos, el texto OCR crudo, coordenadas, estado de validación y métricas de procesamiento.

**`registro_erp`** — Registra cada envío realizado al ERP: `factura_id`, `fecha_sincronizacion`, `estado_erp` y el JSON limpio enviado (`datos_enviados_json`).

**`alertas`** — Alertas de validación vinculadas a cada factura (relación 1:N).
