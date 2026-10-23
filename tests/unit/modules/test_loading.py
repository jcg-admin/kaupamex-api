"""Manifest data-stage contracts; parser and whole-loader acceptance are separate."""
from types import SimpleNamespace
from unittest import mock

from django.utils.connection import ConnectionDoesNotExist
import pytest

from modules.loading import load_data


def package(**changes):
    manifest = {'init_xml': [], 'data': [], 'demo': []}
    manifest.update(changes)
    return SimpleNamespace(name='contract_module', manifest=manifest)


def test_data_keeps_order_and_imports_duplicates(caplog):
    refs = {}
    with mock.patch('modules.loading.convert_file') as convert:
        assert load_data(refs, 'init', 'data', package(
            init_xml=['old.xml'], data=['first.xml', 'old.xml']), using='default')
    assert convert.call_args_list == [
        mock.call('contract_module', name, refs, 'init', noupdate=False, using='default')
        for name in ['old.xml', 'first.xml', 'old.xml']
    ]
    assert 'deprecated' in caplog.text and 'twice' in caplog.text


def test_demo_uses_only_demo_and_protects_updates():
    refs = {}
    with mock.patch('modules.loading.convert_file') as convert:
        assert load_data(refs, 'update', 'demo', package(
            data=['not_demo.xml'], demo=['demo.xml']), using='default')
    convert.assert_called_once_with('contract_module', 'demo.xml', refs,
                                    'update', noupdate=True, using='default')


@pytest.mark.parametrize('kind', ['data', 'demo'])
def test_empty_stage_is_false_and_does_not_call_converter(kind):
    with mock.patch('modules.loading.convert_file') as convert:
        assert load_data({}, 'init', kind, package(), using='default') is False
    convert.assert_not_called()


def test_shared_references_and_converter_failure_propagate():
    refs = {}

    def convert(module, filename, idref, mode, **kwargs):
        assert idref is refs
        if filename == 'first.xml':
            idref['created'] = 10
        else:
            assert idref['created'] == 10
            raise ValueError('Invalid second data file')

    with mock.patch('modules.loading.convert_file', side_effect=convert) as converter:
        with pytest.raises(ValueError, match='Invalid second data file'):
            load_data(refs, 'init', 'data', package(
                data=['first.xml', 'bad.xml', 'never.xml']), using='default')
    assert converter.call_count == 2


def test_database_is_explicit_and_unknown_alias_does_not_fall_back():
    with mock.patch('modules.loading.convert_file') as convert:
        with pytest.raises(TypeError):
            load_data({}, 'init', 'data', package(data=['file.xml']))
        with pytest.raises(ConnectionDoesNotExist):
            load_data({}, 'init', 'data', package(data=['file.xml']),
                      using='missing_manifest_contract_database')
    convert.assert_not_called()
