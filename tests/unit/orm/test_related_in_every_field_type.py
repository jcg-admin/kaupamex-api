"""``related=`` en los tipos que el despachador no cubría (#253).

#252 lo cableó en ``Char`` y en los que fabrica ``make_dispatcher``. Medido
por conducta con ``python3 scripts/census_related_fields.py``, eso deja fuera
la mayor parte del universo, encabezada por ``Many2one``.

La forma la fija la referencia, y es la misma para los nueve: **con
``related=`` los argumentos del tipo se vuelven opcionales**, porque el
extremo de la cadena los determina::

    product_category = fields.Many2one(related='product_id.categ_id')
    tag_ids          = fields.Many2many(related='lead_id.tag_ids')
    subordinate_ids  = fields.One2many(related='employee_id.subordinate_ids')

Y cuando SÍ se guarda, el comodelo vuelve a hacer falta porque hay columna::

    company_id = fields.Many2one(comodel_name='res.company',
                                 related='journal_id.company_id', store=True)

``One2many`` es el caso peor y por eso tiene sección propia: no rechazaba la
clave — la **tragaba** en su ``**kwargs`` y devolvía un campo sin ella. El
sitio de declaración se leía correcto y no hacía nada.
"""
import pytest
from django.apps import apps
from django.db import models

import fields
from orm.fields_nonstored import NonStored

#: Los nueve que la sonda de conducta del censo daba por no cubiertos, con los
#: posicionales mínimos que su constructor exige cuando NO hay ``related``.
UNCOVERED = [
    ('Many2one', ()),
    ('Many2many', ()),
    ('One2many', ()),
    ('Binary', ()),
    ('Image', ()),
    ('Html', ()),
    ('Monetary', ()),
    ('Json', ()),
    ('Properties', ()),
]


class TestEveryConstructorAcceptsTheKey:
    """El mecanismo es del campo, no del tipo — ninguno puede quedarse fuera."""

    @pytest.mark.parametrize('type_name,arguments', UNCOVERED)
    def test_the_constructor_takes_related(self, type_name, arguments):
        field = getattr(fields, type_name)(*arguments, related='partner.name')
        assert field.related == 'partner.name', type_name

    @pytest.mark.parametrize('type_name,arguments', UNCOVERED)
    def test_without_store_the_carrier_is_the_non_stored_one(self, type_name,
                                                             arguments):
        """``:455`` — un related no se guarda por defecto, así que no hay
        columna que declarar y el portador es el descriptor."""
        field = getattr(fields, type_name)(*arguments, related='partner.name')
        assert isinstance(field, NonStored), (
            f'{type_name} devolvió {type(field).__name__}')

    @pytest.mark.parametrize('type_name,arguments', UNCOVERED)
    def test_the_four_defaults_of_the_source_apply(self, type_name, arguments):
        """``:456-458`` — los mismos cuatro, sea cual sea el tipo."""
        field = getattr(fields, type_name)(*arguments, related='partner.name')
        assert (field.store, field.compute_sudo, field.copy, field.readonly) \
            == (False, True, False, True), type_name


class TestTheRelationalArgumentsBecomeOptional:
    """Lo que la referencia declara: sin store, la cadena determina el tipo."""

    def test_many2one_needs_no_comodel_when_it_is_a_projection(self):
        """``odoo19c: account/models/account_analytic_line.py`` —
        ``fields.Many2one(related='product_id.categ_id')``, sin comodelo."""
        field = fields.Many2one(related='product.category')
        assert isinstance(field, NonStored)
        assert field.related == 'product.category'

    def test_many2one_keeps_the_column_when_the_declaration_asks_for_it(self):
        """``odoo19c: account/models/account_bank_statement.py:58`` — con
        ``store=True`` el comodelo vuelve a hacer falta, porque hay columna.

        Es el control que discrimina al anterior: si el constructor devolviera
        siempre un descriptor, este caso pasaría igual y nadie sabría que la
        rama con columna existe.
        """
        field = fields.Many2one(
            'base.ResCompany', related='journal.company', store=True,
            on_delete=models.SET_NULL, null=True)
        assert isinstance(field, models.ForeignKey), type(field).__name__
        assert field.store is True

    def test_many2many_needs_no_comodel_either(self):
        """``fields.Many2many(related="lead_id.tag_ids", readonly=True)``."""
        field = fields.Many2many(related='lead.tags', readonly=True)
        assert isinstance(field, NonStored)
        assert field.readonly is True


class TestOne2manyStopsSwallowingTheKey:
    """El peor de los nueve: aceptaba y no hacía nada.

    ``One2many.__init__`` traga ``**kwargs``, así que
    ``fields.One2many(related='a.b')`` **no reventaba** — devolvía un campo sin
    la ruta puesta. Un constructor que acepta y descarta es peor que uno que
    rechaza: el sitio de declaración se lee correcto y el campo no existe.
    """

    def test_it_no_longer_returns_a_field_without_the_route(self):
        field = fields.One2many(related='employee.subordinates')
        assert getattr(field, 'related', None) == 'employee.subordinates'

    def test_the_ordinary_declaration_still_needs_its_two_arguments(self):
        """El control discriminante: sin ``related`` el ``One2many`` de
        siempre sigue exigiendo comodelo e inverso, que es su contrato."""
        field = fields.One2many('base.ResPartnerBank', 'partner')
        assert not isinstance(field, NonStored)
        assert field.comodel_name == 'base.ResPartnerBank'
        assert field.inverse_name == 'partner'


class TestTheChainResolvesForEachShape:
    """Leer un related relacional da lo que hay al final de la cadena — una
    instancia, un manager o un valor. El recorrido es el mismo ``getattr``."""

    @pytest.fixture
    def account(self, db):
        def base(name):
            return apps.get_model('base', name)
        country, _created = base('ResCountry').objects.get_or_create(
            code='MX', defaults={'name': 'México'})
        bank = base('ResBank').objects.create(name='Banco', country=country)
        partner = base('ResPartner').objects.create(name='Titular')
        return base('ResPartnerBank').objects.create(
            acc_number='0123456789', partner=partner, bank=bank)

    def test_a_many2one_chain_gives_the_instance_at_the_end(self, account):
        """El extremo es un registro, no un escalar: el recorrido no cambia."""
        descriptor = fields.Many2one(related='bank.country')
        descriptor.name = 'bank_country'
        assert descriptor.resolve_related(account).code == 'MX'

    def test_a_one2many_chain_gives_the_manager_at_the_end(self, account):
        """``ResCompany.bank_ids`` (``odoo19c: res_company.py:77``) es de esta
        forma: el extremo es el conjunto del reverso, no un valor."""
        descriptor = fields.One2many(related='partner.bank_accounts')
        descriptor.name = 'bank_accounts_of_the_partner'
        assert descriptor.resolve_related(account).count() == 1
