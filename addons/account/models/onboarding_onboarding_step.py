r"""``onboarding.onboarding.step`` colgado por ``account`` — las acciones de cada paso.

Adaptación de ``addons/account/models/onboarding_onboarding_step.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Ocho símbolos, los ocho **bloqueados por
la misma pieza concreta** — ninguno se omite en silencio.

Bloqueado por: ``ir.actions.act_window`` sin consumidor + sin ``env.ref``
============================================================================

Los ocho métodos de la referencia construyen, verbatim, un diccionario
``{'type': 'ir.actions.act_window', 'res_model': ..., 'views': [(env.ref(
xmlid).id, 'form')], ...}`` — la instrucción que el cliente web de Odoo
interpreta para abrir un formulario modal. Dos piezas están ausentes, medidas
antes de escribir este archivo:

.. code-block:: text

   grep -rn "class.*IrActionsActWindow" src/addons/base/ addons/     → 0 hits
   grep -rn "def get_external_id\|env.ref" src/ addons/ --include=*.py \
     | grep -v odoo-tools                                            → 0 hits

Mismo GAP que ``onboarding/models/onboarding_onboarding.py`` ya declara para
el panel web completo (*"no hay a qué adaptar un cliente web OWL en un
backend Django REST"*) — extendido aquí a las ACCIONES que abrían cada paso
del panel, no sólo al panel mismo. El equivalente aquí sería la ruta DRF que
la interfaz llame para mostrar el formulario correspondiente (empresa,
diseño de documento, cuenta bancaria, primera factura, ejercicio fiscal,
plan de cuentas, impuesto de ventas) — trabajo de una iniciativa de UI, no de
este porte.

Se preservan los OCHO símbolos como funciones que levantan, cada una nombrando
su propia acción bloqueada — no se devuelve ``None``/``{}`` silencioso, que se
leería como "la acción no existe" en vez de "la acción existe y está
bloqueada por falta de mecanismo".

La única pieza con lógica de negocio real — extraída, no perdida
====================================================================

``action_open_step_chart_of_accounts`` valida el paso
(``action_validate_step``) ANTES de construir el ``act_window`` bloqueado —
esa validación sí tiene análogo portable
(``OnboardingOnboardingStep.action_validate_step_by_id``, ya en el base).
Se ejecuta aquí, y sólo la construcción de la acción de navegación queda
bloqueada.
"""
from addons.base.models.res_company import ResCompany
from addons.onboarding.models.onboarding_onboarding_step import (
    OnboardingOnboardingStep,
)
from addons.onboarding.models.onboarding_progress import _resolve_company_id
from orm.method_chain import chain_method


class OnboardingActionBlocked(NotImplementedError):
    """Acción de onboarding bloqueada por falta de ``ir.actions.act_window``
    y de resolución por xmlid — ver el docstring del módulo."""


def _blocked(action_name, missing):
    raise OnboardingActionBlocked(
        f'{action_name}: bloqueado — construye un ir.actions.act_window '
        f'que abriría {missing}; ese mecanismo no está portado en este '
        f'árbol (ver el docstring de onboarding_onboarding_step.py).')


def action_open_step_company_data(self):
    """≙ ``action_open_step_company_data`` (``odoo19c: onboarding_
    onboarding_step.py:9-19``)."""
    _blocked('action_open_step_company_data',
             "el formulario de 'res.company' (vista 'res_company_form_view_onboarding')")


def action_open_step_base_document_layout(self):
    """≙ ``action_open_step_base_document_layout`` (``:21-29``)."""
    _blocked('action_open_step_base_document_layout',
             "'base.document.layout' (vista 'web.view_base_document_layout')")


def action_validate_step_base_document_layout(self, company=None):
    """≙ ``action_validate_step_base_document_layout`` (``:31-36``,
    ``@api.model`` en la referencia — no opera sobre ``self``, localiza el
    step por xmlid).

    **Portable, con el mismo sustituto que ``onboarding_onboarding.py``**:
    sin ``env.ref``, el step se localiza por
    ``panel_step_open_action_name == 'action_open_step_base_document_layout'``
    en vez de por
    ``account.onboarding_onboarding_step_base_document_layout``. Si existe y
    la empresa ya tiene ``external_report_layout_id``, marca el paso hecho.
    """
    step = type(self).objects.filter(
        panel_step_open_action_name='action_open_step_base_document_layout',
    ).first()
    if step is None:
        return False
    company_id = _resolve_company_id(company)
    resolved_company = (
        ResCompany.objects.filter(pk=company_id).first()
        if company_id is not None else None
    )
    if resolved_company is None or not getattr(resolved_company, 'external_report_layout_id', None):
        return False
    return step.action_set_just_done(company=resolved_company) is not None


def action_open_step_bank_account(self):
    """≙ ``action_open_step_bank_account`` (``:39-40``): delega en
    ``self.env.company.setting_init_bank_account_action()``, que construye
    otro ``ir.actions.act_window`` — mismo bloqueo."""
    _blocked('action_open_step_bank_account',
             "el asistente de cuenta bancaria ('setting_init_bank_account_action')")


def action_open_step_create_invoice(self):
    """≙ ``action_open_step_create_invoice`` (``:42-48``)."""
    _blocked('action_open_step_create_invoice',
             "el formulario de 'account.move' (vista 'account.view_move_form')")


def action_open_step_fiscal_year(self):
    """≙ ``action_open_step_fiscal_year`` (``:51-63``): crea un
    ``account.financial.year.op`` wizard y abre su formulario — modelo
    ausente además del act_window."""
    _blocked('action_open_step_fiscal_year',
             "el wizard 'account.financial.year.op' (no portado en este árbol)")


def action_open_step_chart_of_accounts(self):
    """≙ ``action_open_step_chart_of_accounts`` (``:66-88``).

    Ejecuta la validación real (portable) antes de bloquear la navegación —
    ver "La única pieza con lógica de negocio real" en el docstring del
    módulo. ``action_validate_step_by_id`` es ``@classmethod`` en el base
    (recibe el ``pk`` en vez del xmlid, mismo criterio GAP ya documentado
    allá).
    """
    type(self).action_validate_step_by_id(self.pk)
    _blocked('action_open_step_chart_of_accounts',
             "la lista de 'account.account' filtrada por empresa")


def action_open_step_sales_tax(self):
    """≙ ``action_open_step_sales_tax`` (``:92-102``)."""
    _blocked('action_open_step_sales_tax',
             "el formulario de 'res.company' (vista "
             "'account.res_company_form_view_onboarding_sale_tax')")


def apply_account_extensions():
    """Cuelga las ocho acciones (bloqueadas, documentadas) sobre
    ``onboarding.onboarding.step`` — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo estado
    declarado que el resto de archivos de este pase.
    """
    for name, func in (
        ('action_open_step_company_data', action_open_step_company_data),
        ('action_open_step_base_document_layout', action_open_step_base_document_layout),
        ('action_validate_step_base_document_layout', action_validate_step_base_document_layout),
        ('action_open_step_bank_account', action_open_step_bank_account),
        ('action_open_step_create_invoice', action_open_step_create_invoice),
        ('action_open_step_fiscal_year', action_open_step_fiscal_year),
        ('action_open_step_chart_of_accounts', action_open_step_chart_of_accounts),
        ('action_open_step_sales_tax', action_open_step_sales_tax),
    ):
        chain_method(OnboardingOnboardingStep, name, func)
