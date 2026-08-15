"""AppConfig — ``addons.base_sparse_field``.

Este addon no declara modelos: **inyecta dos tipos de campo** en el namespace
de la fachada ``fields`` al cargarse. Es literalmente lo que hace la referencia
en la última línea de su ``models/fields.py``, con su ``from odoo import
fields`` de cabecera::

    fields.Serialized = Serialized

**El destino es la fachada, no el módulo de implementación** — corregido
2026-08-15 (:ref:`h-api-604`). Inyectar en ``orm.fields`` no publicaba nada: la
fachada arma su superficie al importarse, y el ``ready()`` de este addon corre
después, así que ``fields.Serialized`` no existía (medido: ``orm.fields=True |
fields=False``). Un consumidor tenía que escribir ``from orm.fields import
Serialized`` para declarar un campo disperso, cruzando la frontera que la
fachada existe para sostener y que la referencia cruza **0** veces en sus
addons.

La inyección va en ``ready()`` y no a nivel de módulo por el mismo criterio
que ``base_iban``: cuando corre, el registro de apps ya está poblado, así que
un consumidor que declare ``fields.Sparse('data')`` en el cuerpo de su clase
lo encuentra si su addon depende de éste.

Por qué el núcleo no lo importa
================================

Ni ``orm/fields_*.py`` ni la fachada **declaran** estos dos tipos, y es
deliberado: la dependencia iría del núcleo al addon, al revés de lo que la
referencia declara. Allí ``odoo/orm/`` no conoce ``Serialized`` —medido:
``class Serialized`` da **0** hits en ``odoo19c: odoo/orm/`` y **1** en
``addons/base_sparse_field/models/fields.py``— y por eso el addon tiene que
publicar hacia la fachada en vez de que el núcleo lo importe.
"""
import importlib

from django.apps import AppConfig


class BaseSparseFieldConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_sparse_field'
    label = 'base_sparse_field'
    verbose_name = 'Base — Campos dispersos'

    def ready(self):
        """Publica los dos tipos y cuelga la mitad ``ir.model.fields``.

        **Publicar** ≙ ``fields.Serialized = Serialized`` (``odoo19c:
        base_sparse_field/models/fields.py:104``). **Colgar** ≙ el
        ``_inherit = 'ir.model.fields'`` de su ``models.py``: el vocabulario
        ``serialized``, el campo ``serialization_field_id``, la guarda de
        escritura y la pasada de reflexión.

        El ``import_module`` en vez del ``import`` de statement es la
        excepción #4 de ``no-lazy-imports.md``: es una llamada, no un
        statement, así que el gate AST da exit 0 y el arranque se preserva.
        Aquí además es **necesario**, no sólo permitido: importar
        ``ir_model_fields`` al tope del módulo correría ``add_to_class`` antes
        de que el registro esté poblado.
        """
        sparse = importlib.import_module('addons.base_sparse_field.models.fields')
        facade = importlib.import_module('fields')
        facade.Serialized = sparse.Serialized
        facade.Sparse = sparse.Sparse

        extensiones = importlib.import_module(
            'addons.base_sparse_field.models.ir_model_fields')
        extensiones.apply_base_sparse_field_extensions()
