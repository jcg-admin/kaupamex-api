"""Control del instrumento que mide el coste de la ventana de lectura.

El defecto que estos casos discriminan es el que el ejecutor detecto en la
prosa de :ref:`h-api-1072`: una particion cuyos tramos no cubren el universo
deja archivos **sin veredicto**, y nadie lo nota porque cada tramo por
separado se ve bien. El control no mide que los numeros sean bonitos: mide
que la particion sea total y que ningun tramo se quede sin instruccion.
"""
import importlib.util
import pathlib
import sys

import pytest

_AQUI = pathlib.Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    'reading_window_cost', _AQUI / 'measure_reading_window_cost.py')
reading_window_cost = importlib.util.module_from_spec(_SPEC)
sys.modules['reading_window_cost'] = reading_window_cost
_SPEC.loader.exec_module(reading_window_cost)

BANDS = reading_window_cost.BANDS
band_of = reading_window_cost.band_of
summarize = reading_window_cost.summarize


class TestThePartitionCoversTheWholeUniverse:
    """Todo archivo cae en exactamente un tramo, y todo tramo tiene veredicto."""

    @pytest.mark.parametrize('lines', [0, 1, 400, 401, 1500, 1501, 4000, 4001, 999999])
    def test_every_size_lands_in_exactly_one_band(self, lines):
        matches = [band for band in BANDS if band.low <= lines <= band.high]
        assert len(matches) == 1, (
            f'{lines} lineas cae en {len(matches)} tramos: {[b.name for b in matches]}')
        assert band_of(lines) is matches[0]

    def test_the_bands_leave_no_gap_between_them(self):
        # El hueco es invisible tramo a tramo: solo se ve al encadenarlos.
        ordered = sorted(BANDS, key=lambda band: band.low)
        assert ordered[0].low == 0
        for previous, following in zip(ordered, ordered[1:]):
            assert following.low == previous.high + 1, (
                f'hueco entre {previous.name} y {following.name}')

    def test_every_band_declares_a_verdict(self):
        # Este es el caso del episodio 6: un tramo medido y sin instruccion.
        sin_veredicto = [band.name for band in BANDS if not band.verdict.strip()]
        assert not sin_veredicto, f'tramos sin veredicto: {sin_veredicto}'

    def test_the_counts_add_up_to_the_population(self):
        sizes = [10, 400, 401, 1500, 1501, 4000, 4001, 9000]
        counts = summarize(sizes)
        assert sum(counts.values()) == len(sizes)
        assert set(counts) == {band.name for band in BANDS}


class TestTheControlWouldFail:
    """El control discrimina: con la particion rota, los casos caen."""

    def test_a_gap_in_the_bands_is_detected(self):
        Band = reading_window_cost.Band
        rota = [Band('a', 0, 400, 'v'), Band('b', 402, 4000, 'v')]
        huecos = [
            (previous.name, following.name)
            for previous, following in zip(rota, rota[1:])
            if following.low != previous.high + 1
        ]
        assert huecos == [('a', 'b')]

    def test_a_band_without_verdict_is_detected(self):
        Band = reading_window_cost.Band
        muda = [Band('a', 0, 400, 'v'), Band('b', 401, 4000, '')]
        assert [band.name for band in muda if not band.verdict.strip()] == ['b']
