"""El expediente de un gate no se publica en verde si el gate falló.

``probes/persist_gate_evidence.py`` del Workbench. El positivo es real: la
suite completa sobre ``29285b00`` terminó con ``1 error`` y ``EXIT=2``, sin
ningún ``failed``, y el guion la indexó como ``verde``.

*Métrica:* la columna ``observed`` de la fila que el guion escribe.
*Ciega a:* un log cuyo resumen de pytest no diga la verdad del proceso.
"""
import csv
import importlib.util
import pathlib
import sys

import pytest

_PATH = (pathlib.Path(__file__).resolve().parents[3] / 'scripts' / 'workbench'
         / 'orm-continuation-plan-20261103T095630' / 'probes'
         / 'persist_gate_evidence.py')
_spec = importlib.util.spec_from_file_location('persist_gate_evidence', _PATH)
persist = importlib.util.module_from_spec(_spec)
sys.modules['persist_gate_evidence'] = persist
_spec.loader.exec_module(persist)


def _observed(tmp_path, log_text):
    log = tmp_path / 'suite.log'
    log.write_text(log_text)
    persist.main(str(tmp_path), 'gate', 'full-batch', 'abc1234', 'verde',
                 '-', str(log))
    index = tmp_path / 'outputs' / 'gates' / 'index.tsv'
    with index.open(newline='') as handle:
        return next(csv.DictReader(handle, delimiter='\t'))


@pytest.mark.parametrize('log_text, observed, exit_status', [
    ('10 passed, 2 xfailed in 3.00s\nEXIT=0\n', 'verde', '0'),
    # el caso real: errores sin ``failed``, y el proceso salió con 2
    ('10699 passed, 66 skipped, 79 xfailed, 1 error in 975.43s\nEXIT=2\n',
     'fallo', '2'),
    ('9 passed, 1 failed in 3.00s\nEXIT=1\n', 'fallo', '1'),
    # errores aunque nadie anotara la salida del proceso
    ('9 passed, 2 errors in 3.00s\n', 'fallo', '-'),
    # un resumen limpio con salida distinta de cero no es verde
    ('9 passed in 3.00s\nEXIT=137\n', 'fallo', '137'),
    # sin resumen ni salida no hay medida que publicar
    ('bringing up nodes...\n', 'sin-medir', '-'),
])
def test_the_verdict_follows_errors_and_exit(tmp_path, log_text, observed,
                                             exit_status):
    row = _observed(tmp_path, log_text)
    assert (row['observed'], row['exit']) == (observed, exit_status)
