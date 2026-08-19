"""``account.move.reversal`` — al rehacer una factura, sus horas vuelven a
estar sin facturar (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/account_move_reversal.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``AccountMoveReversal``,
``TransientModel``, ``_inherit``), **0 campos**, **1 método**. **Portado
entero** — es el único archivo del addon sin ningún símbolo bloqueado.

Por qué éste sí y ``account_move.py`` no
==========================================

Las dos mitades del enlace apunte ↔ factura tienen dependencias distintas:

- **Enlazar** (``AccountMove._link_timesheets_to_invoice``) necesita saber
  *qué línea de venta* facturó cada hora → depende de ``so_line`` y de
  ``AccountMoveLine.sale_line_ids``. Bloqueado.
- **Desenlazar** (este archivo) sólo necesita saber *qué facturas* se están
  rehaciendo → basta ``timesheet_invoice`` (colgado por
  ``models/hr_timesheet.py``) y ``move_type``, que ``account.move`` ya tiene.

Por eso el candado de integridad —una hora no queda marcada como facturada
por una factura que se rehizo— **sí** se sostiene hoy, aunque el enlace
inicial todavía lo tenga que poner el llamador a mano.

Porte símbolo por símbolo — 1 de 1
=====================================

``reverse_moves`` (:6-15) — **portado**. Encadenado sobre
``api: addons/account/wizard/account_move_reversal.py:315-347``, que es un
``@classmethod`` con firma ``(cls, moves, date=None, reason=None,
journal=None, is_modify=False)``.

Divergencias declaradas, las dos de firma y ninguna de conducta:

1. **La firma.** La fuente es un método de instancia del asistente y lee los
   asientos de ``self.move_ids``; el puerto de este árbol es un
   ``@classmethod`` que los recibe como parámetro (el asistente no tiene
   tabla: ``Meta.abstract = True, managed = False``). El encadenado replica esa
   firma, no la de la fuente — es la firma del método que envuelve.
2. **``sudo()``.** La fuente busca los apuntes con privilegio elevado porque
   el usuario que revierte no suele poder leer hojas de horas ajenas. Aquí la
   autorización es por CAPACIDAD a nivel de vista DRF, no por registro: la
   consulta va directa, que es el mismo criterio ya declarado en
   ``models/project_task.py``.

El **orden** sí se porta verbatim: la fuente desenlaza y *después* llama a
``super()``. ``chain_method`` con el relevo por ``None`` da exactamente eso —
esta función devuelve ``None``, así que el anterior corre a continuación y su
resultado es el que vuelve al llamador.
"""
from addons.account.wizard.account_move_reversal import AccountMoveReversal
from addons.analytic.models import AccountAnalyticLine
from orm.method_chain import chain_method


def reverse_moves(cls, moves, date=None, reason=None, journal=None,
                  is_modify=False):
    """≙ ``reverse_moves`` (``odoo19c: account_move_reversal.py:6-15``).

    Cuando la reversión es "rehacer" (``is_modify``), los apuntes de hoja de
    horas enlazados a las facturas de cliente que se rehacen quedan otra vez
    **sin facturar**: se les borra ``timesheet_invoice``.

    Devuelve ``None`` a propósito — ver la nota sobre el orden en el docstring
    del módulo.
    """
    if not is_modify:
        return None
    invoices = [m for m in moves
                if getattr(m, 'move_type', None) == 'out_invoice'
                and m.pk is not None]
    if invoices:
        AccountAnalyticLine.objects.filter(
            timesheet_invoice__in=invoices,
        ).update(timesheet_invoice=None)
    return None


def apply_sale_timesheet_account_move_reversal_extensions():
    """Encadena ``reverse_moves`` sobre ``account.move.reversal`` — ≙
    ``_inherit = 'account.move.reversal'``.

    **Por qué import directo y no ``extend_model``**, que es lo que usan los
    otros cinco archivos de este addon: ``extend_model`` difiere el trabajo a
    ``apps.lazy_model_operation``, que dispara cuando Django **prepara** la
    clase del modelo. El asistente de reversión declara ``Meta.abstract =
    True, managed = False`` (``api: addons/account/wizard/
    account_move_reversal.py:146-148``), y Django **no** emite
    ``class_prepared`` para una clase abstracta: la operación diferida no
    dispararía nunca y el encadenado sería un silencio, no un error — la
    misma clase de fallo que ``H-API-577`` registra.

    Con el import al top la clase ya existe cuando ``ready()`` llama a esta
    función, así que el encadenado es inmediato y verificable.

    ``classmethod(reverse_moves)`` porque el destino lo declara
    ``@classmethod``; ``chain_method`` detecta el envoltorio y lo reinstala
    igual (``src/orm/method_chain.py:141-143``).
    """
    chain_method(AccountMoveReversal, 'reverse_moves',
                 classmethod(reverse_moves))


__all__ = ['apply_sale_timesheet_account_move_reversal_extensions']
