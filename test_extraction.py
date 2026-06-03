"""
Script de prueba: extrae datos de cada factura usando el extractor híbrido (Gemini + Regex).
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.preprocessing import preprocesar
from src.ocr_engine import extraer_texto
from src.openai_extractor import extraer_datos_hybrid

INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "input")

print("=" * 80)
print("  TEST DE EXTRACCIÓN HÍBRIDA (Gemini + Regex)")
print("=" * 80)

for fname in sorted(os.listdir(INPUT_DIR)):
    if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
        continue

    ruta = os.path.join(INPUT_DIR, fname)
    print(f"\n{'─' * 80}")
    print(f"  📄 {fname}")
    print(f"{'─' * 80}")

    try:
        imagen = preprocesar(ruta)
        texto = extraer_texto(imagen)
        datos = extraer_datos_hybrid(texto)

        metodo = datos.get('metodo_extraccion', 'desconocido')
        print(f"\n  🔧 Método:       {metodo.upper()}")
        print(f"  Proveedor:     {datos['proveedor_nombre']}")
        print(f"  RUC:           {datos['proveedor_ruc']}")
        print(f"  Factura N°:    {datos['numero_factura']}")
        print(f"  Fecha:         {datos['fecha_emision']}")
        print(f"  Moneda:        {datos['moneda']} ({datos['simbolo_moneda']})")
        print(f"  Base Imp.:     {datos['simbolo_moneda']} {datos['subtotal']}")
        print(f"  IGV:           {datos['simbolo_moneda']} {datos['igv']}")
        print(f"  TOTAL:         {datos['simbolo_moneda']} {datos['total']}")

        # Verificar consistencia
        if datos['subtotal'] and datos['igv'] and datos['total']:
            check = round(datos['subtotal'] + datos['igv'], 2)
            ok = "✅" if abs(check - datos['total']) < 1.0 else "❌"
            print(f"  Verificación:  {datos['subtotal']} + {datos['igv']} = {check} vs {datos['total']} {ok}")
        else:
            print(f"  Verificación:  ⚠️ Faltan datos para verificar")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'=' * 80}")
print("  FIN DEL TEST")
print(f"{'=' * 80}")
