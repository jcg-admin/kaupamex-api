"""#313 — un campo M2M calculado se declara como campo y lo vuelca el motor.

Los tres campos que la fuente declara ``Many2many`` con ``compute=`` estaban
aqui sin cablear, y sus tres computos se llamaban a mano desde ``save()``. La
razon escrita en los tres sitios era la misma y es cierta: **un M2M de Django
no se escribe con** ``setattr``. Medido antes de tocar nada
(``scripts/workbench/compute-que-escribe-m2m-*/probes/``):

.. code-block:: text

   many_to_many : True
   setattr sobre el M2M: TypeError: Direct assignment to the forward side of
                         a many-to-many set is prohibited. Use tags.set()

Y ``_flush`` hacia exactamente eso: ``setattr`` + ``save(update_fields=...)``.
Un M2M no cabia por dos motivos a la vez —no admite la asignacion y no es una
columna que ``update_fields`` pueda nombrar—, asi que el cableado de #305 los
dejo fuera.

Veredicto por el criterio de las dos categorias
===============================================

**El stack tiene con que construirlo.** No hay simbolo hecho —Django no tiene
la nocion de un campo relacional calculado— pero las dos primitivas estan y
ninguna viene de fuera del INVENTORY: ``field.many_to_many`` distingue el caso
(``django``, evaluacion y control de flujo) y el manager relacional expone
``.set()``, que resuelve el diff contra la tabla intermedia (``postgresql``,
guardar y consultar). Lo que se construye es la rama que las une.

Por que ``.set()`` y no una tabla ``through`` propia
====================================================

Las dos resuelven el problema; la eleccion es de contexto, no de velocidad.

- ``.set()`` hace un diff por fila: una consulta de lectura y las altas y
  bajas que de verdad cambien. Con ``through`` explicito se puede hacer un
  ``bulk_create`` y bajar a una sola ida por lote.
- Las tres relaciones medidas son de **configuracion** —etiquetas de una
  cuenta contable, campos que disparan una regla— de cardinalidad baja y
  escritura rara. Ahi lo que se paga caro es la superficie: tres modelos
  intermedios nuevos y sus migraciones, para comprar un rendimiento que
  nadie esta pidiendo.
- ``.set()`` ademas emite ``m2m_changed``, que es donde vive el control de
  acceso de la relacion. Bajar a ``bulk_create`` lo evita, y eso es perder
  una guarda a cambio de nada en este caso.

Si manana una relacion de OPERACION —no de configuracion— necesita el
computo, la eleccion correcta ahi es otra, y el motor no lo impide: la rama
mira el campo, no el modelo.

Medido con cada guarda anulada
==============================

Son tres, y el control las mide una a una con
``scripts/evidence/control_313_guardas.py``, que sustituye el cuerpo, corre el
modulo y restaura desde la copia en memoria —nunca ``git checkout``, regla
#177— cerrando con el sha256 de cada archivo.

.. list-table::
   :header-rows: 1

   * - Guarda anulada
     - Resultado
   * - (ninguna)
     - 14 passed
   * - la rama del M2M en el volcado (``orm/models.py:3247``)
     - 1 failed, 13 passed
   * - el M2M en el predicado de persistido (``orm/fields.py:_is_persisted``)
     - 1 failed, 13 passed
   * - el guard de precompute sobre un M2M (``fields_nonstored.py:400``)
     - 1 failed, 13 passed

**La primera version de estos casos NO discriminaba, y eso es el hallazgo.**
Con las tres guardas anuladas daba **14 passed** las tres veces:

- los dos casos de ciclo median el COMPUTO, no el volcado — los tres computos
  del arbol escriben la relacion ellos mismos con ``.set()``, asi que la rama
  de ``_flush_m2m`` podia no existir y el resultado no cambiaba;
- el caso de ``precompute`` afirmaba ``is False`` sobre tres campos que **no
  lo piden**: el ``False`` venia del default y el guard sobraba.

Al perseguir el primero aparecio la causa de fondo: ``_cache_computed_values``
y ``_update_cache`` filtraban por ``column_type``, y un M2M no tiene columna.
El campo se calculaba, el cache no se enteraba, ``field_dirty`` seguia vacio y
la rama del volcado era **codigo muerto**. Sin el control, este porte se habria
cerrado en verde con la mitad del mecanismo sin conectar — que es exactamente
el sub-patron D de ``metrica-decide-la-conclusion.md``.

*Metrica:* casos de este modulo que caen al anular cada una de las tres
guardas.
*Ciega a:* el coste de ``.set()`` sobre una relacion grande —las tres medidas
son de configuracion, de cardinalidad baja— y al orden entre el volcado del
M2M y el de las columnas de la misma fila, que aqui no se ejerce.
"""
import pytest
import fields
from django.apps import apps

from orm import registry
from orm.environments import env, transaction_scope
from orm.utils import model_field_registry


AccountAccount = apps.get_model('account', 'AccountAccount')
AccountAccountTag = apps.get_model('account', 'AccountAccountTag')
BaseAutomation = apps.get_model('base_automation', 'BaseAutomation')
ResCompany = apps.get_model('base', 'ResCompany')

pytestmark = pytest.mark.django_db


def field_of(model, name):
    return model._meta.get_field(name)


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='m2m-313', name='M2M 313')


@pytest.fixture
def tagged(company):
    """Una cuenta con etiqueta propia, y su vecina de codigo inmediato.

    Es la forma que el computo de la fuente resuelve: el plan es una jerarquia
    **por codigo**, y una cuenta sin etiqueta hereda las de la anterior.
    """
    tag = AccountAccountTag.objects.create(name='Ingresos gravados')
    first = AccountAccount.objects.create(
        code='4000', name='Ventas', account_type='income', company=company)
    first.tags.set([tag])
    return tag, first


class TestTheThreeFieldsDeclareTheirCompute:
    """La declaracion, contra la de la fuente."""

    @pytest.mark.parametrize('model,name,compute', [
        (AccountAccount, 'tags', '_compute_account_tags'),
        (BaseAutomation, 'trigger_field_ids', '_compute_trigger_field_ids'),
        (BaseAutomation, 'on_change_field_ids', '_compute_on_change_field_ids'),
    ])
    def test_it_names_its_compute(self, model, name, compute):
        assert field_of(model, name).compute == compute

    @pytest.mark.parametrize('model,name', [
        (AccountAccount, 'tags'),
        (BaseAutomation, 'trigger_field_ids'),
        (BaseAutomation, 'on_change_field_ids'),
    ])
    def test_it_stays_stored_and_writable(self, model, name):
        """La fuente declara los tres ``store=True, readonly=False``: el
        computo RELLENA lo que el usuario no puso, y el usuario si escribe."""
        field = field_of(model, name)
        assert field.store is True
        assert field.editable is True

    def test_asking_for_precompute_on_a_m2m_is_turned_off_with_a_warning(self):
        """DIVERGENCIA DE STACK declarada, y el motor la impone.

        La fuente declara ``tag_ids`` con ``precompute=True``
        (``odoo19c: account_account.py:107``): su ORM asigna el id antes de
        ejecutar la cola, asi que puede escribir la relacion antes del INSERT.
        Aqui no hay tabla intermedia que poblar sin ``pk``, asi que el
        adelanto se desactiva — como ya se desactiva cuando un precomputado
        depende de un almacenado que no lo es (``orm/fields.py:2187-2193``).

        **El caso DECLARA el adelanto**, y ahi esta el control. Afirmar
        ``precompute is False`` sobre los tres campos del arbol no discriminaba
        nada: ninguno lo pide, asi que el ``False`` venia del default y el caso
        pasaba igual con el guard retirado. Medido: con ``elif many_to_many``
        anulado, aquella version daba **14 passed**.
        """
        with pytest.warns(UserWarning, match='many2many'):
            field = fields.Many2many(
                'account.AccountAccountTag', blank=True,
                compute='_compute_account_tags', store=True, readonly=False,
                precompute=True)
        assert field.precompute is False

    def test_a_scalar_field_keeps_its_precompute(self):
        """El control que separa «se apaga en un M2M» de «se apaga siempre».
        Sin este caso, un guard que apagara el adelanto de TODO campo pasaria
        el de arriba sin distinguirse."""
        field = fields.Char(max_length=8, compute='_compute_account_type',
                            store=True, readonly=False, precompute=True)
        assert field.precompute is True


class TestTheDeclarationReachesTheGraph:
    """Un M2M con ``compute=`` es clave del grafo, como cualquier otro."""

    def test_the_code_reaches_the_tags(self):
        derived = {f.name for f in registry.get_dependent_fields(
            field_of(AccountAccount, 'code'))}
        assert 'tags' in derived

    def test_a_field_nobody_computes_from_has_no_dependents(self):
        """El control que discrimina: la MISMA maquinaria sobre un campo del
        que nadie deriva no produce aristas."""
        assert list(registry.get_dependent_fields(
            field_of(AccountAccount, 'note'))) == []


class TestTheCycleReachesTheJoinTable:
    """De punta a punta sobre la tabla intermedia, que es el eje de #313."""

    def test_touching_the_code_writes_the_relation(self, tagged, company):
        tag, first = tagged
        second = AccountAccount.objects.create(
            code='4010', name='Ventas nacionales', account_type='income',
            company=company)
        second.tags.clear()
        assert list(second.tags.all()) == []

        with transaction_scope():
            second.modified(['code'])
            assert second.pk in env().records_to_compute(
                field_of(AccountAccount, 'tags'))
            second.flush_recordset(['tags'])

        assert list(second.tags.all()) == [tag]

    def test_without_touching_it_the_relation_is_left_alone(self, tagged,
                                                            company):
        """El control que discrimina: sin ``modified``, el mismo volcado no
        escribe. Lo que mueve la relacion es la marca, no el ``flush``."""
        _tag, _first = tagged
        second = AccountAccount.objects.create(
            code='4010', name='Ventas nacionales', account_type='income',
            company=company)
        second.tags.clear()

        with transaction_scope():
            second.flush_recordset(['tags'])

        assert list(second.tags.all()) == []

    def test_the_flush_is_the_only_writer_when_the_cache_is_seeded(
            self, tagged, company):
        """El control que discrimina la rama del volcado, y costo encontrarlo.

        En los dos casos de arriba el computo escribe la relacion **el mismo**
        —``self.tags.set(...)`` en su cuerpo—, asi que anular la rama de
        ``_flush_m2m`` los dejaba en verde: median el computo, no el volcado.
        Aqui el computo no corre. El valor se siembra en el cache y se marca
        sucio a mano, que es el estado en que el motor deja un campo calculado,
        y lo unico que puede escribirlo es el volcado.
        """
        tag, _first = tagged
        alone = AccountAccount.objects.create(
            code='7000', name='Orden', account_type='expense', company=company)
        alone.tags.clear()

        field = model_field_registry(AccountAccount)['tags']
        with transaction_scope():
            field._update_cache([alone], [tag], dirty=True)
            alone.flush_recordset(['tags'])

        assert list(alone.tags.all()) == [tag]

    def test_a_scalar_field_still_flushes_through_its_column(self, company):
        """El segundo control, y protege lo que ya funcionaba: la rama nueva
        del M2M no puede haberse comido el camino de la columna.

        **Los dos extremos se leen de la COLUMNA, no del atributo**, y no es
        cosmetico: ``refresh_from_db`` de Django no es la invalidacion del
        ORM. Copia campo a campo con ``setattr``, asi que reasigna tambien
        ``account_type`` —que es calculado y escribible— y esa escritura marca
        a sus dependientes, ``internal_group`` entre ellos. La lectura
        siguiente del atributo recalcula y devuelve ``'expense'`` **haya
        escrito o no el volcado**: es el sub-patron D de
        ``metrica-decide-la-conclusion``, un verde que no discrimina.

        ``values_list`` arma la tupla desde la fila sin instanciar el modelo,
        asi que no pasa por el descriptor ni dispara recalculo alguno.
        """
        columna = lambda: AccountAccount.objects.filter(
            pk=account.pk).values_list('internal_group', flat=True)[0]

        account = AccountAccount.objects.create(
            code='5000', name='Gastos', account_type='expense',
            company=company)
        AccountAccount.objects.filter(pk=account.pk).update(internal_group='')
        assert columna() == ''

        with transaction_scope():
            account.modified(['account_type'])
            account.flush_recordset(['internal_group'])

        assert columna() == 'expense'
