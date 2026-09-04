"""Tests — los quince símbolos de ``res.groups`` que quedaban pendientes.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_groups.py``. La
tarea **#204** los desbloqueó al portar ``tools/set_expression.py``: cuatro de
ellos (``_search_all_implied_ids``, ``_search_all_implied_by_ids``,
``_get_view_group_hierarchy``, ``_ensure_xml_id``) dependían del grafo o de
``get_external_id``, que no existían.

Qué haría fallar a cada control
--------------------------------

``TestSearchFullName``
    ``full_name`` es ``privilegio / nombre`` y **no tiene columna**: la fuente
    descompone el operando para poder buscarlo. Lo haría fallar buscar sólo por
    ``name``, que es lo que un ``filter(name=...)`` ingenuo haría — el caso del
    operando con ``/`` lo detecta.

``TestSearchFullName.test_a_negative_operator_is_refused``
    CONTROL: la fuente devuelve ``NotImplemented`` en vez de adivinar. Sin él,
    un puerto que compusiera la negación pasaría los otros casos igual y daría
    filas de más.

``TestOrderByFullName``
    Ningún ``ORDER BY`` alcanza a ``full_name``; se ordena en Python. Lo haría
    fallar delegar el orden a PostgreSQL — que ni siquiera resolvería.

``TestCopyData``
    Sin el sufijo, la copia choca con ``UNIQUE (privilege_id, name)``. El caso
    lo comprueba **guardando** la copia, no sólo leyendo el dict.

``TestTheClosureSearches``
    Los dos espejos del grafo. El control que discrimina es que cada uno
    devuelve un conjunto **distinto** para la misma pareja padre/hijo: uno baja
    y el otro sube.

``TestTheSettingsGuard``
    CONTROL fail-closed del borrado: lo haría fallar no llamar a la guarda
    desde ``delete``.

``TestInheritedViewGroups``
    Una vista de extensión no declara ``groups`` en el registro — van dentro
    del arch. El control que discrimina es la vista **primaria**, que sí puede
    declararlos: sin ella, una guarda que rechazara cualquier ``groups``
    pasaría igual.

Las dos guardas, medidas con el cuerpo anulado
-----------------------------------------------

Sustituyendo el cuerpo por ``return None`` y corriendo el archivo entero
(``metrica-decide-la-conclusion.md``, sub-patrón D):

===================================== =============================== ==========================
Guarda anulada                        Resultado                       Cae
===================================== =============================== ==========================
``ResGroups._unlink_except_settings_group`` 1 failed, 27 passed       ``..._linked_to_a_settings_field_is_refused``
``IrUiView._check_groups``            1 failed, 27 passed             ``..._extension_view_with_groups_is_refused``
===================================== =============================== ==========================

Cae **exactamente** el caso que depende de cada una. Los 27 que sobreviven en
cada corrida no son un verde falso: o no ejercen esa guarda, o son el control
que mide justo el camino por el que la guarda **deja pasar**. Restaurado y
verificado con ``git diff --stat`` limpio en el archivo tocado.
"""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from addons.base.models.res_groups import ResGroups
from tests.conftest import matching_by_search_method
from addons.base.models.res_groups_privilege import ResGroupsPrivilege
from exceptions import UserError

pytestmark = pytest.mark.integration


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password='GruposPorte123!')


class TestSearchFullName:
    """≙ ``_search_full_name`` (``odoo19c: res_groups.py:131-165``)."""

    @staticmethod
    def _matching(operator, operand):
        """Las filas que el dominio de ``_search_full_name`` selecciona.

        El método devuelve un ``Domain``, como la fuente; estos casos afirman
        **qué filas** salen, así que necesitan el paso de compilación que da
        el optimizador al sustituir la condición.
        """
        return matching_by_search_method(
            ResGroups, '_search_full_name', operator, operand)

    def test_the_bare_name_matches(self, db):
        group = ResGroups.objects.create(name='Contabilidad avanzada 204')
        assert group in self._matching('=', 'Contabilidad avanzada 204')

    def test_the_privilege_slash_name_form_matches(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Ventas 204')
        group = ResGroups.objects.create(name='Responsable 204', privilege=privilege)
        found = self._matching('=', 'Ventas 204 / Responsable 204')
        assert group in found, (
            'el operando compuesto tiene que descomponerse — un filtro por '
            '``name`` a secas no lo encontraría')

    def test_the_privilege_alone_matches_its_groups(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Almacén 204')
        group = ResGroups.objects.create(name='Operario 204', privilege=privilege)
        assert group in self._matching('=', 'Almacén 204')

    def test_a_list_of_operands_is_a_disjunction(self, db):
        uno = ResGroups.objects.create(name='Alfa 204')
        dos = ResGroups.objects.create(name='Beta 204')
        found = self._matching('in', ['Alfa 204', 'Beta 204'])
        assert uno in found and dos in found

    def test_a_negative_operator_is_refused(self, db):
        assert ResGroups._search_full_name('not like', 'x') is NotImplemented
        assert ResGroups._search_full_name('!=', 'x') is NotImplemented


class TestOrderByFullName:
    """≙ ``_search`` (``odoo19c: res_groups.py:167-175``)."""

    def test_the_order_is_computed_in_python(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='ZZZ 204')
        ResGroups.objects.create(name='AAA 204')
        ResGroups.objects.create(name='BBB 204', privilege=privilege)
        pks = {'AAA 204', 'ZZZ 204 / BBB 204'}
        nombres = [g.full_name for g in ResGroups._search(order='full_name')]
        assert nombres == sorted(nombres)
        assert pks <= set(nombres)

    def test_desc_reverses_it(self, db):
        ResGroups.objects.create(name='AAA 204')
        nombres = [g.full_name for g in ResGroups._search(order='full_name DESC')]
        assert nombres == sorted(nombres, reverse=True)

    def test_any_other_order_stays_a_queryset(self, db):
        result = ResGroups._search(order='name')
        assert hasattr(result, 'filter'), (
            'sin orden por full_name el orden lo resuelve PostgreSQL')


class TestCopyData:
    """≙ ``copy_data`` (``odoo19c: res_groups.py:177-182``)."""

    def test_the_copy_gets_a_suffix_and_can_be_saved(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Compras 204')
        group = ResGroups.objects.create(name='Aprobador 204', privilege=privilege)
        values = group.copy_data()
        assert values['name'] == 'Aprobador 204 (copia)'
        # Guardarla es el control: sin sufijo choca con UNIQUE(privilege, name).
        copia = ResGroups.objects.create(
            name=values['name'], privilege=privilege)
        assert copia.pk != group.pk

    def test_an_explicit_name_wins(self, db):
        group = ResGroups.objects.create(name='Con nombre propio 204')
        assert group.copy_data({'name': 'Otro'})['name'] == 'Otro'


class TestTheClosureSearches:
    """≙ ``_search_all_implied_ids`` / ``_search_all_implied_by_ids``."""

    @pytest.fixture
    def cadena(self, db):
        padre = ResGroups.objects.create(name='Padre 204')
        hijo = ResGroups.objects.create(name='Hijo 204')
        hijo.implied_ids.add(padre)
        return padre, hijo

    def test_all_implied_ids_descends_to_the_child(self, cadena):
        padre, hijo = cadena
        found = ResGroups._search_all_implied_ids([padre.pk])
        assert padre in found and hijo in found

    def test_all_implied_by_ids_climbs_to_the_parent(self, cadena):
        padre, hijo = cadena
        found = ResGroups._search_all_implied_by_ids([hijo.pk])
        assert padre in found and hijo in found

    def test_the_two_directions_are_not_the_same_set(self, cadena):
        padre, hijo = cadena
        baja = set(ResGroups._search_all_implied_ids([hijo.pk]).values_list('pk', flat=True))
        sube = set(ResGroups._search_all_implied_by_ids([hijo.pk]).values_list('pk', flat=True))
        assert baja != sube, (
            'si los dos dieran lo mismo, uno de los dos estaría llamando al '
            'accesor equivocado del grafo')
        assert padre.pk in sube and padre.pk not in baja

    def test_negate_returns_the_complement(self, cadena):
        padre, hijo = cadena
        dentro = ResGroups._search_all_implied_by_ids([hijo.pk])
        fuera = ResGroups._search_all_implied_by_ids([hijo.pk], negate=True)
        assert not set(dentro.values_list('pk', flat=True)) & set(
            fuera.values_list('pk', flat=True))

    def test_search_all_user_ids_finds_the_implied_membership(self, db):
        padre = ResGroups.objects.create(name='Padre con usuario 204')
        hijo = ResGroups.objects.create(name='Hijo con usuario 204')
        hijo.implied_ids.add(padre)
        who = _user('grupos.busqueda@practicayoruba.mx')
        who.group_ids.add(hijo)
        found = ResGroups._search_all_user_ids([who])
        assert hijo in found
        assert padre in found, (
            'el usuario pertenece al padre por implicación, no directamente')


class TestUserTypeGroups:
    """≙ ``_get_user_type_groups`` (``odoo19c: res_groups.py:280-287``)."""

    def test_only_the_groups_that_declare_a_type(self, db):
        con = ResGroups.objects.create(
            name='Con tipo 204', user_type=ResGroups.USER_TYPE_PORTAL)
        sin = ResGroups.objects.create(name='Sin tipo 204')
        tipos = ResGroups._get_user_type_groups()
        assert con in tipos and sin not in tipos


class TestEnsureXmlId:
    """≙ ``_ensure_xml_id`` (``odoo19c: res_groups.py:203-221``)."""

    def test_a_group_without_one_gets_a_custom_identifier(self, db):
        group = ResGroups.objects.create(name='Sin xmlid 204')
        result = group._ensure_xml_id()
        assert result[group.pk] == '__custom__.group_%s' % group.pk

    def test_an_existing_identifier_is_kept(self, db):
        data_model = apps.get_model('base', 'IrModelData')
        group = ResGroups.objects.create(name='Con xmlid 204')
        data_model.set_xmlid(group, 'base.group_ya_sembrado_204')
        assert group._ensure_xml_id()[group.pk] == 'base.group_ya_sembrado_204'


class TestInverseAllUserIds:
    """≙ ``_inverse_all_user_ids`` (``odoo19c: res_groups.py:228-240``)."""

    def test_it_adds_the_missing_users(self, db):
        group = ResGroups.objects.create(name='Destino 204')
        who = _user('grupos.inverso.alta@practicayoruba.mx')
        group._inverse_all_user_ids([who])
        assert who in group.user_ids.all()

    def test_it_refuses_to_remove_an_implied_member(self, db):
        padre = ResGroups.objects.create(name='Padre implicante 204')
        hijo = ResGroups.objects.create(name='Hijo implicante 204')
        hijo.implied_ids.add(padre)
        who = _user('grupos.inverso.implicado@practicayoruba.mx')
        who.group_ids.add(hijo)
        assert who in padre.all_user_ids
        with pytest.raises(UserError):
            padre._inverse_all_user_ids([])


class TestTheSettingsGuard:
    """≙ ``_unlink_except_settings_group`` (``odoo19c: res_groups.py:114-119``).

    El guard recorre los modelos concretos que declaran ``classify_fields`` y
    compara el ``implied_group`` de cada campo ``group_*`` contra el nombre del
    grupo que se está borrando.

    *Métrica:* modelos concretos con ``classify_fields`` en el registro de
    apps — **2** (``base_setup.SiteConfigSettings`` y ``web.WebConfigSettings``),
    y **ninguno** declara hoy un campo ``group_*``, así que en el árbol tal
    cual el guard nunca dispara. Por eso el caso positivo **fabrica** el campo
    parcheando ``settings_field_names`` y ``field_attrs``: sin eso el test
    mediría la ausencia de datos, no la guarda.
    *Ciega a:* que el ``implied_group`` real de los addons viene en forma de
    xmlid mientras el resolvedor del árbol busca por ``name`` — la
    incoherencia que la tarea **#206** cierra.
    """

    @staticmethod
    def _settings_model():
        """El modelo concreto de ajustes sobre el que se monta el campo."""
        return next(model for model in apps.get_models()
                    if hasattr(model, 'classify_fields'))

    def test_a_plain_group_deletes(self, db):
        group = ResGroups.objects.create(name='Sin ajuste 204')
        pk = group.pk
        group.delete()
        assert not ResGroups.objects.filter(pk=pk).exists()

    def test_a_group_linked_to_a_settings_field_is_refused(self, db, monkeypatch):
        group = ResGroups.objects.create(name='Con ajuste 204')
        settings_model = self._settings_model()
        monkeypatch.setattr(
            settings_model, 'settings_field_names',
            classmethod(lambda cls: ['group_con_ajuste']))
        monkeypatch.setattr(
            settings_model, 'field_attrs',
            {'group_con_ajuste': {'implied_group': group.name}})
        with pytest.raises(ValidationError):
            group.delete()
        assert ResGroups.objects.filter(pk=group.pk).exists()

    def test_another_group_with_the_same_field_still_deletes(self, db, monkeypatch):
        """El control que discrimina: el campo existe y apunta a OTRO grupo.

        Sin él, el caso de arriba pasaría igual con un guard que levantara
        ante cualquier campo ``group_*``, mirara el nombre o no.
        """
        linked = ResGroups.objects.create(name='Enlazado 204')
        other = ResGroups.objects.create(name='Ajeno 204')
        settings_model = self._settings_model()
        monkeypatch.setattr(
            settings_model, 'settings_field_names',
            classmethod(lambda cls: ['group_con_ajuste']))
        monkeypatch.setattr(
            settings_model, 'field_attrs',
            {'group_con_ajuste': {'implied_group': linked.name}})
        pk = other.pk
        other.delete()
        assert not ResGroups.objects.filter(pk=pk).exists()


class TestTheViewHierarchy:
    """≙ ``_get_view_group_hierarchy`` (``odoo19c: res_groups.py:325-360``)."""

    def test_the_three_keys_and_the_group_payload(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Panel 204')
        group = ResGroups.objects.create(name='Del panel 204', privilege=privilege)
        arbol = ResGroups._get_view_group_hierarchy()
        assert sorted(arbol) == ['categories', 'groups', 'privileges']
        assert arbol['groups'][group.pk]['name'] == 'Del panel 204'
        assert arbol['groups'][group.pk]['privilege_id'] == privilege.pk
        assert group.pk in arbol['privileges'][privilege.pk]['group_ids']

    def test_the_property_reads_the_same_tree(self, db):
        group = ResGroups.objects.create(name='Lectura del panel 204')
        assert group.view_group_hierarchy == ResGroups._get_view_group_hierarchy()


class TestTheAction:
    """≙ ``action_show_all_users`` (``odoo19c: res_groups.py:386-397``)."""

    def test_the_domain_uses_the_transitive_membership(self, db):
        group = ResGroups.objects.create(name='Con acción 204')
        action = group.action_show_all_users()
        assert action['type'] == 'ir.actions.act_window'
        assert action['res_model'] == 'base.ResUsers'
        assert action['domain'] == [('all_group_ids', 'in', [group.pk])], (
            'all_group_ids, no group_ids: la acción promete los implicados')
        assert action['context']['create'] is False


class TestInheritedViewGroups:
    """≙ ``_check_inherited_view_groups`` y ``IrUiView._check_groups``."""

    def test_an_extension_view_with_groups_is_refused(self, db):
        view_model = apps.get_model('base', 'IrUiView')
        group = ResGroups.objects.create(name='De la vista 204')
        base_view = view_model.objects.create(
            name='base 204', model='base.ResPartner', arch_db='<form/>')
        extension = view_model.objects.create(
            name='ext 204', model='base.ResPartner', arch_db='<form/>',
            inherit_id=base_view, mode='extension')
        extension.groups.add(group)
        with pytest.raises(ValidationError):
            group._check_inherited_view_groups()

    def test_a_primary_view_with_groups_is_fine(self, db):
        view_model = apps.get_model('base', 'IrUiView')
        group = ResGroups.objects.create(name='De la vista primaria 204')
        primary = view_model.objects.create(
            name='primaria 204', model='base.ResPartner', arch_db='<form/>')
        primary.groups.add(group)
        group._check_inherited_view_groups()
