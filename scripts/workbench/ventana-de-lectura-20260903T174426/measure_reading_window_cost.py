#!/usr/bin/env python3
"""Cuanto cuesta leer un archivo entero, y en que tramo eso deja de pagar.

El instrumento nace de :ref:`h-api-1072`: cinco episodios de porte donde la
afirmacion salio de una ventana ``sed``/``grep`` que no incluia al refutador,
y un sexto donde la prosa que los documentaba dejo un tramo entero sin
veredicto. La pregunta que responde es la del ejecutor —*"por que no usar*
``cat``\\ *? se gastan mas tokens?"*— y la responde para las **dos**
poblaciones que se leen al portar: nuestro arbol y el de la referencia.

La particion en tramos es total por construccion y cada tramo declara su
veredicto; el control de ``tests/`` mide justo eso, porque un tramo sin
instruccion es invisible mirando los tramos de uno en uno.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import pathlib
import sys

# El declarador de raices de la referencia vive en scripts/ y este modulo en
# scripts/workbench/<pieza>/, asi que se carga por ruta. No se copian las
# rutas: `reference_roots` es la fuente unica, y duplicarlas aqui seria la
# segunda fuente de verdad que su propio docstring prohibe (H-API-335).
_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent.parent
_REFERENCE_SPEC = importlib.util.spec_from_file_location(
    'reference_roots', _SCRIPTS / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_REFERENCE_SPEC)
_REFERENCE_SPEC.loader.exec_module(reference_roots)

# Cuatro bytes por token es la estimacion gruesa que basta para decidir un
# tramo; la razon real del tokenizador no es esa, y el manifiesto lo declara
# como ceguera.
BYTES_PER_TOKEN = 4


@dataclasses.dataclass(frozen=True)
class Band:
    """Un tramo de tamano con su veredicto de lectura."""

    name: str
    low: int
    high: int
    verdict: str


# Los limites no se solapan y no dejan hueco: `test_the_bands_leave_no_gap`
# lo verifica encadenandolos, que es la unica forma de ver el hueco.
BANDS: tuple[Band, ...] = (
    Band('<=400', 0, 400,
         'cat -n entero, siempre'),
    Band('401-1500', 401, 1500,
         'cat -n entero, siempre'),
    Band('1501-4000', 1501, 4000,
         'cat -n entero la PRIMERA vez que la sesion toca el archivo; '
         'despues, ventana declarada'),
    Band('>4000', 4001, 1 << 30,
         'ventana obligatoria: simbolo + bases + llamadores + hermanos de '
         'contrato, y el comando declara su corte'),
)


def band_of(lines: int) -> Band:
    """El tramo al que pertenece un archivo de ``lines`` lineas."""
    for band in BANDS:
        if band.low <= lines <= band.high:
            return band
    raise ValueError(f'ningun tramo cubre {lines} lineas')


@dataclasses.dataclass(frozen=True)
class FileSize:
    """El tamano de un archivo, en las dos unidades que deciden."""

    path: str
    lines: int
    size_bytes: int

    @property
    def tokens(self) -> int:
        return self.size_bytes // BYTES_PER_TOKEN


#: Subarboles anidados que son OTRA poblacion, no ruido. La raiz de ``odoo18c``
#: es ``18.x/odoo-18`` y ese directorio CONTIENE ``enterprise/``: medido
#: 2026-09-03, 13 869 de sus 21 857 ``.py`` viven ahi, en 1292 addons de los
#: que **191 no existen en** ``odoo18e`` —``auth_passkey``, ``certificate``,
#: ``account_iso20022``, ``accountant``…—.
#:
#: Por eso NO se descarta: se mide **aparte**. La licencia que declara un
#: addon decide el mecanismo de porte (copiar con atribucion frente a
#: reimplementar), y :ref:`analisis-inventario-account-cuatro-arboles` midio
#: que 17 addons de ``account`` cambian de veredicto al mirar las cuatro
#: poblaciones en vez de una. Descartar una quinta con 191 addons propios
#: repetiria ese defecto, no lo evitaria.
#:
#: Lo que si seria un error es sumarla al conteo de Community 18: son
#: poblaciones distintas y fundirlas es el eje de la version de
#: :ref:`h-api-76`. Sin alias en ``reference_roots``, asi que va por ruta
#: hasta que la tarea **#65** le de uno.
NESTED_POPULATIONS = {'odoo18c': ('enterprise',)}


def measure_tree(root: pathlib.Path, pattern: str = '*.py',
                 excluded: tuple[str, ...] = ()) -> list[FileSize]:
    """Mide cada archivo del arbol. Salta el que no se pueda leer.

    ``excluded`` son nombres de subarbol de primer nivel que quedan fuera; el
    reporte los nombra junto al conteo, porque una exclusion silenciosa es la
    ventana que no declara lo que dejo fuera.
    """
    measured: list[FileSize] = []
    for path in sorted(root.rglob(pattern)):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in excluded:
            continue
        try:
            lines = len(path.read_text(errors='ignore').splitlines())
        except OSError:
            continue
        measured.append(
            FileSize(str(path.relative_to(root)), lines, path.stat().st_size))
    return measured


def summarize(sizes) -> dict[str, int]:
    """Cuantos archivos hay en cada tramo. Acepta enteros o ``FileSize``."""
    counts = {band.name: 0 for band in BANDS}
    for item in sizes:
        lines = item if isinstance(item, int) else item.lines
        counts[band_of(lines).name] += 1
    return counts


def report(label: str, measured: list[FileSize],
           excluded: tuple[str, ...] = ()) -> dict:
    """El reporte de una poblacion, con su denominador junto a cada conteo."""
    total = len(measured)
    counts = summarize(measured)
    whole_file_ok = sum(
        count for name, count in counts.items()
        if band_of(next(b.low for b in BANDS if b.name == name)).high <= 1500)
    return {
        'population': label,
        'files': total,
        'excluded_subtrees': list(excluded),
        'bands': [
            {
                'band': band.name,
                'files': counts[band.name],
                'share': round(counts[band.name] * 100 / total, 1) if total else 0.0,
                'verdict': band.verdict,
            }
            for band in BANDS
        ],
        'whole_file_always': whole_file_ok,
        'whole_file_always_share':
            round(whole_file_ok * 100 / total, 1) if total else 0.0,
        'largest': [
            {'path': item.path, 'lines': item.lines, 'tokens': item.tokens}
            for item in sorted(measured, key=lambda f: f.lines, reverse=True)[:5]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='*', metavar='ETIQUETA=RUTA',
                        help='poblaciones propias a medir, p. ej. api=src')
    parser.add_argument('--reference', action='store_true',
                        help='anadir los CUATRO alias de la referencia, con '
                             'las raices que declara scripts/reference_roots.py')
    parser.add_argument('--json', action='store_true',
                        help='emitir el reporte como JSON')
    args = parser.parse_args(argv)

    reports = []
    for spec in args.roots:
        label, _, raw = spec.partition('=')
        root = pathlib.Path(raw or label)
        if not root.is_dir():
            print(f'ERROR: {root} no es un directorio', file=sys.stderr)
            return 2
        reports.append(report(label, measure_tree(root)))

    if args.reference:
        # Los cuatro, no uno: medir un solo alias y concluir sobre «la
        # referencia» es el eje de la version que h-api-76 y h-api-227 ya
        # registraron. `require` rehusa si una raiz falta, en vez de publicar
        # un 0 que se leeria como «no hay archivos».
        for alias in sorted(reference_roots.TREE_ROOTS):
            root = reference_roots.require(alias)
            nested = NESTED_POPULATIONS.get(alias, ())
            reports.append(
                report(alias, measure_tree(root, excluded=nested), nested))
            # Cada anidada se mide COMO POBLACION, no se descarta: sus addons
            # propios cambian veredictos de licencia (ver NESTED_POPULATIONS).
            for name in nested:
                nested_root = root / name
                if nested_root.is_dir():
                    reports.append(
                        report(f'{alias}/{name} (sin alias)',
                               measure_tree(nested_root)))

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0

    for item in reports:
        fuera = (f"  (sin {', '.join(item['excluded_subtrees'])}/, "
                 f"que se mide aparte)"
                 if item['excluded_subtrees'] else '')
        print(f"=== {item['population']} — {item['files']} archivos .py{fuera}")
        for band in item['bands']:
            print(f"  {band['files']:5d}  {band['share']:5.1f} %  "
                  f"{band['band']:12s} {band['verdict']}")
        print(f"  cabe entero siempre: {item['whole_file_always']} "
              f"({item['whole_file_always_share']} %)")
        for big in item['largest']:
            print(f"    {big['lines']:6d} lineas  ~{big['tokens']:6d} tok  {big['path']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
