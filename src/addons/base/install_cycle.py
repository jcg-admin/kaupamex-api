"""El ciclo de instalación tras ``migrate`` — receptor de ``post_migrate``.

Diseño: ``designs/module-install-cycle.md`` (L3). Lo conecta
``BaseConfig.ready()``.
"""

from django.apps import apps
from django.db import router

import modules.loading


def load_modules_after_migrate(sender, using, plan=None, **kwargs):
    """Instala o actualiza los addons tras ``migrate`` en ``using``.

    ``post_migrate`` es el punto del stack en que el esquema de todas las
    apps está al día: Django crea ahí permisos y tipos de contenido, y aquí
    corre el paso por módulo de ``load_module_graph`` de la referencia
    (``modules.loading.load_modules``). Dos guardas, las de
    ``django.contrib.auth.management.create_permissions``: sólo con ``plan``
    —lo pasa ``migrate``; ``flush`` emite la misma señal sin él— y sólo en
    una base donde el router migra ``base`` (las bases por empresa no
    alojan el plano de control).
    """
    if plan is None:
        return
    module_model = apps.get_model('base', 'IrModule')
    if not router.allow_migrate_model(using, module_model):
        return
    modules.loading.load_modules(using)
