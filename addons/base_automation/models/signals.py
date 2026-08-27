"""Dispatch de ``base.automation`` — reemplazo Django-nativo de
``_register_hook``/``_unregister_hook`` (ver la sección "Decisión de
mecanismo" del docstring de ``base_automation.py``).

Tres receptores GLOBALES (``sender=None``), conectados una única vez desde
``BaseAutomationConfig.ready()`` — no un patch por-modelo-por-regla como la
referencia. Cubren ``CREATE_TRIGGERS``/``WRITE_TRIGGERS`` (vía
``pre_save``/``post_save``) y ``on_unlink`` (vía ``pre_delete`` — no
``post_delete``: la fila debe existir todavía para evaluar su dominio,
igual que la referencia ejecuta las acciones ANTES de borrar).

Triggers NO conectados aquí (bloqueados, ver docstring de
``base_automation.py``): ``on_change`` (sin motor de onchange),
``on_message_received``/``on_message_sent`` (``MailThread.message_post``
no emite señal enganchable sin tocar ``addons/mail/``).

Guarda de reentrancia
======================

Una acción ejecutada por una automatización puede escribir sobre el MISMO
modelo que la disparó (p. ej. una acción ``on_write`` que vuelve a
``save()`` el registro). Sin guarda, eso reentra el receptor y puede
recursar sin fin — el equivalente de lo que ``__action_done`` evita en la
referencia (marca qué ``(regla, registro)`` ya se procesó en la cadena de
llamadas activa). Aquí el equivalente es un ``set`` en un
``threading.local()``: se registra ``(automation_pk, pk)`` al entrar a
``_process`` y se limpia al salir; un segundo intento del mismo par en la
misma cadena de llamadas se salta.
"""
import threading

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from addons.base_automation.models.base_automation import (
    CREATE_TRIGGERS,
    WRITE_TRIGGERS,
    BaseAutomation,
    BaseAutomationAction,
)

_local = threading.local()


def _processing_set():
    if not hasattr(_local, 'processing'):
        _local.processing = set()
    return _local.processing


def _model_name(sender):
    """``app_label.ModelName`` — mismo formato que ``IrModel.model``
    (ver ``django_model`` property, ``src/addons/base/models/ir_model.py``)."""
    return f'{sender._meta.app_label}.{sender.__name__}'


def _skip(sender):
    """No disparar sobre los modelos propios de este addon — evita ruido
    y una clase de reentrancia trivial (una acción que reconfigura una
    regla no debe re-disparar reglas).

    Tampoco sobre modelos históricos de migraciones (``__fake__``): un
    ``save()`` dentro de una data migration dispararía ``_get_actions``
    contra la tabla ``base_automation`` cuando puede no existir aún —
    medido: ``migrate`` de un despliegue limpio revienta con ``relation
    "base_automation" does not exist``. La referencia no tiene este caso:
    sus parches se instalan *exactamente una vez* al terminar de cargar el
    registro — STEP 9 de ``odoo19c: odoo/modules/loading.py:588-594``,
    posterior a la instalación de módulos — y la re-instalación en runtime
    (``_update_registry``) va gateada por ``self.env.registry.ready``
    (``base_automation.py:675``). Nunca hay parche activo durante la
    carga/migración, así que «sin tabla ⇒ sin reglas» es la traducción fiel.

    Ni sobre el bookkeeping del propio ``migrate``: cada fila que el
    ``MigrationRecorder`` inserta en ``django_migrations`` es un ``save()``
    normal (``recorder.py:102``) y disparaba la consulta — es el traceback
    medido del ``ProgrammingError``. Su ``app_label`` es ``migrations``."""
    return (sender in (BaseAutomation, BaseAutomationAction)
            or sender.__module__ == '__fake__'
            or sender._meta.app_label == 'migrations')


@receiver(pre_save, dispatch_uid='base_automation.capture_old_values')
def _capture_old_values(sender, instance, **kwargs):
    """Captura el estado ANTES de escribir — ``old_values`` de
    ``_check_trigger_fields``. Sin esto, el ``post_save`` no puede saber
    qué campos cambiaron (Django no trae los valores previos)."""
    if _skip(sender) or instance.pk is None:
        instance._base_automation_old_values = None
        return
    instance._base_automation_old_values = (
        sender.objects.filter(pk=instance.pk).values().first())


@receiver(post_save, dispatch_uid='base_automation.dispatch_create_write')
def _dispatch_create_write(sender, instance, created, **kwargs):
    if _skip(sender):
        return
    model_name = _model_name(sender)
    triggers = CREATE_TRIGGERS if created else WRITE_TRIGGERS
    automations = BaseAutomation._get_actions(model_name, triggers)
    if not automations:
        return

    old_row = getattr(instance, '_base_automation_old_values', None)
    old_values = {instance.pk: old_row} if old_row is not None else None
    processing = _processing_set()

    for automation in automations:
        key = (automation.pk, instance.pk)
        if key in processing:
            continue
        processing.add(key)
        try:
            if created:
                pks, domain_post = automation._filter_post_export_domain(
                    sender, [instance.pk])
            else:
                pre_pks = automation._filter_pre(sender, [instance.pk])
                if not pre_pks:
                    continue
                pks, domain_post = automation._filter_post_export_domain(
                    sender, pre_pks)
            if pks:
                automation._process(
                    sender, pks, domain_post=domain_post, old_values=old_values)
        finally:
            processing.discard(key)


@receiver(pre_delete, dispatch_uid='base_automation.dispatch_unlink')
def _dispatch_unlink(sender, instance, **kwargs):
    """``pre_delete``, no ``post_delete`` — la referencia ejecuta las
    acciones ANTES de borrar (``make_unlink``: "check conditions... call
    original method" al final). Con ``post_delete`` la fila ya no existe y
    ``_filter_post`` (que re-consulta la base) siempre daría vacío."""
    if _skip(sender):
        return
    model_name = _model_name(sender)
    automations = BaseAutomation._get_actions(model_name, ['on_unlink'])
    if not automations:
        return
    processing = _processing_set()
    for automation in automations:
        key = (automation.pk, instance.pk)
        if key in processing:
            continue
        processing.add(key)
        try:
            pks = automation._filter_post(sender, [instance.pk])
            if pks:
                automation._process(sender, pks)
        finally:
            processing.discard(key)
