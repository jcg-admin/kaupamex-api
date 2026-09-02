"""#305 — el motor sobre modelos REALES, no sobre sondas.

La tarea #273 construyo el motor y lo probo con modelos de sonda declarados en
el propio archivo de prueba. Esto mide lo otro: que la declaracion ``compute=``
que los 36 campos con columna ahora llevan produce **aristas reales** en el
grafo, y que el ciclo completo —marcar, recalcular, volcar— llega a la columna
de una tabla del producto.

Veredicto por el criterio de las dos categorias: no aplica. Aqui no se
construye nada; se comprueba que lo construido en #273 recibe lo declarado en
#305. Es el control de integracion entre las dos tareas.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps

from orm import registry
from orm.environments import env, transaction_scope
from orm.utils import model_field_registry


AccountAccount = apps.get_model('account', 'AccountAccount')
AccountJournal = apps.get_model('account', 'AccountJournal')
AccountMove = apps.get_model('account', 'AccountMove')
AccountMoveLine = apps.get_model('account', 'AccountMoveLine')
ResCompany = apps.get_model('base', 'ResCompany')
SaleOrder = apps.get_model('sale', 'SaleOrder')
SaleOrderLine = apps.get_model('sale', 'SaleOrderLine')
CrmLead = apps.get_model('crm', 'CrmLead')


@pytest.fixture
def move(db):
    """Un asiento real al que colgar la linea.

    ``move`` es requerido (``account_move_line.py:52``, sin ``null=True``), asi
    que una linea suelta no es una fila valida: el receptor ``pre_save`` de
    ``l10n_mx`` la toca antes de que la base opine. Se construye como ya lo
    hace ``tests/integration/account/test_create_debit_note_endpoint.py:59``.
    """
    company = ResCompany.objects.create(code='wiring-305', name='Wiring 305')
    journal = AccountJournal.objects.create(
        name='Ventas', code='W05', type='sale', company=company)
    return AccountMove.objects.create(
        move_type='out_invoice', date=date(2026, 1, 1),
        journal=journal, company=company, state='draft')


@pytest.fixture
def account(move):
    return AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=move.company)


def field_of(model, name):
    return model._meta.get_field(name)


def dependents(model, name):
    return sorted(f.name for f in
                  registry.get_dependent_fields(field_of(model, name)))


class TestTheDeclarationReachesTheGraph:
    """Un campo con ``compute=`` es clave del grafo; sin el, no lo es."""

    def test_every_declared_dependency_resolves(self):
        """Ninguna cadena punteada nombra un campo que no existe.

        Es el control mas barato del cableado entero: el porte estricto de
        ``resolve_depends`` lanza ``ValueError`` ante un nombre desconocido, asi
        que este caso recorre TODO el arbol y falla nombrando el culpable. Ya
        encontro dos: ``@api.depends('create_date')`` sobre un modelo cuya
        columna de auditoria se llama ``created_at``.
        """
        rotas = []
        for model in apps.get_models():
            for field in model_field_registry(model).values():
                resolver = getattr(field, 'resolve_depends', None)
                if resolver is None or not registry.field_depends[field]:
                    continue
                try:
                    list(resolver(registry))
                except ValueError as error:
                    rotas.append(f'{model.__name__}: {error}')
        assert rotas == []

    def test_a_line_price_reaches_the_line_totals(self):
        assert 'price_subtotal' in dependents(SaleOrderLine, 'price_unit')

    def test_a_line_price_reaches_the_ORDER_totals_through_the_relation(self):
        """El cierre transitivo de la capa B sobre modelos del producto: el
        precio de una linea alcanza el total de SU orden, que es otro modelo."""
        assert 'amount_total' in dependents(SaleOrderLine, 'price_unit')

    def test_the_partner_of_a_lead_reaches_its_derived_fields(self):
        derivados = dependents(CrmLead, 'partner_id')
        for name in ('contact_name', 'email_from', 'phone', 'partner_name'):
            assert name in derivados

    def test_a_field_nobody_computes_from_has_no_dependents(self):
        """El control que discrimina: la MISMA maquinaria sobre un campo del
        que nadie deriva no produce aristas. Sin este caso, los de arriba no
        distinguen «el grafo se construyo» de «todo depende de todo»."""
        assert dependents(AccountMoveLine, 'display_type') == []


class TestTheWiringIsStoredAndNotEditable:
    """El campo conserva su columna y deja de ser escribible desde el API."""

    @pytest.mark.parametrize('model,name', [
        (AccountMoveLine, 'balance'),
        (SaleOrder, 'amount_total'),
        (SaleOrderLine, 'price_subtotal'),
        (CrmLead, 'email_from'),
    ])
    def test_it_keeps_its_column(self, model, name):
        """``store=True`` va explicito en las 36 declaraciones porque el bloque
        ``compute`` de la fuente pone ``store=False`` por defecto: sin el, el
        cableado habria RETIRADO 36 columnas."""
        field = field_of(model, name)
        assert field.store is True
        assert field.column_type

    @pytest.mark.parametrize('model,name', [
        (SaleOrder, 'amount_total'),
        (SaleOrder, 'amount_untaxed'),
        (SaleOrderLine, 'price_subtotal'),
        (CrmLead, 'date_open'),
        (CrmLead, 'won_status'),
    ])
    def test_the_one_the_source_leaves_readonly_is_not_editable(
            self, model, name):
        """El carril nativo de DRF: un campo no editable sale ``read_only`` del
        ``ModelSerializer`` sin que ningun serializer lo declare
        (``rest_framework/utils/field_mapping.py:124-128``).

        La fuente NO declara ``readonly=`` en estos, asi que el bloque
        ``compute`` lo deja en ``not inverse`` = ``True``
        (``fields_nonstored.py:_apply_compute_block``).
        """
        assert field_of(model, name).editable is False

    @pytest.mark.parametrize('model,name', [
        (AccountMoveLine, 'balance'),
        (AccountAccount, 'account_type'),
        (SaleOrder, 'validity_date'),
        (CrmLead, 'name'),
        (CrmLead, 'contact_name'),
        (CrmLead, 'email_from'),
        (CrmLead, 'phone'),
    ])
    def test_the_one_the_source_declares_writable_stays_editable(
            self, model, name):
        """El control que discrimina, y el que este cableado se habia comido.

        La fuente declara ``readonly=False`` en 15 de los 36: ahi el computo
        RELLENA lo que el usuario no puso, y el usuario **si** puede escribir.
        El primer pase de #305 declaro solo ``compute=`` + ``store=True``, y el
        bloque de la fuente derivo ``readonly=True`` por omision — publicando
        read_only 15 campos que la referencia deja escribibles. Sin este caso,
        el de arriba no distingue «el cableado es fiel» de «todo quedo
        bloqueado».
        """
        assert field_of(model, name).editable is True

    @pytest.mark.parametrize('model,name,method', [
        (CrmLead, 'email_from', '_inverse_email_from'),
        (CrmLead, 'phone', '_inverse_phone'),
    ])
    def test_the_two_with_an_inverse_declare_it(self, model, name, method):
        """Los dos que la fuente declara inversibles. El metodo ya existia en
        el arbol (``crm_lead.py:839`` y ``:867``) y ninguna declaracion lo
        nombraba: estaba escrito y desconectado."""
        assert field_of(model, name).inverse == method
        assert callable(getattr(model, method))

    @pytest.mark.parametrize('model,name', [
        (AccountAccount, 'account_type'),
        (AccountMoveLine, 'balance'),
        (SaleOrder, 'validity_date'),
        (SaleOrderLine, 'price_subtotal'),
        (CrmLead, 'team_id'),
    ])
    def test_the_nine_the_source_precomputes_declare_it(self, model, name):
        """``precompute=True`` no es decoracion: ``resolve_depends`` valida la
        cadena y desactiva el adelanto cuando un precomputado depende de un
        almacenado que no lo es (``src/orm/fields.py:2187-2193``)."""
        assert field_of(model, name).precompute is True


class TestTheCycleReachesTheColumn:
    """De punta a punta sobre una tabla del producto."""

    def test_touching_debit_recomputes_the_balance_into_the_column(
            self, move, account):
        line = AccountMoveLine.objects.create(
            move=move, account=account,
            debit=Decimal('100.00'), credit=Decimal('40.00'))
        AccountMoveLine.objects.filter(pk=line.pk).update(
            balance=Decimal('0.00'))
        line.refresh_from_db()
        assert line.balance == Decimal('0.00')

        with transaction_scope():
            line.modified(['debit'])
            assert line.pk in env().records_to_compute(
                field_of(AccountMoveLine, 'balance'))
            line.flush_recordset(['balance'])

        line.refresh_from_db()
        assert line.balance == Decimal('60.00')

    def test_without_touching_it_the_column_is_left_alone(self, move, account):
        """El control que discrimina: sin ``modified``, el mismo volcado no
        escribe. Lo que mueve el valor es la marca, no el ``flush``."""
        line = AccountMoveLine.objects.create(
            move=move, account=account,
            debit=Decimal('100.00'), credit=Decimal('40.00'))
        AccountMoveLine.objects.filter(pk=line.pk).update(
            balance=Decimal('0.00'))
        line.refresh_from_db()

        with transaction_scope():
            line.flush_recordset(['balance'])

        line.refresh_from_db()
        assert line.balance == Decimal('0.00')
