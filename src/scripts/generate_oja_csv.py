"""
generate_oja_csv.py — genera CSV del catálogo OJA para CatalogImportCSVView.

Lee la estructura de directorios de /tmp/references/oja/oja/productos/
(o --catalog-dir) y produce un CSV en el formato extendido:

  name, sku, base_price, category_slug, description, image_files

donde image_files es una lista separada por punto y coma de los nombres
de archivo de imagen (sin ruta), listos para copiarse a MEDIA_ROOT/products/images/.

Uso:
  python kaupamex/scripts/generate_oja_csv.py
  python kaupamex/scripts/generate_oja_csv.py \\
    --catalog-dir /tmp/references/oja/oja/productos/ \\
    --output /tmp/catalogo_oja.csv

El CSV generado se sube vía:
  POST /api/v1/admin/catalogue/import-csv/
  Authorization: Bearer <token admin>
"""
import argparse
import csv
import json
import sys
from pathlib import Path

CATEGORY_NAMES = {
    'akoses-medicinas': 'Akoses / Medicinas',
    'collares-de-orumila': 'Collares de Orumila',
    'collares-y-pulseras': 'Collares y Pulseras',
    'complementos-y-herramientas': 'Complementos y Herramientas',
    'enseres': 'Ingredientes Rituales',
    'isan-iconos': 'Isan / Iconos',
    'lo-nuevo': 'Lo Nuevo',
    'ropa-y-telas': 'Ropa y Telas',
}

SLUG_OVERRIDES = {'enseres': 'ingredientes-rituales'}

_CORTE = ('Recibelo:', 'Valoraciones', 'Información adicional')


def _truncar(text):
    if not text:
        return ''
    for marker in _CORTE:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description='Genera CSV de catálogo OJA')
    parser.add_argument(
        '--catalog-dir',
        default='/tmp/references/oja/oja/productos/',
        help='Directorio raíz del catálogo OJA (default: /tmp/references/oja/oja/productos/)',
    )
    parser.add_argument(
        '--output',
        default='/tmp/catalogo_oja.csv',
        help='Ruta del CSV de salida (default: /tmp/catalogo_oja.csv)',
    )
    args = parser.parse_args()

    catalog_dir = Path(args.catalog_dir)
    if not catalog_dir.exists():
        print(f'ERROR: directorio no encontrado: {catalog_dir}', file=sys.stderr)
        sys.exit(1)

    rows = []
    total_images = 0
    errors = 0

    for cat_dir in sorted(catalog_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith('_'):
            continue
        if cat_dir.name not in CATEGORY_NAMES:
            continue
        cat_slug = SLUG_OVERRIDES.get(cat_dir.name, cat_dir.name)

        for prod_dir in sorted(cat_dir.iterdir()):
            if not prod_dir.is_dir():
                continue
            data_file = prod_dir / 'data.json'
            if not data_file.exists():
                continue
            try:
                data = json.loads(data_file.read_text(encoding='utf-8'))
                imagenes = data.get('imagenes') or []
                image_files = ';'.join(
                    img['archivo'] for img in imagenes if img.get('archivo')
                )
                total_images += len([img for img in imagenes if img.get('archivo')])
                rows.append({
                    'name': (data.get('nombre') or '')[:200],
                    'sku': f'OJA-{data["slug"][:40]}',
                    'base_price': data['precio_actual'],
                    'category_slug': cat_slug,
                    'description': _truncar(data.get('descripcion') or ''),
                    'image_files': image_files,
                })
            except Exception as exc:
                print(f'ERROR en {prod_dir.name}: {exc}', file=sys.stderr)
                errors += 1

    fieldnames = ['name', 'sku', 'base_price', 'category_slug', 'description', 'image_files']
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'CSV generado: {args.output}')
    print(f'  Productos : {len(rows)}')
    print(f'  Imágenes  : {total_images}')
    print(f'  Errores   : {errors}')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
