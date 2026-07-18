from django.apps import AppConfig


class AuthzMenuConfig(AppConfig):
    """App de feature opcional: catálogo de navegación del panel/cuenta (DEC-08/09).

    Proyección UX sobre el core de autorización (``addons.authz``), análoga a
    ``ir.ui.menu`` de Odoo (el árbol de menú es un modelo de datos aparte del
    motor de permisos ``ir.model.access`` / ``ir.rule``). Se separó del core en
    SOL-094 frente B (DEC-01): el árbol se **persiste** aquí; el candado real
    sigue siendo ``HasCapability`` en cada vista (el menú solo decide qué se
    muestra). La vista ``MyMenuView`` vive en ``addons.authz`` y lee este modelo.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_menu'
    verbose_name = 'Autorización — Menú de navegación'
