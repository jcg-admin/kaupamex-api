"""``tools.constants`` — las constantes compartidas del núcleo.

Adaptación fiel de ``odoo19c: odoo/tools/constants.py``. Es un módulo de
**valores**, sin lógica: su razón de existir es que un mismo número o tupla
tenga un solo sitio donde vive.

**Por qué se crea ahora.** Seis de sus ocho símbolos ya estaban en el árbol,
declarados **localmente** en tres archivos distintos, cada uno con un comentario
diciendo que su hogar era este módulo: ``GC_UNLINK_LIMIT`` en ``ir_cron.py`` y
en ``ir_profile.py``, y los cuatro de extensiones más ``EXTERNAL_ASSET`` en
``ir_asset.py``. Tres copias de un valor son tres fuentes de verdad que nadie
sincroniza — lo que ``calibration-verified-numbers.md`` prohíbe— y el defecto no
es hipotético: basta que una cambie.

``PREFETCH_MAX`` entra sin consumidor todavía. No es relleno: es el tope de
registros que el ORM precarga de una vez, y su consumidor es el mecanismo de
*prefetch* que este árbol aún no tiene. Se declara aquí porque el porte de un
archivo lleva **todos** sus símbolos o declara cuáles no y por qué; éste sí se
porta, y su ausencia de consumidores es un dato del árbol, no del archivo.
"""

SCRIPT_EXTENSIONS = ('js',)
STYLE_EXTENSIONS = ('css', 'scss', 'sass', 'less')
TEMPLATE_EXTENSIONS = ('xml',)
ASSET_EXTENSIONS = SCRIPT_EXTENSIONS + STYLE_EXTENSIONS + TEMPLATE_EXTENSIONS

SUPPORTED_DEBUGGER = {'pdb', 'ipdb', 'wdb', 'pudb'}
EXTERNAL_ASSET = object()

PREFETCH_MAX = 1000
"""Número máximo de registros precargados."""

GC_UNLINK_LIMIT = 100_000
"""Número máximo de registros a limpiar en una sola transacción."""
