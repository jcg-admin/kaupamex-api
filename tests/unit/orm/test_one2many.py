"""``One2many`` declarado en el padre — ≙ ``odoo19c: odoo/orm/fields_relational.py:843``.

Hasta ``api@596cd2b`` ``fields.One2many`` valia ``None`` y estaba en el
``__all__`` publico: llamarlo daba ``TypeError: 'NoneType' object is not
callable``. La razon escrita era que *"One2many es el reverso de un FK en
Django (``related_name``), sin clase propia"*, y esa mitad es cierta — lo que
Django **no** da es el **sitio de declaracion**.

La fuente declara el campo en el **padre**, con su comodelo y su inverso::

    child_ids = fields.One2many('res.partner.category', 'parent_id')

Django lo declara en el **hijo**, como ``related_name`` del FK. Al portar un
modelo padre, sus ``One2many`` desaparecen de su cuerpo y reaparecen en otro
archivo. Es el mismo defecto de forma que el episodio de ``store=False``
(:ref:`h-api-361`) y el de :ref:`h-api-350`: todos los simbolos presentes, la
forma cambiada — y el conteo, que es lo unico que el gate mide, no lo ve.

Poblacion medida: **730** ``fields.One2many(`` en ``odoo19c``, de los cuales
**37** en ``base``. El consumidor real no hay que esperarlo: ya existe.
"""
import pytest
from django.apps import apps

import fields
from orm.environments import transaction_scope
from orm.fields_relational import One2many


@pytest.fixture
def category_class():
    return apps.get_model('base', 'ResPartnerCategory')


class TestTheFieldIsCallable:
    """Lo minimo, y lo que estaba roto: el simbolo publico se puede invocar."""

    def test_the_public_facade_exposes_a_callable(self):
        assert fields.One2many is not None, (
            'fields.One2many valia None y estaba en __all__: la fachada '
            'publicaba un simbolo que reventaba al llamarlo')
        assert callable(fields.One2many)

    def test_it_is_the_class_of_the_relational_module(self):
        assert fields.One2many is One2many


class TestTheDeclaredContract:
    """Los dos atributos que la fuente hace obligatorios, y ``copy``."""

    def test_it_keeps_comodel_and_inverse_name(self):
        field = One2many('base.ResPartnerCategory', 'parent')
        assert field.comodel_name == 'base.ResPartnerCategory'
        assert field.inverse_name == 'parent'

    def test_copy_is_false_by_default(self):
        """≙ ``copy: bool = False`` con su comentario verbatim de la fuente:
        *"o2m are not copied by default"* (``odoo19c: :867``).

        No es cosmetico: ``BaseModel.copy`` mira este atributo para decidir si
        arrastra los hijos, y el default contrario duplicaria un arbol entero
        al copiar su raiz.
        """
        assert One2many('base.ResPartnerCategory', 'parent').copy is False

    def test_copy_can_be_turned_on(self):
        assert One2many('base.ResPartnerCategory', 'parent', copy=True).copy is True


class TestItResolvesToTheDjangoReverse:
    """El valor sale del reverso que Django ya construyo — no de una consulta nueva.

    Es la mitad que el ``related_name`` SI da, y el porte no la reimplementa:
    la reusa. El control positivo compara las dos vias sobre los mismos datos.
    """

    @pytest.fixture
    def tree(self, db, category_class):
        with transaction_scope():
            root = category_class.objects.create(name='raiz')
            child_a = category_class.objects.create(name='hijo-a', parent=root)
            child_b = category_class.objects.create(name='hijo-b', parent=root)
            return root, child_a, child_b

    def test_reading_it_gives_the_children(self, tree, category_class):
        root, child_a, child_b = tree
        field = One2many('base.ResPartnerCategory', 'parent')
        field.contribute_to_class(category_class, 'o2m_test_children')
        try:
            assert set(root.o2m_test_children.values_list('pk', flat=True)) == \
                {child_a.pk, child_b.pk}
        finally:
            delattr(category_class, 'o2m_test_children')

    def test_it_agrees_with_the_related_name(self, tree, category_class):
        """EL CONTROL POSITIVO. ``child_ids`` es el ``related_name`` que este
        arbol ya declara en el hijo; el ``One2many`` del padre tiene que dar
        exactamente lo mismo. Si divergen, el porte construyo otra cosa.
        """
        root, _, _ = tree
        field = One2many('base.ResPartnerCategory', 'parent')
        field.contribute_to_class(category_class, 'o2m_test_agree')
        try:
            assert set(root.o2m_test_agree.values_list('pk', flat=True)) == \
                set(root.child_ids.values_list('pk', flat=True))
        finally:
            delattr(category_class, 'o2m_test_agree')

    def test_from_the_class_it_gives_the_descriptor(self, category_class):
        field = One2many('base.ResPartnerCategory', 'parent')
        field.contribute_to_class(category_class, 'o2m_test_descriptor')
        try:
            assert category_class.o2m_test_descriptor is field
        finally:
            delattr(category_class, 'o2m_test_descriptor')


class TestItHasNoColumn:
    """No persiste: es el reverso de una FK que ya existe, no una columna nueva."""

    def test_it_does_not_enter_meta(self, category_class):
        field = One2many('base.ResPartnerCategory', 'parent')
        field.contribute_to_class(category_class, 'o2m_test_meta')
        try:
            names = {f.name for f in category_class._meta.get_fields()}
            assert 'o2m_test_meta' not in names, (
                'el One2many entro en _meta: generaria migracion para una '
                'columna que no existe')
        finally:
            delattr(category_class, 'o2m_test_meta')


class TestTheMissingInverseIsNamed:
    """``update_db`` de la fuente rechaza un inverso inexistente — ≙ ``:903-911``.

    Su mensaje es *"No inverse field %(inverse_field)s found for %(comodel)s"*,
    y el porte lo conserva: un ``AttributeError`` pelado de Python no dice cual
    de los dos nombres esta mal.
    """

    def test_an_unknown_inverse_is_refused_by_name(self, db, category_class):
        field = One2many('base.ResPartnerCategory', 'no_existe_este_campo')
        field.contribute_to_class(category_class, 'o2m_test_bad')
        try:
            with transaction_scope():
                root = category_class.objects.create(name='sin-inverso')
                with pytest.raises(ValueError) as exc:
                    root.o2m_test_bad
            assert 'no_existe_este_campo' in str(exc.value)
            assert 'base.ResPartnerCategory' in str(exc.value)
        finally:
            delattr(category_class, 'o2m_test_bad')


class TestTheDeclaredParametersAreKept:
    """Los cuatro que la fuente documenta en su docstring — ≙ ``:847-860``.

    ``__init__`` los tragaba en ``**_ignored``. Un parametro tragado es peor
    que uno ausente: la llamada del porte se escribe igual que la de la
    fuente, pasa sin error, y no hace nada. El conteo de simbolos —lo unico
    que ``check_porte_completo`` mide— no ve la diferencia.
    """

    def test_the_client_side_domain_is_kept(self):
        field = One2many('base.ResPartnerCategory', 'parent',
                         domain=[('active', '=', True)])
        assert field.domain == [('active', '=', True)]

    def test_the_client_side_context_is_kept(self):
        field = One2many('base.ResPartnerCategory', 'parent',
                         context={'active_test': False})
        assert field.context == {'active_test': False}

    def test_bypass_search_access_is_false_by_default(self):
        """≙ *"whether access rights are bypassed on the comodel (default:
        ``False``)"* (``odoo19c: :859-860``). El default abierto seria un
        hueco de permiso."""
        assert One2many('base.ResPartnerCategory', 'parent').bypass_search_access is False

    def test_bypass_search_access_can_be_turned_on(self):
        field = One2many('base.ResPartnerCategory', 'parent',
                         bypass_search_access=True)
        assert field.bypass_search_access is True

    def test_the_relation_field_of_the_description_is_the_inverse(self):
        """≙ ``_description_relation_field = property(attrgetter('inverse_name'))``
        (``odoo19c: :901``). Es lo que el cliente lee para saber por que
        columna del hijo cuelga el conjunto."""
        field = One2many('base.ResPartnerCategory', 'parent')
        assert field._description_relation_field == 'parent'


class TestTheComodelDomain:
    """``get_comodel_domain`` compone — ≙ ``:918-919``.

    Se mide la **composicion**, que es lo portado. El tipo de retorno de la
    fuente es ``Domain`` y aqui es la lista: bloqueo medido dos veces (ciclo de
    import y registro de apps), declarado en el docstring del metodo con su
    sucesor, tarea **#241**.
    """

    def test_without_a_domain_it_is_empty(self):
        field = One2many('base.ResPartnerCategory', 'parent')
        assert field.get_comodel_domain() == []

    def test_the_declared_domain_comes_through(self):
        field = One2many('base.ResPartnerCategory', 'parent',
                         domain=[('active', '=', True)])
        assert field.get_comodel_domain() == [('active', '=', True)], (
            'el dominio declarado se perdio en la composicion')


class TestAssignmentAppliesTheReferenceDecision:
    """El lado de ESCRITURA — ≙ ``write_real`` (``:967``), rama ``unlink``.

    La fuente decide que hacer con el hijo que se queda fuera del conjunto
    mirando el ``ondelete`` de su inverso, no la nulabilidad de la columna::

        def unlink(lines):
            if getattr(comodel._fields[inverse], 'ondelete', False) == 'cascade':
                to_delete.extend(lines._ids)
            else:
                lines[inverse] = False

    Django decide por otra cosa: su ``RelatedManager.set()`` existe **si la FK
    admite nulo**, y entonces anula. Sobre una FK ``null=True`` con
    ``on_delete=CASCADE`` —que es el caso de ``ResPartnerCategory.parent``—
    las dos politicas discrepan: la fuente borra el huerfano y Django lo deja
    vivo con la columna en nulo. Este es el caso donde el porte tiene que
    imponer la decision de la fuente.
    """

    @pytest.fixture
    def tree(self, db, category_class):
        with transaction_scope():
            root = category_class.objects.create(name='raiz-set')
            a = category_class.objects.create(name='queda', parent=root)
            b = category_class.objects.create(name='sale', parent=root)
            return root, a, b

    def test_a_cascade_inverse_deletes_the_leftover(self, tree, category_class):
        root, kept, dropped = tree
        assert category_class._meta.get_field('parent').null is True, (
            'precondicion del caso: con la FK NOT NULL Django no ofrece set() '
            'y el caso no distinguiria las dos politicas')
        field = One2many('base.ResPartnerCategory', 'parent')
        field.contribute_to_class(category_class, 'o2m_test_write')
        try:
            with transaction_scope():
                root.o2m_test_write = [kept]
            assert not category_class.objects.filter(pk=dropped.pk).exists(), (
                'el huerfano sobrevivio: se aplico la politica de Django '
                '(anular la columna) en vez del ondelete=cascade de la fuente')
            assert category_class.objects.filter(pk=kept.pk).exists()
        finally:
            delattr(category_class, 'o2m_test_write')

    def test_a_set_null_inverse_only_unlinks(self, db):
        """La otra rama, con un modelo REAL del arbol y no un doble.

        ``ResPartner.parent`` es ``null=True`` con ``on_delete=SET_NULL``: la
        fuente lo deja vivo con el inverso en nulo. Medido en el mismo pase que
        el caso de arriba — el arbol declara las dos politicas, asi que el
        control no necesita fabricar ninguna.
        """
        partner_class = apps.get_model('base', 'ResPartner')
        assert partner_class._meta.get_field('parent').null is True
        field = One2many('base.ResPartner', 'parent')
        field.contribute_to_class(partner_class, 'o2m_test_unlink')
        try:
            with transaction_scope():
                root = partner_class.objects.create(name='raiz-partner')
                kept = partner_class.objects.create(name='queda-p', parent=root)
                dropped = partner_class.objects.create(name='sale-p', parent=root)
                root.o2m_test_unlink = [kept]
            dropped.refresh_from_db()
            assert dropped.parent_id is None, (
                'el inverso no se anulo: se aplico la rama de borrado sobre '
                'un SET_NULL, que no es lo que la fuente decide')
            assert partner_class.objects.filter(pk=dropped.pk).exists(), (
                'el hijo se borro con un inverso SET_NULL: la fuente solo '
                'borra cuando el ondelete es cascade')
        finally:
            delattr(partner_class, 'o2m_test_unlink')
