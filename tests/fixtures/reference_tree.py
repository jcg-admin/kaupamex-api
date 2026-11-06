"""Las pruebas que necesitan el árbol de referencia, y qué pasa sin él.

Una prueba que compara este árbol con ``odoo19c`` lee la referencia desde
``odoo-tools``, que el CI no clona. Sin un criterio común, cada módulo lo
resolvía a su manera: medido el 2026-11-05 con la suite completa ejecutada
dos veces —con la referencia y con ``ODOO_TOOLS`` apuntando a una ruta
inexistente—, **257** pruebas cambian de resultado; 225 se omitían por un
mecanismo propio y **32 fallaban**, porque el script que miden lee el árbol
sin comprobar antes que exista. Con ``--maxfail=1`` en ``make ci-verify``,
la primera de esas 32 detiene la ejecución del CI.

El criterio es único: una prueba marcada ``reference`` necesita que exista
el directorio que ``reference_roots.tree('odoo19c')`` declara. Si no existe,
se omite con la ruta en el motivo, antes de ejecutarse.

La marca llega por dos vías:

- **automática**, para la prueba que pide el fixture ``reference`` — la
  convención de los diferenciales, cuyo fixture ya omite por su cuenta;
- **explícita** (``@pytest.mark.reference``), para la que lee el árbol sin
  ese fixture, normalmente a través del script que mide.

Y el resumen de la ejecución separa las omisiones por referencia ausente del
resto: un CI sin referencia que reporta «verde» no ha verificado ninguno de
esos contratos, y la cifra tiene que estar a la vista.

*Métrica:* pruebas marcadas, y cuántas de ellas se omitieron porque el árbol
no existe.
*Ciega a:* la prueba que lee la referencia sin marca ni fixture. Esa prueba
**falla** en un entorno sin referencia en vez de omitirse, y ese fallo es la
alarma que obliga a marcarla; el conteo no la ve.
"""
import importlib.util
import pathlib

import pytest

MARKER = 'reference'
FIXTURE = 'reference'

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_marker', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)


def reference_root():
    """La raíz de ``odoo19c`` que declara ``reference_roots``, exista o no."""
    return pathlib.Path(reference_roots.tree('odoo19c'))


def missing_reason(root):
    """El motivo de omisión si ``root`` no existe; ``None`` si existe."""
    if root.is_dir():
        return None
    return f'referencia ausente: {root} no existe (odoo-tools no clonado)'


def mark_items(items):
    """Marca ``reference`` a cada prueba que pide el fixture ``reference``."""
    marked = 0
    for item in items:
        if (FIXTURE in getattr(item, 'fixturenames', ())
                and item.get_closest_marker(MARKER) is None):
            item.add_marker(MARKER)
            marked += 1
    return marked


def pytest_collection_modifyitems(config, items):
    mark_items(items)


def pytest_runtest_setup(item):
    if item.get_closest_marker(MARKER) is None:
        return
    reason = missing_reason(reference_root())
    if reason is not None:
        pytest.skip(reason)


class ReferenceCount:
    """El conteo de pruebas marcadas, en el proceso que imprime el resumen.

    Con ``-n`` ese proceso no colecta ni ejecuta: sólo recibe los informes de
    los trabajadores. Por eso se cuenta desde ``pytest_runtest_logreport`` y
    no desde los items, que en ese proceso están vacíos.
    """

    def __init__(self):
        self.marked = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.when != 'setup' or MARKER not in report.keywords:
            return
        self.marked += 1
        # Toda omisión de una prueba marcada cuenta, no sólo la de este
        # módulo: un guard propio más fino (un addon concreto de la
        # referencia) también deja su contrato sin verificar.
        if report.skipped:
            self.skipped += 1

    def pytest_terminal_summary(self, terminalreporter):
        line = summary_line(self.marked, self.skipped, reference_root())
        if line is not None:
            terminalreporter.write_line(line)


def pytest_configure(config):
    config.pluginmanager.register(ReferenceCount(), 'reference-count')


def summary_line(marked, skipped, root):
    """La línea del resumen: cuántas pruebas dependen de la referencia."""
    if not marked:
        return None
    if not skipped:
        return (f'referencia: {marked} pruebas marcadas, '
                f'árbol presente en {root}')
    cause = (f'{root} no existe' if missing_reason(root)
             else f'el árbol está en {root}; los motivos, con -rs')
    return (f'referencia: {skipped} de {marked} pruebas marcadas se omitieron '
            f'({cause}); sus contratos NO se verificaron en esta ejecución')
