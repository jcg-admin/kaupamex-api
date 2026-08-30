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

Consecuencia para ``report_type``: su valor es ``pdf``, **uno solo**, y sin el
prefijo ``qweb-``. Son dos recortes con dos motivos distintos, y conviene no
confundirlos.

El **prefijo** cae porque el string de la referencia codifica dos cosas —el
lenguaje de plantillas y el formato— y en **esta cadena** sólo la segunda es
verdad. Conservarlo verbatim metería el sustrato ajeno dentro de nuestro dato;
lo que se porta es el **rol** del campo (en qué formato sale el documento), que
es la parte abstracta.

El **conjunto** se reduce a uno porque los otros dos no se pueden emitir aquí,
y eso está medido: ``_render_qweb_html`` y ``_render_qweb_text`` están portados
—el archivo se porta entero— con el cuerpo de la fuente, que devuelve lo que
``_render_template`` produzca. Allá eso es la representación HTML; aquí es el
**intermedio del descriptor** (``{'bodies': …, 'html_ids': …}``), así que el par
que sale de esos dos métodos lleva un dict donde su nombre promete texto o
marcado. Ofrecerlos en el enum entregaría un dict a un consumidor que espera
bytes. Ver :ref:`h-api-935`.

Su condición de reingreso, de :ref:`h-api-291`, se conserva y gana una tercera
exigencia: el valor entra con su **declarante**, su **test** y —lo nuevo— su
**serializador del descriptor** a ese formato, que es trabajo a construir y no
un símbolo que el stack traiga. Ver ``REPORT_TYPE_CHOICES`` para el detalle.

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
import io
import json
import logging
import subprocess
from pathlib import Path

from django.conf import settings

import fields
import models

from addons.base import report_catalog, report_template
from addons.base.models.ir_actions import IrActionsBase
from addons.base.models.ir_ui_view import VIEW_TYPE_TEMPLATE, IrUiView
from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_model import IrModel
from addons.base.models.report_paperformat import ReportPaperformat
from contextlib import contextmanager
from collections import OrderedDict

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from exceptions import AccessError, UserError, ValidationError
from orm import registry
from orm.domains import Domain, to_q
from orm.environments import (get_context, get_current_company,
                              get_current_user, is_system, sudo)
from orm.fields_temporal import Datetime
from orm.models import filtered_domain
from requests.exceptions import RequestException
from tools.mail import is_html_empty
from tools.pdf import PdfFileReader, PdfFileWriter, PdfReadError
from tools.safe_eval import const_eval, safe_eval, time

_logger = logging.getLogger(__name__)

#: Formato que un reporte puede emitir. **Un solo valor**, y el prefijo
#: ``qweb-`` de la fuente NO se copia — las dos cosas están medidas y
#: decididas, no son omisión de este pase.
#:
#: **El prefijo.** En ``qweb-pdf`` el par es (intérprete, formato):
#: ``qweb`` nombra el lenguaje de plantillas y su intérprete —``ir.qweb``, con
#: 23 métodos ``_compile_directive_*``—, ``pdf`` el formato de salida. Aquí el
#: intérprete no es QWeb: es el motor de plantillas de Django sobre nuestro
#: vocabulario ``<descriptor>`` (``report_template.interpret_descriptor``).
#: Escribir ``qweb-pdf`` afirmaría un sustrato que este árbol no tiene.
#: Medición y las cinco preguntas del ejecutor que la produjeron:
#: ``docs: pm/api/iniciativas/adaptar-familias-odoo-monolito-modular/
#: analisis-que-nombra-qweb-en-report-type.rst`` (v3.0.0) y :ref:`h-api-289`.
#:
#: **Los otros dos valores.** ``html`` y ``text`` salieron del enum en
#: :ref:`h-api-291` con una condición de reingreso escrita: *el valor entra con
#: su renderizador, su declarante y su test; para ``text``, además, separando
#: el contrato del ``builder``*. El bloque C aporta la **primera** —
#: ``_render_qweb_html`` y ``_render_qweb_text`` existen— y ninguna de las
#: otras: medido en este pase, **0** addons declaran ``html`` o ``text`` y
#: **0** tests ejercitan sus renderizadores. Un enum que oferta lo que nadie
#: emite es el defecto que aquel hallazgo cerró; portar el método no obliga a
#: ofrecer el valor.
#:
#: **Y hay una causa anterior a la falta de declarante** (:ref:`h-api-935`):
#: los dos cuerpos son el de la fuente y devuelven lo que ``_render_template``
#: produzca. Allá eso es HTML; aquí es el intermedio del descriptor —un
#: ``dict``—, así que ofrecerlos entregaría un dict donde el nombre del valor
#: promete texto o marcado. La condición de reingreso gana por eso una tercera
#: exigencia: el **serializador del descriptor** a ese formato. Es trabajo a
#: **construir** —el stack no trae ningún símbolo que aplane el descriptor a
#: líneas ni a marcado—, no un cableado.
REPORT_TYPE_PDF = 'pdf'
REPORT_TYPE_CHOICES = [
    (REPORT_TYPE_PDF, 'PDF'),
]

#: El prefijo que ``_render`` antepone al derivar el nombre del renderizador.
#: La fuente deriva ``'_render_' + report_type`` porque su valor ya trae el
#: prefijo dentro; aquí el valor no lo trae —ver arriba— y el **método** sí,
#: porque el nombre de un símbolo es el contrato de extensión y cuatro addons
#: de la referencia enganchan ``_render_qweb_pdf_prepare_streams`` por ese
#: nombre. La derivación es la de la fuente; lo que cambia es de dónde sale el
#: prefijo: de una constante en vez de del dato. Con un solo intérprete la
#: constante no pierde nada — no hay segundo par que discriminar.
RENDERER_PREFIX = '_render_qweb_'

#: ``type`` por defecto de esta acción.
ACTION_TYPE = 'ir.actions.report'
#: ``binding_type`` por defecto — aparece como "Imprimir", no como "Acción".
BINDING_TYPE_REPORT = 'report'


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
        help_text='Formato de salida: PDF. El valor gobierna el despacho '
                  'de _render. Divergencia declarada frente a la fuente, que '
                  'ofrece tres: aquí el intermedio de la composición es el '
                  'descriptor, y sólo el camino del PDF tiene quien lo '
                  'convierta.',
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
            ('type', '=', VIEW_TYPE_TEMPLATE),
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

    # --- Composición: contexto y plantilla ---------------------------------

    @staticmethod
    def _get_template_view(key):
        """La vista ``type='template'`` que declara esa clave, o ``None``.

        ≙ ``_get_template_view`` (``odoo19c: ir_ui_view.py:1162``), con su
        dominio y su orden: ``_get_template_domain`` empareja por ``key``
        (``:1169``) y ``_get_template_order`` desempata por ``priority, id``
        (``:1173``), quedándose con la primera.

        **Un solo resolutor para las dos vías, como la fuente.** Allá el
        reporte no resuelve nada por su cuenta: delega en
        ``ir.ui.view._render_template`` (``ir_actions_report.py:769-789``), y
        el ``t-call`` del compilador entra por este mismo método. Aquí el
        intérprete recibe el resolutor por parámetro, así que la unidad hay
        que sostenerla en un sitio — éste — en vez de repetir el filtro en
        cada llamador.

        La divergencia declarada es ``mode='primary'``, que la fuente no
        filtra: allá el ``active_test`` del ORM basta porque una extensión
        nunca se resuelve sola. Aquí el arch de una extensión es un
        ``<xpath>`` suelto, que no es un ``<descriptor>`` y no se puede
        interpretar; el filtro lo excluye en la resolución en vez de dejarlo
        fallar dentro del intérprete con un mensaje que no nombra la causa.
        """
        return IrUiView.objects.filter(
            key=key, type=VIEW_TYPE_TEMPLATE, active=True, mode='primary',
        ).order_by('priority', 'id').first()

    @classmethod
    def _resolve_template_key(cls, key):
        """El resolutor que ``<call key="…"/>`` consume.

        Devuelve el **arch combinado** del descriptor llamado, no el crudo:
        una extensión XPath sobre la plantilla llamada tiene que llegar al
        documento igual que sobre la raíz, que es lo que hace el mecanismo de
        herencia de ``ir.ui.view``.

        Devuelve ``None`` cuando ninguna vista declara la clave, y es
        deliberado: el intérprete distingue ese caso —levanta nombrando la
        clave (``report_template._interpret_call``)— de la ausencia de
        resolutor. Resolver aquí a un descriptor vacío haría desaparecer un
        bloque entero del papel en silencio.
        """
        view = cls._get_template_view(key)
        return view._get_combined_arch() if view is not None else None

    def _render_template(self, template, values=None):
        """Compone el documento desde su plantilla, del lado del servidor.

        ≙ ``_render_template`` (``odoo19c: ir_actions_report.py:769-789``).

        :param template: la clave de la plantilla — el ``report_name``.
        :param values: métodos y variables adicionales del dibujado.
        :returns: el **intermedio** que el paso de conversión consume.

        **Qué es el intermedio aquí, y por qué eso no lo cambia de sitio.** La
        fuente devuelve la representación HTML que produce
        ``ir.ui.view._render_template``; aquí ese papel lo cumple el
        **descriptor**, que ``report_template.interpret_descriptor`` obtiene
        del mismo sitio: una vista ``type='template'`` resuelta por su clave, con
        el arch ya combinado. Cambia la forma del intermedio, no el paso: sigue
        siendo composición separada de la conversión, que es la razón por la
        que la fuente tiene un motor y N documentos.

        **Un cuerpo por registro, con su id al lado.** La fuente compone los N
        registros en un solo HTML —``t-foreach="docs"`` escribe un ``div`` con
        ``data-oe-id`` por cada uno— y ``_prepare_html`` lo parte después. Aquí
        el arch se interpreta **una vez por registro**, con ``docs`` ligado a
        ese registro, y el intermedio es ``{'bodies': [...], 'html_ids': [...]}``:
        la misma pareja que ``_prepare_html`` devuelve, obtenida antes en la
        cadena. El vocabulario de nuestras plantillas nombra ``docs`` en
        singular (``{{ docs.order_number }}``, no un bucle), así que la
        iteración vive donde la fuente tiene el ``t-foreach``: en el paso de
        composición, no dentro del documento.

        Las cinco variables que la fuente inyecta se inyectan aquí, con el
        mismo nombre — son el contrato de lo que una plantilla puede nombrar:
        ``time``, ``context_timestamp``, ``user``, ``res_company`` y
        ``web_base_url``. ``time`` es el módulo envuelto de ``tools.safe_eval``,
        el mismo que la fuente expone.
        """
        if values is None:
            values = {}

        user = get_current_user()
        company = get_current_company()
        values.update(
            time=time,
            context_timestamp=lambda moment: Datetime.context_timestamp(
                self, moment),
            user=user,
            res_company=company,
            web_base_url=SystemParameter.get_param('web.base.url', default=''),
        )
        # Respaldo: el ``builder`` del catálogo (directiva del ejecutor
        # 2026-08-05 — *"queremos usar también self.env['ir.ui.view']"*, con la
        # vista como fuente primaria y el código como respaldo). Vivía en el
        # ``_render_pdf`` nuestro, que este pase retira; su sitio es aquí,
        # porque resolver la plantilla es lo que este método hace.
        #
        # Con las dos fuentes el catálogo queda abierto a extensión —una vista
        # nueva en BD redefine el documento— y cerrado a modificación: ningún
        # ``builder`` existente cambia por ello.
        view = self._get_template_view(template)
        spec = report_catalog.get(template)
        if view is None and spec is None:
            raise UnknownReport(
                f'{template!r} no tiene plantilla: ninguna vista qweb '
                f'primaria activa declara esa clave, y ningún addon '
                f'instalado lo declara en su catálogo')

        docs = values.get('docs')
        if isinstance(docs, (list, tuple)):
            records = list(docs)
        elif docs is None:
            records = []
        else:
            records = [docs]

        arch = view._get_combined_arch() if view is not None else None
        bodies, html_ids = [], []
        for record in records or [None]:
            context = dict(values, docs=record, report=self)
            if arch is not None:
                bodies.append(report_template.interpret_descriptor(
                    arch, context, resolve_key=self._resolve_template_key))
            else:
                bodies.append(spec.builder(record, **context))
            html_ids.append(getattr(record, 'pk', None))
        return {'bodies': bodies, 'html_ids': html_ids}

    @classmethod
    def _get_rendering_context_model(cls, report):
        """El modelo que dibuja este reporte a medida, o ``None``.

        ≙ ``_get_rendering_context_model`` (``:1121-1123``):
        ``self.env.get('report.%s' % report.report_name)``. El ``env.get`` de
        la fuente —que devuelve ``None`` si el modelo no está— es aquí
        ``IrModelData._model_class``, con el mismo contrato de ausencia y con
        las **dos** vías de resolución que este árbol necesita: el ``_name`` de
        la referencia y, como respaldo, la etiqueta ``app.Modelo`` de Django.
        La segunda no es adorno — ``ir.actions.report.model`` guarda hoy la
        etiqueta (``'sale.SaleOrder'``), no el ``_name``, y sin ese respaldo el
        contexto de dibujado salía con ``docs`` vacío y el PDF sin páginas.
        """
        return IrModelData._model_class('report.%s' % report.report_name)

    @classmethod
    def _get_rendering_context(cls, report, docids, data):
        """El espacio de nombres con que se compone el documento.

        ≙ ``_get_rendering_context`` (``:1125-1142``). Si el reporte declara un
        modelo propio para dibujarse, manda ése; si no, se cae al genérico, que
        expone ``doc_ids``, ``doc_model`` y ``docs``.
        """
        report_model = cls._get_rendering_context_model(report)

        data = data and dict(data) or {}

        if report_model is not None:
            data.update(report_model._get_report_values(docids, data=data))
        else:
            model_cls = IrModelData._model_class(report.model)
            docs = (list(model_cls.objects.filter(pk__in=docids or []))
                    if model_cls else [])
            data.update({
                'doc_ids': docids,
                'doc_model': report.model,
                'docs': docs,
            })
        data['is_html_empty'] = is_html_empty
        return data

    # --- Despacho por formato ---------------------------------------------

    def _render_qweb_text(self, report_ref, docids, data=None):
        """El documento en texto plano, en ``bytes``.

        ≙ ``_render_qweb_text`` (``:1103-1110``), cuya firma promete ``bytes``
        (``:774`` declara ``:rtype: bytes`` para el paso que comparten los tres
        formatos).

        **El paso de serialización es la divergencia declarada.** Allá
        ``_render_template`` ya devuelve HTML, así que el renderizador sólo lo
        codifica; aquí devuelve el **intermedio del descriptor** —el motor de
        libharu dibuja descriptores, no HTML (ADR-017)—, así que hace falta un
        serializador que lo lleve a la representación que la firma promete.
        Lo aporta ``report_template.descriptor_to_text``.
        """
        if not data:
            data = {}
        data.setdefault('report_type', 'text')
        report = self._get_report(report_ref)
        data = self._get_rendering_context(report, docids, data)
        rendered = report._render_template(report.report_name, data)
        return report_template.descriptor_to_text(rendered), 'text'

    def _render_qweb_html(self, report_ref, docids, data=None):
        """El documento sin convertir — el intermedio del pipeline.

        ≙ ``_render_qweb_html`` (``:1112-1119``).

        Es el paso que la fuente reutiliza desde ``_render_qweb_pdf``
        (``:879``), y la prueba de que composición y conversión son pasos
        distintos: los tres formatos comparten plantilla y contexto, y sólo
        difieren en qué se hace con lo que sale de aquí.

        **Devuelve ``bytes``, como la firma de la fuente promete.** El
        intermedio de ``_render_template`` es aquí el descriptor y no el HTML
        —ésa es la divergencia de ADR-017—, así que
        ``report_template.descriptor_to_html`` hace la serialización que allá
        no hace falta. El ``model`` viaja como ``data-oe-model`` del
        ``div.article``, que es donde ``_prepare_html`` (``:383-463``) lo
        busca.
        """
        if not data:
            data = {}
        data.setdefault('report_type', 'html')
        report = self._get_report(report_ref)
        data = self._get_rendering_context(report, docids, data)
        rendered = report._render_template(report.report_name, data)
        return (report_template.descriptor_to_html(rendered, model=report.model),
                'html')

    @classmethod
    def _render(cls, report_ref, res_ids, data=None):
        """Despacha al renderizador del formato que el reporte declara.

        ≙ ``_render`` (``:1144-1151``), incluida su **derivación**: el nombre
        del método sale del propio ``report_type``, no de un mapa.

        Aquí había un ``RENDERER_BY_TYPE`` explícito, con el argumento de que
        «deja ver de un vistazo qué formatos se rinden». Se retira: era un
        mecanismo distinto del de la fuente para el mismo trabajo, y existía
        sólo porque los renderizadores se llamaban ``_render_pdf``. Con los
        nombres de la fuente —``_render_qweb_pdf``— y el prefijo en
        :data:`RENDERER_PREFIX`, la derivación vuelve a alcanzarlos y el mapa
        sobra. La invariante que el mapa protegía —todo valor ofrecido tiene
        renderizador— la mide ahora un test sobre el propio enum.

        Conserva el contrato de ausencia de la fuente (``:1150``): un formato
        sin renderizador devuelve ``None``, no levanta.
        """
        report = cls._get_report(report_ref)
        report_type = report.report_type.lower().replace('-', '_')
        # El ``self`` de la fuente es el modelo, y los renderizadores son
        # métodos de instancia suyos; aquí el receptor es el **registro** del
        # reporte, que es lo que ``_get_report`` devuelve. ``getattr`` sobre él
        # entrega el método ya ligado, igual que allá.
        render_func = getattr(report, RENDERER_PREFIX + report_type, None)
        if not render_func:
            return None
        return render_func(report_ref, res_ids, data=data)

    # --- El motor: estado, argumentos y conversión -------------------------

    @classmethod
    def get_wkhtmltopdf_state(cls):
        """El estado del conversor: ``install``, ``ok``, ``upgrade``,
        ``workers`` o ``broken``.

        ≙ ``get_wkhtmltopdf_state`` (``:275-287``), con los cinco estados de la
        fuente y su significado:

        - ``install``: estado de partida — el conversor no está.
        - ``upgrade``: el binario es de una versión anterior a la mínima.
        - ``ok``: hay binario y sirve.
        - ``workers``: no hay suficientes trabajadores para el dibujado.
        - ``broken``: hay binario y no responde.

        **El conversor aquí son nuestros helpers de libharu** (ADR-017), no
        wkhtmltopdf. El nombre y los cinco estados son los de la fuente porque
        el contrato es el mismo —quien pregunta quiere saber si puede pedir un
        PDF—; lo que cambia es qué se inspecciona para responder.

        De los cinco, dos no tienen forma que tomar en este sustrato y se
        declara por qué, no se omiten: ``upgrade`` exige una versión que
        comparar y los helpers se compilan del árbol, así que su versión es la
        del árbol; ``workers`` exige un pool de procesos, y aquí cada
        conversión es un ``subprocess`` propio (ADR-017), sin pool que quedarse
        corto.
        """
        faltantes = [h for h in report_catalog.HELPERS
                     if not (HELPER_DIR / h).exists()]
        if len(faltantes) == len(report_catalog.HELPERS):
            return 'install'
        if faltantes:
            return 'broken'
        return 'ok'

    def _prepare_html(self, html, report_model=False):
        """Parte el intermedio en cuerpos por registro, con su cabecera y pie.

        ≙ ``_prepare_html`` (``:383-463``).

        :returns: la tupla de cinco de la fuente —``bodies``, ``html_ids``,
            ``header``, ``footer``, ``specific_paperformat_args``.

        La fuente recorre el árbol HTML con ``lxml`` buscando el ``div`` con
        clase ``article``, y saca de cada uno sus atributos ``data-oe-model`` y
        ``data-oe-id`` — así sabe qué registro dibuja cada tramo, que es lo que
        luego permite guardar un adjunto por registro. **Ese par de atributos
        es el contrato**, y aquí lo cumple el descriptor: el intérprete escribe
        un tramo por registro con su ``res_id``.

        ``specific_paperformat_args`` son los ajustes de papel que el propio
        documento declara —márgenes, orientación— y que ganan sobre el formato
        del reporte. La fuente los lee de atributos ``data-report-*``; aquí,
        de la clave ``paperformat`` del descriptor.
        """
        if isinstance(html, dict):
            bodies = html.get('bodies') or [html]
            html_ids = html.get('html_ids') or [
                body.get('res_id') for body in bodies]
            header = html.get('header')
            footer = html.get('footer')
            specific_paperformat_args = html.get('paperformat') or {}
        else:
            bodies, html_ids = [html], [None]
            header = footer = None
            specific_paperformat_args = {}
        return bodies, html_ids, header, footer, specific_paperformat_args

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None,
                         footer=None, landscape=False,
                         specific_paperformat_args=None,
                         set_viewport_size=False):
        """Convierte los cuerpos ya compuestos en un PDF.

        ≙ ``_run_wkhtmltopdf`` (``:513-647``), con su firma completa.

        **El cuerpo maneja NUESTRO motor**: los helpers de ``tools/pdf/``
        basados en libharu (ADR-017), no wkhtmltopdf. Cada cuerpo es un
        descriptor; el helper lo dibuja en un ``subprocess`` propio, que es el
        aislamiento que aquel ADR pide.

        Los argumentos de papel de la fuente —``landscape``,
        ``specific_paperformat_args``, ``set_viewport_size``— se resuelven
        contra el formato del reporte y viajan al descriptor bajo la clave
        ``paperformat``, que es donde el helper los lee.
        """
        report = self._get_report(report_ref) if report_ref else self
        paperformat = report.get_paperformat()
        args = dict(specific_paperformat_args or {})
        if landscape:
            args['orientation'] = 'landscape'
        elif paperformat is not None:
            args.setdefault('orientation',
                            getattr(paperformat, 'orientation', None))
        if set_viewport_size:
            args['viewport_size'] = set_viewport_size

        spec = report_catalog.get(report.report_name)
        if spec is None:
            raise UnknownReport(
                f'{report.report_name!r} no está declarado por ningún addon '
                f'instalado')

        pieces = []
        for body in bodies:
            descriptor = dict(body) if isinstance(body, dict) else {'body': body}
            if header is not None:
                descriptor.setdefault('header', header)
            if footer is not None:
                descriptor.setdefault('footer', footer)
            if args:
                descriptor.setdefault('paperformat', args)
            pieces.append(run_helper(spec.helper, descriptor))
        if len(pieces) == 1:
            return pieces[0]
        with self._merge_pdfs([io.BytesIO(piece) for piece in pieces]) as merged:
            return merged.getvalue()

    # --- Fusión de PDF ------------------------------------------------------

    def _handle_merge_pdfs_error(self, error=None, error_stream=None):
        """Qué hacer cuando un flujo no se deja fusionar.

        ≙ ``_handle_merge_pdfs_error`` (``:791-792``). Es un enganche: quien
        quiera reunir los flujos rotos en vez de abortar pasa su propio
        manejador a :meth:`_merge_pdfs`, que es lo que ``_render_qweb_pdf``
        hace para poder señalar los registros culpables.
        """
        raise UserError('Unable to merge the generated PDFs.')

    @classmethod
    @contextmanager
    def _merge_pdfs(cls, streams, handle_error=None):
        """Fusiona varios flujos de PDF en uno solo.

        ≙ ``_merge_pdfs`` (``:794-812``), con su firma y su contrato: un flujo
        que no se deja leer va al manejador —el de la clase si no se pasa
        otro— y los demás siguen.

        **El mecanismo se construyó**: la fuente lo apoya en ``pypdf``, que
        está excluido del stack porque el proyecto tiene motor propio
        (ADR-017). El lector y el escritor viven en ``tools/pdf``, la raíz que
        la referencia también usa para esto, y entienden el PDF que nuestro
        motor emite. Su alcance y su ceguera están declarados en el docstring
        de ese módulo.

        La fuente devuelve el flujo y lo añade a ``streams`` para que el
        llamador lo cierre; aquí es un gestor de contexto, que es la forma con
        la que el llamador de la fuente ya lo usa (``:1071``:
        ``with self._merge_pdfs(...) as pdf_merged_stream``).
        """
        writer = PdfFileWriter()
        for stream in streams:
            try:
                stream.seek(0)
                writer.appendPagesFromReader(PdfFileReader(stream))
            except (PdfReadError, TypeError, NotImplementedError,
                    ValueError) as error:
                if handle_error is None:
                    cls._handle_merge_pdfs_error(cls, error=error,
                                                 error_stream=stream)
                else:
                    handle_error(error=error, error_stream=stream)
        result_stream = io.BytesIO()
        try:
            writer.write(result_stream)
        except PdfReadError:
            raise UserError('Unable to merge the generated PDFs.')
        result_stream.seek(0)
        try:
            yield result_stream
        finally:
            result_stream.close()

    # --- Flujos por registro ------------------------------------------------

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """Un flujo de PDF por registro, reusando el adjunto que ya exista.

        ≙ ``_render_qweb_pdf_prepare_streams`` (``:814-978``).

        Tres tramos, en el orden de la fuente:

        1. **Recoger lo que ya está.** Para cada registro, si el reporte
           declara ``attachment`` y el contexto no lo desactiva, se busca el
           adjunto; si además declara ``attachment_use``, su contenido **es**
           el flujo y no se vuelve a dibujar.
        2. **Dibujar lo que falta.** Se compone el intermedio con
           ``_render_qweb_html`` —el mismo paso que sirve al formato HTML— se
           parte con ``_prepare_html`` y se convierte con ``_run_wkhtmltopdf``.
        3. **Repartir el resultado.** Un solo registro se lleva el PDF entero;
           varios lo reparten por sus tramos.

        **Divergencia de forma en el reparto, declarada.** La fuente parte el
        PDF ya hecho leyendo sus páginas y sus marcadores con ``pypdf``. Esa
        biblioteca está **excluida del stack por decisión del ejecutor**
        —tenemos motor propio—, así que aquí el reparto se hace **antes**: se
        convierte un descriptor por registro, y cada conversión produce el
        flujo de ese registro. Es el mismo resultado por otra vía, y no
        depende de heurísticas de marcadores.
        """
        if not data:
            data = {}
        data.setdefault('report_type', 'pdf')

        report_sudo = self._get_report(report_ref)
        has_duplicated_ids = res_ids and len(res_ids) != len(set(res_ids))

        collected_streams = OrderedDict()

        no_attachment = get_context().get('report_pdf_no_attachment')
        if res_ids:
            model_cls = IrModelData._model_class(report_sudo.model)
            records = (list(model_cls.objects.filter(pk__in=res_ids))
                       if model_cls else [])
            for record in records:
                res_id = record.pk
                if res_id in collected_streams:
                    continue

                stream = None
                attachment = None
                if (not has_duplicated_ids and report_sudo.attachment
                        and not no_attachment):
                    attachment = report_sudo.retrieve_attachment(record)

                    if attachment and report_sudo.attachment_use:
                        stream = io.BytesIO(attachment.datas.read())

                collected_streams[res_id] = {
                    'stream': stream,
                    'attachment': attachment,
                }

        res_ids_wo_stream = [res_id
                             for res_id, stream_data in collected_streams.items()
                             if not stream_data['stream']]
        all_res_ids_wo_stream = (res_ids if has_duplicated_ids
                                 else res_ids_wo_stream)
        is_conversion_needed = not res_ids or res_ids_wo_stream

        if is_conversion_needed:
            if self.get_wkhtmltopdf_state() == 'install':
                raise UserError(
                    'Unable to find the PDF helpers on this system. '
                    'The PDF can not be created.')

            data.setdefault('debug', False)

            # DIVERGENCIA DECLARADA — la fuente reutiliza aquí
            # ``_render_qweb_html`` (``:879``) porque su intermedio ES el HTML:
            # el ida y vuelta no le cuesta nada. El nuestro es el descriptor
            # (ADR-017), así que serializarlo a HTML para que ``_prepare_html``
            # lo vuelva a partir perdería la estructura que el motor dibuja.
            # Se compone el intermedio directamente, que es el mismo paso que
            # ``_render_qweb_html`` hace antes de serializar.
            data.setdefault('report_type', 'pdf')
            rendering_data = report_sudo._get_rendering_context(
                report_sudo, all_res_ids_wo_stream, data)
            rendered = report_sudo._render_template(
                report_sudo.report_name, rendering_data)

            (bodies, html_ids, header, footer,
             specific_paperformat_args) = report_sudo._prepare_html(
                rendered, report_model=report_sudo.model)

            if (not has_duplicated_ids and report_sudo.attachment
                    and set(res_ids_wo_stream) != set(html_ids)):
                raise UserError(
                    'Report template “%s” has an issue, please contact your '
                    'administrator. \n\nCannot separate file to save as '
                    'attachment because the report\'s template does not '
                    'identify each record.' % report_sudo.name)

            if has_duplicated_ids or not res_ids:
                pdf_content = report_sudo._run_wkhtmltopdf(
                    bodies, report_ref=report_ref, header=header,
                    footer=footer, landscape=get_context().get('landscape'),
                    specific_paperformat_args=specific_paperformat_args,
                    set_viewport_size=get_context().get('set_viewport_size'))
                return {
                    False: {
                        'stream': io.BytesIO(pdf_content),
                        'attachment': None,
                    }
                }

            for body, html_id in zip(bodies, html_ids):
                pdf_content = report_sudo._run_wkhtmltopdf(
                    [body], report_ref=report_ref, header=header,
                    footer=footer, landscape=get_context().get('landscape'),
                    specific_paperformat_args=specific_paperformat_args,
                    set_viewport_size=get_context().get('set_viewport_size'))
                if html_id in collected_streams:
                    collected_streams[html_id]['stream'] = io.BytesIO(
                        pdf_content)
                else:
                    collected_streams[False] = {
                        'stream': io.BytesIO(pdf_content),
                        'attachment': None,
                    }

        return collected_streams

    def _prepare_pdf_report_attachment_vals_list(self, report, streams):
        """Los valores con que se crean los adjuntos del PDF recién hecho.

        ≙ ``_prepare_pdf_report_attachment_vals_list`` (``:981-1017``). Es un
        enganche: un addon que necesite guardar algo más lo extiende.

        :param report: el reporte, leído con privilegio, de la referencia dada.
        :param streams: el diccionario de flujos por registro, con su adjunto
            existente si lo hubiera.
        :return: la lista de valores para crear los adjuntos.
        """
        attachment_vals_list = []
        for res_id, stream_data in streams.items():
            if stream_data['attachment']:
                continue

            if not res_id or not stream_data['stream']:
                _logger.warning(
                    'These documents were not saved as an attachment because '
                    "the template of %s doesn't identify each record. If you "
                    'want it saved, please print the documents separately',
                    report.report_name)
                continue
            model_cls = IrModelData._model_class(report.model)
            record = (model_cls.objects.filter(pk=res_id).first()
                      if model_cls else None)
            if record is None:
                continue
            attachment_name = safe_eval(
                report.attachment, {'object': record, 'time': time})

            if not attachment_name:
                continue

            attachment_vals_list.append({
                'name': attachment_name,
                'raw': stream_data['stream'].getvalue(),
                'res_model': report.model,
                'res_id': record.pk,
                'type': 'binary',
            })
        return attachment_vals_list

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Los flujos, antes de fusionarlos y de guardar sus adjuntos.

        ≙ ``_pre_render_qweb_pdf`` (``:1019-1031``).

        La fuente cae a ``_render_qweb_html`` cuando corre bajo prueba sin
        suficientes trabajadores para llamar al conversor. Aquí el conversor es
        un ``subprocess`` por documento y no depende de un pool, así que la
        caída sólo aplica cuando los helpers no están compilados: ese es el
        mismo hecho —no se puede convertir— medido sobre nuestro sustrato.
        """
        if not data:
            data = {}
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        data.setdefault('report_type', 'pdf')
        if (self.get_wkhtmltopdf_state() != 'ok'
                and not get_context().get('force_report_rendering')):
            return self._render_qweb_html(report_ref, res_ids, data=data)

        return (self._render_qweb_pdf_prepare_streams(
            report_ref, data, res_ids=res_ids), 'pdf')

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """El documento en PDF, con sus adjuntos guardados.

        ≙ ``_render_qweb_pdf`` (``:1033-1101``). Tres tramos: pedir los flujos,
        guardar los adjuntos que falten, y fusionar lo que quede en un solo
        PDF.

        El ``AccessError`` al crear adjuntos se registra y no se propaga —el
        PDF se entrega igual—, que es el contrato de la fuente (``:1057``): no
        poder archivar no es no poder imprimir.
        """
        if not data:
            data = {}
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        data.setdefault('report_type', 'pdf')

        collected_streams, report_type = self._pre_render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data)
        if report_type != 'pdf':
            return collected_streams, report_type

        has_duplicated_ids = res_ids and len(res_ids) != len(set(res_ids))

        report_sudo = self._get_report(report_ref)

        if (not has_duplicated_ids and report_sudo.attachment
                and not get_context().get('report_pdf_no_attachment')):
            attachment_vals_list = self._prepare_pdf_report_attachment_vals_list(
                report_sudo, collected_streams)
            if attachment_vals_list:
                attachment_names = ', '.join(
                    x['name'] for x in attachment_vals_list)
                try:
                    for vals in attachment_vals_list:
                        IrAttachment.objects.create(**vals)
                except AccessError:
                    _logger.info(
                        'Cannot save PDF report %r attachments for user %r',
                        attachment_names, get_current_user())
                else:
                    _logger.info(
                        'The PDF documents %r are now saved in the database',
                        attachment_names)

        stream_to_ids = {id(v['stream']): k
                         for k, v in collected_streams.items() if v['stream']}
        streams_to_merge = [v['stream'] for v in collected_streams.values()
                            if v['stream']]
        error_record_ids = []

        def custom_handle_merge_pdfs_error(error, error_stream):
            error_record_ids.append(stream_to_ids[id(error_stream)])

        if len(streams_to_merge) == 1:
            pdf_content = streams_to_merge[0].getvalue()
        else:
            with self._merge_pdfs(
                    streams_to_merge,
                    custom_handle_merge_pdfs_error) as pdf_merged_stream:
                pdf_content = pdf_merged_stream.getvalue()

        if error_record_ids:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'Problematic record(s)',
                'res_model': report_sudo.model,
                'domain': [('id', 'in', error_record_ids)],
                'views': [(False, 'list'), (False, 'form')],
            }
            num_errors = len(error_record_ids)
            if num_errors == 1:
                action.update({
                    'views': [(False, 'form')],
                    'res_id': error_record_ids[0],
                })
            raise RedirectWarning(
                'Unable to merge the generated PDFs because of %s corrupted '
                'file(s)' % num_errors,
                action,
                'View Problematic Record(s)')

        for stream in streams_to_merge:
            stream.close()

        if res_ids:
            _logger.info(
                'The PDF report has been generated for model: %s, records %s.',
                report_sudo.model, str(res_ids))

        return pdf_content, 'pdf'

    # Aquí vivía ``_render_text``, retirado en H-API-291 por no tener quien lo
    # declarara ni quien lo probara. Su vuelta tiene destinatario concreto —
    # las 7 etiquetas ZPL de ``odoo19c:`` (6 ``stock`` + 1 ``mrp``)— y una
    # condición: entra con su declarante y su test, y separando el contrato
    # del ``builder``, que para texto devuelve ``str`` y no el descriptor.
