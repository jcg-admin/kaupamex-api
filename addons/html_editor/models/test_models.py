"""Modelos de prueba del conversor — un campo por tipo que ``from_html`` cubre.

Adaptación de ``odoo19c: addons/html_editor/models/test_models.py``
(36 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**2 clases en la fuente, 2 portadas, 0 ausentes.** ``Html_EditorConverterTest``
con sus once campos y ``Html_EditorConverterTestSub`` con el suyo.

Por qué un modelo de prueba vive en ``models/`` y no en ``tests/``
==================================================================

Porque tiene tabla. Los conversores de ``ir_qweb_fields.py`` traducen HTML
editado **de vuelta** al valor de un campo (``from_html``), y cada tipo tiene
su propia regla — el entero quita el separador de millar, la fecha se parsea
con el formato del idioma, el *many2one* escribe la relación. Probar eso exige
un modelo real con un campo de cada tipo; la fuente lo declara aquí y aquí se
declara, con su ``_name`` y su tabla, para que el sitio del archivo coincida.

Sus dos nombres de clase llevan un guion bajo en medio
(``Html_EditorConverterTest``): es el nombre que la fuente declara y se
conserva verbatim, como el resto de los símbolos de este puerto.

Divergencias declaradas
=======================

- ``numeric = fields.Float(digits=(16, 2))`` → ``models.DecimalField(
  max_digits=16, decimal_places=2)``. ``orm.fields_numeric.Float`` es el
  ``FloatField`` de Django y no admite ``digits``; el par ``(16, 2)`` de la
  fuente es exactamente ``(max_digits, decimal_places)``, así que la precisión
  se conserva en la columna en vez de perderse en un binario de doble
  precisión. Es lo que este campo existe para ejercitar.
- ``many2one`` va en la **forma C** de ADR-029 (#141): símbolo verbatim de la
  referencia más ``db_column`` explícito. El nombre no lleva sufijo ``_id``
  porque la fuente no lo lleva, y el gate ``scripts/check_fk_naming.py``
  consulta la contraparte antes que el sufijo justamente para ese caso.
- ``fields.Selection`` de este árbol es un ``CharField`` con ``choices``, por
  lo que las etiquetas van en la tupla y el ancho se declara con
  ``max_length``. Los cuatro pares de la fuente se conservan **verbatim**,
  incluidos su texto en francés y sus apóstrofos: son el dato con el que
  ``IrQwebFieldSelection.from_html`` busca la clave por su etiqueta.
"""
import fields
from addons.base.models import TimeStampedModel
from django.db import models as django_models


class Html_EditorConverterTest(TimeStampedModel):
    """≙ ``Html_EditorConverterTest`` (``odoo19c: :6``)."""

    _name = 'html_editor.converter.test'
    _description = 'Html Editor Converter Test'

    # se desactiva la exportación de traducción para estas brillantes
    # etiquetas y valores de campo
    _translate = False

    char = fields.Char(max_length=255, blank=True, default='')
    integer = fields.Integer(default=0)
    float = fields.Float(default=0.0)
    numeric = django_models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Odoo numeric = fields.Float(digits=(16, 2)).',
    )
    # Forma **C** de ADR-029 (#141): el símbolo es el que la referencia
    # declara —``many2one``, sin sufijo ``_id``, uno de los 128 así en
    # ``odoo19c``— y ``db_column`` lo ata a la columna que la referencia crea.
    # Sin él, Django escribiría ``many2one_id``, que es la forma B.
    many2one = fields.Many2one(
        'html_editor.Html_EditorConverterTestSub',
        on_delete=django_models.SET_NULL, null=True, blank=True,
        related_name='converter_tests', db_column='many2one',
    )
    binary = fields.Binary(attachment=False, null=True, blank=True)
    date = fields.Date(null=True, blank=True)
    datetime = fields.Datetime(null=True, blank=True)
    selection_str = fields.Selection(
        max_length=1,
        choices=[
            ('A', "Qu'il n'est pas arrivé à Toronto"),
            ('B', "Qu'il était supposé arriver à Toronto"),
            ('C', "Qu'est-ce qu'il fout ce maudit pancake, tabernacle ?"),
            ('D', "La réponse D"),
        ],
        null=True, blank=True,
        verbose_name="Lorsqu'un pancake prend l'avion à destination de "
                     "Toronto et qu'il fait une escale technique à St Claude, "
                     "on dit:",
    )
    html = fields.Html(blank=True, default='')
    text = fields.Text(blank=True, default='')

    class Meta:
        db_table = 'html_editor_converter_test'
        verbose_name = 'Html Editor Converter Test'


class Html_EditorConverterTestSub(TimeStampedModel):
    """≙ ``Html_EditorConverterTestSub`` (``odoo19c: :33``)."""

    _name = 'html_editor.converter.test.sub'
    _description = 'Html Editor Converter Subtest'

    name = fields.Char(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'html_editor_converter_test_sub'
        verbose_name = 'Html Editor Converter Subtest'
