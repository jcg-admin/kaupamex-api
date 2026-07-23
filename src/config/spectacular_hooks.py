"""
spectacular_hooks.py — config

Hook de postprocesamiento para drf-spectacular.
Aplica el principio Open/Closed al schema OpenAPI:

  CERRADO (base.py):
    SPECTACULAR_SETTINGS tiene solo configuracion global inmutable —
    titulo, version, autenticacion, comportamiento del generador.
    No se toca al añadir nuevas apps.

  ABIERTO (schema.py de cada app):
    Cada app declara SPECTACULAR_TAGS con la descripcion de sus tags.
    El hook collect_app_tags() los agrega automaticamente al schema.
    Añadir un nuevo dominio (catalogue, orders, payments...) nunca
    requiere modificar base.py — solo crear su schema.py.

  Flujo:
    drf-spectacular genera el schema base
    → POSTPROCESSING_HOOKS llama a collect_app_tags()
    → collect_app_tags() itera las apps de INSTALLED_APPS
    → lee SPECTACULAR_TAGS de cada schema.py
    → los añade al schema generado

  Contrato del schema.py de cada app:
    SPECTACULAR_TAGS = [
        {
            'name': 'catalogue',
            'description': 'Catálogo de productos: listado, detalle, búsqueda.',
        },
    ]

    Solo se requiere el campo 'name'. 'description' es opcional pero
    recomendado para la documentación del equipo y clientes externos.
"""
import importlib
import logging

from django.apps import apps

logger = logging.getLogger(__name__)


def _import_app_schema_modules():
    """Importa el modulo ``schema`` de cada app propia (si existe).

    Importarlo ejecuta sus definiciones de nivel de modulo, lo que registra
    como efecto secundario cualquier ``OpenApiAuthenticationExtension`` /
    serializer/view extension declarada ahi (drf-spectacular las auto-registra
    via ``__init_subclass__`` al definirse la clase).
    """
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith(('addons.', 'core')):
            continue  # solo apps propias del proyecto
        try:
            importlib.import_module(f'{app_config.name}.schema')
        except ModuleNotFoundError:
            continue


def register_app_schema_extensions(endpoints, **kwargs):
    """PREPROCESSING hook — registra las extensiones de cada ``schema.py``.

    La resolucion del ``securityScheme`` (y de las serializer/view extensions)
    ocurre DURANTE la generacion del esquema, no en postprocesamiento. Si los
    ``schema.py`` se importan solo despues (como hace ``collect_app_tags``),
    ``CsrfExemptSessionScheme`` no esta registrado a tiempo y drf-spectacular
    emite "could not resolve authenticator" dejando el esquema sin
    ``cookieAuth`` (ADR-018). Este hook fuerza esos imports antes de generar.
    """
    _import_app_schema_modules()
    return endpoints


def collect_app_tags(result, generator, **kwargs):
    """
    Agrega al schema los tags declarados en cada schema.py de las apps.

    Se registra en SPECTACULAR_SETTINGS['POSTPROCESSING_HOOKS'] y drf-
    spectacular lo llama después de generar el schema completo.

    Si una app no tiene schema.py o no declara SPECTACULAR_TAGS, se
    ignora silenciosamente — el hook nunca bloquea la generación.
    """
    collected = []

    for app_config in apps.get_app_configs():
        if not app_config.name.startswith(('addons.', 'core')):
            continue  # solo apps propias del proyecto

        try:
            module = importlib.import_module(f'{app_config.name}.schema')
        except ModuleNotFoundError:
            continue

        tags = getattr(module, 'SPECTACULAR_TAGS', None)
        if not tags:
            continue

        if not isinstance(tags, list):
            logger.warning(
                'SPECTACULAR_TAGS en %s.schema debe ser una lista, se ignora.',
                app_config.name,
            )
            continue

        collected.extend(tags)

    if collected:
        existing_names = {t['name'] for t in result.get('tags', [])}
        for tag in collected:
            if tag.get('name') and tag['name'] not in existing_names:
                result.setdefault('tags', []).append(tag)
                existing_names.add(tag['name'])

    return result
