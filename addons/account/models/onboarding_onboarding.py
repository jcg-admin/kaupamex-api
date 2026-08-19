"""``onboarding.onboarding`` colgado por ``account`` — pasos de facturación y dashboard.

Adaptación de ``addons/account/models/onboarding_onboarding.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Tres símbolos:

===================================  ==========================================
Símbolo                              Estado
===================================  ==========================================
``action_close_panel_account_invoice``    portado — xmlid → ``route_name``
``_prepare_rendering_values``             portado — xmlid → ``route_name``
``action_close_panel_account_dashboard``  portado — xmlid → ``route_name``
===================================  ==========================================

xmlid → ``route_name`` — mismo sustituto que ``onboarding_onboarding_step.py``
================================================================================

Sin ``ir.model.data``/``env.ref`` (medido en el docstring de
``mail_template.py`` de este mismo pase), el identificador estable de un
onboarding concreto aquí es ``route_name`` — el propio campo que
``OnboardingOnboarding`` ya declara para ese fin (ver su docstring: *"Odoo
route_name... sin panel web, no define una ruta HTTP aquí"*). Los dos
xmlids que la referencia nombra (``account.onboarding_onboarding_account_invoice``,
``account.onboarding_onboarding_account_dashboard``) se sustituyen por sus
sufijos como ``route_name``: ``account_invoice`` / ``account_dashboard``.
Ninguno de los dos tiene fila sembrada en este árbol todavía (no hay cargador
de datos declarativos) — la guarda queda **estructuralmente completa** hasta
que exista el seed.

``_prepare_rendering_values`` → ``prepare_rendering_values`` (sin guion bajo)
================================================================================

**Divergencia declarada, no descuido.** La referencia declara este método
``_prepare_rendering_values`` (privado). El puerto base de este mismo modelo
en este árbol —``onboarding/models/onboarding_onboarding.py``— lo declaró
**sin** el guion bajo (``prepare_rendering_values``, público) antes de este
pase; el override tiene que encadenar sobre el nombre que el base
efectivamente expone, o no encadena con nada. Se documenta aquí como un
candidato a corrección retroactiva del base (fuera del alcance de este
archivo — ``porte-completo-no-parcial.md`` exige preservar el guion bajo en
el porte **nuevo**, no reescribir un archivo ajeno ya commiteado).
"""
from addons.account.models.account_move import AccountMove
from addons.onboarding.models.onboarding_onboarding import OnboardingOnboarding
from addons.onboarding.models.onboarding_progress import _resolve_company_id
from orm.method_chain import chain_method

#: Sustitutos de los xmlids de la referencia — ver el docstring del módulo.
ROUTE_ACCOUNT_INVOICE = 'account_invoice'
ROUTE_ACCOUNT_DASHBOARD = 'account_dashboard'


def action_close_panel_account_invoice(self):
    """≙ ``action_close_panel_account_invoice`` (``odoo19c:
    onboarding_onboarding.py:7-9``, ``@api.model``).

    La referencia es ``@api.model`` (se llama sobre el modelo, no una
    instancia) y resuelve el registro por xmlid dentro de
    ``action_close_panel``. Aquí, sin xmlid, se busca por ``route_name`` y se
    delega en ``action_close_panel_by_id`` del base (ya porta el "quietly do
    nothing" de la referencia).
    """
    onboarding = type(self).objects.filter(route_name=ROUTE_ACCOUNT_INVOICE).first()
    if onboarding is not None:
        type(self).action_close_panel_by_id(onboarding.pk)


def action_close_panel_account_dashboard(self):
    """≙ ``action_close_panel_account_dashboard`` (``odoo19c:
    onboarding_onboarding.py:26-28``). Mismo patrón que la de facturación."""
    onboarding = type(self).objects.filter(route_name=ROUTE_ACCOUNT_DASHBOARD).first()
    if onboarding is not None:
        type(self).action_close_panel_by_id(onboarding.pk)


def prepare_rendering_values(self):
    """≙ ``_prepare_rendering_values`` (``odoo19c: onboarding_onboarding.py:11-21``).

    Si este onboarding es el de facturación (``route_name ==
    'account_invoice'``) y su paso "crear factura" sigue sin marcarse hecho,
    verifica si la empresa YA tiene facturas de cliente — de ser así, marca
    el paso como recién completado (portable sin xmlid: el paso se localiza
    por su ``route_name`` propio, que ``OnboardingOnboardingStep`` no tiene
    hoy — se busca por ``panel_step_open_action_name`` en su lugar, el campo
    más cercano a un identificador estable que el modelo de paso expone).

    Devuelve ``None``: bajo ``chain_method`` (relevo) eso invoca la
    implementación previa (el ``prepare_rendering_values`` real del base) sin
    alterar su resultado — el efecto de este override es el side-effect de
    marcar el paso hecho, no cambiar el diccionario de renderizado.
    """
    if self.route_name != ROUTE_ACCOUNT_INVOICE:
        return None
    step = self.steps.filter(
        panel_step_open_action_name='action_open_step_create_invoice',
    ).first()
    if step is None:
        return None
    if step.current_step_state() != 'not_done':
        return None
    company_id = _resolve_company_id(None)
    has_invoices = AccountMove.objects.filter(
        company_id=company_id, move_type='out_invoice',
    ).exists()
    if has_invoices:
        step.action_set_just_done()
    return None


def apply_account_extensions():
    """Cuelga los pasos de facturación/dashboard sobre ``onboarding.onboarding``
    — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo estado
    declarado que el resto de archivos de este pase.
    """
    chain_method(OnboardingOnboarding, 'action_close_panel_account_invoice',
                 action_close_panel_account_invoice)
    chain_method(OnboardingOnboarding, 'action_close_panel_account_dashboard',
                 action_close_panel_account_dashboard)
    chain_method(OnboardingOnboarding, 'prepare_rendering_values',
                 prepare_rendering_values)
