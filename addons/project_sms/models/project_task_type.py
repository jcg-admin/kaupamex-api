"""``project.task.type`` — la plantilla de SMS de la etapa.

Adaptación de Odoo project_sms/models/project_task_type.py
(odoo-tools, odoo19c:, LGPL-3, 12 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo (medido por AST)
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``sms_template_id`` (Many2one ``sms.template``, ``:10-12``)
     - portado — columna real (DIVERGENCIA única)

Divergencia declarada
======================

**El ``domain=[('model', '=', 'project.task')]`` cae.** El ``SmsTemplate``
local (``addons/sms/models/sms_template.py``) no porta el ancla
``model``/``ir.model`` de la referencia — es plantilla de texto plano con
placeholders ``{campo}`` — así que no hay eje por el que acotar el dominio.
Si ``sms.template`` gana el ancla por modelo, la restricción se declara en
el serializer DRF que edite la etapa.
"""
import fields
import models

from orm.model_classes import extend_model


def apply_project_sms_project_task_type_extensions():
    """Cuelga sobre ``project.task.type`` la plantilla de SMS — ≙
    ``_inherit``. Se invoca desde ``ProjectSmsConfig.ready()``."""
    extend_model(
        'project', 'ProjectTaskType',
        campos={
            'sms_template': fields.Many2one(
                'sms.SmsTemplate', null=True, blank=True,
                on_delete=models.SET_NULL, related_name='task_stages',
                verbose_name='Plantilla de SMS',
                help_text='Odoo sms_template_id — si está definida, al '
                          'llegar una tarea a esta etapa se envía un SMS '
                          'al cliente (su domain por modelo no se porta — '
                          'ver la divergencia del docstring del módulo).',
            ),
        },
    )
