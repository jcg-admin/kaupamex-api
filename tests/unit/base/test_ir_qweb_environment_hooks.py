"""Los dos enganches de ``ir.qweb`` que Enterprise 19 consulta —
``_prepare_environment`` y ``_get_template_cache_keys``— más lo que el
primero publica (``QwebJSON``, ``_get_converted_image_data_uri``).

Adaptación de ``odoo19c: odoo/addons/base/models/ir_qweb.py:672-680,
951-953, 1269-1327`` (LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03).

El docstring del módulo los daba por portados desde :ref:`h-api-819` y no
existían: lo destapó ``http_routing`` (#261) al colgar su override con
``wrap_method``, que exige una implementación previa. Estos casos miden lo
que aquel párrafo afirmaba.
"""
import base64
import math

import pytest

from addons.base.models.ir_template_expressions import (
    IrTemplateExpressions, QwebJSON, keep_query, qwebJSON,
)
from orm.environments import context_scope
from tools import config
from tools.safe_eval import datetime as safe_datetime
from tools.safe_eval import time as safe_time


def _base_link(name):
    """El eslabón que ``ir_template_expressions.py`` declara en el cuerpo de
    la clase, sin los ``overrides=``/``chain_method`` que ``http_routing`` y
    ``html_builder`` cuelgan encima — mismo idioma que
    ``tests/unit/digest/test_digest_kpi_actions.py``."""
    current = IrTemplateExpressions.__dict__[name]
    while getattr(current, '_chain_previous', None) is not None:
        current = current._chain_previous
    return current


class TestTemplateCacheKeys:
    def test_the_five_keys_of_the_source_in_order(self):
        base = _base_link('_get_template_cache_keys')
        assert base(IrTemplateExpressions()) == [
            'lang', 'inherit_branding', 'inherit_branding_auto',
            'edit_translations', 'profile',
        ]

    def test_the_installed_chain_starts_with_the_five(self):
        """Los addons que extienden el enganche sólo añaden claves al final
        (``html_builder`` suma ``snippet_lang``): las cinco de la base siguen
        ahí, en su orden."""
        keys = IrTemplateExpressions()._get_template_cache_keys()
        assert keys[:5] == [
            'lang', 'inherit_branding', 'inherit_branding_auto',
            'edit_translations', 'profile',
        ]


class TestPrepareEnvironmentPublishesTheTemplateNames:
    """≙ ``values.update(true=True, false=False)`` y el bloque condicional
    que ``minimal_qcontext`` apaga."""

    def test_true_and_false_are_published_always(self):
        """Con ``minimal_qcontext`` la base sólo publica ``true``/``false``;
        lo demás que aparezca lo cuelgan los addons que extienden el enganche
        (``http_routing`` publica ``slug``/``unslug_url`` en todo contexto,
        como su fuente), no este eslabón."""
        values = {}
        with context_scope(minimal_qcontext=True):
            IrTemplateExpressions()._prepare_environment(values)
        assert values['true'] is True and values['false'] is False
        base = _base_link('_prepare_environment')
        only_base = {}
        with context_scope(minimal_qcontext=True):
            base(IrTemplateExpressions(), only_base)
        assert only_base == {'true': True, 'false': False}

    def test_returns_self_so_callers_can_chain(self):
        qweb = IrTemplateExpressions()
        assert qweb._prepare_environment({}) is qweb

    def test_the_full_context_publishes_the_utilities(self):
        values = {}
        qweb = IrTemplateExpressions()
        qweb._prepare_environment(values)
        assert values['json'] is qwebJSON
        assert values['floor'] is math.floor
        assert values['ceil'] is math.ceil
        assert values['time'] is safe_time
        assert values['datetime'] is safe_datetime
        assert values['keep_query'] is keep_query
        assert values['test_mode_enabled'] is True
        # Ligado al receptor: es el método del objeto, no la función suelta.
        assert values['image_data_uri'].__self__ is qweb
        # Fuera de una petición, ``request`` es None y ``debug`` la cadena
        # vacía — no una excepción.
        assert values['request'] is None and values['debug'] == ''
        assert 'env' in values and 'lang' in values

    def test_minimal_qcontext_withholds_the_utilities(self):
        values = {}
        with context_scope(minimal_qcontext=True):
            IrTemplateExpressions()._prepare_environment(values)
        assert 'json' not in values and 'env' not in values

    def test_setdefault_keeps_a_debug_the_caller_already_chose(self):
        """``values.setdefault('debug', …)``: el valor del llamador manda."""
        values = {'debug': 'assets'}
        IrTemplateExpressions()._prepare_environment(values)
        assert values['debug'] == 'assets'


class TestQwebJSON:
    class _Fragment:
        def __html__(self):
            return '<b>x</b>'

        def __str__(self):
            return '<b>x</b>'

    def test_a_rendered_fragment_is_serialised_as_its_text(self):
        assert qwebJSON.dumps({'f': self._Fragment()}) == '{"f": "<b>x</b>"}'

    def test_the_callers_default_still_applies(self):
        payload = qwebJSON.dumps(
            {'n': {1, 2}}, default=lambda obj: sorted(obj))
        assert payload == '{"n": [1, 2]}'

    def test_it_is_the_script_safe_dumps(self):
        """Hereda el ``dumps`` seguro de :class:`tools.json.JSON`: la cadena
        sabe escaparse al incrustarse (``__html__``), y ahí ``<`` sale como
        ``\\u003c``."""
        payload = QwebJSON().dumps('</script>')
        assert '\\u003c' in payload.__html__()


class TestConvertedImageDataUri:
    def test_without_webp_as_jpg_it_is_the_plain_data_uri(self):
        source = base64.b64encode(b'RIFF....WEBP')
        uri = IrTemplateExpressions()._get_converted_image_data_uri(source)
        assert uri == f'data:image/webp;base64,{source.decode()}'

    @pytest.mark.django_db
    def test_with_webp_as_jpg_and_no_conversion_it_keeps_the_webp(self):
        """La rama busca la conversión por SHA1 y no la encuentra: devuelve
        el WEBP original, sin reventar."""
        source = base64.b64encode(b'RIFF....WEBP')
        with context_scope(webp_as_jpg=True):
            uri = IrTemplateExpressions()._get_converted_image_data_uri(
                source)
        assert uri.startswith('data:image/webp;base64,')


class TestConfigAccessors:
    def test_test_enable_is_true_under_the_testing_settings(self):
        assert config.test_enable() is True

    def test_dev_mode_is_empty_without_debug(self):
        assert config.dev_mode() == []
