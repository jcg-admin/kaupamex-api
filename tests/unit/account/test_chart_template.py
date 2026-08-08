"""Cargar el plan contable genérico en una empresa (#140, :ref:`h-api-348`).

Espeja el propósito de ``odoo19c: account/models/chart_template.py``: una
empresa recién creada no tiene cuentas ni impuestos, y el plan es lo que la
deja operable. Hasta ahora ``account`` no sembraba **nada** — 0 cuentas, 0
impuestos, 0 diarios—, que es la causa de fondo de :ref:`h-api-344`.

Lo que se fija aquí es el mecanismo, no el contenido de las tablas: que los
registros nazcan con identificador externo **por empresa**, que las referencias
entre ellos se resuelvan por ese nombre, y que dos empresas obtengan planos
independientes.
"""
import pytest

from addons.account.models import (
    AccountAccount,
    AccountAccountTag,
    AccountFiscalPosition,
    AccountGroup,
    AccountJournal,
    AccountReconcileModel,
    AccountTax,
    AccountTaxGroup,
    ChartTemplate,
)
from addons.account.models.chart_template import TEMPLATE_REGISTRY, template
from addons.account.models.account_tax_repartition_line import AccountTaxRepartitionLine
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from exceptions import UserError

pytestmark = [pytest.mark.unit]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.mark.django_db
class TestRegistry:
    def test_generic_chart_is_registered(self, db):
        """Importar el módulo de la plantilla la registra — sin barrer clases."""
        assert 'generic_coa' in ChartTemplate.get_chart_template_mapping()

    def test_generic_wins_without_country(self, db):
        assert ChartTemplate.guess_chart_template(None) == 'generic_coa'


@pytest.mark.django_db
class TestLoading:
    def test_loads_the_four_families(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        # 46 del CSV + las 4 de utilidad que crea el paso del banco
        # (transitoria, transferencia y las dos de pendientes).
        assert AccountAccount.objects.filter(company=company).count() == 50
        assert AccountTaxGroup.objects.filter(company=company).count() == 2
        assert AccountTax.objects.filter(company=company).count() == 4
        assert AccountFiscalPosition.objects.filter(company=company).count() == 2

    def test_each_record_gets_its_external_id(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        account = ChartTemplate.ref('receivable', company)
        assert account.code == '121000'
        assert IrModelData.objects.filter(
            module='account', name=f'{company.pk}_receivable').exists()

    def test_tax_points_to_its_group(self, company):
        """La referencia entre registros se resuelve **por nombre**, no por id.

        Es lo que el CSV expresa con ``tax_group_id=tax_group_15``: sin el
        identificador externo esa columna no significa nada.
        """
        ChartTemplate.try_loading('generic_coa', company)

        tax = ChartTemplate.ref('sale_tax_template', company)
        assert tax.tax_group == ChartTemplate.ref('tax_group_15', company)
        assert tax.amount == 15
        assert tax.type_tax_use == 'sale'

    def test_repartition_lines_are_created_with_the_tax(self, company):
        """Cuatro filas del CSV con ``id`` vacío son cuatro líneas hijas.

        Dos de factura (base + impuesto) y dos de rectificativa. La línea de
        impuesto apunta a la cuenta donde se acumula lo recaudado.
        """
        ChartTemplate.try_loading('generic_coa', company)

        tax = ChartTemplate.ref('sale_tax_template', company)
        lines = AccountTaxRepartitionLine.objects.filter(tax=tax)
        assert lines.count() == 4
        assert lines.filter(document_type='invoice').count() == 2
        assert lines.filter(document_type='refund').count() == 2

        received = ChartTemplate.ref('tax_received', company)
        tax_line = lines.filter(repartition_type='tax', document_type='invoice')
        assert tax_line.get().account == received

    def test_company_ends_up_with_default_taxes(self, company):
        """El paso que cierra la carga: la empresa **configurada**.

        Es exactamente el hueco de :ref:`h-api-344` — nadie sembraba un
        impuesto, así que ``account_sale_tax`` no tenía de dónde salir.
        """
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        assert company.account_sale_tax == ChartTemplate.ref(
            'sale_tax_template', company)
        assert company.account_purchase_tax == ChartTemplate.ref(
            'purchase_tax_template', company)


@pytest.mark.django_db
class TestBaseTemplate:
    """Los diarios no pertenecen a un plan: pertenecen a *tener* contabilidad.

    Se declaran con ``@template(model=...)`` sin código, y el resolutor los
    aplica a todo plan — ``[None] + parents`` en la referencia.
    """

    def test_company_receives_the_six_journals(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        journals = AccountJournal.objects.filter(company=company)
        assert journals.count() == 6
        assert set(journals.values_list('code', flat=True)) == {
            'INV', 'BILL', 'MISC', 'EXCH', 'CABA', 'BNK1'}

    def test_reconcile_models_are_created_with_their_line(self, company):
        """Transferencia interna y comisión bancaria, cada una con su línea.

        Las hijas se declaran como lista de diccionarios; el cargador las crea
        igual que las de reparto del CSV.
        """
        ChartTemplate.try_loading('generic_coa', company)

        rules = AccountReconcileModel.objects.filter(company=company)
        assert rules.count() == 2

        fee_rule = ChartTemplate.ref('bank_fees_reco', company)
        assert fee_rule.match_label == 'contains'
        assert fee_rule.line_ids.count() == 1
        assert fee_rule.line_ids.get().amount_string == '100'

    def test_journals_carry_the_three_dashboard_fields(self, company):
        """``sequence``, ``show_on_dashboard`` y ``color`` — de la referencia.

        Una versión anterior los omitía diciendo que "el modelo no los tiene".
        Eso describía nuestro estado, no una incapacidad: los tres existen en
        ``odoo19c`` (``account_journal.py:147`` y
        ``account_journal_dashboard.py:30-31``) y Django los declara igual.
        """
        ChartTemplate.try_loading('generic_coa', company)

        sale_journal = AccountJournal.objects.get(company=company, type='sale')
        assert (sale_journal.sequence, sale_journal.show_on_dashboard, sale_journal.color) == (5, True, 11)

        misc_journal = AccountJournal.objects.get(company=company, code='MISC')
        assert misc_journal.show_on_dashboard is False

    def test_journals_come_out_in_reference_order(self, company):
        """``_order = 'sequence, type, code'`` — no ``code`` a secas."""
        ChartTemplate.try_loading('generic_coa', company)

        codes = list(
            AccountJournal.objects.filter(company=company).values_list('code', flat=True))
        assert codes[:3] == ['INV', 'BILL', 'BNK1']

    def test_sale_journal_is_the_one_the_entry_looks_up(self, company):
        """``create_invoice_from_subscription`` busca por ``type='sale'``.

        Es el consumidor real: sin un diario de ese tipo lanza ``UserError`` y
        el cobro no se puede asentar.
        """
        ChartTemplate.try_loading('generic_coa', company)

        sale_journal = AccountJournal.objects.get(company=company, type='sale')
        assert sale_journal.code == 'INV'
        assert sale_journal == ChartTemplate.ref('sale', company)


@pytest.mark.django_db
class TestLoadOnCompanyCreate:
    """El cargador sin consumidor no vale: una empresa hija hereda el plan.

    ≙ el ``create`` de la referencia, que instancia el plan de la raíz. Una
    empresa **raíz** no entra por aquí — su plan lo elige quien la aprovisiona.
    """

    def test_subsidiary_inherits_root_chart(self, company):
        company.chart_template = 'generic_coa'
        company.save(update_fields=['chart_template'])

        subsidiary = ResCompany.objects.create(
            code='acme-mx', name='ACME México', parent=company)

        assert AccountAccount.objects.filter(company=subsidiary).count() == 46
        assert AccountJournal.objects.filter(company=subsidiary, type='sale').exists()

    def test_nothing_loads_without_a_chart_on_the_root(self, company):
        """El receptor es no-op mientras nadie declare un plan.

        Es lo que hace que cablearlo no cambie el comportamiento de ninguna
        empresa existente.
        """
        assert company.chart_template is None

        subsidiary = ResCompany.objects.create(
            code='acme-co', name='ACME Colombia', parent=company)

        assert AccountAccount.objects.filter(company=subsidiary).count() == 0

    def test_root_does_not_load_itself(self, db):
        """Una raíz es su propio ``parent_ids[0]`` — sin el guard se cargaría sola."""
        root = ResCompany.objects.create(
            code='beta-root', name='BETA', chart_template='generic_coa')

        assert AccountAccount.objects.filter(company=root).count() == 0


@pytest.mark.django_db
class TestCompanyIsolation:
    def test_two_companies_get_independent_charts(self, company):
        """``receivable`` no nombra una cuenta: nombra un papel.

        La cuenta concreta es la de cada empresa, y por eso el identificador
        externo lleva su id delante.
        """
        other = ResCompany.objects.create(code='beta', name='BETA')
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', other)

        first = ChartTemplate.ref('receivable', company)
        second = ChartTemplate.ref('receivable', other)
        assert first != second
        assert first.code == second.code == '121000'
        assert first.company == company and second.company == other

    def test_reloading_does_not_duplicate(self, company):
        """Idempotente por identificador externo, como la referencia."""
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', company)

        assert AccountAccount.objects.filter(company=company).count() == 50


@pytest.mark.django_db
class TestRegistryComposes:
    """Dos declaraciones al mismo ``(codigo, modelo)`` se **componen**.

    ≙ ``_template_register``, un ``defaultdict(list)``
    (``odoo19c: chart_template.py:78-88``). Una versión anterior de este puerto
    guardaba una sola función por clave: la segunda declaración borraba a la
    primera **en silencio**, que es el modo de fallo que este test fija.
    """

    def test_second_declaration_does_not_erase_the_first(self, company):
        @template(model='account.journal')
        def extra_journal(cls, template_code):
            return {'extra': {
                'name': 'Diario extra', 'type': 'general', 'code': 'XTRA'}}

        try:
            ChartTemplate.try_loading('generic_coa', company)
            codes = set(AccountJournal.objects
                          .filter(company=company).values_list('code', flat=True))
            assert 'XTRA' in codes          # la nueva entró
            assert 'INV' in codes           # y la base sigue ahí
        finally:
            TEMPLATE_REGISTRY[None]['account.journal'].remove(extra_journal)

    def test_template_receives_the_chart_code(self, company):
        """La firma ``(cls, template_code)`` no es decorativa.

        Una plantilla **base** sirve a cualquier plan; sin el parámetro no
        podría saber a cuál está sirviendo.
        """
        seen = []

        @template(model='account.journal')
        def spy(cls, template_code):
            seen.append(template_code)
            return {}

        try:
            ChartTemplate.try_loading('generic_coa', company)
            assert seen == ['generic_coa']
        finally:
            TEMPLATE_REGISTRY[None]['account.journal'].remove(spy)


@pytest.mark.django_db
class TestAccountGroups:
    """``account.group`` es el **séptimo** modelo del plan, y abre la lista.

    ≙ ``TEMPLATE_MODELS`` (``odoo19c: chart_template.py:23-31``). El plan
    genérico no trae CSV de grupos —sus cuatro archivos son cuentas, posiciones
    fiscales, grupos de impuesto e impuestos—, pero una localización sí, y sin
    la entrada en ``loaded_models`` su columna no tendría dónde aterrizar: el
    mismo modo de fallo que :ref:`h-api-352`.
    """

    def test_a_declared_group_is_instantiated(self, company):
        @template(model='account.group')
        def extra_group(cls, template_code):
            return {'assets': {
                'name': 'Activo', 'code_prefix_start': '10',
                'code_prefix_end': '19'}}

        try:
            ChartTemplate.try_loading('generic_coa', company)

            group = ChartTemplate.ref('assets', company)
            assert group is not None
            assert (group.code_prefix_start, group.code_prefix_end) == ('10', '19')
        finally:
            TEMPLATE_REGISTRY[None]['account.group'].remove(extra_group)

    def test_a_company_that_already_has_groups_keeps_them(self, company):
        """≙ el guard de ``_pre_reload_data`` (``odoo19c: chart_template.py:308-312``).

        Los grupos son la estructura del plan, no su contenido: re-instanciarlos
        duplicaría el árbol de agrupación.
        """
        AccountGroup.objects.create(
            company=company, name='Mío', code_prefix_start='10',
            code_prefix_end='19')

        @template(model='account.group')
        def extra_group(cls, template_code):
            return {'assets': {
                'name': 'Activo', 'code_prefix_start': '20',
                'code_prefix_end': '29'}}

        try:
            ChartTemplate.try_loading('generic_coa', company)

            assert AccountGroup.objects.filter(company=company).count() == 1
            assert ChartTemplate.ref(
                'assets', company, raise_if_not_found=False) is None
        finally:
            TEMPLATE_REGISTRY[None]['account.group'].remove(extra_group)


@pytest.mark.django_db
class TestTaxTagMapper:
    """Las etiquetas de una línea de reparto llegan por **nombre**, no por id.

    ≙ ``_get_tag_mapper`` + ``_deref_account_tags``
    (``odoo19c: chart_template.py:1244,1294``). Una localización declara sus
    etiquetas fiscales por el nombre que usa la autoridad tributaria, separadas
    por ``||`` porque ese nombre suele llevar comas.

    Cierra además el hueco de un nivel más abajo: ``load_child_lines`` pasaba
    la fila hija sólo por ``resolve_values``, que **omite los M2M por diseño**,
    así que el ``tag_ids`` de una línea de reparto se descartaba en silencio.
    """

    @pytest.fixture
    def tax_tags(self, db):
        """Dos etiquetas fiscales sin país, como las que ve ``generic_coa``."""
        created = {}
        for label in ('Base imponible', 'Cuota repercutida'):
            tag, _new = AccountAccountTag.objects.get_or_create(
                name=label, applicability='taxes')
            created[label] = tag
        return created

    @staticmethod
    def _load_with_tags(company, raw_tags):
        @template(model='account.tax')
        def tagged_tax(cls, template_code):
            return {'tagged_tax': {
                'name': 'Impuesto etiquetado',
                'amount': 16,
                'type_tax_use': 'sale',
                'repartition_line_ids': [{
                    'repartition_type': 'base',
                    'factor_percent': 100,
                    'document_type': 'invoice',
                    'tag_ids': raw_tags,
                }],
            }}

        try:
            ChartTemplate.try_loading('generic_coa', company)
            tax = ChartTemplate.ref('tagged_tax', company)
            return list(tax.repartition_lines.get().tag_ids.all())
        finally:
            TEMPLATE_REGISTRY[None]['account.tax'].remove(tagged_tax)

    def test_a_name_lands_on_the_repartition_line(self, company, tax_tags):
        landed = self._load_with_tags(company, 'Base imponible')

        assert landed == [tax_tags['Base imponible']]

    def test_the_delimiter_splits_two_names(self, company, tax_tags):
        landed = self._load_with_tags(
            company, 'Base imponible||Cuota repercutida')

        assert set(landed) == set(tax_tags.values())

    def test_surrounding_whitespace_does_not_break_the_match(
            self, company, tax_tags):
        """≙ el ``re.sub(r'\\s+', ' ', tag.strip())`` de la referencia."""
        landed = self._load_with_tags(company, '  Base    imponible ')

        assert landed == [tax_tags['Base imponible']]

    def test_an_external_id_takes_the_other_branch(self, company, master_tags):
        """``modulo.nombre`` con módulo instalado se resuelve como identificador.

        La etiqueta maestra tiene ``applicability='accounts'``, así que **no**
        está en el mapa por nombre que el mapeador consulta: si aterriza, sólo
        pudo hacerlo por la rama del identificador externo.
        """
        landed = self._load_with_tags(company, 'account.account_tag_operating')

        assert landed == [master_tags['account_tag_operating']]

    def test_a_dotted_name_of_an_unknown_module_is_not_an_external_id(
            self, company, db):
        """El punto no basta: el prefijo tiene que nombrar un módulo instalado.

        ``ventas.general`` **sí** casa la forma ``modulo.nombre`` —a diferencia
        de un nombre con espacios, que el patrón descarta antes—, así que este
        caso llega al ``apps.is_installed`` y comprueba lo que dice comprobar.
        Medido: ``addons.ventas`` no está instalado, así que cae a la búsqueda
        por nombre.
        """
        tag, _new = AccountAccountTag.objects.get_or_create(
            name='ventas.general', applicability='taxes')

        landed = self._load_with_tags(company, 'ventas.general')

        assert landed == [tag]

    def test_an_unknown_name_is_dropped_without_aborting_the_load(
            self, company, tax_tags):
        """≙ la rama ``ignore_missing_tags`` — el plan se carga igual."""
        landed = self._load_with_tags(
            company, 'Base imponible||Etiqueta que no existe')

        assert landed == [tax_tags['Base imponible']]
        assert AccountAccount.objects.filter(company=company).exists()


@pytest.mark.django_db
class TestAccountCodeWidth:
    """Los códigos del plan se almacenan al ancho que el plan declara.

    ≙ ``_pre_load_data`` (``odoo19c: chart_template.py:520-523``). El CSV
    genérico mezcla anchos —43 códigos de 4 dígitos y 3 de 6— y la referencia
    los rellena con ceros a la derecha hasta ``code_digits`` antes de
    escribirlos. Sin eso, las cuentas cargadas y las **generadas** por este
    mismo módulo convivían a anchos distintos.
    """

    def test_a_four_digit_code_is_padded_to_the_chart_width(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        assert ChartTemplate.ref('receivable', company).code == '121000'
        assert ChartTemplate.ref('payable', company).code == '211000'

    def test_a_code_already_at_the_width_is_left_alone(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        assert ChartTemplate.ref('retained_earnings', company).code == '999998'

    def test_loaded_and_generated_codes_share_one_width(self, company):
        """El defecto que esta normalización cierra, medido de un tirón."""
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        anchos = set(AccountAccount.objects.filter(
            company=company).values_list('code', flat=True))
        assert {len(code) for code in anchos} == {6}
        # Y la generada por ``resolve_account_code`` cae en el mismo ancho.
        assert len(company.account_journal_suspense_account.code) == 6

    def test_the_declared_width_governs_over_the_default(self, company):
        """``code_digits`` sale del plan, no de una constante del cargador."""
        datos = ChartTemplate.get_chart_template_data('generic_coa')
        datos['template_data']['code_digits'] = 8
        ChartTemplate.normalize_account_codes(datos)

        assert datos['account.account']['receivable']['code'] == '12100000'


@pytest.mark.django_db
class TestUtilityBankAccounts:
    """Las cuentas que un diario de banco necesita para poder asentar.

    ≙ ``_setup_utility_bank_accounts`` (``odoo19c: chart_template.py:891``).
    Sin ellas, un cobro que aún no se identifica no tiene dónde esperar y un
    arqueo que no cuadra no tiene contra qué cerrar.
    """

    def test_the_prefix_becomes_the_first_free_code(self, company):
        """``1014`` + 6 dígitos → ``101401`` — ≙ el cálculo de la referencia.

        El código de arranque rellena el prefijo con ceros hasta un dígito
        menos del ancho y cierra con ``1``; de ahí en adelante manda
        ``search_new_account_code``.
        """
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        assert company.account_journal_suspense_account.code == '101401'
        assert company.transfer_account.code == '101701'

    def test_outstanding_accounts_do_not_collide_between_them(self, company):
        """Tres cuentas bajo el mismo prefijo toman tres huecos distintos.

        Es lo que hace el ``cache``: sin él las tres pedirían ``101401``,
        porque ninguna está escrita todavía cuando la siguiente pregunta.
        """
        ChartTemplate.try_loading('generic_coa', company)

        debit = ChartTemplate.ref('account_journal_payment_debit_account', company)
        credit = ChartTemplate.ref('account_journal_payment_credit_account', company)
        assert {debit.code, credit.code} == {'101402', '101403'}
        assert debit.reconcile and credit.reconcile

    def test_the_chart_reuses_the_accounts_it_already_declares(self, company):
        """Lo que el plan trae en su CSV no se duplica — se apunta.

        Las cuatro de diferencia de efectivo y descuento por pronto pago ya
        están en ``account.account-generic_coa.csv``. Si el paso del banco no
        las viera, intentaría crear la de descuento con el código literal
        ``999998``, que en este plan ya es ``retained_earnings``.
        """
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        assert company.default_cash_difference_income_account.code == '442000'
        assert company.account_journal_early_pay_discount_loss_account.code == '443000'
        assert AccountAccount.objects.filter(
            company=company, code='999998').get().name == (
                'Accumulated Retained Earnings')

    def test_the_bank_fees_rule_gets_its_account(self, company):
        """La regla de comisiones nace apuntada — ≙ el cierre de ``_load``.

        Un método correcto al que nadie llama es el defecto de
        :ref:`h-api-346`; este test es su consumidor.
        """
        ChartTemplate.try_loading('generic_coa', company)

        fees = ChartTemplate.ref('bank_fees_reco', company)
        line = fees.line_ids.get()
        assert line.account is not None
        assert line.account.account_type == 'expense'

    def test_a_subsidiary_takes_the_accounts_of_its_root(self, company):
        """Una hija no crea las suyas — ≙ ``company.parent_ids[0]``."""
        company.chart_template = 'generic_coa'
        company.save(update_fields=['chart_template'])
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        subsidiary = ResCompany.objects.create(
            code='acme-sub', name='ACME Sub', parent=company)
        subsidiary.refresh_from_db()

        assert (subsidiary.account_journal_suspense_account
                == company.account_journal_suspense_account)


@pytest.fixture
def master_tags(db):
    """Las tres etiquetas maestras, sembradas por el test.

    No se confía en la data-migration: sus filas **no sobreviven al flush** de
    la suite (:ref:`h-api-337`), así que un test que las diera por puestas
    pasaría o fallaría según el orden de ejecución.
    """
    created = {}
    for name, label in (
        ('account_tag_operating', 'Operating Activities'),
        ('account_tag_financing', 'Financing Activities'),
        ('account_tag_investing', 'Investing & Extraordinary Activities'),
    ):
        tag, _new = AccountAccountTag.objects.get_or_create(
            name=label, applicability='accounts')
        IrModelData.set_xmlid(tag, f'account.{name}', noupdate=True)
        created[name] = tag
    return created


@pytest.mark.django_db
class TestAccountTags:
    """La columna ``tag_ids`` del plan y la herencia por código.

    ≙ ``tag_ids`` de ``odoo19c: account_account.py:104`` y su compute
    ``_compute_account_tags`` (línea 609). El plan genérico etiqueta **13 de
    sus 46** cuentas; las otras 33 heredan de la cuenta de código anterior, que
    es la jerarquía que ningún campo declara.
    """

    def test_the_csv_tag_column_lands_on_the_account(self, company, master_tags):
        """La columna del CSV se resuelve por identificador externo.

        Antes se descartaba entera: ``resolve_values`` saltaba todo M2M con un
        comentario que prometía una resolución posterior inexistente
        (:ref:`h-api-352`).
        """
        ChartTemplate.try_loading('generic_coa', company)

        sales = AccountAccount.objects.get(company=company, code='400000')
        assert list(sales.tags.all()) == [master_tags['account_tag_operating']]

    def test_an_account_without_its_own_tag_inherits_the_previous_one(
            self, company, master_tags):
        """≙ ``_compute_account_tags`` con su ``_get_closest_parent_account``.

        ``4421`` no declara etiqueta, así que toma la de ``4420``. La búsqueda
        es por código ordenado y ``bisect_left``, igual que la referencia.
        """
        parent = AccountAccount.objects.create(
            company=company, code='4420', name='Cash Difference Gain',
            account_type='income_other')
        parent.tags.set([master_tags['account_tag_investing']])

        child = AccountAccount.objects.create(
            company=company, code='4421', name='Otra', account_type='income_other')

        assert list(child.tags.all()) == [master_tags['account_tag_investing']]

    def test_an_explicit_tag_wins_over_the_inherited_one(
            self, company, master_tags):
        """La guarda ``not account.tag_ids`` de la referencia, verbatim."""
        parent = AccountAccount.objects.create(
            company=company, code='4420', name='Cash Difference Gain',
            account_type='income_other')
        parent.tags.set([master_tags['account_tag_investing']])

        child = AccountAccount.objects.create(
            company=company, code='4421', name='Otra', account_type='income_other')
        child.tags.set([master_tags['account_tag_operating']])
        child.save()

        assert list(child.tags.all()) == [master_tags['account_tag_operating']]

    def test_an_account_without_a_type_inherits_the_previous_one(self, company):
        """≙ ``_compute_account_type``, el segundo consumidor del ayudante.

        Requerido y computado no se contradicen: la referencia declara el campo
        ``required=True`` **y** ``precompute=True``, y el cómputo corre antes
        del insert. Aquí lo llama ``save`` antes de guardar.
        """
        AccountAccount.objects.create(
            company=company, code='4420', name='Cash Difference Gain',
            account_type='income_other')

        child = AccountAccount.objects.create(
            company=company, code='4421', name='Otra', account_type='')

        assert child.account_type == 'income_other'
        assert child.internal_group == 'income'

    def test_the_first_account_of_the_chart_falls_back_to_the_default(
            self, company):
        """Sin cuenta anterior, ``asset_current`` — el default de la referencia."""
        first = AccountAccount.objects.create(
            company=company, code='1010', name='Current Assets', account_type='')

        assert first.account_type == 'asset_current'

    def test_a_master_tag_cannot_be_deleted(self, master_tags):
        """≙ ``_unlink_except_master_tags``: el plan las cita por identificador."""
        with pytest.raises(UserError):
            master_tags['account_tag_investing'].delete()

    def test_a_plain_tag_can_be_deleted(self, db):
        """La guarda protege las tres maestras, no toda etiqueta."""
        tag = AccountAccountTag.objects.create(
            name='Casilla 33', applicability='taxes')

        tag.delete()

        assert not AccountAccountTag.objects.filter(name='Casilla 33').exists()
