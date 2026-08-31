"""Escribir un ``related`` escribe en el extremo de la cadena (#254).

#253 dejó los nueve constructores aceptando la clave y el censo en 0 sin
cubrir. Lo que ningún caso ejercía es la **escritura**, y su ausencia no era
inocua: ``bank_name`` y ``bank_bic`` ya se declaran con ``readonly=False``
(``odoo19c: res_bank.py:97-98``), que es la forma con la que la fuente dice
*«esto se puede escribir desde aquí, y el inverso lo propaga»*.

Sin el inverso, ``cuenta.bank_name = 'X'`` guardaba un valor en sombra sobre la
cuenta y **el banco no cambiaba**. Es la misma forma que el ``**_ignored`` de
``One2many`` (:ref:`h-api-978`): acepta y no hace nada.

La conducta la fija ``Field._inverse_related`` (``odoo19c: fields.py:724``),
que este árbol ya tiene portado verbatim sobre ``models.Field`` — pero un
``NonStored`` **no** es un ``models.Field``, así que nunca lo alcanzaba.
"""
import pytest
from django.apps import apps

import fields
from orm.fields_nonstored import NonStored


@pytest.fixture
def account(db):
    """Una cuenta con banco y titular — la cadena completa de ``res_bank``."""
    def base(name):
        return apps.get_model('base', name)
    country, _created = base('ResCountry').objects.get_or_create(
        code='MX', defaults={'name': 'México'})
    bank = base('ResBank').objects.create(
        name='Banco original', bic='ORIGMXMM', country=country)
    partner = base('ResPartner').objects.create(name='Titular')
    return base('ResPartnerBank').objects.create(
        acc_number='0123456789', partner=partner, bank=bank)


class TestTheWriteReachesTheEndOfTheChain:
    """``:724`` — «inverse the related field ``self`` on ``records``»."""

    def test_writing_bank_name_renames_the_bank(self, account):
        """El caso que la fuente declara ``readonly=False`` a propósito: el
        formulario de la cuenta corrige el nombre del banco desde ahí."""
        account.bank_name = 'Banco corregido'

        account.bank.refresh_from_db()
        assert account.bank.name == 'Banco corregido'

    def test_writing_bank_bic_reaches_the_bank_too(self, account):
        account.bank_bic = 'FIXDMXMM'

        account.bank.refresh_from_db()
        assert account.bank.bic == 'FIXDMXMM'

    def test_a_readonly_related_does_not_propagate(self, account):
        """El control que discrimina al anterior.

        ``country_code`` no declara ``readonly=False``, así que toma el defecto
        de ``:458`` —``readonly=True``— y la fuente **no le cablea inverso**
        (``:632``: ``if self.inherited or not (self.readonly or …)``). Escribir
        sobre él no puede alcanzar el país.

        Sin este caso, un ``__set__`` que propagara siempre pasaría el de
        arriba igual y nadie sabría que la frontera existe.
        """
        original_country = account.partner.country_id

        account.country_code = 'US'

        assert account.partner.country_id == original_country
        assert account.country_code == 'US', (
            'el valor en memoria sí se guarda — lo que no viaja es la cadena')


class TestTheGuardOfTheSource:
    """``:731`` — «update 'target' only if 'record' and 'target' are both real
    or both new»."""

    def test_an_unsaved_record_does_not_write_into_a_saved_one(self, db):
        """Verbatim de la fuente: ``bool(target.id) == bool(record.id)``.

        Una cuenta sin guardar que apunta a un banco guardado no puede
        renombrarlo — la escritura se queda en memoria hasta que la cuenta
        exista.
        """
        def base(name):
            return apps.get_model('base', name)
        bank = base('ResBank').objects.create(name='Banco intacto')
        unsaved = base('ResPartnerBank')(acc_number='999', bank=bank)

        unsaved.bank_name = 'No debería llegar'

        bank.refresh_from_db()
        assert bank.name == 'Banco intacto'

    def test_a_broken_link_does_not_raise(self, db):
        """Sin banco no hay extremo donde escribir, y eso no es un error."""
        account = apps.get_model('base', 'ResPartnerBank')(acc_number='888')

        account.bank_name = 'Sin destino'

        assert account.bank_name == 'Sin destino'


class TestTheRelationalShape:
    """El extremo puede ser un manager, no un valor — ``ResCompany.bank_ids``
    (``odoo19c: res_company.py:77``) es de esa forma."""

    def test_writing_a_manager_end_uses_the_django_api(self, account, db):
        """Django prohíbe la asignación directa al reverso de una FK y nombra
        la salida en su propio error: ``.set()``. El inverso la usa en vez de
        reventar.

        .. note:: El conjunto se amplía; **no se puede vaciar**, y no es una
           omisión de aquí.

           ``ResPartnerBank.partner`` no admite nulo, así que Django no le da
           ``clear()`` ni ``remove()`` a su manager inverso: su ``set()`` cae
           al ``add()`` de lo que reciba. Vaciar el conjunto huerfanaría filas
           requeridas, y el stack lo impide por construcción.

           Se midió antes de escribir este caso: ``set([])`` sobre este manager
           deja el conteo intacto, sin error. La primera versión afirmaba lo
           contrario y medía una conducta que Django no ofrece.
        """
        sibling = apps.get_model('base', 'ResPartnerBank').objects.create(
            acc_number='555', partner=account.partner, bank=account.bank)
        third = apps.get_model('base', 'ResPartnerBank').objects.create(
            acc_number='777', partner=apps.get_model(
                'base', 'ResPartner').objects.create(name='Otro titular'),
            bank=account.bank)

        descriptor = fields.One2many(related='partner.bank_accounts',
                                     readonly=False)
        descriptor.name = 'bank_accounts_of_the_partner'
        assert isinstance(descriptor, NonStored)

        descriptor.__set__(account, [third])

        assert account.partner.bank_accounts.count() == 3, (
            'las dos que ya tenía más la que el inverso movió por .set()')
        third.refresh_from_db()
        assert third.partner_id == account.partner_id
        assert sibling.partner_id == account.partner_id


class TestResCompanyBankIds:
    """``ResCompany.bank_ids`` — el campo que este hilo empezó bloqueando.

    ``odoo19c: res_company.py:77`` lo declara
    ``fields.One2many(related='partner_id.bank_ids', readonly=False)``. La
    prosa de ``res_company.py`` lo declinaba con una premisa —*«llega solo
    cuando ``res_partner`` declare el reverso de ``res.bank``»*— que dejó de
    ser cierta cuando ``ResPartnerBank.partner`` declaró
    ``related_name='bank_accounts'``.
    """

    @pytest.fixture
    def company(self, db):
        def base(name):
            return apps.get_model('base', name)
        partner = base('ResPartner').objects.create(name='Titular de la empresa')
        return base('ResCompany').objects.create(
            name='Empresa de prueba', code='prueba', partner=partner)

    def test_the_company_reads_the_accounts_of_its_partner(self, company):
        bank = apps.get_model('base', 'ResBank').objects.create(name='Banco')
        apps.get_model('base', 'ResPartnerBank').objects.create(
            acc_number='111', partner=company.partner, bank=bank)

        assert company.bank_ids.count() == 1
        assert company.bank_ids.first().acc_number == '111'

    def test_it_took_no_column(self):
        """Sin ``store`` no hay columna, y por eso ``makemigrations --check``
        sigue limpio tras declararlo."""
        company_model = apps.get_model('base', 'ResCompany')
        assert 'bank_ids' not in {f.name for f in company_model._meta.get_fields()}
        assert isinstance(company_model.bank_ids, NonStored)

    def test_writing_from_the_company_reaches_the_partner(self, company):
        """Su ``readonly=False`` dice que el conjunto se escribe desde la
        empresa; el inverso lo lleva al titular. Es el eje que #253 dejó sin
        ejercer."""
        bank = apps.get_model('base', 'ResBank').objects.create(name='Banco')
        otro = apps.get_model('base', 'ResPartner').objects.create(name='Otro')
        account_of_another = apps.get_model('base', 'ResPartnerBank').objects.create(
            acc_number='222', partner=otro, bank=bank)

        company.bank_ids = [account_of_another]

        account_of_another.refresh_from_db()
        assert account_of_another.partner_id == company.partner_id
