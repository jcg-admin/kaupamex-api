SPECTACULAR_TAGS = [
    {'name': 'admin-pages',
     'description': 'Páginas estáticas versionadas del sitio (admin, UC-CFG-04).'},
    # Recuperado del ``website/schema.py`` plano, que el resolvedor de
    # ``spectacular_hooks`` nunca leía: prueba ``<app>.controllers.schema``
    # primero y, al existir este archivo, jamás caía al plano (H-API-295).
    {'name': 'static-content',
     'description': 'Páginas de contenido estático administrables.'},
]
