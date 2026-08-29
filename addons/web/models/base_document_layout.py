"""``base.document.layout`` — asistente de papelería y colores del membrete.

Adaptación de Odoo ``odoo19c: addons/web/models/base_document_layout.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Completa el addon ``web`` contra H-API-369 /
DEC-FW-04 (junto con ``models.py``, que ya cubría ``lazymapping``/``Base``/
``ResCompany``/``RecordSnapshot`` de la referencia).

Re-auditado 2026-08-07T13:54:17Z contra H-API-378 — el docstring anterior
declaraba "10 portados / 7 ausentes" por *correspondencia funcional*, pero
los nombres reales no coincidían con la referencia (DEC-FW-04 exige
identificador = nombre de la referencia). El instrumento mecánico
(``scripts/pendientes_cascara.py web``, por AST y nombre exacto — no
substring) medía **2 portados de 18** porque sólo
``extract_image_primary_secondary_colors`` y la clase coincidían de nombre.
Esta pasada corrige la premisa: **renombra 9 métodos** al nombre exacto de
la referencia (comportamiento sin cambios, sólo el identificador) y deja
**7 ausentes**, cada uno re-verificado hoy — no heredado del docstring
anterior (regla ``porte-completo-no-parcial.md``, "la declaración de
ausencias no obliga a quien la lee después").

``TransientModel`` → clase con classmethods, no tabla
=======================================================

Mismo patrón ya fijado por ``account_debit_note.AccountDebitNoteWizard`` y
``ir_profile.BaseEnableProfilingWizard`` (ver sus docstrings): la referencia
es un ``models.TransientModel`` cuyos ~20 campos son en su enorme mayoría
``related='company_id.<campo>'`` — el formulario no tiene estado propio,
sólo proxea y edita ``res.company``. Declarar esos campos aquí duplicaría
columnas que ya existen en ``res_company.py``; se portan como classmethods
que reciben la ``ResCompany`` (o los valores sueltos) por parámetro.

Medición por AST (``python3 scripts/pendientes_cascara.py web``, nombre
exacto — no substring, ver H-API-373): la referencia declara **18**
símbolos (1 clase + 17 defs). **11 portados** (2 ya coincidían de nombre +
9 renombrados en esta pasada), **7 declarados ausentes** con razón
re-medida hoy. No hay recorte silencioso.

Portados (11)
=============

``class BaseDocumentLayout`` (mismo nombre) ·
``extract_image_primary_secondary_colors`` (mismo nombre, sin cambios) ·
``_default_report_footer`` (renombrado de ``default_report_footer``) ·
``_default_company_details`` (renombrado de ``default_company_details`` —
usa :meth:`prepare_display_address`, construida aquí, ver abajo) ·
``_clean_address_format`` (renombrado de ``clean_address_format``) ·
``_compute_custom_colors`` (renombrado de ``compute_custom_colors``) ·
``_compute_logo_colors`` (renombrado de ``compute_logo_colors``, parcial,
ver abajo) · ``_onchange_company_id`` (renombrado de
``defaults_from_company``, parcial, ver abajo) · ``_onchange_custom_colors``
(renombrado de ``onchange_custom_colors``) · ``_onchange_logo`` (renombrado
de ``onchange_logo``) · ``_compute_empty_company_details`` (renombrado de
``is_company_details_empty``).

``_prepare_display_address`` no existe en ``res_partner.py`` — se construye
aquí en vez de excusarse (``porte-completo-no-parcial.md``, regla #7): el
material ya existe (``res.country.address_format`` — ``res_country.py`` —
más ``ResPartner.commercial_company_name`` y los seis campos de dirección),
sólo faltaba la función que los combina. Queda en este archivo porque su
único consumidor sigue siendo este wizard; si un segundo consumidor
aparece, se sube a ``res_partner.py`` (mismo criterio de
``referencia-odoo-gobierna-las-decisiones.md`` sobre medir antes de
suponer consumidor único). No cuenta contra la medición de este archivo:
no es un símbolo de ``base_document_layout.py`` en la referencia.

``_onchange_company_id`` no porta la resolución de ``report_layout_id``
(bloque ``wizard.env["report.layout"].search(...)`` sobre
``external_report_layout_id``): re-verificado hoy en
``src/addons/base/models/res_company.py:78-85`` — ese campo **sigue** sin
columna ("el campo sigue sin columna aquí: añadir la FK migra esta tabla y
va en su propio pase, igual que ``ir_filters.action_id``"), y esta pasada
tiene prohibido generar migraciones (regla dura del encargo). No hay
onchange que portar sobre un campo que no existe. El resto del método
(logo, membrete, detalles, tipografía, colores, formato de papel) sí se
porta completo.

Ausentes (7) — re-verificados hoy, con razón, no con silencio
=================================================================

**Cadena completa de previsualización (5 métodos): ``_compute_preview``,
``_get_preview_template``, ``_get_render_information``, ``_get_asset_style``,
``_get_css_for_preview``.** Dependen de qweb (``ir.qweb._render``) y del
motor de *assets* de Odoo (``ScssStylesheetAsset``) para compilar SCSS → CSS
y renderizar la plantilla ``web.report_invoice_wizard_preview`` dentro de un
``<iframe>``. No es un hueco del ORM que se pueda construir con
``SQL()``/``Query`` (regla dura #7 del encargo): es un motor de plantillas
+ compilador SCSS server-side completo, sin ningún consumidor — este
proyecto compila los estáticos con Webpack en build-time
(``ui: webpack.config.js``, DEC-03/``ui-adaptacion-nativa``) y una UI React
que compondría su propio preview desde los valores ya portados (colores,
logo, tipografía) en vez de recibir un HTML server-rendered. Construir el
motor qweb+SCSS aquí sería instalar una dependencia nueva
(``libsass``/equivalente, ausente de ``pyproject.toml``) para un
consumidor que no existe — divergencia de mecanismo declarada, no pereza.

**``_onchange_report_layout_id`` (1 método).** Depende de
``external_report_layout_id``, re-verificado ausente hoy en
``res_company.py:78-85`` (ver arriba) — no hay campo que sincronizar, y
añadirlo exige una migración fuera de esta pasada.

**``document_layout_save`` (1 método).** Cuerpo completo de la referencia:
``return self.env.context.get('report_action') or {'type':
'ir.actions.act_window_close'}`` — cero lógica de negocio, 100% formato de
acción del cliente web de Odoo (cerrar el diálogo del wizard). Mismo
precedente que ``account_debit_note.AccountDebitNoteWizard.create_debit``
(ver su docstring): el puerto devuelve el dato, no el envoltorio de acción
Odoo — no hay acción de cliente Odoo que envolver aquí (DEC-03,
``ui-adaptacion-nativa``).

Divergencias declaradas dentro de métodos SÍ portados
========================================================

- **:func:`extract_image_primary_secondary_colors`.** Recibe un archivo
  Django (``ImageFieldFile``), no base64 — ``ResCompany.logo`` ya es un
  ``ImageField`` (``image_mixin.py``), no un ``Binary`` en base64, así que
  el hack de padding base64 de la referencia (``logo += b'===' ...``) no
  aplica. La orientación EXIF se corrige con ``PIL.ImageOps.exif_transpose``
  (utilidad nativa de Pillow) en vez de reimplementar la tabla
  ``EXIF_TAG_ORIENTATION_TO_TRANSPOSE_METHODS`` de la referencia — mismo
  resultado observable, instrumento distinto de la misma librería ya
  declarada en ``pyproject.toml``. ``average_dominant_color``/
  ``get_lightness``/``get_saturation``/``rgb_to_hex`` se portan verbatim
  como funciones de módulo (``tools/image.py`` no existe en este árbol;
  único consumidor, no se crea un paquete nuevo para tres funciones).
- **:meth:`_compute_logo_colors`.** No replica el context switch
  ``bin_size`` de la fuente (``wizard.with_context(bin_size=False)``): es
  una optimización del ORM de Odoo para no traer el binario completo cuando
  sólo se pide su tamaño — ``ImageField`` de Django no tiene ese modo
  perezoso, así que no hay nada que conmutar.
- **:meth:`_onchange_company_id`.** La fuente compara
  ``isinstance(company.report_footer, str)``/``company_details`` para
  decidir si el valor de la compañía ya fue fijado por un humano: en Odoo un
  ``Html`` vacío es ``False``, no ``''``. Aquí ``fields.Html`` (Django) nunca
  devuelve ``False`` — vacío es ``''`` — así que el ``isinstance`` sería
  siempre verdadero y la rama quedaría muerta. Se sustituye por un chequeo
  de *truthiness* (``company.report_footer or _default_report_footer(...)``),
  que sí distingue "compañía sin membrete todavía" de "compañía con membrete
  vacío a propósito" — la distinción que la fuente perseguía.
- **:meth:`_default_company_details` / :meth:`_compute_empty_company_details`.**
  Usan un ``html2plaintext`` **acotado** (:func:`_html_has_visible_text`):
  sólo lo necesario para el chequeo booleano "¿queda texto visible?"
  (``strip_tags`` + colapso de espacios), no el conversor completo de la
  fuente (numeración de referencias de links/imágenes, negritas →
  ``*texto*``, tablas → saltos de línea). El conversor completo pertenece a
  ``tools/mail.py`` (aún no portado en este árbol) — construirlo entero
  excede el archivo que se está completando aquí.
"""
from collections import defaultdict
from math import ceil

from django.utils.html import strip_tags
from PIL import Image, ImageOps

from addons.base.models.ir_field_converters import nl2br
from addons.base.models.res_country import DEFAULT_ADDRESS_FORMAT
from orm.models_transient import TransientModel

#: Colores por defecto cuando ni la compañía ni el logo aportan uno —
#: ≙ referencia ``DEFAULT_PRIMARY``/``DEFAULT_SECONDARY``.
DEFAULT_PRIMARY_COLOR = '#000000'
DEFAULT_SECONDARY_COLOR = '#000000'

#: Parámetros de :func:`_average_dominant_color`/
#: :meth:`BaseDocumentLayout.extract_image_primary_secondary_colors` —
#: verbatim de la referencia.
DEFAULT_WHITE_THRESHOLD = 225
DEFAULT_MITIGATE = 175
DEFAULT_MAX_MARGIN = 140


def _average_dominant_color(colors, mitigate=DEFAULT_MITIGATE, max_margin=DEFAULT_MAX_MARGIN):
    """≙ referencia ``tools.image.average_dominant_color``.

    ``tools/image.py`` no existe en este árbol — se porta verbatim como
    función de módulo; único consumidor:
    :meth:`BaseDocumentLayout.extract_image_primary_secondary_colors`.
    """
    colors = list(colors)
    dominant_color = max(colors)
    dominant_rgb = dominant_color[1][:3]
    dominant_set = [dominant_color]
    remaining = []

    total_count = sum(col[0] for col in colors)
    margins = [max_margin * (1 - dominant_color[0] / total_count)] * 3

    colors.remove(dominant_color)

    for color in colors:
        rgb = color[1]
        if (dominant_rgb[0] - margins[0] < rgb[0] < dominant_rgb[0] + margins[0] and
                dominant_rgb[1] - margins[1] < rgb[1] < dominant_rgb[1] + margins[1] and
                dominant_rgb[2] - margins[2] < rgb[2] < dominant_rgb[2] + margins[2]):
            dominant_set.append(color)
        else:
            remaining.append(color)

    dominant_avg = []
    for band in range(3):
        avg = total = 0
        for color in dominant_set:
            avg += color[0] * color[1][band]
            total += color[0]
        dominant_avg.append(int(avg / total))

    brightest = max(dominant_avg)
    final_dominant = []
    for value in dominant_avg:
        scaled = value / (brightest / mitigate) if brightest > mitigate else value
        final_dominant.append(int(scaled))

    return tuple(final_dominant), remaining


def _get_lightness(rgb):
    """≙ referencia ``tools.image.get_lightness`` — luminosidad HSL."""
    return (max(rgb) + min(rgb)) / 2 / 255


def _get_saturation(rgb):
    """≙ referencia ``tools.image.get_saturation`` — saturación HSL."""
    c_max = max(rgb) / 255
    c_min = min(rgb) / 255
    delta = c_max - c_min
    return 0 if delta == 0 else delta / (1 - abs(c_max + c_min - 1))


def _rgb_to_hex(rgb):
    """≙ referencia ``tools.image.rgb_to_hex``."""
    return '#' + ''.join(hex(channel).split('x')[-1].zfill(2) for channel in rgb)


def _html_has_visible_text(html):
    """Chequeo booleano mínimo — no el ``html2plaintext`` completo de la
    referencia. Ver "Divergencias declaradas" en el docstring del módulo.
    """
    return bool(strip_tags(html or '').strip())


class BaseDocumentLayout(TransientModel):
    """Asistente de papelería y membrete (``base.document.layout``).

    Ver el docstring del módulo: los ~20 campos ``related`` de la
    referencia no se declaran aquí (duplicarían columnas de
    ``res_company.py``); las classmethods reciben la ``ResCompany`` — o sus
    valores sueltos — como parámetro, igual que
    ``account_debit_note.AccountDebitNote``.
    """

    class Meta:
        abstract = True
        managed = False

    # --- Defaults del formulario ------------------------------------------

    @staticmethod
    def _default_report_footer(company):
        """≙ referencia ``_default_report_footer`` (mismo nombre).

        La fuente une con ``Markup(' ')`` (HTML-safe); aquí ``report_footer``
        es un ``Html`` de texto plano sin marcado propio, así que un
        ``' '.join`` produce el mismo resultado observable.
        """
        footer_fields = [
            value for value in (company.phone, company.email, company.website, company.vat)
            if isinstance(value, str) and value
        ]
        return ' '.join(footer_fields)

    @staticmethod
    def _clean_address_format(address_format, company_data):
        """≙ referencia ``_clean_address_format`` (mismo nombre) — quita las
        líneas de la plantilla cuyo dato vino vacío."""
        missing_company_data = [key for key, value in company_data.items() if not value]
        for key in missing_company_data:
            marker = '%%(%s)s\n' % key
            if key in address_format:
                address_format = address_format.replace(marker, '')
        return address_format

    @staticmethod
    def prepare_display_address(partner, without_company=False):
        """``_prepare_display_address`` de ``res.partner`` — no existe ahí
        aún, se construye aquí. Ver "Portados" en el docstring del módulo.

        ≙ referencia ``odoo19c: base/models/res_partner.py:1177-1194``.
        """
        country = partner.country
        state = partner.state
        args = defaultdict(str, {
            'state_code': getattr(state, 'code', '') or '',
            'state_name': getattr(state, 'name', '') or '',
            'country_code': getattr(country, 'code', '') or '',
            'country_name': getattr(country, 'name', '') or '',
            'company_name': partner.commercial_company_name or '',
        })
        for field_name in ('street', 'street2', 'zip', 'city'):
            args[field_name] = getattr(partner, field_name, '') or ''

        address_format = (getattr(country, 'address_format', '') if country else '') \
            or DEFAULT_ADDRESS_FORMAT
        if without_company:
            args['company_name'] = ''
        elif partner.commercial_company_name:
            address_format = '%(company_name)s\n' + address_format
        return address_format, args

    @classmethod
    def _default_company_details(cls, company):
        """≙ referencia ``_default_company_details`` (mismo nombre)."""
        partner = company.partner
        address_format, company_data = cls.prepare_display_address(partner)
        address_format = cls._clean_address_format(address_format, company_data)
        # company_name puede seguir ausente del formato preparado si la
        # dirección no tenía entidad comercial propia — el mismo caso que
        # comenta la referencia.
        if 'company_name' not in address_format:
            address_format = '%(company_name)s\n' + address_format
            company_data['company_name'] = company_data['company_name'] or company.name
        return nl2br(address_format) % company_data

    # --- Colores del membrete ------------------------------------------

    @staticmethod
    def _compute_custom_colors(logo, primary_color, secondary_color,
                                logo_primary_color, logo_secondary_color):
        """≙ referencia ``_compute_custom_colors`` (mismo nombre) — ¿los
        colores del formulario difieren de los que da el logo?"""
        logo_primary = (logo_primary_color or '').lower()
        logo_secondary = (logo_secondary_color or '').lower()
        return bool(
            logo and primary_color and secondary_color
            and not (
                primary_color.lower() == logo_primary
                and secondary_color.lower() == logo_secondary
            )
        )

    @classmethod
    def _compute_logo_colors(cls, logo):
        """≙ referencia ``_compute_logo_colors`` (mismo nombre; sin el
        context switch ``bin_size`` — ver "Divergencias declaradas" en el
        docstring del módulo)."""
        return cls.extract_image_primary_secondary_colors(logo)

    @classmethod
    def _onchange_company_id(cls, company):
        """≙ referencia ``_onchange_company_id`` (mismo nombre) — valores
        por defecto del formulario al elegir/cambiar la compañía. Parcial:
        ver "Portados" en el docstring del módulo (``report_layout_id`` no
        se sincroniza).
        """
        logo = company.logo
        report_footer = company.report_footer or cls._default_report_footer(company)
        company_details = company.company_details or cls._default_company_details(company)

        logo_primary_color, logo_secondary_color = cls._compute_logo_colors(logo)

        primary_color = company.primary_color or logo_primary_color or DEFAULT_PRIMARY_COLOR
        secondary_color = company.secondary_color or logo_secondary_color or DEFAULT_SECONDARY_COLOR

        return {
            'logo': logo,
            'report_header': company.report_header,
            'report_footer': report_footer,
            'company_details': company_details,
            'paperformat': company.paperformat,
            'font': company.font,
            'primary_color': primary_color,
            'secondary_color': secondary_color,
            'logo_primary_color': logo_primary_color,
            'logo_secondary_color': logo_secondary_color,
        }

    @staticmethod
    def _onchange_custom_colors(logo, custom_colors, logo_primary_color, logo_secondary_color):
        """≙ referencia ``_onchange_custom_colors`` (mismo nombre).

        Devuelve el dict de campos a actualizar — vacío si no aplica. El
        llamador (la vista DRF) decide cómo fusionarlo con el estado del
        formulario, igual que ``account_debit_note`` devuelve valores en
        vez de mutar un recordset.
        """
        if logo and not custom_colors:
            return {
                'primary_color': logo_primary_color or DEFAULT_PRIMARY_COLOR,
                'secondary_color': logo_secondary_color or DEFAULT_SECONDARY_COLOR,
            }
        return {}

    @classmethod
    def _onchange_logo(cls, new_logo, company_logo, company_primary_color, company_secondary_color):
        """≙ referencia ``_onchange_logo`` (mismo nombre).

        Devuelve el dict de campos a actualizar — vacío si no aplica (mismo
        criterio de retorno que :meth:`_onchange_custom_colors`).
        """
        if new_logo == company_logo and company_primary_color and company_secondary_color:
            return {}
        logo_primary_color, logo_secondary_color = cls.extract_image_primary_secondary_colors(new_logo)
        changes = {}
        if logo_primary_color:
            changes['primary_color'] = logo_primary_color
        if logo_secondary_color:
            changes['secondary_color'] = logo_secondary_color
        return changes

    @staticmethod
    def extract_image_primary_secondary_colors(logo, white_threshold=DEFAULT_WHITE_THRESHOLD,
                                                 mitigate=DEFAULT_MITIGATE):
        """≙ referencia ``extract_image_primary_secondary_colors``.

        Identifica los colores dominantes primario y secundario de
        ``logo``. Ver "Divergencias declaradas" en el docstring del módulo
        (archivo Django en vez de base64; ``ImageOps.exif_transpose`` en vez
        de la tabla de transposición de la referencia).

        :param logo: archivo del logo (``ImageFieldFile`` o compatible).
        :param white_threshold: valor máximo de banda para considerar un
            color "blanco" y descartarlo.
        :param mitigate: techo de banda del promedio final.
        :return: tupla de dos valores hex (primario, secundario), o
            ``(False, False)`` si no hay logo o no se pudo decodificar.
        """
        if not logo:
            return False, False
        try:
            logo.open()
            image = ImageOps.exif_transpose(Image.open(logo))
        except Exception:
            return False, False

        base_w, base_h = image.size
        if not base_h:
            return False, False
        w = ceil(50 * base_w / base_h)
        h = 50

        image_converted = image.convert('RGBA')
        image_resized = image_converted.resize((w, h), resample=Image.NEAREST)

        colors = []
        for color in image_resized.getcolors(w * h):
            red, green, blue, alpha = color[1]
            if not (red > white_threshold and green > white_threshold
                    and blue > white_threshold) and alpha > 0:
                colors.append(color)

        if not colors:  # puede pasar cuando la imagen entera es blanca
            return False, False
        primary, remaining = _average_dominant_color(colors, mitigate=mitigate)
        secondary = _average_dominant_color(remaining, mitigate=mitigate)[0] if remaining else primary

        # Si ambos colores tienen luminosidad similar, el más saturado pasa
        # a primario; si la diferencia de luminosidad es grande, el más
        # brillante pasa a primario.
        l_primary = _get_lightness(primary)
        l_secondary = _get_lightness(secondary)
        if (l_primary < 0.2 and l_secondary < 0.2) or (l_primary >= 0.2 and l_secondary >= 0.2):
            s_primary = _get_saturation(primary)
            s_secondary = _get_saturation(secondary)
            if s_primary < s_secondary:
                primary, secondary = secondary, primary
        elif l_secondary > l_primary:
            primary, secondary = secondary, primary

        return _rgb_to_hex(primary), _rgb_to_hex(secondary)

    # --- Detalles de la compañía -----------------------------------------

    @staticmethod
    def _compute_empty_company_details(company_details):
        """≙ referencia ``_compute_empty_company_details`` (mismo nombre).
        Ver "Divergencias declaradas" en el docstring del módulo."""
        return not _html_has_visible_text(company_details or '')
