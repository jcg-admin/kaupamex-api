"""Qué forma tiene un ``related=`` en la fuente — el control de una premisa.

**Por qué existe este archivo.** Cuatro archivos de este árbol declinan portar
un campo ``related=`` y dan su razón en prosa. Dos de esas razones describen
``store=True`` —«una copia que puede divergir», «inventar estado que hay que
sincronizar»— y se aplican a campos que la referencia declara **sin store**.
Un ``related`` sin ``store`` no es una columna: es una proyección que se
calcula al leer.

La prosa no tenía con qué medirse, así que envejeció mal y se contradecía
dentro del mismo archivo (``res_bank.py`` los llama «copia» arriba y
«proyecciones de un join» doce líneas más abajo). Este archivo le pone el
instrumento: si la forma de la fuente cambia, el caso falla y la prosa se
re-mide en vez de heredarse.

No mide nuestro árbol —hoy declara **0** campos ``related=``— sino la
**fuente**, que es lo que la premisa afirmaba.
"""
import collections
import importlib.util
import pathlib
import re

import pytest

#: El declarador único de rutas de la referencia. Se carga por ruta y no por
#: ``import`` porque ``scripts/`` no es un paquete importable desde ``tests/``;
#: es la misma vía que usa ``tests/unit/scripts/test_check_mirrored_roots.py``.
#: Lo que NO se hace es teclear la ruta larga de la referencia: está
#: triplicada por empaquetado y esa es justamente la segunda fuente de verdad
#: que ``calibration-verified-numbers`` prohíbe (H-API-335).
_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_tests', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)


RELATED = re.compile(r"related\s*=\s*'([^']+)'")
STORED = re.compile(r"store\s*=\s*True")


def _reference_root():
    try:
        return pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:                       # noqa: BLE001 — la raíz es opcional
        return None


def _ported_addons():
    """Los addons que este árbol porta, que es la población que nos toca."""
    names = sorted(p.name for p in (_REPO / 'addons').iterdir() if p.is_dir())
    return names + ['base']


def _related_declarations():
    """``Counter`` de ``related=`` en la fuente: total y con ``store``."""
    root = _reference_root()
    if root is None or not root.is_dir():
        pytest.skip('la referencia no está montada en esta sesión')

    counts = collections.Counter()
    for addon in _ported_addons():
        for base_dir in (root / 'odoo/addons' / addon, root / 'addons' / addon):
            if not base_dir.is_dir():
                continue
            for module in base_dir.rglob('*.py'):
                for line in module.read_text(errors='ignore').splitlines():
                    if 'fields.' in line and RELATED.search(line):
                        counts['total'] += 1
                        counts['stored' if STORED.search(line) else 'plain'] += 1
    return counts


class TestARelatedIsAProjectionNotACopy:
    """La premisa que dos bloques de prosa daban por buena, medida."""

    def test_the_reference_declares_them_in_bulk(self):
        """El denominador: no son un caso aislado que se pueda declinar."""
        counts = _related_declarations()
        assert counts['total'] > 400, (
            f"sólo {counts['total']} declaraciones halladas: el recorrido no "
            'está viendo la referencia y un conteo bajo aquí se leería como '
            '«casi no los usa», que es lo contrario de lo medido')

    def test_the_vast_majority_carry_no_store(self):
        """El corazón del asunto.

        La razón retirada —«una copia que puede divergir»— describe
        ``store=True``. Si la mayoría lo llevara, la prosa sería correcta y
        este caso lo diría.
        """
        counts = _related_declarations()
        plain, total = counts['plain'], counts['total']
        assert plain / total > 0.85, (
            f'{plain} de {total} sin store ({plain / total:.0%}): si esto baja, '
            'la razón que se retiró de res_bank.py y de account_peppol vuelve '
            'a ser discutible y hay que re-medirla, no restaurarla a ciegas')

    def test_the_named_field_of_the_refuted_prose_has_no_store(self):
        """El caso nombrado, que es el que la prosa justificaba.

        Sin este control, el porcentaje de arriba podría cumplirse y
        ``country_code`` ser justamente la excepción.
        """
        root = _reference_root()
        if root is None or not root.is_dir():
            pytest.skip('la referencia no está montada en esta sesión')
        source = (root / 'odoo/addons/base/models/res_bank.py').read_text()
        declaration = next(
            line for line in source.splitlines()
            if 'country_code' in line and RELATED.search(line))
        assert "related='country.code'" in declaration
        assert not STORED.search(declaration), (
            f'country_code SÍ declara store en la fuente: la prosa retirada '
            f'era correcta y hay que restaurarla — {declaration.strip()}')

    def test_the_detector_does_see_a_store_when_there_is_one(self):
        """El control que discrimina, sobre un caso REAL del mismo archivo.

        Sin él, un ``STORED`` que no casara nunca haría pasar el caso de
        arriba y nadie lo notaría: sería el verde que no distingue «no lleva
        store» de «el detector no sabe verlo».

        ``company_id`` (``odoo19c: res_bank.py:101``) es el vecino que **sí**
        lo declara, y está en los 45 de 597 que lo llevan.
        """
        root = _reference_root()
        if root is None or not root.is_dir():
            pytest.skip('la referencia no está montada en esta sesión')
        source = (root / 'odoo/addons/base/models/res_bank.py').read_text()
        declaration = next(
            line for line in source.splitlines()
            if 'company_id' in line and RELATED.search(line))
        assert STORED.search(declaration), (
            'el detector de store no vio un store que la fuente sí declara: '
            f'los otros casos de este archivo no distinguen nada — {declaration.strip()}')
