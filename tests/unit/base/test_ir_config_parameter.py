"""Contrato de la CABECERA de ``SystemParameter`` — atributos de clase de
Odoo ``ir.config_parameter`` (``odoo19c: odoo/addons/base/models/
ir_config_parameter.py:28-34``).

Tarea #387 (H-API-580 / ``atributos-de-clase-de-modelo.md``): la clase de la
referencia declara 5 atributos ORM (``_name``, ``_description``,
``_rec_name``, ``_order``, ``_allow_sudo_commands``); el puerto no declaraba
ninguno. Cada test aquí verifica UNO de esos 5, portado verbatim, más su
forma Django derivada donde el atributo la tiene. El comportamiento
runtime (get/set, caché, protección de claves, seed) ya está cubierto por
``test_system_parameter.py`` — este archivo NO lo duplica.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models import SystemParameter
from addons.base.models import ir_config_parameter as config_module
from addons.base.models.ir_config_parameter import _DEFAULT_PARAMETERS
from orm import registry
from tools.cache import ormcache


class TestHeaderClassAttributes:
    """Los 5 atributos ORM que la referencia declara, verbatim."""

    def test_name_matches_the_reference_model_name(self):
        # odoo19c: ir_config_parameter.py:30 — _name = 'ir.config_parameter'
        assert SystemParameter._name == 'ir.config_parameter'

    def test_description_matches_the_reference_description(self):
        # odoo19c: ir_config_parameter.py:31 — _description = 'System Parameter'
        assert SystemParameter._description == 'System Parameter'

    def test_rec_name_matches_the_reference_rec_name(self):
        # odoo19c: ir_config_parameter.py:32 — _rec_name = 'key'
        assert SystemParameter._rec_name == 'key'

    def test_order_matches_the_reference_order(self):
        # odoo19c: ir_config_parameter.py:33 — _order = 'key'
        assert SystemParameter._order == 'key'

    def test_allow_sudo_commands_matches_the_reference_value(self):
        # odoo19c: ir_config_parameter.py:34 — _allow_sudo_commands = False
        assert SystemParameter._allow_sudo_commands is False


class TestHeaderDjangoDerivedForm:
    """Cada atributo verbatim convive con su forma Django — no la sustituye
    (atributos-de-clase-de-modelo.md: "no sustituyen a su forma Django")."""

    def test_table_diverges_from_name_dot_replaced_by_declared_naming(self):
        # odoo19c: model_classes.py:266 — _table = _name.replace('.', '_')
        # habria dado 'ir_config_parameter'. Aqui es 'system_parameter'
        # (el nombre de la clase Django, ya migrado en 0001_initial).
        # DIVERGENCIA DECLARADA, no simbolo ausente: renombrar la tabla
        # excede el alcance de esta tarea (solo admite migracion nueva si
        # agrega campo/indice, no si renombra una tabla ya migrada).
        assert SystemParameter._name.replace('.', '_') == 'ir_config_parameter'
        assert SystemParameter._meta.db_table == 'system_parameter'

    def test_description_coexists_with_verbose_name(self):
        assert SystemParameter._meta.verbose_name == SystemParameter._description

    def test_order_coexists_with_meta_ordering(self):
        assert list(SystemParameter._meta.ordering) == [SystemParameter._order]

    def test_rec_name_is_a_real_field(self):
        # _rec_name apunta a un campo existente del modelo (el que etiqueta
        # el registro; lo consume __str__ en este puerto).
        field_names = {f.name for f in SystemParameter._meta.get_fields()}
        assert SystemParameter._rec_name in field_names


class TestOrmcacheAdoption:
    """El puerto memoriza con ``ormcache``, no con un mapa a mano.

    La razon declarada del ``_PARAM_CACHE`` ad-hoc era que el stack no traia
    el mecanismo. Dejo de ser cierta con ``api@c636e68c``: ``tools/cache.py``
    y los contenedores de ``orm/registry.py`` existen. La referencia decora
    ``_get_param`` con ``@ormcache('key', cache='stable')``
    (``odoo19c: ir_config_parameter.py:69-70``).
    """

    def test_get_param_is_decorated_with_ormcache(self):
        # __cache__ lo cuelga ormcache.__call__ sobre el envoltorio.
        cache = SystemParameter._get_param.__func__.__cache__
        assert isinstance(cache, ormcache)

    def test_the_cache_family_is_the_one_the_reference_declares(self):
        # odoo19c: ir_config_parameter.py:70 — cache='stable'
        assert SystemParameter._get_param.__func__.__cache__.cache_name == 'stable'

    def test_the_ad_hoc_cache_is_gone(self):
        assert not hasattr(config_module, '_PARAM_CACHE')
        assert not hasattr(config_module, '_clear_cache')

    def test_the_key_carries_the_model_name_and_the_db_alias(self):
        # La referencia declara ('key',) y su Registry es POR BASE, asi que la
        # dimension de base va implicita. Aqui el registry es el modulo
        # (divergencia de enlace ya declarada en tools/cache.py), asi que el
        # alias entra en la clave: sin el, dos bases compartirian entrada.
        key = SystemParameter._get_param.__func__.__cache__.key(
            SystemParameter, 'k', 'otra_base')
        assert key[0] == 'ir.config_parameter'
        assert key[2] == 'k'
        assert key[3] == 'otra_base'


@pytest.mark.django_db
class TestPortedMutationMethods:
    """Los cinco simbolos que el gate reportaba ausentes, con el nombre de la
    referencia: ``init``, ``create``, ``write``, ``unlink`` y
    ``unlink_default_parameters``."""

    def test_create_invalidates_the_stable_family(self):
        SystemParameter.set_param('k', 'v')
        SystemParameter.get_param('k')                    # siembra la entrada
        registry.cache_of('stable')['centinela'] = 1
        SystemParameter.create({'key': 'otra', 'value': 'x'})
        assert 'centinela' not in registry.cache_of('stable').snapshot

    def test_create_accepts_a_list_like_the_reference(self):
        # odoo19c: :101 — @api.model_create_multi
        created = SystemParameter.create([
            {'key': 'lote.a', 'value': '1'},
            {'key': 'lote.b', 'value': '2'},
        ])
        assert len(created) == 2
        assert SystemParameter.get_param('lote.a') == '1'

    def test_write_invalidates_the_stable_family(self):
        p = SystemParameter.objects.create(key='w', value='v1')
        SystemParameter.get_param('w')
        registry.cache_of('stable')['centinela'] = 1
        p.write({'value': 'v2'})
        assert 'centinela' not in registry.cache_of('stable').snapshot
        assert SystemParameter.get_param('w') == 'v2'

    def test_write_refuses_to_rename_a_protected_key(self):
        # odoo19c: :107-110 — el mensaje nombra las claves ilegales
        p = SystemParameter.objects.get(key='database.uuid')
        with pytest.raises(ValidationError) as exc:
            p.write({'key': 'database.renamed'})
        assert 'database.uuid' in str(exc.value)

    def test_unlink_invalidates_the_stable_family(self):
        p = SystemParameter.objects.create(key='u', value='v')
        SystemParameter.get_param('u')
        registry.cache_of('stable')['centinela'] = 1
        p.unlink()
        assert 'centinela' not in registry.cache_of('stable').snapshot
        assert SystemParameter.get_param('u') is None

    def test_unlink_default_parameters_refuses_a_protected_key(self):
        # odoo19c: :118-121 — @api.ondelete(at_uninstall=False)
        p = SystemParameter.objects.get(key='database.uuid')
        with pytest.raises(ValidationError):
            p.unlink_default_parameters()

    def test_unlink_default_parameters_is_silent_on_a_free_key(self):
        p = SystemParameter.objects.create(key='libre', value='v')
        assert p.unlink_default_parameters() is None

    def test_init_seeds_the_default_parameters(self):
        # odoo19c: :44 — el nombre de la referencia es ``init``, no ``seed``
        SystemParameter.init()
        for key in _DEFAULT_PARAMETERS:
            assert SystemParameter.objects.filter(key=key).exists()

    def test_init_with_force_overwrites(self):
        SystemParameter.init()
        before = SystemParameter.get_param('database.uuid')
        SystemParameter.init(force=True)
        assert SystemParameter.get_param('database.uuid') != before
