"""``account.payment.method.line`` — lo que ``account_payment`` le cuelga
(≙ ``_inherit``).

Adaptación de
``odoo19c: account_payment/models/account_payment_method_line.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 86 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

6 símbolos en la referencia: 2 campos + 4 métodos. Portados 4, no portados 2.

Portado
========

==================================  ======================================
Símbolo de la referencia            Aquí
==================================  ======================================
``payment_provider_id``             propiedad ``payment_provider``
                                    (get/set), vía
                                    ``AccountPaymentMethodLineProvider``
``payment_provider_state``          propiedad ``payment_provider_state``
``_compute_name``                   ``wrap_method`` (la base primero, ver
                                    abajo)
``_unlink_except_active_provider``  receptor ``pre_delete``
==================================  ======================================

Divergencia en ``payment_provider_state``: la referencia es
``related='payment_provider_id.state'`` (``enabled``/``test``/``disabled``,
3 valores). ``PaymentGateway`` (``api: payment/models/payment_provider.py``)
no tiene ``state`` — tiene ``is_active`` booleano. Se mapea
``'enabled' if is_active else 'disabled'``; el valor intermedio ``'test'``
no tiene contraparte (``PaymentGateway`` no distingue sandbox por fila, el
propio gateway ``TEST`` ES el sandbox — ver ``models/account_payment_
method.py``).

``_compute_name`` se instala con ``wrap_method``
------------------------------------------------

La referencia hace ``super()._compute_name()`` PRIMERO y luego aplica su
lógica encima. ``wrap_method`` es ese ``super()``: la extensión recibe la
implementación previa ligada y la llama antes de su cuerpo. Además deja la
previa enlazada en ``_chain_previous``, y ``Field.get_depends`` recorre ese
enlace: el campo conserva el ``@api.depends('payment_method.name')`` de la
base. El patrón anterior —capturar la base en una variable de módulo y
sustituir el atributo con ``setattr``— no dejaba enlace, y el campo quedaba
sin ninguna dependencia (``registry.field_depends[name] == ()``).

La dependencia propia de la referencia, ``payment_provider_id.name``, no se
declara: aquí ``payment_provider`` es una ``property`` sobre el vínculo
``AccountPaymentMethodLineProvider``, no un campo, y el grafo no puede
recorrerla. // pendiente: declararla cuando ``payment_provider_id`` se porte
como ``Many2one`` (sucesor en el plan, ``orm-extension-depends-merge-0485``).

No portado (declarado, no improvisado)
=========================================

- **``_compute_payment_provider_id``** — auto-vincula la línea a un
  proveedor elegible de la compañía llamando a
  ``journal_id._get_journals_payment_method_information()``. ``api:
  account/models/account_journal.py`` no declara ese método (medido: el
  archivo no tiene métodos propios más allá de ``__str__``) ni el concepto
  de "proveedores candidatos por compañía" que alimenta. Condición de
  cierre: requiere construir esa agregación en ``account.journal`` primero
  — fuera del alcance de este addon (tocaría ``account/``, prohibido para
  este agente).
- **``action_open_provider_form``** — devuelve un ``ir.actions.act_window``
  (acción de UI). Sin cliente web aquí.
"""
from addons.account.models.account_payment_method import AccountPaymentMethodLine
from addons.account_payment.models.links import AccountPaymentMethodLineProvider
from exceptions import UserError
from orm.method_chain import wrap_method
from tools.translate import _
from django.db.models.signals import pre_delete
from django.dispatch import receiver


def _get_link(method_line):
    """Fila satélite de esta línea, o ``None`` si aún no hay ninguna.

    El guard de ``pk`` NO es defensivo: es el camino normal. La base llama a
    ``_compute_name()`` desde ``save()`` ANTES del INSERT
    (``account/models/account_payment_method.py:160``), así que este lookup
    corre de forma rutinaria sobre una instancia sin ``pk``. Sin el guard,
    Django aborta con ``ValueError: Model instances passed to related filters
    must be saved.`` — medido: rompía 4 tests de ``tests/unit/account/`` que
    pasaban antes de instalar este addon.

    Una línea todavía no insertada no puede tener satélite, así que ``None``
    es la respuesta exacta, no un parche.
    """
    if method_line.pk is None:
        return None
    return AccountPaymentMethodLineProvider.objects.filter(
        method_line=method_line).first()


def _get_or_create_link(method_line):
    link, _created = AccountPaymentMethodLineProvider.objects.get_or_create(
        method_line=method_line)
    return link


# -- payment_provider (≙ payment_provider_id) ---------------------------------

def _get_payment_provider(self):
    link = _get_link(self)
    return link.provider if link is not None else None


def _set_payment_provider(self, value):
    link = _get_or_create_link(self)
    link.provider = value
    link.save(update_fields=['provider'])


# -- payment_provider_state (≙ payment_provider_state related) ---------------

def _get_payment_provider_state(self):
    """``'enabled'``/``'disabled'`` según ``PaymentGateway.is_active`` — sin
    el valor intermedio ``'test'`` (divergencia del docstring del módulo)."""
    provider = _get_payment_provider(self)
    if provider is None:
        return None
    return 'enabled' if provider.is_active else 'disabled'


# -- _compute_name (wrap_method: la base primero) -----------------------------

def _compute_name(self, previous):
    """≙ ``odoo19c: account_payment/models/account_payment_method_line.py:
    21-26``: nombre del método si aún vacío tras la base."""
    previous()
    provider = _get_payment_provider(self)
    if provider is not None and not self.name:
        self.name = provider.name


@receiver(pre_delete, sender=AccountPaymentMethodLine,
          dispatch_uid='account_payment.unlink_except_active_provider')
def _unlink_except_active_provider(sender, instance, **kwargs):
    """≙ ``odoo19c: account_payment/models/account_payment_method_line.py:
    63-74`` (``@api.ondelete(at_uninstall=False)``): no se borra una línea
    vinculada a una pasarela activa."""
    provider = _get_payment_provider(instance)
    if provider is not None and provider.is_active:
        raise UserError(_(
            "You can't delete a payment method that is linked to an active "
            "provider. Linked provider: %s") % provider.name)


def apply_account_payment_extensions():
    """≙ ``_inherit = 'account.payment.method.line'`` de ``account_payment``.

    Se llama desde ``AccountPaymentConfig.ready()``. El receptor
    ``@receiver`` de arriba se conecta al importar este módulo — no hace
    falta conectarlo aquí (mismo criterio que ``account_fleet``).
    """
    for nombre, getter, setter in (
        ('payment_provider', _get_payment_provider, _set_payment_provider),
    ):
        if not hasattr(AccountPaymentMethodLine, nombre):
            setattr(AccountPaymentMethodLine, nombre, property(getter, setter))

    if not hasattr(AccountPaymentMethodLine, 'payment_provider_state'):
        AccountPaymentMethodLine.payment_provider_state = property(
            _get_payment_provider_state)

    wrap_method(AccountPaymentMethodLine, '_compute_name', _compute_name)
