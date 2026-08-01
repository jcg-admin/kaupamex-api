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

Consecuencia para ``report_type``: las tres claves de la referencia
(``qweb-html`` / ``qweb-pdf`` / ``qweb-text``) **se conservan verbatim**
aunque el renderizador difiera. Renombrarlas a algo "más nuestro" rompería la
correspondencia con la referencia sin ganar nada, y el día que se conecte el
render habría que deshacerlo.

Qué NO se porta, con su medición
================================

- **Todo el motor**: ``_build_wkhtmltopdf_args``, ``_run_wkhtmltopdf``,
  ``_run_wkhtmltoimage``, ``_prepare_html``, ``_render_qweb_pdf``,
  ``_render_qweb_html``, ``_render_qweb_text``, ``_render_template``,
  ``_merge_pdfs``, ``_get_rendering_context``, ``barcode``,
  ``get_available_barcode_masks``, ``get_wkhtmltopdf_state``. Ver arriba.
- **``associated_view``** — busca la vista QWeb que usa el reporte. Medido:
  ``grep -rn "^class IrUiView\\b" src/`` → **0** clases; ``ir_ui_view.py`` es
  archivo aparte de la referencia y sigue pendiente.
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
import logging

import fields
import models

from addons.base.models.ir_actions import IrActionsBase
from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.models.res_groups import ResGroups

_logger = logging.getLogger(__name__)

#: ``report_type`` — las tres claves de la referencia, verbatim. Se conservan
#: aunque el renderizador de este árbol sea otro; ver el docstring del módulo.
REPORT_TYPE_CHOICES = [
    ('qweb-html', 'HTML'),
    ('qweb-pdf', 'PDF'),
    ('qweb-text', 'Texto'),
]

#: ``type`` por defecto de esta acción.
ACTION_TYPE = 'ir.actions.report'
#: ``binding_type`` por defecto — aparece como "Imprimir", no como "Acción".
BINDING_TYPE_REPORT = 'report'


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
        max_length=16, choices=REPORT_TYPE_CHOICES, default='qweb-pdf',
        verbose_name='Tipo de reporte',
        help_text='Claves verbatim de la referencia; el renderizador de este '
                  'árbol es otro (libharu, ADR-017).',
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
