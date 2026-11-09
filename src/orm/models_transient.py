"""``TransientModel`` — fiel a ``odoo19c: odoo/orm/models_transient.py``.

Un ``TransientModel`` es un modelo **persistente temporal**: se escribe a una
tabla real y se recolecta (*vacuum*) periódicamente. Sirve a wizards y
asistentes de un solo uso.

**Tiene tabla, y eso es la mitad que faltaba.** La fuente lo declara sin
ambigüedad —``_auto = True``, *"automatically create database backend"*
(``:18``)— y su recolección la hace ``_transient_vacuum``, decorado con
``@api.autovacuum``. La versión anterior de este módulo declaraba
``Meta.managed = False`` con el razonamiento de que *"un wizard normalmente NO
necesita tabla: su estado vive en la sesión/request"*, y dejaba escrito que la
política de vacuum se anclaría *"cuando el wizard exista"*.

Ese día llegó: ``ServerActionHistoryWizard``
(``addons/base/models/ir_actions.py``)
se crea y se consulta, y sin tabla su suite fallaba con
``relation "server_action_history_wizard" does not exist``. El razonamiento de
la sesión no era una divergencia de mecanismo sino una apuesta sobre el futuro,
y se perdió. Ahora la base declara tabla, como la fuente, y el barrido que la
mantiene acotada está portado abajo.

Los tres concretos que declaran ``managed = False`` en su **propio** ``Meta``
—``IrDemo``, ``BaseEnableProfilingWizard`` y ``ResConfig``— lo conservan: cada
uno trae su razón escrita y ninguna se midió en este pase. Su veredicto es la
tarea **#201**.

**El ``ir.autovacuum`` de este árbol ya recoge el método.** Su colector barre
el
registro buscando ``@api.autovacuum``
(``addons/base/models/ir_autovacuum.py``),
así que ``_transient_vacuum`` entra en su pasada sin cablear nada más.
"""

import datetime

from django.db import router

from orm.decorators import autovacuum
from orm.fields_temporal import (
    TransactionClockSaveMixin,
    TransactionDateTimeField,
    transaction_now,
)
from orm.models import Model
from tools import config
from tools.constants import GC_UNLINK_LIMIT
from tools.func import lazy_classproperty

#: Ninguna fila usada en los últimos cinco minutos se borra — ≙ ``:77``.
MINIMUM_IDLE_SECONDS = 300


class TransientModel(TransactionClockSaveMixin, Model):
    """
    Modelo transitorio (wizard/asistente) — ≙ ``TransientModel`` (``:10-33``).

    Docstring de la fuente, verbatim: *"Model super-class for transient
    records,
    meant to be temporarily persistent, and regularly vacuum-cleaned."*

    La segunda mitad de ese docstring —*"A TransientModel has a simplified
    access rights management, all users can create new records, and may only
    access the records they created"*— **no tiene implementación en la
    referencia**: medido en ``odoo-tools@abe4040ec1``, ``ir_rule.py`` no
    contiene ninguna regla sobre ``create_uid`` y ``ir_model.py`` sólo
    consulta ``_transient`` al reflejar el modelo (``:434,488``). El acceso a
    un transitorio pasa, allá y aquí, por ``ir.model.access`` y las reglas
    de fila; no hay contrato de creador que portar. Diseño:
    ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/``
    ``transient-model-clock.md``.
    """

    class Meta:
        abstract = True

    #: ≙ las columnas que ``_log_access`` añade (``odoo19c:
    #: odoo/orm/models.py:296``), que la fuente exige a todo transitorio
    #: (``odoo/orm/model_classes.py:217-220``): sin fecha de escritura no hay
    #: limpieza por antigüedad. Mismos nombres que ``TimeStampedModel``, la
    #: convención del árbol para ``create_date``/``write_date``. Su valor es
    #: el reloj de la transacción, ``cr.now()`` (``models.py:4801-4805``).
    created_at = TransactionDateTimeField(auto_now_add=True, null=True)
    updated_at = TransactionDateTimeField(auto_now=True, null=True)

    #: ≙ ``:18-21``. ``_auto``: crea tabla; ``_register``: no se registra
    #: como modelo propio, sólo se hereda; ``_abstract``: no es abstracto.
    #: Aquí la tabla la decide ``Meta.abstract`` de Django; los tres se
    #: declaran porque ``is_abstract`` (``orm/model_classes.py``) y quien lea
    #: la cabecera los consultan como en la fuente.
    _auto = True
    _register = False
    _abstract = False
    _transient = True
    #: ≙ ``:24-27``: el tope de filas y la vida ociosa en horas salen de la
    #: configuración al primer acceso, no al importar. Por defecto ``0`` (sin
    #: tope) y ``1.0`` horas (``odoo19c: odoo/tools/config.py:436-443``).
    _transient_max_count = lazy_classproperty(
        lambda _: int(config.osv_memory_count_limit()))
    _transient_max_hours = lazy_classproperty(
        lambda _: float(config.transient_age_limit()))

    @classmethod
    @autovacuum
    def _transient_vacuum(cls):
        """
        Limpia los registros transitorios — ≙ ``_transient_vacuum``
        (``:29-66``).

        Desaloja filas viejas de la tabla cuando se alcanza alguna de las dos
        condiciones, ``_transient_max_count`` o ``_transient_max_hours``. Si
        ninguna está declarada, no borra nada: el cero significa *ilimitado*,
        no *todo*.

        Devuelve ``(nombre, quedan_mas)`` como la fuente: el método lo
        comparten
        todos los transitorios, así que el nombre es lo que permite al log
        decir
        cuál se barrió, y la bandera si hace falta otra pasada.
        """
        has_remaining = False
        if cls._transient_max_hours:
            has_remaining |= cls._transient_clean_rows_older_than(
                cls._transient_max_hours * 60 * 60
            )
        if cls._transient_max_count:
            has_remaining |= cls._transient_clean_old_rows(
                cls._transient_max_count
            )
        return getattr(cls, '_name', cls._meta.label), has_remaining

    @classmethod
    def _transient_clean_old_rows(cls, max_count):
        """≙ ``_transient_clean_old_rows`` (``:67-73``) — desalojo por conteo.

        La fuente cuenta con ``SELECT count(*)`` crudo para saltarse el ORM;
        aquí ``objects.count()`` emite ese mismo ``SELECT`` y no hay motivo
        para
        escribirlo a mano.

        Cuando se pasa del tope se borra por **antigüedad** con el mínimo de
        cinco minutos, no sólo el excedente. Es deliberado en la fuente y su
        docstring lo explica: *"Not just 2, otherwise each addition would
        immediately cause the maximum to be reached again."*
        """
        if cls.objects.count() > max_count:
            return cls._transient_clean_rows_older_than(MINIMUM_IDLE_SECONDS)
        return False

    @classmethod
    def _transient_clean_rows_older_than(cls, seconds):
        """
        ≙ ``_transient_clean_rows_older_than`` (``:75-83``) — por antigüedad.

        El piso de cinco minutos es de la fuente y protege lo que se está
        usando: una fila recién escrita es el formulario que alguien tiene
        abierto.

        ``write_date`` de allá es aquí ``updated_at`` (``TimeStampedModel``);
        el
        transitorio que no lo declare cae a ``created_at``, y si tampoco lo
        tiene no se barre por antigüedad — su tope será el de conteo.
        """
        seconds = max(seconds, MINIMUM_IDLE_SECONDS)
        # ``self.env.cr.now()`` (``:78``): el reloj de la transacción, no el
        # de pared.
        cutoff = (transaction_now(router.db_for_write(cls))
                  - datetime.timedelta(seconds=seconds))
        names = {f.name for f in cls._meta.get_fields()}
        stamp = (
            'updated_at'
            if 'updated_at' in names
            else 'created_at' if 'created_at' in names else None
        )
        if stamp is None:
            return False
        ids = list(
            cls.objects.filter(**{f'{stamp}__lt': cutoff}).values_list(
                'pk', flat=True
            )[:GC_UNLINK_LIMIT]
        )
        if ids:
            cls.objects.filter(pk__in=ids).delete()
        return len(ids) == GC_UNLINK_LIMIT
