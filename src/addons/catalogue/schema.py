"""
schema.py — addons.catalogue

Extensiones drf-spectacular para el catálogo de productos.
Importado desde CatalogueConfig.ready().
"""

# ─────────────────────────────────────────────────────────────────────
# SPECTACULAR_TAGS
# Recogidas automáticamente por config.spectacular_hooks.collect_app_tags
# ─────────────────────────────────────────────────────────────────────
SPECTACULAR_TAGS = [
    {
        'name': 'catalogue',
        'description': (
            'Catálogo de productos Yoruba: listado paginado con filtros por '
            'categoría y ordenamiento. Accesible sin autenticación.'
        ),
    },
    {
        'name': 'categories',
        'description': 'Árbol de categorías del catálogo.',
    },
]
