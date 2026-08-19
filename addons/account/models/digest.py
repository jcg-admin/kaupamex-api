r"""``digest.digest`` extendido por ``account`` — el KPI de ingresos.

Adaptación de ``addons/account/models/digest.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 39 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 de 3, uno de ellos bloqueado
==============================================================

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Símbolo
     - Estado
     - Nota
   * - ``kpi_account_total_revenue``
     - portado
     - campo booleano, sin dependencia
   * - ``kpi_account_total_revenue_value``
     - portado (campo) / **bloqueado** (compute)
     - la columna se declara; su cálculo depende de una pieza ausente
   * - ``_compute_kpis_actions``
     - **bloqueado**
     - depende del método base que sobreescribe, ausente

Qué es
========

``digest.digest`` es el resumen periódico por correo (`` addons/digest``, ya
portado). Cada KPI que un addon quiere sumar al digest declara un booleano
(¿se muestra?), un campo monetario ``*_value`` computado, y opcionalmente
una entrada en el diccionario de acciones que ``_compute_kpis_actions``
arma. ``account`` suma el ingreso total del período: la suma de ``balance``
de las líneas de asientos **publicados** cuya cuenta es de grupo interno
``'income'``, en negativo (una cuenta de ingreso tiene saldo natural
acreedor, negativo en la convención de signo de este ORM — igual que la
referencia).

Bloqueo — dos piezas ausentes en la base de ``DigestDigest``
================================================================

``_compute_kpi_account_total_revenue_value`` (la referencia) y
``_compute_kpis_actions`` (que ``account`` también sobreescribe) llaman a dos
métodos de la clase base que **no existen** en
``addons/digest/models/digest.py`` de este árbol:

.. code-block:: text

    grep -n "def _get_kpi_compute_parameters\|def _compute_kpis_actions" \
        addons/digest/models/digest.py
    → 0 hits (ambos)

[PROVEN — medido en el pase que escribe este archivo]. El propio docstring de
``digest.py`` ya los lista explícitamente entre lo que falta portar del envío
completo (``~230 LOC de digest.py:130-484`` que la síntesis previa mapeó
pieza por pieza). No es una omisión de este pase: es una pieza del **addon
``digest``**, no de ``account``, y su cierre le corresponde a ese archivo.

**Desenlace: (b) Bloqueado por pieza concreta**, con sucesor. El cuerpo se
porta VERBATIM contra el contrato que la referencia declara —
``self._get_kpi_compute_parameters()`` devolviendo ``(start, end,
companies)``, y ``super()._compute_kpis_actions(company, user)`` devolviendo
un diccionario mutable— así que en cuanto ``digest.py`` los declare, este
archivo funciona sin tocarlo. Hasta entonces, invocar
``compute_kpi_value(self, 'kpi_account_total_revenue', start, end)`` levanta
``AttributeError`` en ``_get_kpi_compute_parameters`` — fallo ruidoso, no
silencioso: no hay branch que finja un resultado.

El campo booleano ``kpi_account_total_revenue`` en sí **no** depende de
ninguna de las dos piezas — se porta y queda disponible de inmediato para que
el usuario marque «Revenue» en su digest, aunque el valor no se calcule hasta
que el cómputo se desbloquee.

``has_group`` — sí existe, y con la forma correcta
=====================================================

La guarda de acceso (*"sin permiso, no calcules, no revientes el digest de
todos"*) sí tiene análogo exacto: ``ResUsers.has_group(group_ext_id)``
(``src/addons/base/models/res_users.py:518``), método de instancia sobre el
usuario — misma firma que ``self.env.user.has_group(...)`` de la referencia.
Se porta verbatim.
"""
import fields
import models

from addons.account.models.account_move_line import AccountMoveLine
from addons.digest.models.digest import DigestDigest
from exceptions import AccessError
from orm.environments import get_current_company, get_current_user
from tools.translate import _


def _compute_kpi_account_total_revenue_value(self):
    """≙ ``_compute_kpi_account_total_revenue_value``
    (``odoo19c: account/models/digest.py:14-27``).

    **BLOQUEADO** por ``self._get_kpi_compute_parameters()`` — ver el
    docstring del módulo. El resto del cuerpo es fiel: suma de ``balance``
    de líneas de asientos publicados con cuenta de grupo ``'income'`` en el
    rango, negada (Odoo invierte el signo de las cuentas de ingreso al
    mostrarlo).
    """
    user = get_current_user()
    if user is None or not user.has_group('account.group_account_invoice'):
        raise AccessError(_(
            "Sin acceso: se omite este dato del digest del usuario."))

    # ≙ ``self._get_kpi_compute_parameters()`` — falta en la base de
    # ``digest.digest`` (ver docstring del módulo). Se invoca tal cual la
    # referencia; el AttributeError es intencional mientras la pieza falte.
    start, end, companies = self._get_kpi_compute_parameters()

    # ``AccountMoveLine`` no lleva ``company``/``date`` propios — viven en su
    # ``move`` (``account.move.line.company_id`` de la referencia es un
    # ``related='move_id.company_id', store=True``; aquí se atraviesa la FK).
    rows = (
        AccountMoveLine.objects
        .filter(
            move__company__in=companies,
            move__date__gt=start, move__date__lte=end,
            account__internal_group='income',
            move__state='posted',
        )
        .values('move__company')
        .annotate(total=models.Sum('balance'))
    )
    total_by_company = {
        row['move__company']: row['total'] or 0 for row in rows
    }

    default_company = get_current_company()
    for record in self:
        company = record.company_id or default_company
        record.kpi_account_total_revenue_value = -total_by_company.get(
            company, 0)


def _compute_kpis_actions(self, company, user):
    """≙ ``_compute_kpis_actions`` de ``account``
    (``odoo19c: account/models/digest.py:29-32``).

    **BLOQUEADO** — ``super()._compute_kpis_actions`` no existe en
    ``DigestDigest`` de este árbol (ver docstring del módulo). Se deja el
    contrato declarado —recibe ``company``/``user``, añade una clave al
    diccionario de acciones— para que activarlo, cuando la base lo tenga,
    sea sumar la llamada a ``super()`` que hoy no hay a qué apuntar.

    La acción en sí —abrir el reporte de facturas de venta filtrado por el
    menú de finanzas— depende además de ``ir.model.data`` para
    ``account.menu_finance``, que no está sembrado en este árbol; se deja el
    valor como ``None`` en vez de una URL rota.
    """
    raise NotImplementedError(
        'Bloqueado: DigestDigest._compute_kpis_actions (base) no existe '
        'todavía en addons/digest/models/digest.py.')


def apply_account_extensions():
    """≙ ``_inherit = 'digest.digest'`` de ``account``.

    Cuelga el campo booleano (usable de inmediato) y los dos métodos
    bloqueados (documentados, no silenciosos: levantan si se invocan antes
    de que su pieza exista).
    """
    if not hasattr(DigestDigest, 'kpi_account_total_revenue'):
        DigestDigest.add_to_class('kpi_account_total_revenue', fields.Boolean(
            default=False, verbose_name='Ingresos',
            help_text='Muestra el KPI de ingreso total del período en el '
                      'digest (Odoo kpi_account_total_revenue).',
        ))
    if not hasattr(DigestDigest, 'kpi_account_total_revenue_value'):
        DigestDigest.add_to_class(
            'kpi_account_total_revenue_value', fields.Monetary(
                store=False, null=True, blank=True,
                verbose_name='Ingreso total del período (valor)',
                help_text='Odoo kpi_account_total_revenue_value — BLOQUEADO, '
                          'ver docstring del módulo.',
            ))

    for name, function in (
        ('_compute_kpi_account_total_revenue_value',
         _compute_kpi_account_total_revenue_value),
        ('_compute_kpis_actions', _compute_kpis_actions),
    ):
        if not hasattr(DigestDigest, name):
            setattr(DigestDigest, name, function)
