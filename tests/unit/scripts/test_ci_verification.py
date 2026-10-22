"""El contrato CI detiene etapas y rehúsa destinos compartidos."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from check_ci_database import refusal  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def disposable(name='kaupamex_ci_unit'):
    return {'ENGINE': 'django.db.backends.postgresql', 'NAME': name,
            'TEST': {'NAME': name}}


@pytest.mark.parametrize('name', ['kaupamex_core_qa', 'kaupamex_core', 'postgres', '', 'customer_prod'])
def test_shared_or_product_database_is_refused_even_with_acknowledgement(name):
    assert refusal(disposable(name), name, 'config.settings.testing')


def test_exact_disposable_postgresql_destination_is_accepted():
    assert refusal(disposable(), 'kaupamex_ci_unit', 'config.settings.testing') is None


@pytest.mark.parametrize('change', ['no_ack', 'wrong_ack', 'wrong_test_name', 'sqlite', 'production'])
def test_inconsistent_or_unacknowledged_destination_is_refused(change):
    db = disposable()
    ack = 'kaupamex_ci_unit'
    module = 'config.settings.testing'
    if change == 'no_ack':
        ack = None
    elif change == 'wrong_ack':
        ack = 'kaupamex_ci_other'
    elif change == 'wrong_test_name':
        db['TEST']['NAME'] = 'kaupamex_core_qa'
    elif change == 'sqlite':
        db['ENGINE'] = 'django.db.backends.sqlite3'
    else:
        module = 'config.settings.production'
    assert refusal(db, ack, module)


@pytest.mark.parametrize('failed_stage,expected', [
    ('sync', ['sync']),
    ('python', ['sync', 'python']),
    ('pdf', ['sync', 'python', 'pdf']),
    ('pytest', ['sync', 'python', 'pdf', 'pytest']),
    ('', ['sync', 'python', 'pdf', 'pytest']),
])
def test_make_preserves_failure_and_does_not_run_downstream_even_with_j(tmp_path, failed_stage, expected):
    executable = tmp_path / 'uv'
    executable.write_text(
        f'#!{sys.executable}\n'
        'import json,os,sys\n'
        'stage="pdf" if "fake-make" in sys.argv[0] else '
        '("sync" if sys.argv[1]=="sync" else sys.argv[3])\n'
        'with open(os.environ["STAGE_LOG"],"a") as f: f.write(json.dumps([stage,sys.argv[1:]])+"\\n")\n'
        'sys.exit(7 if stage==os.environ["FAILED_STAGE"] else 0)\n')
    executable.chmod(0o755)
    (tmp_path / 'fake-make').symlink_to(executable)
    log = tmp_path / 'stages.jsonl'
    env = dict(os.environ, PATH=f'{tmp_path}:{os.environ["PATH"]}',
               STAGE_LOG=str(log), FAILED_STAGE=failed_stage)
    done = subprocess.run(['make', '-j4', '-f', str(ROOT / 'Makefile'),
                           'ci-verify', f'MAKE={tmp_path / "fake-make"}'],
                          cwd=tmp_path, env=env, text=True, capture_output=True)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [r[0] for r in rows] == expected, done.stdout + done.stderr
    assert (done.returncode != 0) == bool(failed_stage)
    if failed_stage:
        assert 'Error 7' in done.stderr
    if 'pytest' in expected:
        args = rows[-1][1]
        assert '--maxfail=1' in args and '--create-db' in args and '--frozen' in args
        assert '--junitxml=test-results/pytest.xml' in args


@pytest.mark.parametrize('failure', ['assertion', 'fixture'])
def test_pytest_stops_after_failure_or_fixture_error_and_writes_junit(tmp_path, failure):
    marker = tmp_path / 'must-not-run'
    test = tmp_path / 'test_discriminator.py'
    first = ('def test_first(): assert False\n' if failure == 'assertion' else
             '@pytest.fixture\ndef broken(): raise RuntimeError("setup failed")\n'
             'def test_first(broken): pass\n')
    test.write_text('import pytest\nfrom pathlib import Path\n' + first +
                    f'def test_second(): Path({str(marker)!r}).touch()\n')
    xml = tmp_path / 'results.xml'
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    done = subprocess.run([sys.executable, '-m', 'pytest', '-c', '/dev/null',
                           '--maxfail=1', '-q', f'--junitxml={xml}', str(test)],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert done.returncode == 1, done.stdout + done.stderr
    assert not marker.exists()
    assert xml.exists()
