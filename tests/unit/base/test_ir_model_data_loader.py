"""El bloque escritor de ``ir.model.data`` — tarea #115.

Cierra el porte de los diez símbolos del cargador contra
``odoo19c: addons/base/models/ir_model.py:2218-2537``. Hasta esta tarea la
clase tenía el **resolutor** (leer un identificador externo) y un
``set_xmlid`` propio, pero no el cargador: ``_update_xmlids`` con su
``INSERT ... ON CONFLICT``, ``_lookup_xmlids``, ``_load_xmlid`` y
``_process_end``.

Cuatro bloques: la cabecera, el escritor en lote, el resolutor memorizado y
el barrido de fin de carga.
"""
import pytest

from addons.base.models import ResCompany
from addons.base.models.ir_model import IrModelData
from exceptions import AccessError
from orm import registry
from orm.environments import sudo
from tools.cache import ormcache


class TestHeaderClassAttributes:
    """Los cuatro atributos de clase que la referencia declara, verbatim."""

    def test_name(self):
        # odoo19c: ir_model.py:2229
        assert IrModelData._name == 'ir.model.data'

    def test_description(self):
        assert IrModelData._description == 'Model Data'

    def test_order(self):
        assert IrModelData._order == 'module, model, name'

    def test_sudo_commands_are_not_allowed(self):
        assert IrModelData._allow_sudo_commands is False


class TestPortedSymbolNames:
    """Los símbolos del cargador, con el guion bajo de la fuente."""

    @pytest.mark.parametrize('name', [
        '_compute_complete_name', '_compute_reference', '_compute_display_name',
        '_xmlid_lookup', '_xmlid_to_res_model_res_id', '_xmlid_to_res_id',
        'check_object_reference', 'copy_data', '_lookup_xmlids',
        '_update_xmlids', '_build_insert_xmlids_values',
        '_build_update_xmlids_query', '_load_xmlid', 'toggle_noupdate',
        '_process_end', '_process_end_unlink_record', '_module_data_uninstall',
    ])
    def test_the_reference_symbol_is_declared(self, name):
        assert callable(getattr(IrModelData, name))

    @pytest.mark.parametrize('promoted', [
        'xmlid_lookup', 'xmlid_to_res_model_res_id', 'xmlid_to_res_id',
    ])
    def test_the_promoted_name_is_gone(self, promoted):
        # porte-completo-no-parcial.md: quitar el guion bajo publica lo
        # reservado. Los tres se despromovieron en esta tarea.
        assert not hasattr(IrModelData, promoted)

    def test_the_insert_columns_carry_the_audit_pair(self):
        # El INSERT en bruto esquiva a Django; sin estas dos la columna
        # NOT NULL revienta. Medido: reventaba.
        columns = IrModelData._build_insert_xmlids_values()
        assert columns['created_at'] == "now() at time zone 'UTC'"
        assert columns['updated_at'] == "now() at time zone 'UTC'"

    def test_the_lookup_is_memoised_like_the_reference(self):
        # odoo19c: :2270 — @tools.ormcache('xmlid')
        assert isinstance(IrModelData._xmlid_lookup.__func__.__cache__, ormcache)

    def test_the_key_carries_the_db_alias(self):
        # DIVERGENCIA DE CLAVE declarada: aquí el registry es el módulo.
        assert IrModelData._xmlid_lookup.__func__.__cache__.args == (
            'xmlid', 'using')


@pytest.mark.django_db
class TestUpdateXmlids:
    """``_update_xmlids`` — el INSERT en lote y su cláusula de conflicto."""

    def _company(self, code='imd-uno'):
        return ResCompany.objects.create(code=code, name=code.upper())

    def test_it_creates_the_row(self):
        registry.clear_cache('default')
        company = self._company()
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_one', 'record': company},
        ])
        row = IrModelData.objects.get(module='base', name='imd_probe_one')
        assert (row.model, row.res_id) == ('base.ResCompany', company.pk)

    def test_it_fills_the_audit_columns(self):
        registry.clear_cache('default')
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_audit', 'record': self._company('imd-aud')},
        ])
        row = IrModelData.objects.get(module='base', name='imd_probe_audit')
        assert row.created_at is not None and row.updated_at is not None

    def test_it_repoints_instead_of_duplicating(self):
        registry.clear_cache('default')
        first, second = self._company('imd-a'), self._company('imd-b')
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_move', 'record': first}])
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_move', 'record': second}])
        rows = IrModelData.objects.filter(module='base', name='imd_probe_move')
        assert rows.count() == 1
        assert rows.first().res_id == second.pk

    def test_noupdate_protects_the_row_when_updating(self):
        """El ``AND NOT ir_model_data.noupdate`` de la fuente, medido."""
        registry.clear_cache('default')
        first, second = self._company('imd-p1'), self._company('imd-p2')
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_keep', 'record': first,
             'noupdate': True}])
        IrModelData._update_xmlids(
            [{'xml_id': 'base.imd_probe_keep', 'record': second}], update=True)
        row = IrModelData.objects.get(module='base', name='imd_probe_keep')
        assert row.res_id == first.pk        # la bandera lo protegió

    def test_without_noupdate_an_update_repoints(self):
        registry.clear_cache('default')
        first, second = self._company('imd-q1'), self._company('imd-q2')
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_move2', 'record': first}])
        IrModelData._update_xmlids(
            [{'xml_id': 'base.imd_probe_move2', 'record': second}], update=True)
        assert IrModelData.objects.get(
            module='base', name='imd_probe_move2').res_id == second.pk

    def test_it_registers_the_xmlid_as_loaded(self):
        registry.loaded_xmlids.clear()
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_loaded', 'record': self._company('imd-l')}])
        assert 'base.imd_probe_loaded' in registry.loaded_xmlids

    def test_it_seeds_the_lookup_cache(self):
        """La optimización de la fuente: sembrar en vez de vaciar."""
        registry.clear_cache('default')
        company = self._company('imd-seed')
        IrModelData._update_xmlids([
            {'xml_id': 'base.imd_probe_seed', 'record': company}])
        # La row se borra por SQL para que el resolutor no pueda volver a
        # leerla; si responde, salió de la caché sembrada.
        IrModelData.objects.filter(
            module='base', name='imd_probe_seed').delete()
        assert IrModelData._xmlid_lookup('base.imd_probe_seed') == (
            'base.ResCompany', company.pk)

    def test_an_empty_list_does_nothing(self):
        assert IrModelData._update_xmlids([]) is None

    def test_set_xmlid_goes_through_the_same_writer(self):
        registry.loaded_xmlids.clear()
        company = self._company('imd-set')
        IrModelData.set_xmlid(company, 'base.imd_probe_set', noupdate=True)
        row = IrModelData.objects.get(module='base', name='imd_probe_set')
        assert row.noupdate is True
        assert 'base.imd_probe_set' in registry.loaded_xmlids


@pytest.mark.django_db
class TestLookupXmlids:
    """``_lookup_xmlids`` — el LEFT JOIN que distingue dos ausencias."""

    def test_a_missing_xmlid_is_absent_from_the_result(self):
        assert IrModelData._lookup_xmlids(
            ['base.imd_absent'], ResCompany) == []

    def test_an_empty_input_short_circuits(self):
        assert IrModelData._lookup_xmlids([], ResCompany) == []

    def test_a_live_record_comes_back_with_its_id(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-live', name='Live')
        IrModelData.set_xmlid(company, 'base.imd_live')
        rows = IrModelData._lookup_xmlids(['base.imd_live'], ResCompany)
        assert len(rows) == 1
        assert rows[0][4] == company.pk and rows[0][6] == company.pk

    def test_a_dangling_xmlid_comes_back_with_a_null_join(self):
        """La mitad que el LEFT JOIN compra: el identificador sobrevivió."""
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-dead', name='Dead')
        IrModelData.set_xmlid(company, 'base.imd_dead')
        pk = company.pk
        ResCompany.objects.filter(pk=pk).delete()
        rows = IrModelData._lookup_xmlids(['base.imd_dead'], ResCompany)
        assert len(rows) == 1
        assert rows[0][4] == pk and rows[0][6] is None


@pytest.mark.django_db
class TestProcessEnd:
    """``_process_end`` — retira lo que el módulo dejó de declarar."""

    def test_a_reloaded_xmlid_survives(self):
        registry.clear_cache('default')
        registry.loaded_xmlids.clear()
        company = ResCompany.objects.create(code='imd-keep', name='Keep')
        IrModelData.set_xmlid(company, 'probe_mod.imd_keep')
        IrModelData._process_end(['probe_mod'])
        assert ResCompany.objects.filter(pk=company.pk).exists()

    def test_an_xmlid_the_module_stopped_declaring_is_removed(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-drop', name='Drop')
        IrModelData.set_xmlid(company, 'probe_mod.imd_drop')
        registry.loaded_xmlids.clear()        # la recarga ya no lo declara
        IrModelData._process_end(['probe_mod'])
        assert not ResCompany.objects.filter(pk=company.pk).exists()
        assert not IrModelData.objects.filter(
            module='probe_mod', name='imd_drop').exists()

    def test_noupdate_protects_the_record_from_the_sweep(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-safe', name='Safe')
        IrModelData.set_xmlid(company, 'probe_mod.imd_safe', noupdate=True)
        registry.loaded_xmlids.clear()
        IrModelData._process_end(['probe_mod'])
        assert ResCompany.objects.filter(pk=company.pk).exists()

    def test_without_modules_it_short_circuits(self):
        assert IrModelData._process_end([]) is True


@pytest.mark.django_db
class TestResolverAndToggle:
    """El resolutor y las dos superficies que lo acompañan."""

    def test_check_object_reference_returns_the_pair(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-chk', name='Chk')
        IrModelData.set_xmlid(company, 'base.imd_chk')
        assert IrModelData.check_object_reference('base', 'imd_chk') == (
            'base.ResCompany', company.pk)

    def test_toggle_noupdate_flips_the_flag(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-tog', name='Tog')
        IrModelData.set_xmlid(company, 'base.imd_tog')
        with sudo():
            IrModelData.toggle_noupdate('base.ResCompany', company.pk)
        assert IrModelData.objects.get(
            module='base', name='imd_tog').noupdate is True

    def test_toggle_noupdate_inverts_a_second_time(self):
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-tog2', name='Tog2')
        IrModelData.set_xmlid(company, 'base.imd_tog2', noupdate=True)
        with sudo():
            IrModelData.toggle_noupdate('base.ResCompany', company.pk)
        assert IrModelData.objects.get(
            module='base', name='imd_tog2').noupdate is False

    def test_toggle_noupdate_flips_every_xmlid_of_the_record(self):
        # La fuente itera el `search` entero: un mismo registro puede llevar
        # identificador de más de un módulo, y los invierte todos.
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-two', name='Two')
        IrModelData.set_xmlid(company, 'base.imd_two_a')
        IrModelData.set_xmlid(company, 'sale.imd_two_b')
        with sudo():
            IrModelData.toggle_noupdate('base.ResCompany', company.pk)
        assert list(IrModelData.objects.filter(
            model='base.ResCompany', res_id=company.pk,
        ).order_by('name').values_list('noupdate', flat=True)) == [True, True]

    def test_toggle_noupdate_on_a_record_without_an_xmlid_is_a_noop(self):
        company = ResCompany.objects.create(code='imd-none', name='None')
        with sudo():
            assert IrModelData.toggle_noupdate(
                'base.ResCompany', company.pk) is None

    def test_toggle_noupdate_requires_write_access_on_the_target(self):
        # CONTROL que puede fallar (sub-patrón D): la guarda de la fuente es
        # `check_access('write')` sobre el registro apuntado, no una de
        # administrador. Sin elevación y con la ACL vacía, la escritura se
        # deniega — y con ella la inversión de la bandera.
        registry.clear_cache('default')
        company = ResCompany.objects.create(code='imd-deny', name='Deny')
        IrModelData.set_xmlid(company, 'base.imd_deny')
        with pytest.raises(AccessError):
            IrModelData.toggle_noupdate('base.ResCompany', company.pk)
        assert IrModelData.objects.get(
            module='base', name='imd_deny').noupdate is False

    def test_load_xmlid_marks_it_as_loaded(self):
        registry.clear_cache('default')
        registry.loaded_xmlids.clear()
        company = ResCompany.objects.create(code='imd-mark', name='Mark')
        IrModelData.set_xmlid(company, 'base.imd_mark')
        registry.loaded_xmlids.clear()
        assert IrModelData._load_xmlid('base.imd_mark') is not None
        assert 'base.imd_mark' in registry.loaded_xmlids

    def test_load_xmlid_of_an_absent_record_marks_nothing(self):
        registry.loaded_xmlids.clear()
        assert IrModelData._load_xmlid('base.imd_never') is None
        assert 'base.imd_never' not in registry.loaded_xmlids

    def test_copy_data_gives_the_copy_a_distinct_name(self):
        row = IrModelData(module='base', name='imd_orig',
                          model='base.ResCompany', res_id=1)
        assert IrModelData.copy_data(row)['name'].startswith('imd_orig_')
        assert IrModelData.copy_data(row)['name'] != 'imd_orig'

    def test_display_name_falls_back_to_the_complete_name(self):
        row = IrModelData(module='base', name='imd_x', model='base.Absent',
                           res_id=1)
        assert row._compute_display_name() == 'base.imd_x'

    def test_reference_is_the_model_id_pair(self):
        row = IrModelData(module='base', name='imd_y',
                           model='base.ResCompany', res_id=7)
        assert row._compute_reference() == 'base.ResCompany,7'
