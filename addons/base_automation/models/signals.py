"""Dispatch de ``base.automation`` — reemplazo Django-nativo de
``_register_hook``/``_unregister_hook`` (ver la sección "Decisión de
mecanismo" del docstring de ``base_automation.py``).

Tres receptores GLOBALES (``sender=None``), conectados una única vez desde
``BaseAutomationConfig.ready()`` — no un patch por-modelo-por-regla como la
referencia. Cubren ``CREATE_TRIGGERS``/``WRITE_TRIGGERS`` (vía
``pre_save``/``post_save``) y ``on_unlink`` (vía ``pre_delete`` — no
``post_delete``: la fila debe existir todavía para evaluar su dominio,
igual que la referencia ejecuta las acciones ANTES de borrar).

El recálculo de un calculado almacenado no pasa por ``save()``: el volcado
escribe columnas sin señales (``_persist_columns``). Su contraparte es el
parche de ``_compute_field_value`` de la fuente (``make_compute_field_value``,
``base_automation.py:909-946``), que este módulo instala una vez sobre
``BaseModel`` con ``wrap_method``.

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
from contextlib import nullcontext

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from orm import registry
from orm.environments import Environment, env
from orm.method_chain import wrap_method
from orm.models import BaseModel

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
    return (
        sender in (BaseAutomation, BaseAutomationAction)
        or sender.__module__ == '__fake__'
        or sender._meta.app_label == 'migrations'
    )


@receiver(pre_save, dispatch_uid='base_automation.capture_old_values')
def _capture_old_values(sender, instance, **kwargs):
    """Captura el estado ANTES de escribir — ``old_values`` de
    ``_check_trigger_fields``. Sin esto, el ``post_save`` no puede saber
    qué campos cambiaron (Django no trae los valores previos)."""
    instance._base_automation_pre = None
    if _skip(sender) or instance.pk is None:
        instance._base_automation_old_values = None
        return
    with _record_environment(kwargs.get('using')):
        instance._base_automation_old_values = (
            sender.objects.filter(pk=instance.pk).values().first()
        )
        # ≙ ``make_write`` (``base_automation.py:884-889``): las reglas y su
        # precondición se leen ANTES de escribir; después, la base ya tiene
        # los valores nuevos.
        if _rules_table_exists(kwargs.get('using')):
            instance._base_automation_pre = {
                automation.pk: automation._filter_pre(sender, [instance.pk])
                for automation in BaseAutomation._get_actions(
                    _model_name(sender), WRITE_TRIGGERS)
            }


def _know_watched_models():
    """Llena el conjunto de modelos con reglas de escritura del registro de
    la base activa si aún no se sabe (``BaseAutomation._register_hook``)."""
    if getattr(env().registry, 'base_automation_write_models', None) is None:
        BaseAutomation._register_hook()


@receiver(post_save, dispatch_uid='base_automation.dispatch_create_write')
def _dispatch_create_write(sender, instance, created, **kwargs):
    if _skip(sender) or not _rules_table_exists(kwargs.get('using')):
        return
    with _record_environment(kwargs.get('using')):
        _know_watched_models()
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
                        sender, [instance.pk]
                    )
                else:
                    # Una regla que no existía antes de escribir no se
                    # procesa: la fuente fija las reglas antes de la
                    # escritura.
                    pre = getattr(instance, '_base_automation_pre', None)
                    pre_pks = (pre or {}).get(automation.pk)
                    if not pre_pks:
                        continue
                    pks, domain_post = automation._filter_post_export_domain(
                        sender, pre_pks
                    )
                if pks:
                    automation._process(
                        sender, pks, domain_post=domain_post,
                        old_values=old_values
                    )
            finally:
                processing.discard(key)


@receiver(pre_delete, dispatch_uid='base_automation.dispatch_unlink')
def _dispatch_unlink(sender, instance, **kwargs):
    """``pre_delete``, no ``post_delete`` — la referencia ejecuta las
    acciones ANTES de borrar (``make_unlink``: "check conditions... call
    original method" al final). Con ``post_delete`` la fila ya no existe y
    ``_filter_post`` (que re-consulta la base) siempre daría vacío."""
    if _skip(sender) or not _rules_table_exists(kwargs.get('using')):
        return
    with _record_environment(kwargs.get('using')):
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


#: Alias cuya tabla ``base_automation`` ya existe. Una vez creada no
#: desaparece en el proceso, así que basta medirla hasta verla.
_RULES_TABLE_SEEN = set()


def _rules_table_exists(using):
    """«Sin tabla ⇒ sin reglas» también para los modelos vivos.

    ``_skip`` cubre los modelos históricos de una migración; un
    ``ComputeStoredFields`` escribe con los modelos vivos dentro de
    ``migrate`` (``base.0105`` calcula ``ir.rule.global``), cuando en una base
    nueva la tabla de ``base_automation`` todavía no existe. La fuente nunca
    tiene el parche activo durante la carga (STEP 9 de ``load_modules``).
    Medido: ``make ci-multidb`` sobre ``b08a7da1`` con ``--create-db`` moría
    con ``relation "base_automation" does not exist``.
    """
    alias = using or DEFAULT_DB_ALIAS
    if alias in _RULES_TABLE_SEEN:
        return True
    connection = connections[alias]
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
    if BaseAutomation._meta.db_table in tables:
        _RULES_TABLE_SEEN.add(alias)
        return True
    return False


def _record_environment(using):
    """El entorno de la base donde se escribe la fila.

    La fuente consulta las automatizaciones, filtra y procesa con
    ``self.env`` del registro (``base_automation.py:909-1015``): el cursor de
    la base de la fila. Aquí la señal trae esa base en ``using``; sin entrar
    en ella, el enrutador resuelve por la empresa activa y, con varias bases
    y ninguna empresa, rechaza la consulta (ci-multidb ``5dc2e8c1``).
    """
    return Environment(using) if using else nullcontext()


def _compute_field_value(self, previous, field):
    """≙ ``make_compute_field_value`` (``base_automation.py:909-946``).

    Docstring de la fuente: *"Instanciate a compute_field_value method that
    processes automation rules"*, con la nota *"This is to catch updates made
    by field recomputations"*. La precondición y los valores viejos se leen
    antes del cómputo; después, la postcondición y ``_process``.

    Divergencia de mecanismo: la fuente filtra en memoria
    (``filtered_domain``) y aquí ``_records_matching_domain`` consulta la
    base, así que los campos calculados se vuelcan antes de la
    postcondición. La precondición se evalúa sin el contexto
    ``changed_fields`` (``:927-928``): ``_filter_pre`` de este árbol no lee
    contexto.
    """
    model = type(self)
    stored_fnames = [f.name for f in registry.field_computed[field]
                     if f.store]
    # El conjunto lo fija ``BaseAutomation._register_hook`` al cargar el
    # registro: un modelo sin reglas de escritura no consulta la base, como
    # el modelo que la fuente no parchea.
    watched = getattr(self.env.registry, 'base_automation_write_models',
                      None) or ()
    if not stored_fnames or _model_name(model) not in watched:
        return previous(field)
    using = self.env.db_alias
    if _skip(model) or not _rules_table_exists(using):
        return previous(field)
    with _record_environment(using):
        automations = BaseAutomation._get_actions(
            _model_name(model), WRITE_TRIGGERS)
        records = self.filtered(lambda record: record.id)
        if not (automations and records):
            previous(field)
            return True
        ids = list(records.ids)
        pre = {automation: automation._filter_pre(model, ids)
               for automation in automations}
        old_values = {
            row['pk']: row
            for row in model.objects.filter(pk__in=ids).values(
                'pk', *stored_fnames)
        }
        previous(field)
        records.flush_recordset(stored_fnames)
        processing = _processing_set()
        for automation in automations:
            pending = [pk for pk in pre[automation]
                       if (automation.pk, pk) not in processing]
            if not pending:
                continue
            keys = {(automation.pk, pk) for pk in pending}
            processing.update(keys)
            try:
                pks, domain_post = automation._filter_post_export_domain(
                    model, pending)
                if pks:
                    automation._process(model, pks, domain_post=domain_post,
                                        old_values=old_values)
            finally:
                processing.difference_update(keys)
    return True


wrap_method(BaseModel, '_compute_field_value', _compute_field_value)
