"""``account.merge.wizard`` (+ su línea) — fusionar cuentas contables.

Adaptación de Odoo ``addons/account/wizard/account_merge_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``. Las "líneas de wizard"
(``account.merge.wizard.line``) tampoco tienen tabla: viajan como dicts
``{'display_type', 'account', 'grouping_key', 'is_selected', 'sequence',
'info'}`` — las mismas claves que los campos de la referencia.

El retarget de claves foráneas — construido aquí, no excusado
==============================================================

La referencia delega el corazón de la fusión en dos helpers del wizard de
fusión de partners de ``base`` (``_update_foreign_keys_generic`` y
``_update_reference_fields_generic`` de
``base.partner.merge.automatic.wizard``), que este árbol no porta (ver
``wizard/base_partner_merge.py``). La primera mitad se **construye** en
``_update_foreign_keys_to_account``: Django expone las FKs entrantes por
introspección (``AccountAccount._meta.related_objects`` ≙ el barrido de
``ir.model.fields`` de la referencia) y el retarget es un ``UPDATE`` por
campo. La segunda mitad (campos Reference/Many2oneReference genéricos)
queda **bloqueada por el wizard de base**: el barrido genérico de
referencias polimórficas es suyo; al portarse, ``_action_merge`` lo llama
donde hoy está el comentario del paso 3.2.

``AccountMergeWizard`` — 10 símbolos (5 campos + 5 defs)
=========================================================

===============================  ==========================================
Símbolo de la referencia          Qué pasa aquí
===============================  ==========================================
``account_ids`` (campo)           PORTADO — parámetro ``accounts``
``is_group_by_name`` (campo)      PORTADO — parámetro ``is_group_by_name``
``wizard_line_ids`` (campo)       PORTADO — retorno de
                                   ``_compute_wizard_line_ids`` (dicts)
``disable_merge_button``          PORTADO — ``_compute_disable_merge_button``
``default_get``                   PORTADO
``_get_grouping_key``             PORTADO (parcial declarado, ver su
                                   docstring)
``_compute_wizard_line_ids``      PORTADO
``_compute_disable_merge_button`` PORTADO
``_get_window_action``            NO — ``ir.actions.act_window`` sobre una
                                   vista XML (navegación del cliente Odoo,
                                   misma exclusión que
                                   ``AccountDebitNoteWizard``).
``action_merge``                  PORTADO (sin el ``display_notification``
                                   final — navegación; devuelve las cuentas
                                   supervivientes)
``_check_access_rights``          PORTADO (parcial declarado, ver su
                                   docstring)
``_action_merge``                 PORTADO (parcial declarado, ver su
                                   docstring)
===============================  ==========================================

``AccountMergeWizardLine`` — 14 símbolos (9 campos + 5 defs)
=============================================================

===================================  ======================================
Símbolo de la referencia              Qué pasa aquí
===================================  ======================================
``wizard_id``/``grouping_key``/       PORTADO — claves del dict de línea
``sequence``/``display_type``/
``is_selected``/``account_id``/``info``
``company_ids`` (related)             NO — la cuenta del puerto tiene FK
                                       simple de empresa (``company``), no
                                       ``company_ids`` multi-empresa; la
                                       restricción de empresas usa esa FK.
``account_has_hashed_entries``        NO — bloqueado por el hash
(compute)                              inalterable (``move_id.
                                       inalterable_hash``), no portado —
                                       misma pieza ausente que declara
                                       ``account_secure_entries_wizard.py``.
``_compute_account_has_hashed_entries``  NO — ídem.
``_compute_info``                     PORTADO
``_get_group_name``                   PORTADO (parcial declarado:
                                       ``non_trade`` no existe en la
                                       cuenta; ``active`` ≙ ``not
                                       deprecated``)
``_apply_different_companies_constraint``  PORTADO (sobre la FK simple de
                                       empresa)
``_apply_hashed_moves_constraint``    NO — bloqueado por el hash (arriba).
===================================  ======================================
"""
from collections import defaultdict

from django.db import transaction

from addons.account.models.account_account import AccountAccount
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountMergeWizard(TransientModel):
    """≙ ``account.merge.wizard`` — agrupa cuentas compatibles y las fusiona
    conservando la primera de cada grupo."""

    _name = 'account.merge.wizard'
    _description = "Account merge wizard"

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def default_get(cls, account_ids):
        """≙ ``default_get`` — sólo sobre cuentas, y al menos dos."""
        accounts = list(AccountAccount.objects.filter(pk__in=list(account_ids)))
        if len(accounts) != len(set(account_ids)):
            raise UserError(_("This can only be used on accounts."))
        if len(accounts) < 2:
            raise UserError(_("You must select at least 2 accounts."))
        return accounts

    @classmethod
    def _get_grouping_key(cls, account, is_group_by_name=False):
        """ Return a grouping key for the given account.

        (Docstring verbatim de la referencia.) Parcial declarado: los
        campos de agrupación de allá son ``['account_type', 'non_trade',
        'currency_id', 'reconcile', 'active']`` — ``non_trade`` no existe
        en el puerto de la cuenta, y ``active`` se lee como ``not
        deprecated`` (el puerto declara ``deprecated``).
        """
        grouping = (
            account.account_type,
            account.currency_id,
            account.reconcile,
            not account.deprecated,
        )
        if is_group_by_name:
            grouping = grouping + (account.name,)
        return grouping

    @classmethod
    def _compute_wizard_line_ids(cls, accounts, is_group_by_name=False):
        """ Determine which accounts to merge together.

        (Docstring verbatim de la referencia.) Devuelve la lista de dicts
        de línea — sección + una línea por cuenta, mismo filtro de cuentas
        de banco/efectivo."""
        accounts = [account for account in accounts
                    if account.account_type not in ('asset_bank', 'asset_cash')]

        grouped = defaultdict(list)
        for account in accounts:
            grouped[cls._get_grouping_key(account, is_group_by_name)].append(
                account)

        wizard_lines = []
        sequence = 0
        for grouping_key, group_accounts in grouped.items():
            grouping_key_str = str(grouping_key)
            sequence += 1
            wizard_lines.append({
                'display_type': 'line_section',
                'grouping_key': grouping_key_str,
                'sequence': sequence,
                'account': group_accounts[0],
                'is_selected': False,
                'info': False,
            })
            for account in group_accounts:
                sequence += 1
                wizard_lines.append({
                    'display_type': 'account',
                    'account': account,
                    'grouping_key': grouping_key_str,
                    'is_selected': True,
                    'sequence': sequence,
                    'info': False,
                })
        return wizard_lines

    @classmethod
    def _compute_disable_merge_button(cls, wizard_lines):
        """≙ ``_compute_disable_merge_button`` — no hay nada que fusionar si
        ningún grupo junta 2+ cuentas elegibles."""
        selectable = [line for line in wizard_lines
                      if line['display_type'] == 'account'
                      and line['is_selected'] and not line['info']]
        by_group = defaultdict(list)
        for line in selectable:
            by_group[line['grouping_key']].append(line)
        return all(len(group) < 2 for group in by_group.values())

    @classmethod
    @transaction.atomic
    def action_merge(cls, wizard_lines, is_group_by_name=False):
        """ Merge each group of accounts in `self.wizard_line_ids`.

        (Docstring verbatim de la referencia.) Devuelve las cuentas
        supervivientes en vez del ``display_notification`` (navegación del
        cliente Odoo). El ``sorted('account_has_hashed_entries')`` de la
        referencia no aplica mientras el hash esté bloqueado (ver la tabla
        del módulo): el orden de llegada decide la superviviente.
        """
        accounts = [line['account'] for line in wizard_lines
                    if line['display_type'] == 'account']
        cls._check_access_rights(accounts)

        survivors = []
        selected = [line for line in wizard_lines
                    if line['display_type'] == 'account'
                    and line['is_selected'] and not line['info']]
        by_group = defaultdict(list)
        for line in selected:
            by_group[line['grouping_key']].append(line['account'])
        for group_accounts in by_group.values():
            if len(group_accounts) > 1:
                survivors.append(cls._action_merge(group_accounts))
        return survivors

    @classmethod
    def _check_access_rights(cls, accounts, user=None):
        """≙ ``_check_access_rights`` (parcial declarado, con ``user`` por
        parámetro opcional).

        La referencia verifica ``check_access('write')`` por registro y que
        el usuario alcance TODAS las empresas de las cuentas. Aquí la
        autorización por registro/capacidad es de la capa DRF (capacidades
        ``authz``, fail-closed — quien exponga el wizard gatea la vista);
        cuando el llamador pasa ``user`` con ``companies`` accesibles, el
        guard de empresas se aplica con la FK simple del puerto.
        """
        if user is None or not hasattr(user, 'companies'):
            return accounts
        allowed = {company.pk for company in user.companies.all()}
        forbidden = sorted(
            str(account.company) for account in accounts
            if account.company_id not in allowed)
        if forbidden:
            raise UserError(_(
                "You do not have the right to perform this operation as "
                "you do not have access to the following companies: %s.")
                % ", ".join(forbidden))
        return accounts

    @classmethod
    def _update_foreign_keys_to_account(cls, accounts_to_remove,
                                         account_to_merge_into):
        """El retarget de FKs — la mitad construida de
        ``_update_foreign_keys_generic`` (ver el docstring del módulo).

        Recorre las relaciones entrantes de ``AccountAccount``
        (``_meta.related_objects`` ≙ el barrido de ``ir.model.fields``) y
        reapunta cada una de las cuentas a eliminar hacia la superviviente.
        """
        removed_pks = [account.pk for account in accounts_to_remove]
        for relation in AccountAccount._meta.related_objects:
            if not relation.many_to_one and not relation.one_to_one \
                    and not relation.many_to_many:
                continue
            related_model = relation.related_model
            field_name = relation.field.name
            if relation.many_to_many:
                # M2M: reemplazar la membresía fila a fila.
                for record in related_model.objects.filter(
                        **{f'{field_name}__in': removed_pks}).distinct():
                    manager = getattr(record, field_name)
                    manager.remove(*accounts_to_remove)
                    manager.add(account_to_merge_into)
            else:
                related_model.objects.filter(
                    **{f'{field_name}__in': removed_pks},
                ).update(**{field_name: account_to_merge_into.pk})

    @classmethod
    def _action_merge(cls, accounts):
        """ Merge `accounts`:
            - the first account is extended to each company of the others, keeping their codes and names;
            - the others are deleted; and
            - journal items and other references are retargeted to the first account.

        (Docstring verbatim de la referencia.) Parcial declarado:

        - Paso 1 de la referencia (``code_store``/``company_ids`` por
          empresa, SQL jsonb): la cuenta del puerto tiene UN código y UNA
          empresa — no hay mapa código-por-empresa que consolidar.
        - Paso 3.1 (FKs): construido — ``_update_foreign_keys_to_account``.
        - Paso 3.2 (campos Reference genéricos): bloqueado por el wizard de
          fusión de ``base`` (ver el docstring del módulo).
        - Paso 3.3 (fusión de traducciones jsonb de ``name``): el ``name``
          del puerto es ``Char`` plano, no jsonb por idioma — nada que
          fusionar.
        - Paso 4/5: el DELETE es el ``delete()`` del ORM (sin
          ``registry.clear_cache`` — no hay ormcache aquí).
        """
        accounts = list(accounts)
        account_to_merge_into = accounts[0]
        accounts_to_remove = accounts[1:]

        cls._check_access_rights(accounts)
        cls._update_foreign_keys_to_account(
            accounts_to_remove, account_to_merge_into)
        for account in accounts_to_remove:
            account.delete()
        return account_to_merge_into


class AccountMergeWizardLine(TransientModel):
    """≙ ``account.merge.wizard.line`` — una fila del agrupador: sección o
    cuenta. Aquí las filas viajan como dicts (ver el docstring del módulo);
    esta clase porta su lógica."""

    _name = 'account.merge.wizard.line'
    _description = "Account merge wizard line"
    _order = 'sequence, id'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _compute_info(cls, wizard_lines, is_group_by_name=False):
        """ This re-computes the error message for each wizard line every time the user selects or deselects a wizard line.

        In reality accounts will only affect the mergeability of other accounts in the same merge group.
        Therefore this method delegates the logic of determining whether an account can be merged to
        `_apply_different_companies_constraint` and `_apply_hashed_moves_constraint` which work on a merge group basis.

        (Docstring verbatim de la referencia; el constraint de hash está
        bloqueado — ver la tabla del módulo.)"""
        for line in wizard_lines:
            if line['display_type'] == 'line_section':
                line['info'] = cls._get_group_name(line, is_group_by_name)
        by_group = defaultdict(list)
        for line in wizard_lines:
            if line['display_type'] == 'account':
                by_group[line['grouping_key']].append(line)
        for group in by_group.values():
            for line in group:
                line['info'] = False
            cls._apply_different_companies_constraint(group)
        return wizard_lines

    @classmethod
    def _get_group_name(cls, line, is_group_by_name=False):
        """ Return a human-readable name for a wizard line's group, based on its `account_id`, in the format:
        '{Trade/Non-trade} Receivable {USD} {Reconcilable} {Deprecated}'

        (Docstring verbatim de la referencia.) Parcial declarado:
        ``non_trade`` no existe en la cuenta (sin prefijo Trade/Non-trade)
        y ``active`` se lee como ``not deprecated``."""
        account = line['account']
        account_type_label = dict(AccountAccount.ACCOUNT_TYPES).get(
            account.account_type, account.account_type)

        other_name_elements = []
        if account.currency_id:
            other_name_elements.append(account.currency.name)
        if account.reconcile:
            other_name_elements.append(_("Reconcilable"))
        if account.deprecated:
            other_name_elements.append(_("Deprecated"))

        if not is_group_by_name:
            grouping_key_name = account_type_label
            if other_name_elements:
                grouping_key_name = (
                    f'{grouping_key_name} ({", ".join(other_name_elements)})')
        else:
            grouping_key_name = (
                f'{account.name} '
                f'({", ".join([account_type_label] + other_name_elements)})')
        return grouping_key_name

    @classmethod
    def _apply_different_companies_constraint(cls, wizard_lines):
        """ Set `info` on wizard lines if an account cannot be merged
            because it belongs to the same company as another account.

            If users want to do that, they should mass-edit the account on the journal items.

            The wizard lines in `self` should have the same `grouping_key`.

        (Docstring verbatim de la referencia — invertido al puerto: aquí la
        cuenta tiene UNA empresa, así que el conflicto es "misma empresa
        que otra cuenta ya vista", con la FK simple.)"""
        companies_seen = {}
        for line in wizard_lines:
            if not line['is_selected'] or line['info']:
                continue
            company_id = line['account'].company_id
            if company_id in companies_seen:
                line['info'] = _("Belongs to the same company as %s.") % (
                    companies_seen[company_id])
            else:
                companies_seen[company_id] = line['account']
        return wizard_lines
