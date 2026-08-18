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
from addons.base.models import SystemParameter


class TestHeaderClassAttributes:
    """Los 5 atributos ORM que la referencia declara, verbatim."""

    def test_name_matches_odoo_model_name(self):
        # odoo19c: ir_config_parameter.py:30 — _name = 'ir.config_parameter'
        assert SystemParameter._name == 'ir.config_parameter'

    def test_description_matches_odoo_description(self):
        # odoo19c: ir_config_parameter.py:31 — _description = 'System Parameter'
        assert SystemParameter._description == 'System Parameter'

    def test_rec_name_matches_odoo_rec_name(self):
        # odoo19c: ir_config_parameter.py:32 — _rec_name = 'key'
        assert SystemParameter._rec_name == 'key'

    def test_order_matches_odoo_order(self):
        # odoo19c: ir_config_parameter.py:33 — _order = 'key'
        assert SystemParameter._order == 'key'

    def test_allow_sudo_commands_matches_odoo_value(self):
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
