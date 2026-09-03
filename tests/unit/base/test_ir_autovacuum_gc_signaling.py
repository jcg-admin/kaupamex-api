"""``_gc_orm_signaling`` — la poda de las tablas del eje de señalización.

Contrato de la fuente (``odoo19c: odoo/addons/base/models/ir_autovacuum.py:64-75``),
con su comentario verbatim: *"keep the last 10 entries for each signal, and all
entries from the last hour"*. Las dos condiciones se conjugan con ``AND`` en el
``DELETE``, así que una fila **sobrevive** si está entre las diez últimas **o**
si es de la última hora.

**El control que discrimina** es
:meth:`TestThePruningKeepsBothClauses.test_a_fresh_row_survives_past_the_tenth`
y su hermano ``test_the_two_clauses_conjugate``: sin ellos, un cuerpo que se
dejara la cláusula de fecha —o la de identificador— seguiría en verde. Están
escritos con las filas frescas **antes** de las viejas en orden de ``id``,
que es la única disposición en la que las dos cláusulas dan conteos distintos:

============================  =========  ============
Cuerpo                        remanente  ¿se ve?
============================  =========  ============
``id`` **AND** fecha (fiel)   15         —
sólo ``id``                   10         sí, cae
sólo fecha                     5         sí, cae
============================  =========  ============
"""
import pytest
from django.db import connection

from addons.base.models.ir_autovacuum import IrAutovacuum, is_autovacuum
from orm.decorators import autovacuum
from orm.registry import signaling_table_names

#: La tabla sobre la que se miden los conteos. Cualquiera de las siete sirve;
#: se fija una para que el caso no dependa del orden de la lista.
TABLE = 'orm_signaling_default'


def seed(table, fresh, old):
    """Vacía ``table`` e inserta ``fresh`` filas recientes y luego ``old`` viejas.

    El orden importa: las recientes reciben los ``id`` **más bajos**, así que
    quedan fuera de las diez últimas y sólo la cláusula de fecha las salva.
    """
    with connection.cursor() as cr:
        cr.execute(f'DELETE FROM "{table}"')
        for _ in range(fresh):
            cr.execute(f'INSERT INTO "{table}" (date) VALUES (NOW())')
        for _ in range(old):
            cr.execute(
                f'INSERT INTO "{table}" (date) '
                f"VALUES (NOW() - interval '2 hours')")


def count(table):
    with connection.cursor() as cr:
        cr.execute(f'SELECT count(*) FROM "{table}"')
        return cr.fetchone()[0]


class TestThePruningKeepsBothClauses:
    """El ``DELETE`` conjuga identificador y fecha, no una de las dos."""

    def test_old_rows_past_the_tenth_are_deleted(self, db):
        """Quince filas viejas: sobreviven las diez últimas."""
        seed(TABLE, fresh=0, old=15)
        IrAutovacuum._gc_orm_signaling()
        assert count(TABLE) == 10

    def test_a_fresh_row_survives_past_the_tenth(self, db):
        """El control de la cláusula de fecha.

        Quince filas de la última hora: **ninguna** se borra, aunque cinco
        queden fuera de las diez últimas. Un cuerpo sin
        ``AND date < NOW() - interval '1 hours'`` dejaría diez y este caso cae.
        """
        seed(TABLE, fresh=15, old=0)
        IrAutovacuum._gc_orm_signaling()
        assert count(TABLE) == 15

    def test_the_two_clauses_conjugate(self, db):
        """El control de las dos a la vez, con la disposición que las separa.

        Cinco frescas primero y quince viejas después: las diez últimas
        sobreviven por identificador y las cinco frescas por fecha — quedan
        **quince**. Con sólo la cláusula de identificador quedarían diez; con
        sólo la de fecha, cinco.
        """
        seed(TABLE, fresh=5, old=15)
        IrAutovacuum._gc_orm_signaling()
        assert count(TABLE) == 15

    def test_ten_old_rows_are_untouched(self, db):
        """El borde: con diez o menos, ``max(id)-9`` no deja nada por debajo."""
        seed(TABLE, fresh=0, old=10)
        IrAutovacuum._gc_orm_signaling()
        assert count(TABLE) == 10


class TestTheSweepCoversEveryTable:
    """El barrido recorre las siete, no la que dé el ejemplo."""

    def test_every_signaling_table_is_pruned(self, db):
        """Un cuerpo que nombrara una sola tabla dejaría quince en las otras."""
        for table in signaling_table_names():
            seed(table, fresh=0, old=15)
        IrAutovacuum._gc_orm_signaling()
        assert {table: count(table) for table in signaling_table_names()} == {
            table: 10 for table in signaling_table_names()}

    def test_the_list_is_the_one_the_axis_declares(self, db):
        """No hay una segunda copia de los siete nombres en el barrido."""
        assert len(signaling_table_names()) == 7
        assert 'orm_signaling_registry' in signaling_table_names()


class TestTheMethodIsCollected:
    """Sin el decorador, el barrido nunca lo llamaría."""

    def test_it_is_marked_as_autovacuum(self):
        assert is_autovacuum(IrAutovacuum._gc_orm_signaling)

    def test_the_collector_finds_it(self, db):
        """El control: lo que importa no es la marca sino que el colector la vea.

        ``_collect_methods`` recorre ``apps.get_models()`` con
        ``inspect.getmembers``; un método marcado en una clase que el registro
        no conociera quedaría invisible y este caso lo delataría.
        """
        found = [(model, attr) for model, attr, _ in IrAutovacuum._collect_methods()
                 if attr == '_gc_orm_signaling']
        assert found == [(IrAutovacuum, '_gc_orm_signaling')], found

    def test_its_name_stays_private(self):
        """El guion bajo es el contrato — ``porte-completo-no-parcial.md``."""
        def gc_public():
            pass

        with pytest.raises(AssertionError):
            autovacuum(gc_public)
