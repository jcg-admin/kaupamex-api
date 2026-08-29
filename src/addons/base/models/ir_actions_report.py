"""``ir.actions.report`` — la acción que imprime un reporte.

Adaptación de ``odoo/addons/base/models/ir_actions_report.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1217 líneas). Declara **qué** se
imprime —modelo, plantilla, formato de papel, si se guarda como adjunto— y,
en la referencia, también **cómo**: las otras ~900 líneas son el motor de
render (QWeb → HTML → ``wkhtmltopdf`` → PDF, con fusión de PDFs y códigos de
barras).

Aquí se porta la declaración. El motor no, porque este árbol **ya tiene otro**
y son incompatibles por diseño (ver abajo).

Cierra ``report_paperformat.report_ids``
========================================

``report_paperformat.py`` dejó anotado que su ``One2many`` aparecería solo
cuando este archivo llegara: *"su FK declarará ``related_name='report_ids'``
y la relación aparece de este lado sola, sin tocar este archivo"*. Es
exactamente lo que hace el ``paperformat`` de aquí. El destino estaba fechado
y se cumple sin editar el otro archivo — se corrige su medición en el mismo
commit (regla de H-API-149).

El motor de render: dos sustratos, no uno con hueco
===================================================

Esta divergencia cubre **10 puntos de enganche** que Enterprise 19 usa sobre
este modelo —``_render_qweb_pdf`` (2), ``_render_qweb_html``,
``_get_rendering_context``, ``_get_rendering_context_model``,
``_render_qweb_pdf_prepare_streams``, ``_run_wkhtmltopdf``, ``associated_view``,
``report_action``, ``_get_readable_fields``—: todos son del pipeline
HTML→PDF que aquí no existe. Medido en la tarea #78, :ref:`h-api-819`.

La referencia rinde HTML con QWeb y lo convierte con ``wkhtmltopdf``, un
binario externo cuyo estado (``install`` / ``ok`` / ``upgrade`` / ``workers``
/ ``broken``) el propio modelo consulta.

Este árbol genera PDF con **helpers en C sobre libharu**, invocados por
subprocess desde las vistas — ``tools/pdf/Makefile`` declara ``pdf_receipt``
(UC-PAY-10) y ``pdf_report`` (UC-RPT-04 / UC-REP-05), y ADR-017 razona el
aislamiento de fallos frente a ``mod_wsgi``. Medido:
``grep -rln "reportlab\\|weasyprint\\|wkhtmltopdf\\|FPDF" src/ --include=*.py``
→ **0** archivos. [PROVEN] No hay pipeline HTML→PDF que portar contra, ni
falta: hay uno distinto, decidido y documentado.

Consecuencia para ``report_type``: sus valores son ``pdf`` / ``text``, **no**
``qweb-*``. El string de la referencia codifica dos cosas —el lenguaje de
plantillas y el formato— y en **esta cadena** sólo la segunda es verdad.
Conservarlo verbatim metería el sustrato ajeno dentro de nuestro dato; lo que
se porta es el **rol** del campo (en qué formato sale el documento), que es la
parte abstracta. Ver ``REPORT_TYPE_CHOICES`` para la tabla de correspondencia.

Precisión, porque la versión anterior de este párrafo decía de más: el árbol
**sí tiene** lenguaje de plantillas —el de Django, configurado en
``config/settings/base.py:165``— y **sí tiene** el patrón de plantilla como
dato: ``mail.template.body_html`` guarda el cuerpo con placeholders
``{{ object.campo }}`` y ``MailTemplate.render`` lo interpreta con
``Template(text).render(ctx)`` (``mail/models/mail_template.py:100``). Lo que
no lo usa es **el reporte**: su documento es código (el ``builder`` del
``ReportSpec``). Eso es una elección de esta cadena, no una carencia del
árbol — y como tal se documenta, no se presenta como límite.

Qué NO se porta, con su medición
================================

**Actualizado en el pase del bloque B (tarea #170).** Seis entradas de esta
lista dejaron de ser ciertas: ``associated_view``, ``retrieve_attachment``
completo, ``get_paperformat_by_xmlid``, ``_get_readable_fields``,
``report_action`` y ``_action_configure_external_report_layout`` **están
portados**, con el nombre y la firma de la fuente. Cada uno esperaba un
mecanismo que este pase construyó en vez de declarar como divergencia:

.. list-table::
   :header-rows: 1

   * - Mecanismo que faltaba
     - Dónde vive ahora
   * - evaluador general de expresiones
     - ``tools/safe_eval.py`` — porte completo con validación de opcodes
       (tarea #140)
   * - ``get_base_url``
     - ``orm/models.py`` (``BaseUrlMixin``) más ``adopt_base_url``, que lo
       universaliza como la fuente lo tiene en ``BaseModel``
   * - ``_for_xml_id`` / ``_get_action_dict``
     - ``IrActionsBase``, donde la fuente los declara
   * - ``_is_remote_source`` / ``_migrate_remote_to_local``
     - ``IrAttachment``, donde la fuente los declara

Lo que sigue fuera, y por qué:

- **Todo el motor**: ``_build_wkhtmltopdf_args``, ``_run_wkhtmltopdf``,
  ``_run_wkhtmltoimage``, ``_prepare_html``, ``_render_qweb_pdf``,
  ``_render_qweb_html``, ``_render_qweb_text``, ``_render_template``,
  ``_merge_pdfs``, ``_get_rendering_context``, ``barcode``,
  ``get_available_barcode_masks``, ``get_wkhtmltopdf_state``. Ver arriba: el
  motor es nuestro (helpers libharu, por decreto del ejecutor), no
  wkhtmltopdf. Es el bloque D del porte.
- **``_search_model_id``** — portado en el bloque A con el ``Domain`` de la
  fuente; esta entrada quedó obsoleta y se retira.
- **``external_report_layout_id`` de ``res.company``** — la FK no tiene
  columna todavía. No es una divergencia de este archivo: está declarada
  como pase propio en ``res_company.py``, porque añadirla migra esa tabla.
  ``report_action`` la lee con ``getattr``, y sin ella toma la misma rama que
  la fuente cuando la compañía no tiene plantilla configurada.
"""
import json
import logging
import subprocess
from pathlib import Path

from django.conf import settings

import fields
import models

from addons.base import report_catalog, report_template
from addons.base.models.ir_actions import IrActionsBase
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_model import IrModel
from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from exceptions import ValidationError
from orm import registry
from orm.domains import Domain, to_q
from orm.environments import (get_context, get_current_company, is_system,
                              sudo)
from orm.models import filtered_domain
from requests.exceptions import RequestException
from tools.safe_eval import const_eval, safe_eval, time

_logger = logging.getLogger(__name__)

#: ``report_type`` — **formato de salida** del documento.
#:
#: Dos decisiones distintas, ambas contra la referencia:
#:
#: **1. Sin prefijo, porque el eje que nombra no existe aquí.** ``qweb-pdf``
#: es un par: **lenguaje de plantillas** (``qweb``) + formato (``pdf``). El
#: prefijo identifica *qué intérprete lee la definición del documento*.
#:
#: El mapeo real de las piezas, para no confundirlas:
#:
#: =========================  =======================================
#: Referencia                 Aquí
#: =========================  =======================================
#: plantilla QWeb (XML, dato) ``builder`` (función Python, código)
#: motor QWeb que la lee      — ninguno **en esta cadena** (ver abajo)
#: intermedio: HTML           intermedio: descriptor JSON
#: conversor: wkhtmltopdf     conversor: helper en C (libharu)
#: =========================  =======================================
#:
#: JSON es nuestro **intermedio** —el análogo del HTML—, no el análogo de
#: QWeb. Así que ``json-pdf`` sería un nombre equivocado: pondría el formato
#: del intermedio donde va el intérprete.
#:
#: **La segunda fila dice "en esta cadena", no "en el árbol", y la distinción
#: importa.** El árbol tiene lenguaje de plantillas —el de Django,
#: ``config/settings/base.py:165``— y tiene el patrón completo de plantilla
#: como dato: ``mail.template.body_html`` guarda el cuerpo con placeholders
#: ``{{ object.campo }}`` y ``MailTemplate.render`` lo interpreta
#: (``mail/models/mail_template.py:100``), con la misma sintaxis que el
#: ``inline_template`` de la referencia. El reporte **no lo usa**: su documento
#: es código. Es una elección de esta cadena, no una carencia del árbol.
#:
#: Para el nombre del valor da igual —no hay intérprete **que este campo
#: discrimine**, así que el eje del prefijo no aplica y queda sólo el
#: formato—, pero para la deuda no da igual, y por eso se dice aquí.
#:
#: **La divergencia que esto implica, dicha en voz alta:** la referencia hace
#: del documento un dato a propósito — una plantilla se edita sin tocar
#: Python, y un addon puede extender la de otro por XPath sin bifurcarla.
#: Nuestro builder no da ninguna de las dos cosas: cambiar un documento es
#: cambiar código, y extenderlo desde otro addon exige envolver la función.
#: Es el costo de **no haber conectado** el reporte al motor que el árbol ya
#: tiene — reversible, no estructural.
#:
#: **2. Un solo valor, porque es lo único que este árbol sabe emitir.** El
#: enum lista formatos con renderizador **y con quien los declare**, no el
#: catálogo de la referencia. Medido antes de recortarlo: ``text`` tenía 0
#: addons declarándolo y 0 tests ejercitando su renderizador, y peor —
#: ``ReportSpec`` traía **un** slot ``builder`` con **dos** contratos
#: incompatibles según el tipo (``dict`` para pdf, ``str`` para text) sin
#: nada que lo hiciera cumplir. ``html`` nunca tuvo renderizador siquiera.
#: Los dos estaban por copiar el catálogo ajeno — el mismo defecto que el
#: prefijo, un nivel más abajo (H-API-291).
#:
#: Ninguno de los dos se pierde. Medido en ``odoo19c:`` sobre declaraciones
#: reales —``<field name="report_type">…</field>`` de un registro, no
#: menciones— con ``odoo-tools@622ddc2a``: ``qweb-text`` en **7** reportes
#: (6 ``stock`` + 1 ``mrp``, etiquetas ZPL) y ``qweb-html`` en **1**
#: (``stock``). *Ciega a:* declaraciones en Python en vez de XML, que este
#: patrón no ve; los 6 hits de ``web`` que un grep amplio devuelve son el
#: despachador del framework y tests JS, no declaraciones.
#:
#: El día que se porten, el valor entra **con** su renderizador, su
#: declarante y su test, y el contrato del ``builder`` se separa entonces —
#: que es cuando se sabrá qué forma necesita. Mientras tanto, una fila con
#: ``text`` cae en el contrato de ausencia y devuelve ``None``.
#:
#: Precedente del proyecto para la misma clase de llamada: ``Company`` y no
#: ``Tenant`` (``terminologia-l0-company.md``).
#:
#: Correspondencia para quien compare las dos tablas: ``pdf`` ≙ ``qweb-pdf``.
#: ``qweb-text`` y ``qweb-html`` no tienen análogo **todavía** — no porque
#: sean intraducibles, sino porque nada aquí los emite.
REPORT_TYPE_PDF = 'pdf'
REPORT_TYPE_CHOICES = [
    (REPORT_TYPE_PDF, 'PDF'),
]

#: ``type`` por defecto de esta acción.
ACTION_TYPE = 'ir.actions.report'
#: ``binding_type`` por defecto — aparece como "Imprimir", no como "Acción".
BINDING_TYPE_REPORT = 'report'

#: Despacho del paso 4: ``report_type`` → método que lo rinde.
#:
#: La referencia lo **deriva** del propio valor
#: (``getattr(self, '_render_' + report_type)``, ``:1148``). Aquí el mapeo es
#: explícito: con los valores ya nombrados por formato (ver
#: ``REPORT_TYPE_CHOICES``) la derivación daría ``_render_pdf`` y funcionaría,
#: pero un mapa explícito deja ver de un vistazo **qué formatos se rinden** y
#: cuáles no — que es justamente la información que aquí no es obvia.
#:
#: Hoy el mapa tiene una sola entrada, y esa es la información: **este árbol
#: emite PDF y nada más**. Cualquier otro valor —``text`` de una fila vieja,
#: ``html`` de un addon que lo declare antes de tiempo— cae en el contrato de
#: ausencia y devuelve ``None``, no un error; mismo contrato que ``:1150``.
RENDERER_BY_TYPE = {
    REPORT_TYPE_PDF: '_render_pdf',
}

#: Directorio de los helpers compilados. ``BASE_DIR`` es ``src/``
#: (``config/settings/base.py:6``), así que los binarios que produce
#: ``make pdf`` caen exactamente aquí.
HELPER_DIR = Path(settings.BASE_DIR) / 'tools' / 'pdf'

#: Techo duro para que un helper colgado no bloquee al worker. UC-PAY-10 fija
#: un SLO de P95 < 2 s; 15 s es el failsafe, no el objetivo.
HELPER_TIMEOUT_SECONDS = 15

#: Códigos de salida del contrato de los helpers (cabecera de
#: ``tools/pdf/pdf_report.c``), mapeados a mensaje para que el fallo diga qué
#: pasó en vez de "exit 2".
HELPER_EXIT_MEANING = {
    1: 'descriptor JSON inválido o no parseable',
    2: 'error de libharu al generar el PDF',
    3: 'error de lectura de stdin',
}


class ReportError(Exception):
    """El reporte no pudo generarse."""


class UnknownReport(ReportError):
    """``report_name`` no está declarado por ningún addon instalado."""


class HelperNotBuilt(ReportError):
    """El binario del helper no existe.

    Se distingue del fallo de ejecución a propósito: la causa es de despliegue
    (falta correr ``make pdf``), no del dato ni del código.
    """


class HelperFailed(ReportError):
    """El helper corrió y salió con código != 0, o excedió el timeout."""


def run_helper(helper, descriptor):
    """Ejecuta un helper de ``tools/pdf/`` y devuelve su stdout.

    Función de módulo, no método: espeja ``_run_wkhtmltopdf`` de la referencia,
    que existe **dos veces** — cruda a nivel de módulo (``:41``) y como método
    que arma los argumentos (``:514``). La cruda no necesita el registro, así
    que no lo pide.

    Aislamiento por ``subprocess`` según ADR-017: un fallo nativo de libharu
    mata al hijo, no al worker. El descriptor viaja por stdin como JSON UTF-8;
    el PDF vuelve por stdout como bytes.

    :raises HelperNotBuilt: si el binario no existe (falta ``make pdf``).
    :raises HelperFailed: si sale con código != 0 o excede el timeout.
    """
    path = HELPER_DIR / helper
    if not path.exists():
        raise HelperNotBuilt(
            f'{path} no existe; correr `make pdf` en api (ADR-017, H-API-287)')

    # El descriptor viaja en UTF-8 crudo. Ya no hace falta ``ensure_ascii``:
    # desde que el helper embebe LiberationSans y registra el encoder UTF-8,
    # su lector JSON traduce ``\uXXXX`` a UTF-8 y copia el UTF-8 crudo tal
    # cual — medido: ambas formas dibujan "— ñ é Á ¿ ¡ αβγ €" idénticas.
    #
    # Hasta T-002 esto era ``ensure_ascii=True``, y no por estilo: con la
    # fuente WinAnsi anterior la rama ``\uXXXX`` era la ÚNICA que producía el
    # acento correcto, y el UTF-8 crudo llegaba al papel como sus bytes
    # ("días" -> "dÃ­as"). Ver H-API-290.
    payload = json.dumps(descriptor, ensure_ascii=False).encode('utf-8')
    try:
        completed = subprocess.run(
            [str(path)], input=payload, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=HELPER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HelperFailed(
            f'{helper} excedió {HELPER_TIMEOUT_SECONDS}s') from exc

    if completed.returncode != 0:
        meaning = HELPER_EXIT_MEANING.get(
            completed.returncode, 'fallo no declarado en el contrato')
        stderr = completed.stderr.decode('utf-8', 'replace').strip()
        _logger.error('helper %s exit=%s (%s) stderr=%s',
                      helper, completed.returncode, meaning, stderr)
        raise HelperFailed(
            f'{helper} salió con {completed.returncode}: {meaning}')

    if not completed.stdout.startswith(b'%PDF'):
        # Exit 0 con salida que no es PDF: el contrato dice que no puede pasar,
        # así que si pasa hay que verlo, no servirlo.
        raise HelperFailed(f'{helper} salió 0 pero su stdout no es un PDF')

    return completed.stdout


class IrActionsReport(IrActionsBase):
    """``ir.actions.report`` — declaración de un reporte imprimible.

    Hereda ``IrActionsBase`` (abstracto) porque la referencia declara
    ``_inherit = ['ir.actions.actions']`` **con** ``_table =
    'ir_act_report_xml'``: tabla propia, no compartida. Mismo criterio que el
    resto de la familia en ``ir_actions.py``.
    """

    #: Los seis atributos de clase que la fuente declara
    #: (``odoo19c: ir_actions_report.py:158-163``), verbatim. Conviven con su
    #: forma Django en ``Meta``: ``_table`` con ``db_table``, ``_order`` con
    #: ``ordering``, ``_description`` con ``verbose_name``. No se sustituyen
    #: entre sí — ``atributos-de-clase-de-modelo.md``.
    _name = 'ir.actions.report'
    _description = 'Report Action'
    _inherit = ['ir.actions.actions']
    _table = 'ir_act_report_xml'
    _order = 'name, id'
    _allow_sudo_commands = False

    model = fields.Char(
        max_length=255, db_index=True, verbose_name='Nombre del modelo',
        help_text='Modelo técnico sobre el que imprime. Char plano, mismo '
                  'criterio que ir_rule.model_name e ir_filters.model_id.',
    )
    model_id = fields.Many2one(
        IrModel, store=False,
        default=lambda record: record._compute_model_id(),
        help_text='La fila de ir.model que corresponde a "model". Derivada, '
                  'sin columna: la fuente la declara con compute y sin store.',
    )
    report_type = fields.Selection(
        max_length=16, choices=REPORT_TYPE_CHOICES, default=REPORT_TYPE_PDF,
        verbose_name='Tipo de reporte',
        help_text='Formato de salida. Sin el prefijo qweb- de la referencia: '
                  'aquí no hay QWeb, el render es libharu (ADR-017).',
    )
    report_name = fields.Char(
        max_length=255, verbose_name='Nombre de la plantilla')
    report_file = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Archivo del reporte',
        help_text='Ruta al archivo principal, o vacío si el contenido vive en '
                  'otro campo.',
    )
    group_ids = fields.Many2many(
        ResGroups, blank=True, db_table='res_groups_report_rel',
        related_name='report_ids', verbose_name='Grupos',
        help_text='Vacío = sin restricción por grupo. La autorización '
                  'efectiva sigue siendo por capacidad (DEC-11).',
    )
    multi = fields.Boolean(
        default=False, verbose_name='Sobre varios documentos',
        help_text='Marcado, la acción NO aparece en la barra lateral de un '
                  'formulario — es de lote.',
    )
    paperformat_id = fields.Many2one(
        ReportPaperformat, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, db_column='paperformat_id', related_name='report_ids',
        verbose_name='Formato de papel',
        help_text='Este related_name es el One2many que report_paperformat.py '
                  'dejó anotado como pendiente.',
    )
    print_report_name = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Nombre del archivo impreso',
        help_text='Nombre del archivo que se descarga. Vacío = no se cambia. '
                  'En la referencia admite una expresión Python; aquí es dato, '
                  'no se evalúa.',
    )
    attachment_use = fields.Boolean(
        default=False, verbose_name='Recargar desde el adjunto',
        help_text='Marcado, imprimir dos veces con el mismo nombre de adjunto '
                  'devuelve el reporte anterior en vez de regenerarlo.',
    )
    attachment = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Prefijo del adjunto guardado',
        help_text='Nombre del adjunto donde se guarda el resultado. Vacío = no '
                  'se guarda. Expresión Python en la referencia; aquí es dato.',
    )
    domain = fields.Char(
        max_length=1024, blank=True, default='',
        verbose_name='Dominio de filtrado',
        help_text='Con valor, la acción sólo aparece en los registros que lo '
                  'cumplen. Este archivo NO lo evalúa.',
    )

    class Meta:
        db_table = 'ir_act_report_xml'
        ordering = ['name', 'id']
        verbose_name = 'Acción de reporte'
        verbose_name_plural = 'Acciones de reporte'

    def save(self, *args, **kwargs):
        """Fija los dos valores por defecto que la referencia pone en el campo.

        Allá son ``default=`` de ``type`` y ``binding_type``, que su ORM
        aplica por herencia; aquí los campos vienen del abstracto y no pueden
        redefinir su ``default`` sin duplicar la columna.
        """
        if not self.type:
            self.type = ACTION_TYPE
        if not self.binding_type or self.binding_type == 'action':
            self.binding_type = BINDING_TYPE_REPORT
        super().save(*args, **kwargs)

    # --- Anclaje contextual ---------------------------------------------

    def _compute_model_id(self):
        """La fila de ``ir.model`` que corresponde a ``model``.

        ≙ ``_compute_model_id`` (``odoo19c: ir_actions_report.py:194-197``),
        que allá lleva ``@api.depends('model')`` y **asigna** el valor a cada
        registro del conjunto. Aquí devuelve el valor de UNA fila, que es la
        forma que el campo sin columna consume: su ``default`` invocable lo
        llama con el registro y guarda lo que devuelve. Es la misma
        divergencia de enlace ya declarada en
        ``properties_base_definition_mixin._compute_properties_base_definition_id``.
        """
        return IrModel._get(self.model)

    @classmethod
    def _search_model_id(cls, operator, value):
        """Traduce una búsqueda por ``model_id`` a una por ``model``.

        ≙ ``_search_model_id`` (``odoo19c: ir_actions_report.py:199-217``).
        El campo no tiene columna, así que buscar por él exige resolver antes
        qué filas de ``ir.model`` cumplen el criterio y luego filtrar por sus
        nombres técnicos — que es exactamente lo que la fuente hace, con el
        mismo reparto por operador:

        - un operador negativo devuelve ``NotImplemented``, para que el motor
          lo resuelva por la vía general en vez de por aquí;
        - una cadena busca contra ``display_name``;
        - un ``Domain`` se usa tal cual;
        - ``any!`` salta las reglas de fila, igual que su ``sudo()``;
        - ``any`` o un entero buscan por ``id``;
        - ``in`` construye la disyunción, decidiendo por elemento si es ``id``
          o ``display_name``.
        """
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        rows = IrModel.objects.none()
        if isinstance(value, str):
            rows = cls._models_matching(Domain('display_name', operator, value))
        elif isinstance(value, Domain):
            rows = cls._models_matching(value)
        elif operator == 'any!':
            with sudo():
                rows = cls._models_matching(Domain('id', operator, value))
        elif operator == 'any' or isinstance(value, int):
            rows = cls._models_matching(Domain('id', operator, value))
        elif operator == 'in':
            rows = cls._models_matching(Domain.OR(
                Domain('id' if isinstance(item, int) else 'display_name',
                       operator, item)
                for item in value
                if item
            ))
        return Domain('model', 'in', list(rows.values_list('model', flat=True)))

    @staticmethod
    def _models_matching(domain):
        """Las filas de ``ir.model`` que cumplen el dominio.

        La fuente escribe ``self.env['ir.model'].search(domain)``: allá el
        modelo trae el buscador y el dominio es su lenguaje nativo. Aquí el
        equivalente son dos piezas — ``domains.to_q`` compila el dominio a un
        ``Q`` y el manager lo aplica—, y separarlas en un ayudante evita
        repetir la traducción en las cinco ramas de arriba.
        """
        return IrModel.objects.filter(to_q(domain, IrModel))

    def _get_readable_fields(self):
        """Los campos que el cliente puede leer de esta acción.

        ≙ ``_get_readable_fields`` (``odoo19c: ir_actions_report.py:219-229``),
        con su unión verbatim y sus dos comentarios: *"these two are not real
        fields of ir.actions.report but are expected in the route
        /report/<converter>/<reportname> and must not be removed by
        clean_action"* para ``context`` y ``data``, y *"and this one is used by
        the frontend later on"* para ``close_on_report_download``.

        La allowlist que gobierna la respuesta HTTP sigue siendo el
        ``Meta.fields`` explícito del serializer DRF. Este método es el
        enganche donde la fuente lo pone, y su salida es la misma unión — así
        una extensión encuentra el punto que espera.
        """
        return super()._get_readable_fields() | {
            'report_name', 'report_type', 'target',
            'context', 'data',
            'close_on_report_download',
            'domain',
        }

    def create_action(self):
        """``create_action`` — ancla el reporte al modelo sobre el que imprime.

        Con el anclaje puesto, la acción aparece en la barra contextual de ese
        modelo.
        """
        self.binding_model_name = self.model
        self.binding_type = BINDING_TYPE_REPORT
        self.save(update_fields=['binding_model_name', 'binding_type',
                                 'updated_at'])

    def unlink_action(self):
        """``unlink_action`` — quita el anclaje sin borrar el reporte."""
        if not self.binding_model_name:
            return
        self.binding_model_name = ''
        self.save(update_fields=['binding_model_name', 'updated_at'])

    def associated_view(self):
        """La acción de ventana que lista las vistas de este reporte.

        ≙ ``associated_view`` (``odoo19c: ir_actions_report.py:231-241``).
        Se usa en el formulario de ``ir.actions.report`` para buscar de forma
        ingenua la vista o vistas que intervienen en el dibujado.

        Devuelve ``False`` si no hay acción resuelta o si el ``report_name``
        no lleva punto — las dos guardas de la fuente, verbatim.
        """
        action_ref = IrModelData.ref('base.action_ui_view',
                                     raise_if_not_found=False)
        if not action_ref or len(self.report_name.split('.')) < 2:
            return False
        action_data = action_ref._get_action_dict()
        action_data['domain'] = [
            ('name', 'ilike', self.report_name.split('.')[1]),
            ('type', '=', 'qweb'),
        ]
        return action_data

    # --- Formato de papel -------------------------------------------------

    def get_paperformat(self):
        """El formato del reporte, o el de la compañía activa.

        ≙ ``get_paperformat`` (``odoo19c: ir_actions_report.py:288-289``):
        ``self.paperformat_id or self.env.company.paperformat_id``. El
        ``env.company`` de la fuente es ``get_current_company()`` de
        ``orm.environments``.

        La firma llevaba un ``company=None`` nuestro, con la nota de que
        «este archivo no conoce el contexto de la petición». Era falso —
        ``get_current_company()`` existe desde antes— y por eso se retira: la
        firma vuelve a la de la fuente.
        """
        if self.paperformat_id:
            return self.paperformat_id
        company = get_current_company()
        return getattr(company, 'paperformat_id', None) if company else None

    def get_paperformat_by_xmlid(self, xml_id):
        """El formato del reporte que ese identificador externo nombra.

        ≙ ``get_paperformat_by_xmlid`` (``:291-292``). Sin ``xml_id``, el de
        la compañía activa — la misma rama que la fuente.
        """
        if not xml_id:
            company = get_current_company()
            return getattr(company, 'paperformat_id', None) if company else None
        return IrModelData.ref(xml_id).get_paperformat()

    # --- Plantilla y URL --------------------------------------------------

    def _get_layout(self):
        """La plantilla envolvente mínima, o ``None`` si no está sembrada.

        ≙ ``_get_layout`` (``:294-295``):
        ``self.env.ref('web.minimal_layout', raise_if_not_found=False)``.
        """
        return IrModelData.ref('web.minimal_layout',
                               raise_if_not_found=False)

    def _get_report_url(self, layout=None):
        """La raíz desde la que el motor resuelve los recursos del documento.

        ≙ ``_get_report_url`` (``:297-299``). El parámetro ``report.url``
        gana; si no está, la URL base del envoltorio, o la de este registro.

        La fuente encadena ``(layout or self._get_layout() or self)`` y le
        pide ``get_base_url()`` — el método de ``BaseModel`` que este árbol
        porta en ``orm.models.BaseUrlMixin``, así que los tres eslabones saben
        responder. Ese mixin llega a **todo** modelo por
        ``orm.model_classes.adopt_base_url``, no sólo a los que heredan de la
        base común: sin esa universalidad el porte sería del método y no del
        mecanismo.
        """
        report_url = SystemParameter.get_param('report.url')
        return report_url or (
            layout or self._get_layout() or self).get_base_url()

    # --- Adjunto ----------------------------------------------------------

    def retrieve_attachment(self, record):
        """Recupera el adjunto de un registro concreto.

        ≙ ``retrieve_attachment`` (``:260-273``).

        :param record: el registro dueño del adjunto.
        :return: el adjunto, o ``None``

        El nombre sale de evaluar la expresión guardada en ``self.attachment``
        contra ``{'object': record, 'time': time}``. Ese evaluador **ya no es
        una divergencia**: ``tools.safe_eval`` porta la validación de opcodes
        de la fuente desde la tarea #140, así que la expresión típica de este
        campo —``'INV_%s.pdf' % object.name``— se evalúa aquí con las mismas
        guardas que allá.

        La fuente devuelve un conjunto de a lo sumo un registro
        (``search(..., limit=1)``); aquí es la instancia o ``None``, que es la
        forma que toma un ``limit=1`` con este ORM.
        """
        attachment_name = safe_eval(
            self.attachment, {'object': record, 'time': time}
        ) if self.attachment else ''
        if not attachment_name:
            return None
        return IrAttachment.objects.filter(
            name=attachment_name,
            res_model=self.model,
            res_id=record.pk,
        ).first()

    @classmethod
    def _prepare_local_attachments(cls, attachments):
        """Baja a local los adjuntos remotos y devuelve los que ya lo están.

        ≙ ``_prepare_local_attachments`` (``:1209-1217``). Un motor de PDF no
        puede ir a buscar una URL externa a mitad del dibujado, así que lo
        remoto se migra antes; lo que no se pueda migrar se descarta, y el
        fallo se registra sin detener el resto.

        La fuente atrapa
        ``(ValidationError, requests.exceptions.RequestException)``. Aquí la
        segunda es la misma clase: ``requests`` está declarado en
        ``pyproject.toml`` y es la biblioteca que la fuente usa.
        """
        for attachment in attachments:
            if attachment._is_remote_source():
                try:
                    attachment._migrate_remote_to_local()
                except (ValidationError, RequestException) as error:
                    _logger.error(
                        'Failed to migrate attachment %s to local: %s',
                        attachment.pk, error)
        return [a for a in attachments if not a._is_remote_source()]

    # --- Búsqueda ---------------------------------------------------------

    @classmethod
    def _get_report_from_name(cls, report_name):
        """El reporte cuya plantilla se llama así.

        ≙ ``_get_report_from_name`` (``:649-657``). El guion bajo es de la
        fuente y vuelve en este pase: sin él el símbolo quedaba promovido a
        API pública, que es un compromiso que la fuente nunca tomó.

        La fuente encadena ``.with_context(...).sudo().search(..., limit=1)``;
        aquí el ``sudo()`` es el contexto de ``orm.environments`` y el
        ``limit=1`` es ``.first()``.
        """
        with sudo():
            return cls.objects.filter(report_name=report_name).first()

    @classmethod
    def _get_report(cls, report_ref):
        """El reporte que esa referencia nombra, leído con privilegio.

        ≙ ``_get_report`` (``:659-685``). ``report_ref`` puede ser:

        - el id de una ``ir.actions.report``
        - un registro de ``ir.actions.report``
        - una referencia de ``ir.model.data`` a una ``ir.actions.report``
        - el ``report_name`` de una ``ir.actions.report``

        Las cuatro ramas y sus dos ``ValueError`` son de la fuente, en su
        orden. El ``ReportSudo`` de la fuente es el contexto ``sudo()``.
        """
        with sudo():
            if isinstance(report_ref, int):
                return cls.objects.filter(pk=report_ref).first()
            if isinstance(report_ref, models.Model):
                if not isinstance(report_ref, cls):
                    raise ValueError(
                        'Expected report of type %s, got %s'
                        % (cls._name, type(report_ref).__name__))
                return report_ref
            report = cls.objects.filter(report_name=report_ref).first()
            if report:
                return report
            report = IrModelData.ref(report_ref, raise_if_not_found=False)
            if report:
                if not isinstance(report, cls):
                    raise ValueError(
                        'Fetching report %r: type %s, expected %s'
                        % (report_ref, type(report).__name__, cls._name))
                return report
            raise ValueError('Fetching report %r: report not found'
                             % report_ref)

    @classmethod
    def get_valid_action_reports(cls, model, record_ids):
        """Los reportes cuyo dominio satisface al menos uno de esos registros.

        ≙ ``get_valid_action_reports`` (``:1195-1207``).

        :param model: el modelo de los registros a validar
        :param record_ids: ids de los registros a validar

        Un reporte **sin** dominio siempre vale — la fuente los mete enteros
        antes de recorrer los demás. Uno con dominio vale si algún registro lo
        satisface, lo que se decide con ``filtered_domain``
        (``orm/models.py:311``), que es el homónimo de la fuente.

        La fuente lee el dominio con ``literal_eval``; aquí es ``const_eval``
        de ``tools.safe_eval``, que **es** ``ast.literal_eval`` con el nombre
        de la fuente.
        """
        model_cls = registry.model_by_name(model)
        records = (list(model_cls.objects.filter(pk__in=record_ids))
                   if model_cls else [])
        reports = list(cls.objects.filter(model=model))
        with_domain = [r for r in reports if r.domain]
        valid_action_report_ids = [r.pk for r in reports if not r.domain]
        for action in with_domain:
            if filtered_domain(records, const_eval(action.domain)):
                valid_action_report_ids.append(action.pk)
        return valid_action_report_ids

    @classmethod
    def valid_reports_for(cls, model_name, groups=()):
        """Los reportes de un modelo que esos grupos pueden ver. **Nuestro.**

        **No es el porte de ``get_valid_action_reports``** — ése está arriba,
        con su nombre y su firma. Este método hace otra cosa: filtra por el
        campo ``group_ids``, y la fuente resuelve esa visibilidad por su ACL
        sobre la acción, no con un método del modelo. Hasta este pase el
        docstring lo presentaba como el porte de aquél, que es la fidelidad
        declarada y no entregada que el gate de la tarea #75 vigila.

        Un reporte **sin** grupos vale para todos; uno con grupos vale sólo si
        el usuario tiene alguno. Es la misma asimetría que ``ir.rule`` y
        ``ir.embedded.actions``: la lista vacía significa «sin restricción»,
        no «nadie».
        """
        group_ids = {getattr(group, 'pk', group) for group in groups}
        applicable = []
        for report in cls.objects.filter(model=model_name).prefetch_related(
                'group_ids'):
            declared = set(report.group_ids.values_list('pk', flat=True))
            if not declared or (declared & group_ids):
                applicable.append(report)
        return applicable

    # --- Acción para el cliente -------------------------------------------

    def report_action(self, docids, data=None, config=True):
        """Devuelve una acción de tipo ``ir.actions.report``.

        ≙ ``report_action`` (``:1153-1185``).

        :param docids: id, ids o registro de lo que se va a imprimir (si no se
            usa, pasar una lista vacía)
        :param data:
        :param bool config:

        El ``self.env.context`` de la fuente es ``get_context()``; su
        ``env.is_admin()`` es ``is_system()``; su ``env.company`` es
        ``get_current_company()``.

        ``external_report_layout_id`` **no tiene columna todavía** — la FK
        está declarada como pase propio en el docstring de ``res_company.py``,
        porque añadirla migra esa tabla. Se lee con ``getattr(..., None)``, y
        la rama que toma sin ella es exactamente la de la fuente cuando la
        compañía no tiene plantilla configurada: ofrecer el configurador.
        """
        context = get_context()
        if docids:
            if isinstance(docids, models.Model):
                active_ids = [docids.pk]
            elif isinstance(docids, int):
                active_ids = [docids]
            elif isinstance(docids, list):
                active_ids = docids
            else:
                active_ids = list(docids)
            context = dict(context, active_ids=active_ids)

        report_action = {
            'context': context,
            'data': data,
            'type': 'ir.actions.report',
            'report_name': self.report_name,
            'report_type': self.report_type,
            'report_file': self.report_file,
            'name': self.name,
        }

        discard_logo_check = get_context().get('discard_logo_check')
        company = get_current_company()
        if (is_system()
                and not getattr(company, 'external_report_layout_id', None)
                and config and not discard_logo_check):
            return self._action_configure_external_report_layout(report_action)

        return report_action

    def _action_configure_external_report_layout(
            self, report_action,
            xml_id='web.action_base_document_layout_configurator'):
        """Envuelve la acción del reporte en la del configurador de plantilla.

        ≙ ``_action_configure_external_report_layout`` (``:1187-1193``). La
        acción devuelta lleva el reporte dentro de su contexto, para que el
        cliente lo dispare cuando el usuario termine de configurar.
        """
        action = IrActionsBase._for_xml_id(self, xml_id)
        py_ctx = json.loads(action.get('context') or '{}')
        report_action['close_on_report_download'] = True
        py_ctx['report_action'] = report_action
        action['context'] = py_ctx
        return action

    # --- Motor ------------------------------------------------------------
    #
    # Pasos 3-5 de la cadena (ver ``report_catalog.py``). Viven aquí, en el
    # modelo, porque es donde la referencia los pone: su motor entero está en
    # ``ir_actions_report.py`` (1217 líneas, medido) y su punto de entrada es
    # ``report._render(...)`` — un método del registro, no un módulo hermano.
    #
    # Lo que NO está: el paso 6 (fusionar, estampar). Opera sobre el PDF ya
    # hecho, no tiene consumidor todavía, y en la referencia parte vive fuera
    # del modelo (``add_banner`` en ``odoo/tools/pdf/``). Cuando llegue, ese
    # es su lugar.

    def render(self, records, **ctx):
        """Genera este reporte sobre ``records``.

        Paso 4 — despacho por ``report_type``. Espeja ``_render`` (``:1145``)
        incluido su contrato de ausencia: un tipo sin renderizador devuelve
        ``None``, no levanta (``:1150``).

        :returns: tupla ``(contenido, extensión)`` — hoy siempre ``bytes`` y
            ``'pdf'``, porque es el único formato con renderizador. Misma
            forma que la referencia (``:1110``), que devuelve ``str`` cuando
            el tipo es de texto.
        :raises UnknownReport: si nadie declara este ``report_name``.
        """
        spec = report_catalog.get(self.report_name)
        if spec is None:
            raise UnknownReport(
                f'{self.report_name!r} no está declarado por ningún addon '
                f'instalado')
        method = RENDERER_BY_TYPE.get(self.report_type)
        render_func = getattr(self, method, None) if method else None
        if render_func is None:
            return None
        return render_func(spec, records, ctx)

    def _render_pdf(self, spec, records, ctx):
        """Composición + conversión: descriptor JSON → helper en C → PDF.

        La composición tiene DOS fuentes, en este orden (directiva del
        ejecutor 2026-08-05 — *"queremos usar también self.env['ir.ui.view']"*):

        1. **Plantilla en BD** — una vista ``type='qweb'`` cuya ``key`` es el
           ``report_name``. Es el camino de la referencia
           (``:769-781`` resuelve ``ir.ui.view``): el arch combinado —con las
           extensiones XPath de otros addons ya aplicadas— se **interpreta**
           hacia el descriptor (``report_template.interpret_descriptor``).
        2. **Builder en código** — el ``callable`` del catálogo, que queda
           como respaldo. Así el catálogo sigue abierto a extensión (una
           vista nueva en BD redefine el documento) y cerrado a modificación
           (ningún builder existente cambia por ello).
        """
        descriptor = self._descriptor_from_view(records, ctx)
        if descriptor is None:
            descriptor = spec.builder(records, **ctx)
        return run_helper(spec.helper, descriptor), 'pdf'

    def _descriptor_from_view(self, records, ctx):
        """El descriptor desde la plantilla en BD, o ``None`` si no la hay.

        La resolución por ``key`` espeja ``_get_template_view`` de la fuente:
        la vista QWeb se identifica por su clave estable, no por id. Sólo se
        consideran vistas **primarias activas** — una extensión no es un
        documento, es un parche, y entra vía ``get_combined_arch`` de su
        primaria.
        """
        view = IrUiView.objects.filter(
            key=self.report_name, type='qweb', active=True,
            mode='primary',
        ).order_by('priority', 'id').first()
        if view is None:
            return None
        context = dict(ctx, docs=records, report=self)
        return report_template.interpret_descriptor(
            view._get_combined_arch(), context)

    # Aquí vivía ``_render_text``, retirado en H-API-291 por no tener quien lo
    # declarara ni quien lo probara. Su vuelta tiene destinatario concreto —
    # las 7 etiquetas ZPL de ``odoo19c:`` (6 ``stock`` + 1 ``mrp``)— y una
    # condición: entra con su declarante y su test, y separando el contrato
    # del ``builder``, que para texto devuelve ``str`` y no el descriptor.
