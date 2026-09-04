"""``sparse_fields.test`` — el modelo con que la referencia ejercita el addon.

Adaptación de ``odoo19c: addons/base_sparse_field/models/models.py:79-87``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03).

Se porta **aunque sea de prueba**, y no se muda a ``tests/``: la referencia lo
declara en el addon, así que forma parte de lo que el addon publica. Su papel
es ser el modelo sobre el que se comprueba que un campo disperso lee, escribe
y **se refleja** — sin él, ``reflect_sparse_fields`` no tendría contra qué
correr en un modelo real de Django.

``TransientModel`` con ``managed = False``: no genera tabla, igual que el resto
de los transitorios de este árbol (``orm/models_transient.py``). Alcanza para
el mecanismo, que vive en descriptores y en el mapa JSON de la instancia. La
referencia sí le da tabla —sus transitorios se guardan y se barren con un
vacuum— y ese barrido no está portado; queda declarado, no simulado.

El nombre técnico es el ``label`` de Django
===========================================

La referencia lo identifica con ``_name = 'sparse_fields.test'``. Aquí la
identidad de un modelo es ``app_label.ObjectName``, que es lo que
``IrModel._reflect_models`` escribe en el catálogo — no hay ``_name`` en este
árbol (medido: 0 declaraciones fuera de docstrings que citan la referencia).
Así que este modelo se llama ``base_sparse_field.SparseFieldsTest``, y no se
inventa un atributo que ningún consumidor lee.

Cómo cambia la declaración, y por qué
======================================

La referencia declara el **tipo** en la clase del campo y el almacén en un
``kwarg``::

    integer  = fields.Integer(sparse='data')
    partner  = fields.Many2one('res.partner', sparse='data')

Aquí es al revés: el almacén va en el descriptor y el tipo en lo que el valor
necesite para volver del JSON (``fields.py`` lo documenta con su medición —
``models.CharField(sparse='data')`` levanta ``TypeError``). El ``boolean`` de
la referencia no lleva ``coerce`` porque ``jsonb`` ya devuelve ``bool``.

**``selection`` pierde su vocabulario.** La referencia declara
``fields.Selection([('one', 'One'), ('two', 'Two')], sparse='data')`` y su ORM
valida contra esas dos claves. ``Sparse`` no tiene dónde recibir un
vocabulario, así que aquí es una cadena sin validar. Es una divergencia
declarada, no un olvido: el validador viviría en el descriptor, y añadirlo
sería diseñar un mecanismo que ningún consumidor del árbol pide hoy.
"""
from addons.base_sparse_field.models.fields import Serialized, Sparse
from orm.models_transient import TransientModel


class SparseFieldsTest(TransientModel):
    """≙ ``Sparse_FieldsTest`` — seis campos dispersos sobre un serializado."""

    data = Serialized(verbose_name='Datos')
    boolean = Sparse('data', help_text='≙ fields.Boolean(sparse="data")')
    integer = Sparse('data', coerce=int, help_text='≙ fields.Integer(...)')
    float = Sparse('data', coerce=float, help_text='≙ fields.Float(...)')
    char = Sparse('data', coerce=str, help_text='≙ fields.Char(...)')
    selection = Sparse('data', coerce=str, help_text='≙ fields.Selection(...)')
    partner = Sparse('data', relational_model='base.ResPartner',
                     help_text='≙ fields.Many2one("res.partner", ...)')

    class Meta(TransientModel.Meta):
        app_label = 'base_sparse_field'
        db_table = 'sparse_fields_test'
        verbose_name = 'Prueba de campos dispersos'
        verbose_name_plural = 'Pruebas de campos dispersos'

    def __str__(self):
        return f'sparse_fields.test #{self.pk}'
