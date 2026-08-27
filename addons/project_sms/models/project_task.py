"""``project.task`` — el SMS al cliente cuando la tarea cambia de etapa.

Adaptación de Odoo project_sms/models/project_task.py
(odoo-tools, odoo19c:, LGPL-3, 30 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 métodos (medido por AST)
=======================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``_send_sms`` (``:10-16``)
     - método verbatim (divergencias 1-3)
   * - ``create`` (``:19-22``)
     - receptor ``post_save`` con ``created=True`` (divergencia 4)
   * - ``write`` (``:24-30``)
     - par de receptores ``pre_save``/``post_save`` (divergencia 4)

Divergencias declaradas
========================

1. **``task.partner_id`` no existe en la tarea local** — el addon
   ``project`` de este árbol puso el cliente en el proyecto
   (``project/models/project_project.py``: ``partner``, help_text "Odoo
   partner_id"); la condición y el destinatario se leen de
   ``task.project.partner`` (un usuario; su teléfono sale de la propiedad
   ``phone`` de ``base.ResUsers``, que delega en su partner).
2. **``not task.is_template``** cae — la maquinaria de tareas plantilla de
   la referencia no está portada en ``project`` (medido: 0 hits de
   ``is_template`` en ``addons/project/``); no hay plantillas que excluir.
3. **``_message_sms_with_template``/``sudo()``** — el mixin SMS de
   ``mail.thread`` no está portado; el envío se materializa creando el
   ``SmsSms`` con el cuerpo renderizado (mismo criterio que
   ``sale_sms/models/sale_order_sms_confirmation.py::send_for``). Sin
   usuario ambiente no hay ``sudo`` que aplicar.
4. **``create``/``write`` → señales** — sin ``vals`` dict, "cambió la
   etapa" se mide comparando contra el valor previo en BD (``pre_save`` lo
   captura en la instancia) y el envío corre en ``post_save`` — después
   del guardado, la misma ventana que el ``super()``-primero de la
   referencia (mismo patrón que ``hr_fleet/models/employee.py``).
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from addons.project.models.project_task import ProjectTask
from addons.sms.models import SmsSms
from orm.model_classes import extend_model


def _send_sms(self):
    """≙ ``_send_sms`` (``:10-16``) — crea el SMS de aviso al cliente del
    proyecto si la etapa actual tiene plantilla. Devuelve el ``SmsSms``
    creado o ``None`` (condición no cumplida)."""
    if self.stage_id is None or self.project_id is None:
        return None
    template = self.stage.sms_template
    partner = self.project.partner
    if template is None or partner is None:
        return None
    number = partner.phone
    if not number:
        return None
    body = template.render({
        'task': self.name or '',
        'stage': self.stage.name or '',
        'project': self.project.name or '',
    })
    return SmsSms.objects.create(number=number, body=body)


@receiver(pre_save, sender=ProjectTask,
          dispatch_uid='project_sms.task_pre_save_capture_stage')
def _task_pre_save(sender, instance, **kwargs):
    """La mitad previa del ``write`` de la referencia (``:24-30``) —
    captura la etapa previa para que ``post_save`` detecte el cambio."""
    instance._project_sms_old_stage_id = None
    if instance.pk is not None:
        instance._project_sms_old_stage_id = (
            sender.objects.filter(pk=instance.pk)
            .values_list('stage_id', flat=True).first()
        )


@receiver(post_save, sender=ProjectTask,
          dispatch_uid='project_sms.task_post_save_send_sms')
def _task_post_save(sender, instance, created, **kwargs):
    """≙ ``create`` (``:19-22``) + la mitad posterior del ``write``
    (``:24-30``): envía el SMS al crear la tarea y al cambiar su etapa."""
    if created:
        instance._send_sms()
        return
    old_stage_id = getattr(instance, '_project_sms_old_stage_id', None)
    if instance.stage_id != old_stage_id:
        instance._send_sms()


def apply_project_sms_project_task_extensions():
    """Cuelga sobre ``project.task`` el envío de SMS por etapa — ≙
    ``_inherit``. Se invoca desde ``ProjectSmsConfig.ready()``. Los
    receptores de señal de arriba se conectan al importar este módulo
    (``ready()`` ya lo importa una vez; ``dispatch_uid`` los hace
    idempotentes)."""
    extend_model(
        'project', 'ProjectTask',
        metodos={
            '_send_sms': _send_sms,
        },
    )
