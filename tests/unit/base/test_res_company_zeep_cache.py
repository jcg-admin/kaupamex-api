"""El bucket de WSDL de ``ResCompany`` — ``ZeepOrmCache`` y sus dos métodos.

≙ ``odoo19c: res_company.py:18-27, 511-521``. La caché de ``zeep`` por defecto
es un SQLite en disco; aquí la reemplaza el bucket ``stable`` del registro, por
compañía, de modo que el WSDL de una autoridad tributaria se descarga una vez
por proceso y no una por petición.
"""
from types import SimpleNamespace

import pytest
import zeep as zeep_lib

from addons.base.models.res_company import ResCompany, ZeepOrmCache
from orm import registry


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex prueba zeep')


@pytest.fixture(autouse=True)
def bucket_limpio():
    """El bucket vive en la caché ``stable``, compartida por el proceso."""
    registry.cache_of('stable').clear()
    yield
    registry.cache_of('stable').clear()


class TestTheBucketIsPerCompanyAndPersists:

    def test_it_returns_the_same_dict_across_calls(self, company):
        """El control que puede fallar: si la memorización se cayera, cada
        llamada devolvería un ``dict`` nuevo y lo escrito se perdería.
        """
        first = company._get_zeep_cache__()
        first['http://sat/wsdl'] = b'<definitions/>'
        assert company._get_zeep_cache__() is first
        assert company._get_zeep_cache__()['http://sat/wsdl'] == b'<definitions/>'

    def test_two_companies_do_not_share_the_bucket(self, company):
        other_company = ResCompany.objects.create(name='Otra company')
        company._get_zeep_cache__()['http://sat/wsdl'] = b'<a/>'
        assert other_company._get_zeep_cache__() == {}

    def test_the_key_is_the_company_id_not_the_instance(self, company):
        company._get_zeep_cache__()['http://sat/wsdl'] = b'<a/>'
        reloaded = ResCompany.objects.get(pk=company.pk)
        assert reloaded._get_zeep_cache__()['http://sat/wsdl'] == b'<a/>'

    def test_the_double_underscore_suffix_of_the_source_is_kept(self):
        # ``porte-completo-no-parcial.md``: el nombre ES el contrato.
        assert hasattr(ResCompany, '_get_zeep_cache__')
        assert hasattr(ResCompany, '_get_zeep_client__')


class TestTheCacheImplementsTheContractOfZeep:
    """``zeep.cache.Base`` declara ``add(url, content)`` y ``get(url)``."""

    def test_it_is_a_zeep_cache(self, company):
        assert isinstance(ZeepOrmCache(company), zeep_lib.cache.Base)

    def test_add_writes_into_the_bucket_of_its_company(self, company):
        ZeepOrmCache(company).add('http://sat/wsdl', b'<definitions/>')
        assert company._get_zeep_cache__()['http://sat/wsdl'] == b'<definitions/>'

    def test_get_reads_back_what_add_wrote(self, company):
        cache = ZeepOrmCache(company)
        cache.add('http://sat/wsdl', b'<definitions/>')
        assert cache.get('http://sat/wsdl') == b'<definitions/>'

    def test_get_returns_none_for_an_unknown_url(self, company):
        assert ZeepOrmCache(company).get('http://sat/otro') is None


class TestTheClientInstallsTheCacheOnlyWhenTheTransportHasNone:

    @pytest.fixture
    def zeep_client_spy(self, monkeypatch):
        captured = {}

        def fake(*args, **kwargs):
            captured['kwargs'] = kwargs
            return SimpleNamespace(service=SimpleNamespace(_operations={}))

        monkeypatch.setattr(zeep_lib, 'Client', fake)
        return captured

    def test_a_transport_without_cache_gets_the_orm_one(self, company, zeep_client_spy):
        company._get_zeep_client__('http://sat/servicio?wsdl')
        cache = zeep_client_spy['kwargs']['transport'].cache
        assert isinstance(cache, ZeepOrmCache)
        assert cache.company == company

    def test_a_transport_with_its_own_cache_is_not_overwritten(self, company, zeep_client_spy):
        """El control que puede fallar: quien pasa su caché decide.

        Sin la guarda ``if not transport.cache`` el envoltorio la pisaría, y
        este caso sería el único en rojo.
        """
        own_cache = zeep_lib.cache.InMemoryCache()
        transport = zeep_lib.Transport(cache=own_cache)
        company._get_zeep_client__('http://sat/servicio?wsdl', transport=transport)
        assert zeep_client_spy['kwargs']['transport'].cache is own_cache

    def test_the_cache_it_installs_is_written_through(self, company, zeep_client_spy):
        company._get_zeep_client__('http://sat/servicio?wsdl')
        cache = zeep_client_spy['kwargs']['transport'].cache
        cache.add('http://sat/wsdl', b'<definitions/>')
        assert company._get_zeep_cache__()['http://sat/wsdl'] == b'<definitions/>'
