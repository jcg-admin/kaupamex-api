"""AppConfig — ``addons.base_sparse_field``.

Este addon no declara modelos: **inyecta dos tipos de campo** en el namespace
de ``orm.fields`` al cargarse. Es literalmente lo que hace la referencia en la
última línea de su ``models/fields.py``::

    fields.Serialized = Serialized

La inyección va en ``ready()`` y no a nivel de módulo por el mismo criterio
que ``base_iban``: cuando corre, el registro de apps ya está poblado, así que
un consumidor que declare ``fields.Sparse('data')`` en el cuerpo de su clase
lo encuentra si su addon depende de éste.

Por qué el núcleo no lo importa
================================

``orm/fields.py`` **no** exporta estos dos tipos, y es deliberado: la
dependencia iría del núcleo al addon, al revés de lo que la referencia
declara. Allí ``odoo/orm/`` no conoce ``Serialized`` —medido: ``class
Serialized`` da **0** hits en ``odoo19c: odoo/orm/`` y **1** en
``addons/base_sparse_field/models/fields.py``— y por eso el addon tiene que
parchear hacia adentro en vez de que el núcleo lo importe.
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
        orm_fields = importlib.import_module('orm.fields')
        orm_fields.Serialized = sparse.Serialized
        orm_fields.Sparse = sparse.Sparse

        extensiones = importlib.import_module(
            'addons.base_sparse_field.models.ir_model_fields')
        extensiones.apply_base_sparse_field_extensions()
