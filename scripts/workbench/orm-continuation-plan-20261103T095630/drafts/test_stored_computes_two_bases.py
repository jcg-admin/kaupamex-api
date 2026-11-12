# Borrador: reemplaza a TestStoredComputesStayInTheirBase en
# tests/integration/company/test_multidb_isolation.py cuando el gate completo
# del lote 2 termine (el árbol está bajo verificación). Instrucción §6.


class TestStoredComputesStayInTheirBase:
    """Los cálculos almacenados de una fila se marcan y se vuelcan en su base.

    ≙ ``Environment.__new__`` (``odoo19c: odoo/orm/environments.py:70-80``):
    la transacción del ORM es la del cursor; dos bases no comparten marcas,
    caché ni volcado. Las dos bases recién aprovisionadas dan el mismo ``pk``
    a filas creadas en el mismo orden —se comprueba, no se supone—: si las
    marcas fueran a una sola transacción, la de una base pisaría la de la
    otra. Cada base lleva un ``name`` distinto, del que
    ``_compute_start_end`` deriva ``start``/``end``.
    designs/transaction-per-alias.md.
    """

    MODEL = 'test_orm.shared.compute'

    @classmethod
    def _model(cls, alias):
        return type(Environment(alias, 1, {})[cls.MODEL])

    @classmethod
    def _row(cls, alias, pk):
        return cls._model(alias).objects.using(alias).values(
            'name', 'start', 'end').get(pk=pk)

    @staticmethod
    def _flush(alias):
        with Environment(alias, 1, {}) as env:
            env.flush_all()

    def test_django_creations_compute_in_their_own_base(
            self, two_company_databases):
        alias_a, alias_b = two_company_databases
        row_a = self._model(alias_a).objects.using(alias_a).create(
            name='5->25')
        row_b = self._model(alias_b).objects.using(alias_b).create(
            name='7->9')
        assert row_a.pk == row_b.pk
        for alias in (alias_a, alias_b):
            self._flush(alias)
        assert self._row(alias_a, row_a.pk) == {
            'name': '5->25', 'start': 5, 'end': 25}
        assert self._row(alias_b, row_b.pk) == {
            'name': '7->9', 'start': 7, 'end': 9}

    def test_orm_creations_compute_in_their_own_base(
            self, two_company_databases):
        alias_a, alias_b = two_company_databases
        created = {}
        for alias, name in ((alias_a, '3->4'), (alias_b, '6->8')):
            with Environment(alias, 1, {}) as env:
                created[alias] = env[self.MODEL].sudo().create(
                    {'name': name}).id
        assert created[alias_a] == created[alias_b]
        for alias in (alias_a, alias_b):
            self._flush(alias)
        assert self._row(alias_a, created[alias_a]) == {
            'name': '3->4', 'start': 3, 'end': 4}
        assert self._row(alias_b, created[alias_b]) == {
            'name': '6->8', 'start': 6, 'end': 8}

    def test_a_recompute_marks_only_its_own_transaction(
            self, two_company_databases):
        """Las marcas de recálculo de una base no aparecen en la otra, con el
        mismo ``pk`` en las dos, y volcar una no escribe en la otra."""
        alias_a, alias_b = two_company_databases
        model_a = self._model(alias_a)
        row_a = model_a.objects.using(alias_a).create(name='1->2')
        row_b = self._model(alias_b).objects.using(alias_b).create(
            name='1->2')
        assert row_a.pk == row_b.pk
        for alias in (alias_a, alias_b):
            self._flush(alias)
        field = model_a._meta.get_field('start')
        with Environment(alias_a, 1, {}) as env_a:
            record = env_a[self.MODEL].browse(row_a.pk)
            record.write({'name': '30->40'})
            assert env_a.is_to_compute(field, row_a.pk)
            env_b = Environment(alias_b, 1, {})
            assert env_b.transaction is not env_a.transaction
            assert not env_b.is_to_compute(field, row_b.pk)
            env_a.flush_all()
        assert self._row(alias_a, row_a.pk) == {
            'name': '30->40', 'start': 30, 'end': 40}
        assert self._row(alias_b, row_b.pk) == {
            'name': '1->2', 'start': 1, 'end': 2}

    def test_the_caches_of_the_two_bases_are_separate(
            self, two_company_databases):
        alias_a, alias_b = two_company_databases
        row_a = self._model(alias_a).objects.using(alias_a).create(
            name='2->3')
        row_b = self._model(alias_b).objects.using(alias_b).create(
            name='8->9')
        assert row_a.pk == row_b.pk
        for alias in (alias_a, alias_b):
            self._flush(alias)
        with Environment(alias_a, 1, {}) as env_a:
            assert env_a[self.MODEL].browse(row_a.pk).start == 2
        with Environment(alias_b, 1, {}) as env_b:
            assert env_b[self.MODEL].browse(row_b.pk).start == 8

    def test_a_rolled_back_recompute_leaves_both_bases_as_they_were(
            self, two_company_databases):
        alias_a, alias_b = two_company_databases
        row_a = self._model(alias_a).objects.using(alias_a).create(
            name='4->5')
        row_b = self._model(alias_b).objects.using(alias_b).create(
            name='4->5')
        for alias in (alias_a, alias_b):
            self._flush(alias)
        with transaction.atomic(using=alias_a):
            with Environment(alias_a, 1, {}) as env_a:
                env_a[self.MODEL].browse(row_a.pk).write({'name': '50->60'})
                env_a.flush_all()
            assert self._row(alias_a, row_a.pk)['start'] == 50
            transaction.set_rollback(True, using=alias_a)
        assert self._row(alias_a, row_a.pk) == {
            'name': '4->5', 'start': 4, 'end': 5}
        assert self._row(alias_b, row_b.pk) == {
            'name': '4->5', 'start': 4, 'end': 5}
