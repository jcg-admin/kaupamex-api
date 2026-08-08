"""``report.paperformat`` — configuración de formato de papel para impresión.

Adaptación fiel de ``odoo/addons/base/models/report_paperformat.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 213 líneas). Define el tamaño de
página, los márgenes y el DPI con que se imprime un reporte.

``PAPER_SIZES`` se copia **verbatim**: 31 entradas, extraídas de la fuente con
``ast.literal_eval`` en vez de a mano, precisamente para que ni una medida ni
una descripción se transcriban mal. La lista viene del enum ``QPrinter::
PaperSize`` de Qt, que la referencia cita en su comentario de cabecera —
recortarla obligaría a re-etiquetar tamaños el día que alguien elija uno
"raro", que es lo que la fidelidad evita.

Procedencia de los campos — todos se portan:

- ``name`` (required) · ``default`` · ``format`` (Selection sobre las 31
  claves, default ``A4``) · los cuatro márgenes (``Float``, defaults 40/20/7/7)
  · ``page_height`` / ``page_width`` (``Integer``) · ``orientation``
  (Landscape/Portrait, default Landscape) · ``header_line`` ·
  ``header_spacing`` (default 35) · ``disable_shrinking`` · ``dpi``
  (required, default 90) · ``css_margins``.
- ``print_page_width`` / ``print_page_height`` son ``compute`` **sin**
  ``store`` en la referencia → aquí son propiedades derivadas, no columnas.
  Preservan el detalle que importa: en Landscape **se intercambian** ancho y
  alto (comentario ``# swap sizes`` de la fuente).
- ``_check_format_or_page`` (``@api.constrains``) → ``clean()`` de Django, que
  es donde vive la validación de modelo. Mismo mensaje que allá.

``report_ids`` — cerrado, tal como estaba fechado
=================================================

``report_ids`` es el ``One2many`` a ``ir.actions.report`` por su
``paperformat_id``. Este archivo declaró dos veces que llegaría solo, y así
fue:

1. Primera redacción: *"0 clases ``IrActions``"* — cierto entonces.
2. Tras portar ``ir_actions.py``: **9** clases, pero
   ``grep -rn "^class IrActionsReport" src/`` → **0**, porque
   ``ir.actions.report`` vive en su propio archivo de la referencia.
3. **Ahora** (porte de ``ir_actions_report.py``):
   ``grep -rn "^class IrActionsReport\b" src/`` → **1** clase. [PROVEN]

Y se cumplió la predicción literal —*"su FK declarará
``related_name='report_ids'`` y la relación aparece de este lado sola, sin
tocar este archivo"*—: el ``paperformat`` de ``ir_actions_report.py`` lleva
ese ``related_name``, y **este archivo no necesitó una sola línea nueva** para
ganar la relación. Sólo se corrige la medición, que es lo que envejece.

Es el tercer hueco de esta iniciativa que se cierra **porque estaba anotado
con su destino**, tras H-API-142 y los dos campos de ``ir_filters``.

``page_height``/``page_width`` llevan ``default=False`` en la referencia — un
booleano donde el tipo es entero, quirk de su ORM (falsy ≡ "sin valor"). Aquí
son ``null=True`` con ``default=None``, que es la forma correcta de decir lo
mismo en Django sin arrastrar el quirk a la columna.
"""
import fields
import models
from django.core.exceptions import ValidationError

# Ver el enum QPrinter::PaperSize de Qt, que la referencia cita:
# http://doc.qt.io/archives/qt-4.8/qprinter.html#PaperSize-enum
PAPER_SIZES = [
    {
        'key': 'A0',
        'description': 'A0  5   841 x 1189 mm',
        'height': 1189.0,
        'width': 841.0,
    },
    {
        'key': 'A1',
        'description': 'A1  6   594 x 841 mm',
        'height': 841.0,
        'width': 594.0,
    },
    {
        'key': 'A2',
        'description': 'A2  7   420 x 594 mm',
        'height': 594.0,
        'width': 420.0,
    },
    {
        'key': 'A3',
        'description': 'A3  8   297 x 420 mm',
        'height': 420.0,
        'width': 297.0,
    },
    {
        'key': 'A4',
        'description': 'A4  0   210 x 297 mm, 8.26 x 11.69 inches',
        'height': 297.0,
        'width': 210.0,
    },
    {
        'key': 'A5',
        'description': 'A5  9   148 x 210 mm',
        'height': 210.0,
        'width': 148.0,
    },
    {
        'key': 'A6',
        'description': 'A6  10  105 x 148 mm',
        'height': 148.0,
        'width': 105.0,
    },
    {
        'key': 'A7',
        'description': 'A7  11  74 x 105 mm',
        'height': 105.0,
        'width': 74.0,
    },
    {
        'key': 'A8',
        'description': 'A8  12  52 x 74 mm',
        'height': 74.0,
        'width': 52.0,
    },
    {
        'key': 'A9',
        'description': 'A9  13  37 x 52 mm',
        'height': 52.0,
        'width': 37.0,
    },
    {
        'key': 'B0',
        'description': 'B0  14  1000 x 1414 mm',
        'height': 1414.0,
        'width': 1000.0,
    },
    {
        'key': 'B1',
        'description': 'B1  15  707 x 1000 mm',
        'height': 1000.0,
        'width': 707.0,
    },
    {
        'key': 'B2',
        'description': 'B2  17  500 x 707 mm',
        'height': 707.0,
        'width': 500.0,
    },
    {
        'key': 'B3',
        'description': 'B3  18  353 x 500 mm',
        'height': 500.0,
        'width': 353.0,
    },
    {
        'key': 'B4',
        'description': 'B4  19  250 x 353 mm',
        'height': 353.0,
        'width': 250.0,
    },
    {
        'key': 'B5',
        'description': 'B5  1   176 x 250 mm, 6.93 x 9.84 inches',
        'height': 250.0,
        'width': 176.0,
    },
    {
        'key': 'B6',
        'description': 'B6  20  125 x 176 mm',
        'height': 176.0,
        'width': 125.0,
    },
    {
        'key': 'B7',
        'description': 'B7  21  88 x 125 mm',
        'height': 125.0,
        'width': 88.0,
    },
    {
        'key': 'B8',
        'description': 'B8  22  62 x 88 mm',
        'height': 88.0,
        'width': 62.0,
    },
    {
        'key': 'B9',
        'description': 'B9  23  33 x 62 mm',
        'height': 62.0,
        'width': 33.0,
    },
    {
        'key': 'B10',
        'description': 'B10    16  31 x 44 mm',
        'height': 44.0,
        'width': 31.0,
    },
    {
        'key': 'C5E',
        'description': 'C5E 24  163 x 229 mm',
        'height': 229.0,
        'width': 163.0,
    },
    {
        'key': 'Comm10E',
        'description': 'Comm10E 25  105 x 241 mm, U.S. Common 10 Envelope',
        'height': 241.0,
        'width': 105.0,
    },
    {
        'key': 'DLE',
        'description': 'DLE 26 110 x 220 mm',
        'height': 220.0,
        'width': 110.0,
    },
    {
        'key': 'Executive',
        'description': 'Executive 4   7.5 x 10 inches, 190.5 x 254 mm',
        'height': 254.0,
        'width': 190.5,
    },
    {
        'key': 'Folio',
        'description': 'Folio 27  210 x 330 mm',
        'height': 330.0,
        'width': 210.0,
    },
    {
        'key': 'Ledger',
        'description': 'Ledger  28  431.8 x 279.4 mm',
        'height': 279.4,
        'width': 431.8,
    },
    {
        'key': 'Legal',
        'description': 'Legal    3   8.5 x 14 inches, 215.9 x 355.6 mm',
        'height': 355.6,
        'width': 215.9,
    },
    {
        'key': 'Letter',
        'description': 'Letter 2 8.5 x 11 inches, 215.9 x 279.4 mm',
        'height': 279.4,
        'width': 215.9,
    },
    {
        'key': 'Tabloid',
        'description': 'Tabloid 29 279.4 x 431.8 mm',
        'height': 431.8,
        'width': 279.4,
    },
    {
        'key': 'custom',
        'description': 'Custom',
    },
]

#: Clave → (ancho, alto) en mm, para la derivación de tamaño de impresión.
_SIZE_BY_KEY = {
    ps['key']: (ps['width'], ps['height'])
    for ps in PAPER_SIZES if 'width' in ps
}

ORIENTATION_LANDSCAPE = 'Landscape'
ORIENTATION_PORTRAIT = 'Portrait'


class ReportPaperformat(models.Model):
    """Configuración de formato de papel (``report.paperformat``)."""

    name = fields.Char(max_length=120, verbose_name='Nombre')
    default = fields.Boolean(
        default=False, verbose_name='¿Formato de papel por defecto?')
    format = fields.Selection(
        max_length=16,
        choices=[(ps['key'], ps['description']) for ps in PAPER_SIZES],
        default='A4', blank=True,
        verbose_name='Tamaño de papel',
        help_text='Seleccione el tamaño de papel adecuado.',
    )
    margin_top = fields.Float(default=40, verbose_name='Margen superior (mm)')
    margin_bottom = fields.Float(default=20, verbose_name='Margen inferior (mm)')
    margin_left = fields.Float(default=7, verbose_name='Margen izquierdo (mm)')
    margin_right = fields.Float(default=7, verbose_name='Margen derecho (mm)')
    # La referencia pone ``default=False`` en estos dos enteros — quirk de su
    # ORM donde falsy ≡ "sin valor". Aquí eso se dice con null.
    page_height = fields.Integer(
        null=True, blank=True, default=None, verbose_name='Alto de página (mm)')
    page_width = fields.Integer(
        null=True, blank=True, default=None, verbose_name='Ancho de página (mm)')
    orientation = fields.Selection(
        max_length=16,
        choices=[
            (ORIENTATION_LANDSCAPE, 'Horizontal'),
            (ORIENTATION_PORTRAIT, 'Vertical'),
        ],
        default=ORIENTATION_LANDSCAPE, verbose_name='Orientación',
    )
    header_line = fields.Boolean(
        default=False, verbose_name='Mostrar línea de encabezado')
    header_spacing = fields.Integer(
        default=35, verbose_name='Espaciado del encabezado')
    disable_shrinking = fields.Boolean(
        default=False, verbose_name='Desactivar el ajuste inteligente')
    dpi = fields.Integer(default=90, verbose_name='DPI de salida')
    css_margins = fields.Boolean(
        default=False, verbose_name='Usar márgenes CSS')

    class Meta:
        db_table = 'report_paperformat'
        ordering = ['name', 'id']
        verbose_name = 'Formato de papel'
        verbose_name_plural = 'Formatos de papel'

    def __str__(self):
        return self.name

    def clean(self):
        """``_check_format_or_page`` — formato o medidas propias, no ambos."""
        super().clean()
        if self.format != 'custom' and (self.page_width or self.page_height):
            raise ValidationError(
                'Puede seleccionar un formato o un ancho/alto de página '
                'específico, pero no ambos.'
            )

    def _print_page_size(self):
        """Ancho y alto reales de impresión — ``_compute_print_page_size``.

        En Landscape se intercambian (``# swap sizes`` de la fuente).
        """
        width = height = 0.0
        if self.format:
            if self.format == 'custom':
                width = self.page_width or 0.0
                height = self.page_height or 0.0
            else:
                width, height = _SIZE_BY_KEY[self.format]
        if self.orientation == ORIENTATION_LANDSCAPE:
            width, height = height, width
        return width, height

    @property
    def print_page_width(self):
        """Ancho de impresión (mm) — derivado, no columna."""
        return self._print_page_size()[0]

    @property
    def print_page_height(self):
        """Alto de impresión (mm) — derivado, no columna."""
        return self._print_page_size()[1]
