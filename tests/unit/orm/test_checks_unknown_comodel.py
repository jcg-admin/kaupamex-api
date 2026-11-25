"""El check de ``comodel_name`` desconocido — TASK-API-0411.

``odoo19c: odoo/orm/fields_relational.py:92-94`` afirma en
``setup_nonrelated`` que el comodelo está en el registro::

    assert self.comodel_name in model.pool, \\
        f"Field {self} with unknown comodel_name ..."

En el puerto un ``_name`` punteado que nunca se registra deja la etiqueta
centinela ``orm.<nombre>`` pendiente, y ``fields.E300`` de Django nombra el
centinela, no el nombre que el autor escribió. ``orm.E001`` porta la
aserción como system check.

Las sondas viven en ``isolate_apps``: un modelo roto en el registro global
contaminaría los checks de toda la suite.

*Métrica:* errores ``orm.E001`` sobre los modelos de la app consultada.
*Ciega a:* ``One2many``, que no es campo de Django ni deja centinela.
"""

from django.core import checks as django_checks
from django.core.checks import run_checks
from django.core.checks.registry import registry as check_registry
from django.db import models
from django.test.utils import isolate_apps

import fields
from orm.checks import UNKNOWN_COMODEL_ID, check_unknown_comodel


def unknown_comodel_messages(isolated_apps):
    """Los ``orm.E001`` del check sobre la app ``stock`` aislada."""
    app_config = isolated_apps.get_app_config('stock')
    return [message for message in check_unknown_comodel(
        app_configs=[app_config]) if message.id == UNKNOWN_COMODEL_ID]


class TestUnknownComodelIsReported:

    def test_many2one_names_the_field_and_the_source_name(self):
        with isolate_apps('addons.stock') as isolated_apps:
            class UnknownMany2oneProbe(models.Model):
                partner_id = fields.Many2one('res.partnerr', null=True)

                class Meta:
                    app_label = 'stock'

            messages = unknown_comodel_messages(isolated_apps)

        assert len(messages) == 1
        assert messages[0].level == django_checks.ERROR
        assert messages[0].msg == (
            "Field stock.unknownmany2oneprobe.partner_id with unknown "
            "comodel_name 'res.partnerr'")
        assert 'orm.res_partnerr' not in messages[0].msg

    def test_many2many_is_reported_too(self):
        with isolate_apps('addons.stock') as isolated_apps:
            class UnknownMany2manyProbe(models.Model):
                tag_ids = fields.Many2many('res.partnerr')

                class Meta:
                    app_label = 'stock'

            messages = unknown_comodel_messages(isolated_apps)

        assert [message.msg for message in messages] == [
            "Field stock.unknownmany2manyprobe.tag_ids with unknown "
            "comodel_name 'res.partnerr'"]


class TestKnownComodelIsNotReported:

    def test_registered_comodel(self):
        with isolate_apps('addons.stock') as isolated_apps:
            class KnownComodelProbe(models.Model):
                partner_id = fields.Many2one('res.partner', null=True)

                class Meta:
                    app_label = 'stock'

            assert unknown_comodel_messages(isolated_apps) == []

    def test_abstract_comodel_is_in_the_registry(self):
        # ``ir.fields.converter`` se anota con ``register_abstract``: la
        # fuente lo tiene en ``model.pool`` y la aserción pasa.
        with isolate_apps('addons.stock') as isolated_apps:
            class AbstractComodelProbe(models.Model):
                converter_id = fields.Many2one(
                    'ir.fields.converter', null=True)

                class Meta:
                    app_label = 'stock'

            assert unknown_comodel_messages(isolated_apps) == []


class TestTheCheckIsRegistered:

    def test_registered_with_the_models_tag(self):
        assert check_unknown_comodel in check_registry.get_checks()
        assert django_checks.Tags.models in check_unknown_comodel.tags

    def test_the_real_tree_has_no_unknown_comodel(self):
        assert [message for message in run_checks()
                if message.id == UNKNOWN_COMODEL_ID] == []
