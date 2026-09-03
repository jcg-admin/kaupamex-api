r"""``ir.autovacuum`` — barrido periódico de los métodos ``@api.autovacuum``.

Adaptación fiel de ``odoo/addons/base/models/ir_autovacuum.py``
(``odoo-tools@bf077302``, ``odoo19c:``). Es el colector que recorre el
registro de modelos buscando métodos decorados con ``@api.autovacuum`` y los
llama a todos, sin que cada uno necesite su propio cron.

Se preservan las tres decisiones de diseño de la referencia, porque cada una
resuelve un problema real y no son intercambiables:

1. **Barajar el orden en cada corrida** (``random.shuffle``). El comentario
   original lo dice: evita que un método que siempre falla o siempre tarda
   deje sin correr a los que van detrás.
2. **Cola con reencolado** (``collections.deque``). Un método puede devolver
   ``(hechos, restantes)``; si quedan restantes, vuelve al frente de la cola
   para continuar donde se quedó. Así un barrido grande avanza por lotes en
   vez de bloquear la corrida entera.
3. **Aislar el fallo de cada método** (``try/except`` + ``rollback``). Una
   excepción en uno no aborta el resto: se registra y se sigue. Sin esto el
   primer método roto cancelaría todos los demás.

**Divergencias, medidas.**

- ``self.env.is_admin()`` de la referencia → verificación de capacidad en el
  llamador (DEC-11). La otra mitad de su doble check —
  ``context.get('cron_id')``— **sí** se porta con su forma: se lee de
  ``orm.environments.get_context()``, el espejo de ``env.context``, que el
  runner del cron puebla con ``context_scope``. La adaptación anterior lo
  declaraba como parámetro explícito y era **inalcanzable**: ``_callback``
  invoca ``method()`` sin argumentos, así que el barrido levantaba
  ``PermissionError`` en toda corrida programada. Ver :ref:`h-api-752`.
- ``self.env.values()`` (el registro de modelos de Odoo) → ``apps.get_models()``
  de Django, que es el registro equivalente.
- ``func(model)`` → ``func()``. La referencia obtiene la función **sin ligar**
  de ``model.__class__`` y por eso le pasa el modelo como primer argumento.
  Aquí los métodos de barrido son ``classmethod`` — operan sobre la tabla
  entera, no sobre una fila—, así que ``inspect.getmembers`` los devuelve ya
  ligados a su clase y llamarlos con un argumento extra reventaría.
- ``self.env['ir.cron']._commit_progress()`` **SÍ se porta**, desde este pase.
  Este bullet decía que *"pertenece al runner del cron, que ``ir_cron.py``
  declara explícitamente como diferido"*; medido, ``ir_cron.py:62`` dice **"El
  runner del cron — PORTADO COMPLETO (2026-08-26)"** y ``_commit_progress``
  está en ``:1130``. Ver :ref:`h-api-984`.
- ``_gc_orm_signaling`` **SÍ se porta, desde este pase**. Este bullet decía
  *"no se porta TODAVÍA … no hay tablas que barrer; portarlo sería declarar una
  capacidad inexistente. Construir esas tablas es la tarea #256, y este método
  entra con ellas"*. Las tablas existen: las crea
  ``base/migrations/0085_orm_signaling_tables.py`` y las consume el eje de
  señalización de ``orm.registry`` (``setup_signaling``, ``get_sequences``,
  ``check_signaling``, ``signal_changes``). La declinación era correcta y su
  condición de cierre se cumplió, así que el método entra con ellas.

  El cero que la declinación citaba —el patrón anclado de ``db_table`` y de las
  dos declaraciones del eje— hoy mide **2**: las dos ``def`` de
  ``orm/registry.py``. Ese ascenso es exactamente lo que la cita prometía
  observar cuando el mecanismo llegara, así que la cita **se retira** en vez de
  actualizarse: un reclamo de cero cuya condición se cumplió ya no mide nada.

  Lo delató el gate ``check_stale_zero_claims``, no una relectura — un reclamo
  de cero es una afirmación fechada y el gate la re-ejecuta, que es la única
  razón por la que este método no se quedó declinado tras construir sus tablas.
"""
import collections
import inspect
import logging
import random
import time

from django.apps import apps
from django.db import connection
from django.db import models as django_models
from django.db import transaction

from addons.base.models.ir_cron import IrCron
from orm.decorators import autovacuum
from orm.environments import get_context
from orm.registry import signaling_table_names
from tools.sql import SQL

_logger = logging.getLogger(__name__)


def is_autovacuum(func):
    """¿``func`` es un método de autovacuum? — verbatim de la referencia."""
    return callable(func) and getattr(func, '_autovacuum', False)


class IrAutovacuum(django_models.Model):
    """Colector del decorador ``@api.autovacuum`` (``ir.autovacuum``).

    En la referencia es un ``AbstractModel`` — un modelo **sin tabla** que sólo
    aporta comportamiento, pero que **sí está registrado por nombre**: por eso
    su cron lo apunta con ``model_id ref="model_ir_autovacuum"``
    (``odoo19c: odoo/addons/base/data/ir_cron_data.xml:5``).

    Aquí eso se traduce a un modelo concreto con ``Meta.managed = False``, que
    es el mapeo declarado de su ``_auto`` (``atributos-de-clase-de-modelo.md``):
    Django lo registra —``apps.get_model('base', 'IrAutovacuum')`` resuelve— y
    no le crea tabla. **Era una clase plana**, y esa forma lo hacía inalcanzable
    para el runner del cron, que resuelve su objetivo con ``apps.get_model``.
    Ver :ref:`h-api-752`.
    """

    _name = 'ir.autovacuum'
    _description = 'Automatic Vacuum'

    class Meta:
        managed = False
        db_table = 'ir_autovacuum'
        verbose_name = 'Barrido automático'
        verbose_name_plural = 'Barridos automáticos'

    @staticmethod
    def _collect_methods():
        """Todos los ``(modelo, atributo, función)`` decorados con autovacuum."""
        return [
            (model, attr, func)
            for model in apps.get_models()
            for attr, func in inspect.getmembers(model, is_autovacuum)
        ]

    @classmethod
    def _run_vacuum_cleaner(cls):
        """Limpieza completa: llama con seguridad a cada método decorado.

        **``classmethod`` y con guion bajo**, las dos por contrato ajeno:

        - el runner del cron invoca ``getattr(apps.get_model(m), método)()``
          sin argumentos (``ir_cron.py:_callback``), así que un método de
          instancia no se puede despachar;
        - la fuente lo declara ``_run_vacuum_cleaner`` y el guion bajo **es**
          el contrato (``porte-completo-no-parcial.md``). Se llamaba
          ``run_vacuum_cleaner``, que promovía a API pública lo que la fuente
          reservó.

        El ``cron_id`` sale del contexto —``get_context()``, el espejo de
        ``env.context``— que ``_callback`` puebla con ``context_scope``. Sin él
        el barrido se niega a correr, igual que la referencia.
        """
        if not get_context().get('cron_id'):
            raise PermissionError(
                '_run_vacuum_cleaner sólo corre desde el cron (falta cron_id '
                'en el contexto)'
            )

        all_methods = cls._collect_methods()
        # Barajar en cada corrida: evita que un método bloqueante deje
        # siempre sin correr a los que van detrás (comentario de la fuente).
        random.shuffle(all_methods)
        queue = collections.deque(all_methods)
        while queue:
            model, attr, func = queue.pop()
            _logger.debug('Llamando %s.%s()', model, attr)
            try:
                start_time = time.monotonic()
                # Ligado a su clase (classmethod) — sin argumento de modelo.
                result = func()
                # ≙ ``self.env['ir.cron']._commit_progress()`` (``:50``).
                # Va AQUI, entre la llamada y el reparto del resultado: un
                # metodo que revienta salta al ``except`` sin pasar por aqui,
                # y su trabajo a medias se descarta. Comitearlo antes de
                # llamar, o en un ``finally``, asentaria ese trabajo parcial.
                IrCron._commit_progress()
                if isinstance(result, tuple) and len(result) == 2:
                    func_done, func_remaining = result
                    _logger.debug(
                        '%s.%s  barrió %r registros, restantes %r',
                        model, attr, func_done, func_remaining,
                    )
                    if func_remaining:
                        queue.appendleft((model, attr, func))
                _logger.debug(
                    '%s.%s  tomó %.2fs', model, attr, time.monotonic() - start_time)
            except Exception:
                # Un método roto no cancela el resto — se registra y se sigue.
                _logger.exception('Falló %s.%s()', model, attr)
                transaction.rollback()


    @classmethod
    @autovacuum
    def _gc_orm_signaling(cls):
        """Poda las tablas de señalización — ≙ ``:64-75``.

        Comentario de la fuente, verbatim: *"keep the last 10 entries for each
        signal, and all entries from the last hour. This keeps the signaling
        tables small enough for performance, but also gives a useful glimpse
        into the recent signaling history, including the timestamps of the
        increments"*. Las dos condiciones se conjugan con ``AND``: una fila
        sobrevive si está entre las diez últimas **o** si es de la última hora.

        Las tablas son de sólo-inserción y cada invalidación añade una fila, así
        que sin este barrido crecen sin techo — y son las que
        ``Registry.get_sequences`` lee en **cada** petición con un ``max(id)``
        por tabla.

        **Divergencias de puerta, no de contenido:**

        - La lista de tablas sale de ``signaling_table_names()``, que ya la
          declara una vez para el eje y la migración; la fuente reconstruye
          ``['registry', *_CACHES_BY_KEY]`` aquí por tercera vez.
        - El cursor sale de ``connection`` y no de ``self.env.cr``: aquí el
          método es ``classmethod`` por el contrato del runner del cron (ver el
          docstring de :meth:`_run_vacuum_cleaner`), así que no hay ``self`` del
          que colgar un entorno.
        """
        with connection.cursor() as cr:
            for table in signaling_table_names():
                query = SQL(
                    "DELETE FROM %s WHERE id < (SELECT max(id)-9 FROM %s) "
                    "AND date < NOW() - interval '1 hours'",
                    SQL.identifier(table), SQL.identifier(table),
                )
                cr.execute(query.code, query.params)
