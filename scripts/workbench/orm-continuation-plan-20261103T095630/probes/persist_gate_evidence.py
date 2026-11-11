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
"""
import csv
import hashlib
import json
import pathlib
import re
import shutil
import sys

COLUMNS = ['execution_id', 'kind', 'revision', 'database', 'exit',
           'passed', 'failed', 'errors', 'xfailed', 'seconds',
           'expected', 'observed', 'limitation', 'files']
SUMMARY = re.compile(r'(\d+) (passed|failed|errors?|xfailed)')


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
    failed = row['failed'] if isinstance(row['failed'], int) else 0
    row['observed'] = ('fallo' if failed or exit_status not in (0, '-')
                       else 'verde')
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


if __name__ == '__main__':
    main(*sys.argv[1:])
