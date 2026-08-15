"""``base.partner.merge`` — la fusión de contactos duplicados.

Ejercita el porte de ``odoo19c: odoo/addons/base/wizard/base_partner_merge.py``
(``odoo-tools@622ddc2a``). Cada test cita la línea de la referencia cuyo
contrato verifica.
"""
import pytest
from django.db import connection

from addons.base.wizard.base_partner_merge import MergeGroup, PartnerMerge
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_partner_bank import ResPartnerBank
from exceptions import UserError

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_partner():
    def _make(name, **kwargs):
        # ``is_company`` es NOT NULL en este árbol — a diferencia de la
        # referencia, donde un booleano admite NULL y se lee como falso.
        kwargs.setdefault('is_company', False)
        return ResPartner.objects.create(name=name, **kwargs)
    return _make


# --- Ayudantes de introspección (``_get_fk_on``, ``table_columns``) ---

def test_the_foreign_keys_pointing_at_a_table_are_discovered():
    """≙ ``_get_fk_on`` (``odoo19c: :80-101``): las relaciones hacia la tabla."""
    relaciones = PartnerMerge._get_fk_on('res_partner')
    # ``res_users.partner_id`` apunta a ``res_partner``; el nombre real de la
    # columna lo pone Django (``partner_id``).
    assert ('res_users', 'partner_id') in relaciones


def test_a_column_without_unique_or_check_constraint_is_reported_as_free():
    """≙ ``_has_check_or_unique_constraint`` (``:104-117``)."""
    # ``res_partner.name`` no lleva UNIQUE ni CHECK.
    assert PartnerMerge._has_check_or_unique_constraint('res_partner', 'name') is False


# --- El orden de destino (``_get_ordered_partner``) ---

def test_the_destination_is_the_oldest_active_partner(make_partner):
    """≙ ``_get_ordered_partner`` (``:556-563``): activo primero, luego el más
    antiguo; el destino de la fusión es el ÚLTIMO de esa lista."""
    viejo = make_partner('Ana')
    nuevo = make_partner('Ana')
    ordenados = PartnerMerge._get_ordered_partner([nuevo.pk, viejo.pk])
    # ordenado por (no activo, created_at) descendente → el destino es el último
    assert ordenados[-1].pk == viejo.pk


def test_an_archived_partner_never_wins_the_destination(make_partner):
    """La referencia ordena por ``(not p.active, create_date)`` reverse: un
    archivado queda ANTES, así que nunca es el último (el destino)."""
    archivado = make_partner('Ana', active=False)
    activo = make_partner('Ana')
    ordenados = PartnerMerge._get_ordered_partner([archivado.pk, activo.pk])
    assert ordenados[-1].pk == activo.pk


# --- La consulta de agrupación (``_generate_query``) ---

def test_the_grouping_query_lowercases_email_and_name():
    """≙ ``_generate_query`` (``:481-521``): ``email`` y ``name`` se agrupan en
    minúscula; ``vat`` sin espacios."""
    consulta = PartnerMerge._generate_query(['email', 'name'])
    assert 'lower(email)' in consulta
    assert 'lower(name)' in consulta


def test_the_grouping_query_strips_spaces_from_vat():
    consulta = PartnerMerge._generate_query(['vat'])
    assert "replace(vat, ' ', '')" in consulta


def test_the_grouping_query_only_keeps_groups_of_two_or_more():
    consulta = PartnerMerge._generate_query(['email'])
    assert 'HAVING COUNT(*) >= 2' in consulta


def test_the_grouping_query_excludes_null_on_the_text_criteria():
    """La referencia filtra ``IS NOT NULL`` sólo sobre email/name/vat."""
    consulta = PartnerMerge._generate_query(['email', 'is_company'])
    assert 'email IS NOT NULL' in consulta
    assert 'is_company IS NOT' not in consulta


def test_an_empty_group_list_is_rejected():
    """≙ ``_compute_selected_groupby`` (``:523-538``): sin criterio, error."""
    with pytest.raises(UserError):
        PartnerMerge._compute_selected_groupby({})


def test_the_selected_groupby_drops_the_prefix():
    grupos = PartnerMerge._compute_selected_groupby(
        {'group_by_email': True, 'group_by_name': False})
    assert grupos == ['email']


# --- La fusión (``_merge``) ---

def test_merging_fewer_than_two_partners_is_a_no_op(make_partner):
    """≙ ``_merge`` (``:417-421``): con menos de dos, no hace nada."""
    solo = make_partner('Ana')
    PartnerMerge._merge([solo.pk])
    assert ResPartner.objects.filter(pk=solo.pk).exists()


def test_merging_more_than_three_partners_is_refused(make_partner):
    """≙ ``:423-424``: por seguridad, tres es el máximo."""
    ids = [make_partner(f'Ana {i}', email='a@b.mx').pk for i in range(4)]
    with pytest.raises(UserError):
        PartnerMerge._merge(ids)


def test_a_partner_cannot_be_merged_with_its_own_parent(make_partner):
    """≙ ``:427-433``: padre e hijo no se fusionan."""
    padre = make_partner('Empresa', is_company=True)
    hijo = make_partner('Empresa', parent=padre)
    with pytest.raises(UserError):
        PartnerMerge._merge([padre.pk, hijo.pk])


def test_partners_with_different_emails_need_the_extra_check_disabled(make_partner):
    """≙ ``:439-440``: con ``extra_checks`` sólo el administrador fusiona
    contactos de correos distintos."""
    a = make_partner('Ana', email='a@b.mx')
    b = make_partner('Ana', email='otro@b.mx')
    with pytest.raises(UserError):
        PartnerMerge._merge([a.pk, b.pk], extra_checks=True)


def test_the_source_partners_disappear_after_the_merge(make_partner):
    """≙ ``:470-471``: los origen se borran, el destino queda."""
    viejo = make_partner('Ana', email='a@b.mx')
    nuevo = make_partner('Ana', email='a@b.mx')
    PartnerMerge._merge([viejo.pk, nuevo.pk])
    assert ResPartner.objects.filter(pk=viejo.pk).exists()      # destino
    assert not ResPartner.objects.filter(pk=nuevo.pk).exists()  # origen


def test_the_destination_inherits_a_value_the_source_had(make_partner):
    """≙ ``_update_values`` (``:340-397``): el destino recoge los campos que
    tenía puestos el origen y él no."""
    destino = make_partner('Ana', email='a@b.mx')
    origen = make_partner('Ana', email='a@b.mx', phone='555-1234')
    PartnerMerge._merge([destino.pk, origen.pk])
    destino.refresh_from_db()
    assert destino.phone == '555-1234'


def test_a_foreign_key_is_repointed_at_the_destination(make_partner, django_user_model):
    """≙ ``_update_foreign_keys`` (``:316-322``): lo que apuntaba al origen
    pasa a apuntar al destino."""
    destino = make_partner('Ana', email='a@b.mx')
    origen = make_partner('Ana', email='a@b.mx')
    banco = ResPartnerBank.objects.create(acc_number='MX001', partner=origen)
    PartnerMerge._merge([destino.pk, origen.pk])
    banco.refresh_from_db()
    assert banco.partner_id == destino.pk


def test_a_duplicated_bank_account_is_absorbed_not_duplicated(make_partner):
    """≙ ``_merge_bank_accounts`` (``:399-413``): si el destino ya tiene esa
    cuenta, la del origen se borra en vez de mudarse."""
    destino = make_partner('Ana', email='a@b.mx')
    origen = make_partner('Ana', email='a@b.mx')
    ResPartnerBank.objects.create(acc_number='MX001', partner=destino)
    ResPartnerBank.objects.create(acc_number='MX001', partner=origen)
    PartnerMerge._merge([destino.pk, origen.pk])
    assert ResPartnerBank.objects.filter(partner=destino).count() == 1


def test_a_distinct_bank_account_moves_to_the_destination(make_partner):
    destino = make_partner('Ana', email='a@b.mx')
    origen = make_partner('Ana', email='a@b.mx')
    ResPartnerBank.objects.create(acc_number='MX001', partner=destino)
    ResPartnerBank.objects.create(acc_number='MX002', partner=origen)
    PartnerMerge._merge([destino.pk, origen.pk])
    assert ResPartnerBank.objects.filter(partner=destino).count() == 2


def test_the_explicit_destination_is_respected(make_partner):
    """≙ ``:442-448``: si el llamador nombra destino, ese gana — no el orden."""
    primero = make_partner('Ana', email='a@b.mx')
    segundo = make_partner('Ana', email='a@b.mx')
    PartnerMerge._merge([primero.pk, segundo.pk], dst_partner=segundo)
    assert ResPartner.objects.filter(pk=segundo.pk).exists()
    assert not ResPartner.objects.filter(pk=primero.pk).exists()


def test_partners_linked_to_more_than_one_user_are_refused(
        make_partner, django_user_model):
    """≙ ``:435-436``: dos usuarios distintos bloquean la fusión."""
    a = make_partner('Ana', email='a@b.mx')
    b = make_partner('Ana', email='a@b.mx')
    django_user_model.objects.create(partner=a, login='ana1')
    django_user_model.objects.create(partner=b, login='ana2')
    with pytest.raises(UserError):
        PartnerMerge._merge([a.pk, b.pk])


# --- El barrido de duplicados (``_process_query`` / los procesos) ---

def test_the_scan_finds_a_group_of_duplicates(make_partner):
    """≙ ``_process_query`` (``:618-648``): agrupa y devuelve los grupos."""
    make_partner('Ana', email='a@b.mx')
    make_partner('Ana', email='a@b.mx')
    make_partner('Otra', email='otra@b.mx')
    grupos = PartnerMerge._process_query(PartnerMerge._generate_query(['email']))
    assert len(grupos) == 1
    assert len(grupos[0].aggr_ids) == 2


def test_a_group_of_one_is_not_reported(make_partner):
    """``:632-634``: menos de dos accesibles, no es grupo."""
    make_partner('Sola', email='sola@b.mx')
    grupos = PartnerMerge._process_query(PartnerMerge._generate_query(['email']))
    assert grupos == []


def test_the_manual_process_returns_the_groups_it_found(make_partner):
    """≙ ``action_start_manual_process`` (``:650-662``)."""
    make_partner('Ana', email='a@b.mx')
    make_partner('Ana', email='a@b.mx')
    grupos = PartnerMerge.action_start_manual_process({'group_by_email': True})
    assert len(grupos) == 1


def test_the_automatic_process_merges_every_group_it_finds(make_partner):
    """≙ ``action_start_automatic_process`` (``:664-681``)."""
    make_partner('Ana', email='a@b.mx')
    make_partner('Ana', email='a@b.mx')
    fusionados = PartnerMerge.action_start_automatic_process({'group_by_email': True})
    assert fusionados == 1
    assert ResPartner.objects.filter(email='a@b.mx').count() == 1


def test_the_exclusion_of_partners_with_a_user_skips_the_group(
        make_partner, django_user_model):
    """≙ ``_compute_models`` + ``_partner_use_in`` (``:540-554``, ``:565-573``):
    con ``exclude_contact`` un grupo con usuario no se propone."""
    a = make_partner('Ana', email='a@b.mx')
    make_partner('Ana', email='a@b.mx')
    django_user_model.objects.create(partner=a, login='ana1')
    grupos = PartnerMerge._process_query(
        PartnerMerge._generate_query(['email']), exclude_contact=True)
    assert grupos == []


def test_the_group_holder_carries_the_smallest_id(make_partner):
    """``MergeGroup`` porta el ``min_id``/``aggr_ids`` de
    ``base.partner.merge.line`` (``:19-27``)."""
    a = make_partner('Ana', email='a@b.mx')
    b = make_partner('Ana', email='a@b.mx')
    grupos = PartnerMerge._process_query(PartnerMerge._generate_query(['email']))
    assert grupos[0].min_id == min(a.pk, b.pk)


def test_the_parent_migration_flattens_a_self_parented_partner(make_partner):
    """≙ ``parent_migration_process_cb`` (``:683-...``): al terminar, ningún
    contacto queda como padre de sí mismo."""
    solo = make_partner('Ana', email='a@b.mx')
    with connection.cursor() as cursor:
        cursor.execute('UPDATE res_partner SET parent_id = id WHERE id = %s',
                       [solo.pk])
    PartnerMerge.parent_migration_process_cb()
    solo.refresh_from_db()
    assert solo.parent_id is None


def test_the_summable_fields_are_empty_by_default():
    """≙ ``_get_summable_fields`` (``:334-338``): la base no suma nada; los
    addons que lo necesiten sobreescriben."""
    assert PartnerMerge._get_summable_fields() == []
