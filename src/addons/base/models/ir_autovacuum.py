"""``ir.autovacuum`` — barrido periódico de los métodos ``@api.autovacuum``.

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

- ``self.env.is_admin()`` + ``context.get('cron_id')`` de la referencia →
  parámetro ``cron_id`` explícito y verificación de capacidad en el llamador
  (DEC-11). La referencia usa ese doble check para negarse a correr fuera del
  cron; aquí ``cron_id`` cumple el mismo papel y su ausencia levanta
  ``PermissionError``.
- ``self.env.values()`` (el registro de modelos de Odoo) → ``apps.get_models()``
  de Django, que es el registro equivalente.
- ``func(model)`` → ``func()``. La referencia obtiene la función **sin ligar**
  de ``model.__class__`` y por eso le pasa el modelo como primer argumento.
  Aquí los métodos de barrido son ``classmethod`` — operan sobre la tabla
  entera, no sobre una fila—, así que ``inspect.getmembers`` los devuelve ya
  ligados a su clase y llamarlos con un argumento extra reventaría.
- ``self.env['ir.cron']._commit_progress()`` **no se porta**: pertenece al
  *runner* del cron, que ``ir_cron.py`` declara explícitamente como diferido
  (*"el runner del cron — DIFERIDO"*). Cuando ese runner exista, esta llamada
  entra con él.
- ``_gc_orm_signaling`` **no se porta**: barre las tablas
  ``orm_signaling_<señal>`` del invalidador de caché multi-proceso de Odoo.
  Medido con ``grep -rl orm_signaling src/ | grep -v ir_autovacuum.py`` → **0**
  archivos (el filtro excluye esta propia mención). No hay tablas que barrer;
  portarlo sería declarar una capacidad inexistente.
"""
import collections
import inspect
import logging
import random
import time

from django.apps import apps
from django.db import transaction

_logger = logging.getLogger(__name__)


def is_autovacuum(func):
    """¿``func`` es un método de autovacuum? — verbatim de la referencia."""
    return callable(func) and getattr(func, '_autovacuum', False)


class IrAutovacuum:
    """Colector del decorador ``@api.autovacuum`` (``ir.autovacuum``).

    En la referencia es un ``AbstractModel`` — un modelo sin tabla que sólo
    aporta comportamiento. Aquí es una clase plana por la misma razón: no
    tiene columnas, y un modelo abstracto de Django no aporta nada sobre una
    clase normal cuando no hay campos que heredar.
    """

    @staticmethod
    def _collect_methods():
        """Todos los ``(modelo, atributo, función)`` decorados con autovacuum."""
        return [
            (model, attr, func)
            for model in apps.get_models()
            for attr, func in inspect.getmembers(model, is_autovacuum)
        ]

    def run_vacuum_cleaner(self, cron_id=None):
        """Limpieza completa: llama con seguridad a cada método decorado.

        ``cron_id`` es el equivalente del ``context['cron_id']`` de la
        referencia: sin él, el barrido se niega a correr. La capacidad del
        invocador se verifica en el llamador (DEC-11).
        """
        if not cron_id:
            raise PermissionError(
                'run_vacuum_cleaner sólo corre desde el cron (falta cron_id)'
            )

        all_methods = self._collect_methods()
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
