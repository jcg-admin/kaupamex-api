"""Related scalar inverse: existing Django save boundary and actual SQL effects."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

from addons.base.models import ResBank, ResCountry, ResPartner, ResPartnerBank

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def account():
    country, _ = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})
    bank = ResBank.objects.create(name='Original bank', bic='ORIGMXMM', country=country)
    partner = ResPartner.objects.create(name='Related inverse account', country=country)
    return ResPartnerBank.objects.create(
        acc_number='01234567891', bank=bank, partner=partner)


@pytest.mark.parametrize('source,target,value', [
    ('bank_name', 'name', 'Updated bank'), ('bank_bic', 'bic', 'FIXDMXMM'),
])
def test_explicit_save_persists_the_related_scalar_target(account, source, target, value):
    with CaptureQueriesContext(connection) as queries:
        setattr(account, source, value)
    assert len(queries) == 0
    original = ResBank.objects.values_list(target, flat=True).get(pk=account.bank_id)
    assert original != value

    account.save()

    assert ResBank.objects.values_list(target, flat=True).get(pk=account.bank_id) == value


@pytest.mark.parametrize('shape', ['scalar', 'list', 'tuple'])
def test_inverse_dispatch_accepts_existing_consumer_record_shapes(account, shape):
    account.bank_name = 'Dispatched bank'
    records = {'scalar': account, 'list': [account], 'tuple': (account,)}[shape]

    account._meta.get_field('bank_name').determine_inverse(records)

    assert ResBank.objects.values_list('name', flat=True).get(pk=account.bank_id) == 'Dispatched bank'


def test_unsaved_source_does_not_update_a_saved_target(account):
    record = ResPartnerBank(bank=account.bank, partner=account.partner, acc_number='01234567892')
    record.bank_name = 'Must remain local'
    with CaptureQueriesContext(connection) as queries:
        record._meta.get_field('bank_name').determine_inverse(record)
    assert len(queries) == 0
    account.bank.refresh_from_db()
    assert account.bank.name == 'Original bank'


def test_two_unsaved_records_propagate_only_in_memory(account):
    bank = ResBank(name='Unsaved bank')
    record = ResPartnerBank(bank=bank, partner=account.partner, acc_number='01234567893')
    record.bank_name = 'Unsaved updated'
    with CaptureQueriesContext(connection) as queries:
        record._meta.get_field('bank_name').determine_inverse(record)
    assert len(queries) == 0
    assert bank.name == 'Unsaved updated'
    assert bank.pk is None


def test_readonly_related_assignment_does_not_update_the_country(account):
    account.country_code = 'US'
    account.save()
    assert ResCountry.objects.get(pk=account.partner.country_id).code == 'MX'


def test_real_target_save_error_is_not_silenced(account, monkeypatch):
    account.bank_name = 'Cannot persist'

    def fail_save(self, *args, **kwargs):
        raise RuntimeError('target persistence failure')

    monkeypatch.setattr(ResBank, 'save', fail_save)
    with pytest.raises(RuntimeError, match='target persistence failure'):
        account._meta.get_field('bank_name').determine_inverse([account])


class WrongBankWriteRouter:
    def db_for_write(self, model, **hints):
        if model is ResBank:
            return 'unexpected_inverse_alias'
        return None


def test_inverse_keeps_the_target_database_despite_a_conflicting_router(account):
    account.bank_name = 'Bound target database'
    assert account.bank._state.db == 'default'
    with override_settings(DATABASE_ROUTERS=[WrongBankWriteRouter()]):
        account._meta.get_field('bank_name').determine_inverse(account)
    assert ResBank.objects.values_list('name', flat=True).get(pk=account.bank_id) == 'Bound target database'


def test_batch_snapshots_source_values_before_target_writes(account):
    second = ResPartnerBank.objects.create(
        acc_number='01234567892', bank=account.bank, partner=account.partner)
    account.bank_name = 'First snapshot'
    second.bank_name = 'Second snapshot'

    account._meta.get_field('bank_name').determine_inverse([account, second])

    assert ResBank.objects.values_list('name', flat=True).get(pk=account.bank_id) == 'Second snapshot'


def test_saved_source_does_not_update_an_unsaved_target(account):
    bank = ResBank(name='New target stays unchanged')
    account.bank = bank
    account.bank_name = 'Must not cross the identity guard'
    with CaptureQueriesContext(connection) as queries:
        account._meta.get_field('bank_name').determine_inverse(account)
    assert len(queries) == 0
    assert bank.name == 'New target stays unchanged'
    assert bank.pk is None
