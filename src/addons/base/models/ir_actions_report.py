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

- **Todo el motor**: ``_build_wkhtmltopdf_args``, ``_run_wkhtmltopdf``,
  ``_run_wkhtmltoimage``, ``_prepare_html``, ``_render_qweb_pdf``,
  ``_render_qweb_html``, ``_render_qweb_text``, ``_render_template``,
  ``_merge_pdfs``, ``_get_rendering_context``, ``barcode``,
  ``get_available_barcode_masks``, ``get_wkhtmltopdf_state``. Ver arriba.
- **``associated_view``** — busca la vista QWeb que usa el reporte.
  **Actualizado** (porte de ``ir_ui_view.py``):
  ``grep -rn "^class IrUiView\\b" src/`` → **1** clase. [PROVEN] Pero el
  método sigue sin portarse por una razón **distinta** de la que tenía: no le
  falta el modelo, le falta la **acción de ventana resuelta por ``xml_id``**
  (``self.env.ref('base.action_ui_view')``) que devuelve para que el cliente
  la abra — y eso depende de ``ir.model.data``, que existe pero nadie puebla.
- **``_search_model_id``** — implementa la búsqueda por modelo con el
  ``Domain`` de Odoo (``NEGATIVE_OPERATORS``, ``any!``, ``Domain.OR``). Es la
  mecánica de su motor de dominios; en Django la búsqueda equivalente es un
  ``filter`` del ORM y no necesita un método que la traduzca.
- **``retrieve_attachment`` completo** — el nombre del adjunto sale de
  ``safe_eval(self.attachment, {'object': record, 'time': time})``: una
  expresión Python almacenada. Mismo criterio que ``ir_rule.domain_force``
  (``api@020e965``) e ``ir_actions.server.code``: el campo se porta —es el
  dato— y **este archivo no lo evalúa**. Lo que sí se porta es la **consulta**,
  que es la otra mitad: ``find_attachment(record, attachment_name)`` recibe el
  nombre ya resuelto y busca el adjunto. Partirlo así deja utilizable la mitad
  que no depende del evaluador, en vez de perder las dos.
- **``get_paperformat_by_xmlid``** — resuelve un ``xml_id`` contra
  ``ir.model.data``, tabla que existe desde ``api@b618a6b`` pero que nadie
  puebla todavía. ``get_paperformat()`` sin ``xml_id`` **sí** se porta entera.
- **``_get_readable_fields``** — allowlist de campos que el cliente puede
  leer; aquí eso lo declara el ``Meta.fields`` explícito del serializer DRF.
- **``report_action`` / ``_action_configure_external_report_layout``** —
  devuelven diccionarios de acción que consume el cliente web de Odoo.
"""
import json
import logging
import subprocess
from pathlib import Path

from django.conf import settings

import fields
import models

from addons.base import report_catalog
from addons.base.models.ir_actions import IrActionsBase
from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.models.res_groups import ResGroups

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
#: Precedente del proyecto para la misma clase de llamada: ``Company`` y no
#: ``Tenant`` (``terminologia-l0-company.md``).
#:
#: **2. Sin ``html``.** No es un rename: es un formato que este árbol **no
#: produce**. Estaba en el enum sólo por copiar el catálogo ajeno — el mismo
#: defecto que el prefijo, un nivel más arriba: declarar como opción una
#: capacidad de la referencia, no nuestra. La referencia tiene **un** reporte
#: ``qweb-html`` (``stock.report_stock_rule``); si algún día se porta, hará
#: falta su renderizador, y el valor entra **con** él.
#:
#: Correspondencia para quien compare las dos tablas:
#: ``pdf`` ≙ ``qweb-pdf`` · ``text`` ≙ ``qweb-text`` · (sin análogo de
#: ``qweb-html``).
REPORT_TYPE_PDF = 'pdf'
REPORT_TYPE_TEXT = 'text'
REPORT_TYPE_CHOICES = [
    (REPORT_TYPE_PDF, 'PDF'),
    (REPORT_TYPE_TEXT, 'Texto'),
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
#: ``html`` no tiene entrada: exigiría un intermedio neutral que el colapso
#: composición+conversión de los helpers no deja construir (ver
#: ``report_catalog.py``). Su ausencia devuelve ``None``, no un error — mismo
#: contrato que ``:1150``.
RENDERER_BY_TYPE = {
    REPORT_TYPE_PDF: '_render_pdf',
    REPORT_TYPE_TEXT: '_render_text',
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

    model = fields.Char(
        max_length=255, db_index=True, verbose_name='Nombre del modelo',
        help_text='Modelo técnico sobre el que imprime. Char plano, mismo '
                  'criterio que ir_rule.model_name e ir_filters.model_id.',
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
    groups = fields.Many2many(
        ResGroups, blank=True, db_table='res_groups_report_rel',
        related_name='report_ids', verbose_name='Grupos',
        help_text='Odoo group_ids. Vacío = sin restricción por grupo. La '
                  'autorización efectiva sigue siendo por capacidad (DEC-11).',
    )
    multi = fields.Boolean(
        default=False, verbose_name='Sobre varios documentos',
        help_text='Marcado, la acción NO aparece en la barra lateral de un '
                  'formulario — es de lote.',
    )
    paperformat = fields.Many2one(
        ReportPaperformat, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='report_ids',
        verbose_name='Formato de papel',
        help_text='Odoo paperformat_id. Este related_name es el One2many que '
                  'report_paperformat.py dejó anotado como pendiente.',
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

    # --- Formato de papel -------------------------------------------------

    def get_paperformat(self, company=None):
        """``get_paperformat`` — el del reporte, o el de la compañía.

        La referencia lee ``self.env.company``; aquí la compañía la aporta el
        llamador, porque este archivo no conoce el contexto de la petición.
        """
        if self.paperformat_id:
            return self.paperformat
        return getattr(company, 'paperformat', None) if company else None

    # --- Adjunto ----------------------------------------------------------

    def find_attachment(self, record, attachment_name):
        """Mitad consultable de ``retrieve_attachment``.

        La fuente calcula ``attachment_name`` evaluando la expresión guardada
        en ``self.attachment``; ese evaluador **no se porta** (ver el docstring
        del módulo). El nombre llega ya resuelto y aquí se hace la búsqueda,
        que es la otra mitad y sí es portable.

        Devuelve el adjunto o ``None``.
        """
        if not attachment_name:
            return None
        return IrAttachment.objects.filter(
            name=attachment_name,
            res_model=self.model,
            res_id=record.pk,
        ).first()

    # --- Búsqueda ---------------------------------------------------------

    @classmethod
    def get_report_from_name(cls, report_name):
        """``_get_report_from_name`` — el reporte cuya plantilla se llama así."""
        return cls.objects.filter(report_name=report_name).first()

    @classmethod
    def valid_reports_for(cls, model_name, groups=()):
        """``get_valid_action_reports`` — reportes aplicables a un modelo.

        Un reporte **sin** grupos vale para todos; uno con grupos vale sólo si
        el usuario tiene alguno. Es la misma asimetría que ``ir.rule`` y
        ``ir.embedded.actions``: la lista vacía significa "sin restricción",
        no "nadie".

        No evalúa ``domain`` — filtrar por él es del llamador, que es quien
        tiene los registros.
        """
        group_ids = {getattr(group, 'pk', group) for group in groups}
        applicable = []
        for report in cls.objects.filter(model=model_name).prefetch_related(
                'groups'):
            declared = set(report.groups.values_list('pk', flat=True))
            if not declared or (declared & group_ids):
                applicable.append(report)
        return applicable

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

        :returns: tupla ``(contenido, extensión)`` — ``bytes`` para
            ``qweb-pdf``, ``str`` para ``qweb-text``. Misma forma que la
            referencia (``:1110``, ``:1119``).
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

        Aquí los pasos 3 y 5 ocurren juntos porque el helper hace ambos; el
        colapso está declarado en ``report_catalog.py``.
        """
        return run_helper(spec.helper, spec.builder(records, **ctx)), 'pdf'

    def _render_text(self, spec, records, ctx):
        """Salida de texto plano — el constructor la produce entera.

        Es el ``report_type`` de las etiquetas térmicas: en la referencia
        ``label_product_product``, ``label_lot_template`` y cinco más son
        ``qweb-text`` (medido: 7 registros en ``stock``, 1 en ``mrp``). ZPL es
        un lenguaje de impresora, así que producirlo es **componer texto** —
        no hace falta hardware ni para generarlo ni para probarlo.
        """
        return spec.builder(records, **ctx), 'txt'
