"""Extender un modelo **nombrándolo**, sin importarlo — ≙ el ``_inherit`` de la referencia.

Adaptación del acoplamiento tardío que la referencia obtiene de su registro
(``odoo-tools@622ddc2a``, ``odoo19c: odoo/orm/model_classes.py:152-231`` —
``add_to_registry``, que resuelve cada nombre de ``_inherit`` contra
``registry[parent_name]``, LGPL-3).

Por qué existe
================

Un addon de la referencia extiende a otro **sin importarlo**::

    class ProductRemoval(models.Model):
        _inherit = ['product.removal', 'pos.load.mixin']

La cadena es una dirección, no un símbolo: su cargador no garantiza orden de
import, así que el acoplamiento tiene que ser tardío por construcción.

Este árbol tenía sólo la mitad temprana — ``chain_method(ClaseImportada, …)``
y ``Model.add_to_class(…)``, que exigen que el destino **ya esté importado**.
Eso obliga a que el extensor importe al extendido, y con ello a que el grafo
de imports sea acíclico: es la causa de que ``base`` y ``authz`` se enreden
(tarea **#322**).

Django **sí** trae el mecanismo, y no hubo que construirlo: ``Apps
.lazy_model_operation`` (``django/apps/registry.py:388-426``) encola la función
hasta que el modelo se registre, y ``Apps.do_pending_operations`` (``:428-435``)
la dispara desde la última línea de ``register_model`` (``:239``). Lo que sí
faltaba —y es lo que aporta este módulo— es el adaptador que lo vuelve seguro.

La trampa que este módulo cierra
==================================

Medido en el binario, no leído de la documentación (ver
``tests/unit/orm/test_extension_tardia_por_nombre.py``):

=======================================  ==================================================
Pieza de Django                          Cómo trata la clave
=======================================  ==================================================
``get_registered_model`` (``:278``)      **normaliza** — ``model_name.lower()``
``_pending_operations[…]`` (``:424``)    **verbatim** — la tupla tal como se pasó
``do_pending_operations`` (``:432``)     **reconstruye en minúscula** desde ``_meta``
=======================================  ==================================================

Consecuencia: pasar ``('stock', 'StockLocation')`` con caja alta **funciona**
si el destino ya estaba cargado y **se cuelga en silencio** si aún no lo
estaba. No hay excepción, no hay aviso: la extensión simplemente nunca corre, y
el resultado depende del orden de ``INSTALLED_APPS``. Es la clase de fallo que
aparece meses después al reordenar una lista.

``extend_model`` normaliza la clave antes de encolar. Es una línea, y es toda la
razón de que este envoltorio exista en vez de llamar a Django directo.

Cómo se usa
=============

Desde el ``ready()`` del addon que extiende, sin importar el destino::

    from orm.model_extension import extend_model
    import fields

    def aplicar():
        extend_model('product', 'ProductTemplate', campos={
            'tracking': fields.Selection(max_length=8, choices=..., default='none'),
        }, metodos={
            'is_storable_default': _is_storable_default,
        })

El destino puede no existir todavía: la extensión se aplica en cuanto se
registre. Si nunca se registra —el addon no está instalado— la extensión
sencillamente no ocurre, que es exactamente la semántica de un ``depends``
opcional.
"""
import fields as _fields_mod  # noqa: F401  (documenta el vocabulario esperado)
from django.apps import apps

from orm.method_chain import chain_method

__all__ = ['extend_model', 'add_field_if_absent', 'model_key']


def model_key(app_label, model_name):
    """La clave que ``do_pending_operations`` va a reconstruir.

    ``Model._meta.label`` da ``stock.StockLocation``; la cola se indexa por
    ``_meta.model_name``, que Django guarda en minúscula. Normalizar aquí es lo
    que impide el cuelgue silencioso descrito en el docstring del módulo.
    """
    return (app_label, model_name.lower())


def add_field_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idéntico al ``_add_if_absent`` que ya repiten ``account``,
    ``account_fleet``, ``l10n_mx`` y ``product_expiry``: el idioma de extensión
    por ``add_to_class`` no tiene MRO, así que dos addons que cuelguen el mismo
    campo duplicarían la columna.

    Devuelve ``True`` si lo añadió — para que el llamador pueda medir en vez de
    suponer.
    """
    if any(f.name == name for f in model._meta.get_fields()):
        return False
    model.add_to_class(name, field)
    return True


def extend_model(app_label, model_name, campos=None, metodos=None,
                 propiedades=None, luego=None):
    """Extiende ``app_label.model_name`` cuando exista — ≙ ``_inherit``.

    Ninguno de los cuatro bloques es obligatorio; se aplican en este orden
    sobre la clase destino:

    ``campos``
        ``{nombre: field}`` — vía :func:`add_field_if_absent`.
    ``metodos``
        ``{nombre: función}`` — vía ``chain_method``, que preserva la
        implementación previa (el ``super()`` que este idioma no tiene).
    ``propiedades``
        ``{nombre: función}`` — instaladas como ``property``, para los
        ``compute`` sin ``store`` de la referencia. No pisa una existente.
    ``luego``
        ``f(modelo)`` — escotilla para lo que no cae en los tres anteriores
        (índices, constraints, receptores de señal).

    **No devuelve el modelo**: en el caso interesante todavía no existe. Quien
    necesite la clase la pide dentro de ``luego``, que la recibe como argumento.
    """
    def aplicar(modelo):
        for nombre, field in (campos or {}).items():
            add_field_if_absent(modelo, nombre, field)
        for nombre, funcion in (metodos or {}).items():
            chain_method(modelo, nombre, funcion)
        for nombre, funcion in (propiedades or {}).items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, property(funcion))
        if luego is not None:
            luego(modelo)

    apps.lazy_model_operation(aplicar, model_key(app_label, model_name))
