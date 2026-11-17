"""Persiste el expediente de un gate en el banco y lo indexa con su hash.

Es el paso PERSIST de la secuencia EXECUTE, FINALIZE, PERSIST, VERIFY
PERSISTENCE, MARK RECLAIMABLE, CLEANUP. Copia los archivos de un gate (el
juego que escribe ``scripts/run_multidb_isolation.py``: ``record.json``,
``pytest_isolation.log``, ``junit_isolation.xml``, ``check_ci_database.log``,
o el log de una suite) a ``outputs/gates/<nombre>/`` y añade su fila a
``outputs/gates/index.tsv``. No inventa campos: lo que el gate no registró
queda como ``-``.

Uso: python persist_gate_evidence.py <banco> <nombre> <kind> <revisión>
         <resultado esperado> <limitación> <archivo>...
     python persist_gate_evidence.py reclaim <banco> [--mark-only] <copia>...

``reclaim`` es MARK RECLAIMABLE y CLEANUP, después de commitear el banco: una
copia del scratchpad se retira sólo si su ``sha256`` figura en una fila del
índice, el archivo del banco con ese nombre está en ``HEAD`` con el mismo blob
y sin cambios locales, y ningún proceso la tiene abierta. Cada decisión queda
en ``outputs/gates/reclaimed.tsv``; ``--mark-only`` la anota sin retirar.
"""
import csv
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

COLUMNS = ['execution_id', 'kind', 'revision', 'database', 'exit',
           'passed', 'failed', 'errors', 'xfailed', 'seconds',
           'expected', 'observed', 'limitation', 'files']
SUMMARY = re.compile(r'(\d+) (passed|failed|errors?|xfailed)')
EXIT_MARK = re.compile(r'^EXIT=(\d+)$')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(paths):
    """Los totales de la última línea de resumen de pytest entre los logs."""
    found = {}
    for path in paths:
        if path.suffix != '.log':
            continue
        for line in path.read_text(errors='replace').splitlines():
            if ' in ' in line and SUMMARY.search(line):
                found = {kind.rstrip('s') if kind.startswith('error')
                         else kind: int(number)
                         for number, kind in SUMMARY.findall(line)}
    return found


def exit_mark(paths):
    """La salida del proceso que la suite anota al final de su log
    (``EXIT=<n>``); ``None`` si ningún log la trae."""
    found = None
    for path in paths:
        if path.suffix != '.log':
            continue
        for line in path.read_text(errors='replace').splitlines():
            match = EXIT_MARK.match(line)
            if match:
                found = int(match.group(1))
    return found


def verdict(totals, exit_status):
    """Tres estados: ``fallo`` si algo falló, dio error o el proceso salió
    distinto de cero; ``sin-medir`` si no hay ni resumen ni salida; si no,
    ``verde``. Un resumen sin ``failed`` no basta: los errores y la salida
    cuentan."""
    if not totals and exit_status == '-':
        return 'sin-medir'
    if (totals.get('failed') or totals.get('error')
            or exit_status not in (0, '-')):
        return 'fallo'
    return 'verde'


def main(bench, name, kind, revision, expected, limitation, *files):
    target = pathlib.Path(bench) / 'outputs' / 'gates' / name
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in map(pathlib.Path, files):
        destination = target / source.name
        shutil.copyfile(source, destination)
        copied.append(destination)
    record = {}
    for path in copied:
        if path.name == 'record.json':
            record = json.loads(path.read_text())
    totals = counts(copied)
    exit_status = record.get('pytest_exit', '-')
    if exit_status == '-':
        marked = exit_mark(copied)
        exit_status = '-' if marked is None else marked
    row = {
        'execution_id': name, 'kind': kind, 'revision': revision,
        'database': record.get('database', '-'), 'exit': exit_status,
        'passed': totals.get('passed', '-'),
        'failed': totals.get('failed', 0 if totals else '-'),
        'errors': totals.get('error', 0 if totals else '-'),
        'xfailed': totals.get('xfailed', 0 if totals else '-'),
        'seconds': record.get('pytest_seconds', '-'),
        'expected': expected, 'observed': '-', 'limitation': limitation,
        'files': ';'.join(f'{p.name}:{sha256(p)}' for p in copied),
    }
    row['observed'] = verdict(totals, exit_status)
    index = target.parent / 'index.tsv'
    rows = []
    if index.exists():
        with index.open(encoding='utf-8') as handle:
            rows = [r for r in csv.DictReader(handle, delimiter='\t')
                    if r['execution_id'] != name]
    rows.append(row)
    with index.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, COLUMNS, delimiter='\t',
                                lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(name, row['observed'], row['passed'], row['failed'],
          row['errors'])


RECLAIM_COLUMNS = ['source', 'sha256', 'bank_file', 'decision']


def _open_paths(paths):
    """Las rutas de ``paths`` que algún proceso tiene abiertas (``lsof``)."""
    if not paths:
        return set()
    result = subprocess.run(['lsof', '-Fn', '--', *map(str, paths)],
                            capture_output=True, text=True)
    return {line[1:] for line in result.stdout.splitlines()
            if line.startswith('n')}


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args],
                          capture_output=True, text=True)


def _bank_file(gates, digest, name):
    """El archivo del banco que el índice registra con ese nombre y hash."""
    index = gates / 'index.tsv'
    if not index.exists():
        return None
    with index.open(encoding='utf-8') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            if f'{name}:{digest}' in row['files'].split(';'):
                return gates / row['execution_id'] / name
    return None


def _decide(gates, source, digest, open_paths):
    bank = _bank_file(gates, digest, source.name)
    if bank is None:
        return None, 'kept:not-in-index'
    if not bank.exists() or sha256(bank) != digest:
        return bank, 'kept:bank-modified'
    repo = pathlib.Path(_git(gates, 'rev-parse', '--show-toplevel')
                        .stdout.strip())
    relative = bank.resolve().relative_to(repo.resolve()).as_posix()
    blob = _git(repo, 'hash-object', str(source.resolve())).stdout.strip()
    head = _git(repo, 'rev-parse', '--verify', '-q',
                f'HEAD:{relative}').stdout.strip()
    if not blob or head != blob:
        return bank, 'kept:not-in-head'
    if _git(repo, 'diff', '--quiet', 'HEAD', '--', relative).returncode:
        return bank, 'kept:bank-modified'
    if str(source.resolve()) in open_paths:
        return bank, 'kept:open'
    return bank, 'reclaimable'


def reclaim(bench, *sources):
    mark_only = '--mark-only' in sources
    sources = [pathlib.Path(s) for s in sources if s != '--mark-only']
    gates = pathlib.Path(bench) / 'outputs' / 'gates'
    open_paths = _open_paths([s.resolve() for s in sources if s.exists()])
    rows = []
    for source in sources:
        if not source.is_file():
            continue
        digest = sha256(source)
        bank, decision = _decide(gates, source, digest, open_paths)
        if decision == 'reclaimable' and not mark_only:
            source.unlink()
            decision = 'removed'
        rows.append({'source': str(source), 'sha256': digest,
                     'bank_file': str(bank or '-'), 'decision': decision})
    ledger = gates / 'reclaimed.tsv'
    exists = ledger.exists()
    with ledger.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, RECLAIM_COLUMNS, delimiter='\t',
                                lineterminator='\n')
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row['decision'], row['source'])
    return rows


if __name__ == '__main__':
    if sys.argv[1:2] == ['reclaim']:
        reclaim(*sys.argv[2:])
    else:
        main(*sys.argv[1:])
