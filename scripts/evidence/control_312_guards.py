"""Control del pase de precompute — anula cada guarda y mide qué cae (#312).

Un verde no distingue *"el motor corre el precompute"* de *"el test no
pregunta"*. Este control lo separa: sustituye el cuerpo de cada guarda sobre
una copia en memoria, corre el módulo de tests, y **exige** que caigan los
casos que dependen de ella. Si con la guarda anulada la suite sigue verde, el
caso mide otra cosa y hay que rehacerlo — sub-patrón D de
``metrica-decide-la-conclusion.md``.

Nunca ``git checkout``: la restauración sale de la copia en memoria y se cierra
con el sha256 de cada archivo más un ``git diff --stat`` vacío (regla #177).

Uso::

    DJANGO_SETTINGS_MODULE=config.settings.testing \\
        uv run python scripts/evidence/control_312_guards.py
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE = 'tests/unit/orm/test_precompute_before_insert.py'

#: Cada guarda: el archivo, el texto que la implementa, el texto que la
#: anula, y la clase de casos que su ausencia tiene que tumbar.
GUARDS = (
    (
        'la exclusión del valor que el llamador dio',
        'src/orm/models.py',
        """        if not getattr(field, 'readonly', False):
            if name in given or getattr(field, 'attname', name) in given:
                continue
""",
        '',
        'TestOnlyTheUncoveredPrecomputeIsPending',
    ),
    (
        'el orden por dependencia',
        'src/orm/models.py',
        """    chain = chain + (name,)
    for dotted in registry.field_depends[field]:
        head = dotted.split('.')[0]
        other = pending.get(head)
        if other is not None and head not in chain and other.compute not in done:
            _run_precompute_field(instance, head, pending, done, chain)
""",
        '',
        'TestTheComputesRunInDependencyOrder',
    ),
    (
        'el guard de fila nueva',
        'src/orm/models.py',
        '    if raw or not instance._state.adding:\n',
        '    if raw:\n',
        'TestTheReceiverFiresOnlyOnInsert',
    ),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_subset(selector=None):
    """Corre el módulo (o una clase suya) y devuelve la última línea de pytest."""
    target = MODULE if selector is None else f'{MODULE}::{selector}'
    out = subprocess.run(
        ['uv', 'run', 'pytest', target, '-q', '--reuse-db',
         '-p', 'no:cacheprovider'],
        cwd=ROOT, capture_output=True, text=True,
    )
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    return lines[-1] if lines else '(sin salida)'


def git_diff_stat():
    return subprocess.run(['git', 'diff', '--stat'], cwd=ROOT,
                          capture_output=True, text=True).stdout


def main():
    #: El árbol puede tener trabajo sin commitear, así que el cierre compara
    #: el diff CONTRA SÍ MISMO —antes y después— y no contra HEAD.
    diff_before = git_diff_stat()

    print('== control sin anular nada ==')
    print(' ', run_subset())

    failures = []
    for name, relative, old, new, klass in GUARDS:
        path = ROOT / relative
        original = path.read_text()
        before = sha256(path)
        if original.count(old) != 1:
            failures.append(f'{name}: el texto de la guarda no aparece 1 vez')
            continue
        path.write_text(original.replace(old, new))
        try:
            result = run_subset(klass)
        finally:
            path.write_text(original)
        print(f'== anulada: {name} ==')
        print(f'  {klass}: {result}')
        if 'failed' not in result and 'error' not in result:
            failures.append(
                f'{name}: con la guarda anulada {klass} sigue verde — '
                'el caso no la mide')
        after = sha256(path)
        if before != after:
            failures.append(f'{name}: sha256 distinto tras restaurar')

    print('== cierre ==')
    if git_diff_stat() == diff_before:
        print('  git diff --stat: idéntico al de antes del control')
    else:
        failures.append('el árbol cambió respecto de antes del control')

    if failures:
        print('\nFALLOS:')
        for f in failures:
            print(f'  - {f}')
        return 1
    print('  todas las guardas discriminan; árbol restaurado')
    return 0


if __name__ == '__main__':
    sys.exit(main())
