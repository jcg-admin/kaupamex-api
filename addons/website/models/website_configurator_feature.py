"""Modelo ``website.configurator.feature`` — una pieza del configurador.

Adaptación de Odoo ``addons/website/models/website_configurator_feature.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3). Mismo nombre de archivo que
la referencia.

Contrato medido de la fuente (AST, 60 líneas): **1 clase, 3 atributos de
clase, 11 campos, 2 métodos**. Cobertura de este porte:

- **Atributos de clase: 3 de 3** — ``_name``, ``_description`` y ``_order``
  se declaran verbatim (``odoo19c: :10-13``), más su forma Django
  (``Meta.db_table`` derivado de ``_name`` con puntos→guiones bajos y
  ``Meta.ordering`` derivado de ``_order``).
- **Campos: 11 de 11 portados**, con dos divergencias declaradas:

  1. ``name`` y ``description`` declaran ``translate=True`` en la fuente
     (``:16-17``); la traducción por campo NO se porta — el almacenamiento
     jsonb de traducciones es la tarea **#333** (misma divergencia que
     declara ``website.py`` para su enumerador de búsqueda). El campo sí.
  2. ``module_id`` (``:22``, Many2one a ``ir.module.module``) se porta como
     FK a ``authz.Module``, que es el equivalente de ``ir.module.module`` en
     este árbol — el mismo mapeo que ``website.py:560`` usa para
     ``theme_id`` ("ir.module.module, que aquí es authz.Module").

- **Métodos: 2 de 2 portados**:

  1. ``_check_module_xor_page_view`` (``:27-30``) — mismo nombre y mismo
     cuerpo; la ``@api.constrains`` de la fuente se conecta vía ``clean()``,
     el patrón de ``website_menu.py``.
  2. ``_process_svg`` (``:32-59``) — staticmethod, lógica de reemplazo
     verbatim. Divergencia de mecanismo declarada: ``tools.file_open`` no
     está portado en este árbol (0 hits de ``def file_open`` en ``src/``);
     el SVG del tema se resuelve con ``pathlib`` sobre las raíces de addons
     (``addons/`` y ``src/addons/``), con un guard de nombre simple que
     replica el confinamiento a los addons paths que ``file_open`` impone.
     Sin temas en el árbol (0 directorios ``theme_*`` en ``addons/``), la
     rama ``FileNotFoundError → False`` de la fuente es la que aplica.

Nota colateral medida en la fuente: su ``import re`` (``:3``) no se usa en
ninguna de sus 60 líneas — aquí ``re`` sí se usa (guard del nombre de tema).
"""
import re
from pathlib import Path

from django.db import models

from addons.base.models import TimeStampedModel
from exceptions import ValidationError
from tools.translate import _

# Raíces donde puede vivir un addon de tema: la carpeta de este addon y
# ``src/addons``. Sustituyen al catálogo de addons paths que la referencia
# consulta vía ``tools.file_open``.
_ADDONS_DIR = Path(__file__).resolve().parents[2]
_ADDON_ROOTS = (_ADDONS_DIR, _ADDONS_DIR.parent / 'src' / 'addons')

# Un nombre de tema es un identificador simple. Es el confinamiento que
# ``file_open`` da gratis en la referencia: sin él, un ``theme`` con ``../``
# leería fuera de las raíces de addons.
_THEME_NAME_RE = re.compile(r'^[a-z0-9_]+$', re.IGNORECASE)


class WebsiteConfiguratorFeature(TimeStampedModel):
    """Una feature ofrecida por el configurador de sitios.

    Cada registro es o bien una página que el configurador crea (lleva
    ``page_view``) o bien un módulo que instala/activa (lleva ``module``) —
    exactamente uno de los dos, y lo valida
    ``_check_module_xor_page_view``.
    """

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: addons/website/models/website_configurator_feature.py:10-13``),
    # verbatim.
    _name = 'website.configurator.feature'
    _description = 'Website Configurator Feature'
    _order = 'sequence'

    sequence = models.IntegerField(
        default=0, verbose_name='Secuencia',
        help_text='Odoo sequence (Integer sin default explícito: la '
                  'referencia lee 0 cuando no está fijado).',
    )
    name = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nombre',
        help_text='Odoo name (translate=True; la traducción por campo llega '
                  'con #333).',
    )
    description = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descripción',
        help_text='Odoo description (translate=True; la traducción por campo '
                  'llega con #333).',
    )
    icon = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Icono',
        help_text='Odoo icon.',
    )
    iap_page_code = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Código de página IAP',
        help_text='Odoo iap_page_code: "Page code used to tell IAP '
                  'website_service for which page a snippet list should be '
                  'generated".',
    )
    website_config_preselection = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Preselección por tipo de sitio',
        help_text='Odoo website_config_preselection: "Comma-separated list '
                  'of website type/purpose for which this feature should be '
                  'pre-selected".',
    )
    page_view = models.ForeignKey(
        'base.IrUiView', on_delete=models.CASCADE, null=True, blank=True,
        related_name='configurator_features', verbose_name='Vista de página',
        help_text='Odoo page_view_id (ondelete=cascade). La vista plantilla '
                  'de la página que la feature crea.',
    )
    module = models.ForeignKey(
        'authz.Module', on_delete=models.CASCADE, null=True, blank=True,
        related_name='configurator_features', verbose_name='Módulo',
        help_text='Odoo module_id (ondelete=cascade, Many2one a '
                  'ir.module.module — aquí authz.Module, el mismo mapeo que '
                  'theme_id en website.py). El módulo que la feature '
                  'instala/activa.',
    )
    feature_url = models.CharField(
        max_length=255, blank=True, default='', verbose_name='URL',
        help_text='Odoo feature_url.',
    )
    menu_sequence = models.IntegerField(
        default=0, verbose_name='Secuencia de menú',
        help_text='Odoo menu_sequence: "If set, a website menu will be '
                  'created for the feature." Cero = no fijado, la misma '
                  'semántica de truthiness de la referencia.',
    )
    menu_company = models.BooleanField(
        default=False, verbose_name='Bajo el menú Company',
        help_text='Odoo menu_company: "If set, add the menu as a second '
                  'level menu, as a child of \'Company\' menu."',
    )

    class Meta:
        db_table = 'website_configurator_feature'
        # ≙ ``_order = 'sequence'`` (``odoo19c: :13``).
        ordering = ['sequence']
        verbose_name = 'Feature del configurador de sitios'
        verbose_name_plural = 'Features del configurador de sitios'

    def __str__(self):
        return self.name

    # ── Restricciones ────────────────────────────────────────────────────────

    def _check_module_xor_page_view(self):
        """≙ ``_check_module_xor_page_view`` (``odoo19c: :27-30``).

        Exactamente uno de ``page_view``/``module`` debe estar fijado. El
        cuerpo lee ``module_id``/``page_view_id`` — los attnames que Django
        expone para las FK — así que la comparación es la de la fuente,
        carácter por carácter.
        """
        if bool(self.module_id) == bool(self.page_view_id):
            raise ValidationError(_(
                "One and only one of the two fields 'page_view_id' and "
                "'module_id' should be set"))

    def clean(self):
        """Puerta de la ``@api.constrains`` de la fuente.

        Django concentra la validación de instancia en ``clean()``; el
        ``_check_module_xor_page_view`` conserva su nombre y su cuerpo, y
        aquí se invoca — mismo patrón que ``website_menu.py``.
        """
        super().clean()
        self._check_module_xor_page_view()

    # ── SVG del tema ─────────────────────────────────────────────────────────

    @staticmethod
    def _process_svg(theme, colors, image_mapping):
        """≙ ``_process_svg`` (``odoo19c: :32-59``).

        El SVG de la miniatura del tema, con los colores y las imágenes por
        defecto sustituidos por los elegidos. ``False`` si el tema no tiene
        SVG — la rama ``FileNotFoundError`` de la fuente.

        Divergencia de mecanismo declarada en el docstring del módulo: la
        fuente lee con ``tools.file_open`` (no portado); aquí el archivo
        ``<theme>/static/description/<theme>.svg`` se resuelve con
        ``pathlib`` sobre las raíces de addons, y el guard de nombre simple
        reemplaza el confinamiento que ``file_open`` impone.
        """
        if not theme or not _THEME_NAME_RE.match(theme):
            return False
        svg = None
        for root in _ADDON_ROOTS:
            candidate = root / theme / 'static' / 'description' / f'{theme}.svg'
            if candidate.is_file():
                svg = candidate.read_text()
                break
        if svg is None:
            return False

        default_colors = {
            'color1': '#3AADAA',
            'color2': '#7C6576',
            'color3': '#F6F6F6',
            'color4': '#FFFFFF',
            'color5': '#383E45',
            'menu': '#MENU_COLOR',
            'footer': '#FOOTER_COLOR',
        }
        color_mapping = {
            default_colors[color_key]: color_value
            for color_key, color_value in colors.items()
            if color_key in default_colors
        }

        # Sustituye los colores por defecto por los elegidos.
        for default_color, chosen_color in color_mapping.items():
            svg = svg.replace(default_color, chosen_color)

        # Sustituye las imágenes por defecto por las de la industria.
        for default_img, new_img in image_mapping.items():
            svg = svg.replace(default_img, new_img)
        return svg
