"""Lo que ``account`` le cuelga a la divisa — ≙ ``_inherit`` (T-B2a).

Adaptación de ``addons/account/models/res_currency.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``).

**Los dos campos que T-B1 contó para este modelo no se portan** — y aun así
este archivo no está vacío, porque lo sustantivo de la extensión no es un
campo: es un **guard de integridad** que la referencia declara en la misma
clase.

Los dos campos, y qué los bloquea
==================================

- **``fiscal_country_codes``** (``odoo19c: res_currency.py:17``) mapea
  ``account_fiscal_country_id.code`` sobre las empresas permitidas. Ese campo
  pertenece al Bloque 1 (los 72 de ``res.company``) y está ausente — medido:
  ``grep -n "account_fiscal_country" base/models/res_company.py`` → 0 hits.
  **Lo cierra la tarea #137.**
- **``display_rounding_warning``** (``:15``) compara
  ``record._origin.rounding`` con ``record.rounding``: es el aviso que la
  vista de formulario de Odoo muestra **mientras se edita**, contrastando el
  valor en pantalla con el de la base. ``_origin`` es el pseudo-registro de
  ``onchange``; aquí no hay onchange de servidor, así que no hay análogo.
  **DESCONOCIDO declarado**, con su condición de cierre: se decide si alguna
  vez existe un canal equivalente (validar en el serializer contra el valor
  previo), no antes.

El guard sí se porta — con su ceguera declarada
===============================================

``odoo19c: res_currency.py:27-39`` impide **reducir los decimales** de una
divisa que ya generó apuntes. La razón es que ``rounding`` no es cosmético:
es el factor con el que ya se redondearon importes asentados. Bajarlo a
posteriori haría que la misma fila se leyera con otro valor que el que se
contabilizó.

*Métrica:* el guard consulta si existe algún apunte con esta divisa.
*Ciega a:* la rama ``company_currency_id`` de la referencia — nuestro
``AccountMoveLine`` declara ``currency`` y **no** ``company_currency``
(medido: ``grep -n "currency" account_move_line.py`` da un solo campo). Un
apunte en la moneda de la empresa que **no** repite la divisa en ``currency``
no lo ve este guard.

Se porta igual porque un guard parcial bloquea un superconjunto de nada, y
porque la alternativa —no portarlo— deja el cambio destructivo sin ninguna
barrera. Lo que no se hace es presentarlo como completo: cuando entre el
multi-divisa (tarea #114, :ref:`h-api-324`) hay que volver aquí y añadir la
segunda rama.
"""
from addons.account.models.account_move_line import AccountMoveLine
from addons.base.models.res_currency import ResCurrency
from exceptions import UserError
from tools.translate import _


def _has_accounting_entries(self):
    """≙ ``_has_accounting_entries`` (``odoo19c: res_currency.py:34-39``).

    ``True`` si esta divisa ya se usó para redondear algún apunte. Ver la
    ceguera declarada en el docstring del módulo.
    """
    return AccountMoveLine.objects.filter(currency=self).exists()


def assert_rounding_can_change(self, nuevo_rounding):
    """≙ el guard de ``write`` (``odoo19c: res_currency.py:27-32``).

    La referencia lo pone dentro de ``write``; aquí es un método explícito
    porque este ORM no tiene un ``write`` que reciba el ``vals`` completo
    antes de tocar la fila. Se invoca desde el serializer o el servicio que
    cambia el redondeo.

    Bloquea **reducir** la precisión (``nuevo > actual``, en la aritmética de
    la referencia: un ``rounding`` mayor significa menos decimales) y
    ``0``, que la referencia trata como caso especial.
    """
    if (nuevo_rounding > self.rounding or nuevo_rounding == 0) \
            and _has_accounting_entries(self):
        raise UserError(_(
            'No se puede reducir el número de decimales de una divisa que ya '
            'se usó para generar apuntes contables.'))


def apply_account_extensions():
    """Cuelga el guard de la divisa — ≙ ``_inherit``.

    Se invoca desde ``AccountConfig.ready()``. No añade columnas: los dos
    campos de la referencia están bloqueados (ver el docstring del módulo).
    """
    for nombre, funcion in (
        ('_has_accounting_entries', _has_accounting_entries),
        ('assert_rounding_can_change', assert_rounding_can_change),
    ):
        if not hasattr(ResCurrency, nombre):
            setattr(ResCurrency, nombre, funcion)
