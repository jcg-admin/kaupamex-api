"""Tests — addons.geo.CatalogPostalCode + loader load_sepomex (T-202/T-206).

Cubre: el modelo mapea las 15 columnas SEPOMEX, la clave natural
(postal_code, settlement_consecutive_id) es única (un CP -> N colonias), y el
loader parsea correctamente el formato oficial (latin-1, CRLF, licencia +
cabecera descartadas).
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from addons.base_address_extended.models import CatalogPostalCode

pytestmark = pytest.mark.django_db


def _row(**over):
    data = dict(
        postal_code='01000', settlement_name='San Ángel', settlement_type='Colonia',
        municipality='Álvaro Obregón', state='Ciudad de México', city='Ciudad de México',
        office_postal_code='01001', state_code='09', office_code='01001',
        postal_code_internal_code='', settlement_type_code='09', municipality_code='010',
        settlement_consecutive_id='0001', zone='Urbano', city_code='01',
    )
    data.update(over)
    return CatalogPostalCode.objects.create(**data)


def test_model_stores_all_15_columns():
    obj = _row()
    obj.refresh_from_db()
    assert obj.country == 'MX'                       # default país (fuente actual)
    assert obj.postal_code == '01000'
    assert obj.settlement_name == 'San Ángel'      # latin-1 accents preserved
    assert obj.municipality == 'Álvaro Obregón'
    assert obj.zone == CatalogPostalCode.ZONE_URBANO
    assert obj.postal_code_internal_code == ''      # c_CP siempre vacío


def test_natural_key_is_scoped_by_country():
    """El mismo (postal_code, settlement_consecutive_id) puede coexistir en dos
    países — el catálogo es internacional (envíos internacionales futuros)."""
    _row(country='MX', postal_code='28001', settlement_consecutive_id='0001',
         settlement_name='Centro')
    # Mismo CP+consecutivo, país distinto (ej. España): permitido.
    _row(country='ES', postal_code='28001', settlement_consecutive_id='0001',
         settlement_name='Salamanca', municipality='Madrid', state='Madrid',
         zone='')
    assert CatalogPostalCode.objects.filter(postal_code='28001').count() == 2
    assert CatalogPostalCode.objects.filter(country='ES').count() == 1


def test_one_cp_maps_to_many_settlements():
    """Un CP mapea a N colonias: postal_code NO es único."""
    _row(settlement_consecutive_id='0001', settlement_name='San Ángel')
    _row(settlement_consecutive_id='0005', settlement_name='Los Alpes')
    assert CatalogPostalCode.objects.filter(postal_code='01000').count() == 2


def test_natural_key_is_unique():
    """(postal_code, settlement_consecutive_id) es único."""
    _row(settlement_consecutive_id='0001')
    with pytest.raises(IntegrityError):
        _row(settlement_consecutive_id='0001')


def test_loader_parses_official_format(tmp_path):
    """El loader descarta licencia+cabecera, decodifica latin-1, strip CRLF."""
    # Archivo estilo SEPOMEX: latin-1, CRLF, línea de licencia + cabecera + 2 datos.
    header = ('d_codigo|d_asenta|d_tipo_asenta|D_mnpio|d_estado|d_ciudad|d_CP|'
              'c_estado|c_oficina|c_CP|c_tipo_asenta|c_mnpio|id_asenta_cpcons|'
              'd_zona|c_cve_ciudad')
    r1 = '01000|San Ángel|Colonia|Álvaro Obregón|Ciudad de México|Ciudad de México|01001|09|01001||09|010|0001|Urbano|01'
    r2 = '01010|Los Alpes|Colonia|Álvaro Obregón|Ciudad de México|Ciudad de México|01001|09|01001||09|010|0005|Urbano|01'
    content = '\r\n'.join(['El Catálogo Nacional... licencia', header, r1, r2]) + '\r\n'
    f = tmp_path / 'sepomex.txt'
    f.write_bytes(content.encode('latin-1'))

    out = StringIO()
    call_command('load_sepomex', path=str(f), stdout=out)

    assert CatalogPostalCode.objects.count() == 2
    sa = CatalogPostalCode.objects.get(settlement_consecutive_id='0001')
    assert sa.settlement_name == 'San Ángel'        # accents intact through latin-1
    assert sa.municipality == 'Álvaro Obregón'
    assert '2 filas insertadas' in out.getvalue()


def test_loader_truncate_reloads_clean(tmp_path):
    _row(postal_code='99999', settlement_consecutive_id='0001')
    header = ('d_codigo|d_asenta|d_tipo_asenta|D_mnpio|d_estado|d_ciudad|d_CP|'
              'c_estado|c_oficina|c_CP|c_tipo_asenta|c_mnpio|id_asenta_cpcons|'
              'd_zona|c_cve_ciudad')
    r1 = '01000|San Ángel|Colonia|Álvaro Obregón|CDMX|CDMX|01001|09|01001||09|010|0001|Urbano|01'
    content = '\r\n'.join(['licencia', header, r1]) + '\r\n'
    f = tmp_path / 'sepomex.txt'
    f.write_bytes(content.encode('latin-1'))

    call_command('load_sepomex', path=str(f), truncate=True, stdout=StringIO())
    assert CatalogPostalCode.objects.count() == 1
    assert not CatalogPostalCode.objects.filter(postal_code='99999').exists()
