"""Observe scalar descriptor overhead without SQL or acceptance thresholds.

Reuse the existing 100000-read, three-sample protocol. Compare the current
adapter with its wrapped predecessor on the same loaded scalar value.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import timeit
from unittest.mock import patch

import django
from django.apps import apps

from verify_record_environment_candidate import (
    RecordEnvironmentSnapshot, SOURCES,
)

JOB = Path(__file__).resolve().parents[1]


def main():
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True
    ).strip()
    source = {
        module: subprocess.check_output(['git', 'show', revision + ':' + path])
        for module, path in SOURCES.items()
    }
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'record_env_no_connection',
            'USER': 'record_env_no_connection',
            'PASSWORD': secrets.token_urlsafe(30),
            'HOST': '127.0.0.1', 'PORT': '1',
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    with TemporaryDirectory(prefix='record-env-scalar-') as directory:
        paths = {}
        for module, value in source.items():
            paths[module] = Path(directory) / (module.split('.')[-1] + '.py')
            paths[module].write_bytes(value)
        finder = RecordEnvironmentSnapshot(paths)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in scalar measure'),
            ):
                django.setup()
                model = apps.get_model('base', 'SystemParameter')
                row = model(key='fixture.record.environment', value='x')
                descriptor = vars(model)['key']
                cls = type(descriptor)
                current = cls.__get__
                previous = current.__wrapped__
                assert row.key == 'fixture.record.environment'
                samples = timeit.repeat(
                    'row.key', globals={'row': row}, number=100_000, repeat=3
                )
                with patch.object(cls, '__get__', previous):
                    assert row.key == 'fixture.record.environment'
                    baseline = timeit.repeat(
                        'row.key', globals={'row': row},
                        number=100_000, repeat=3,
                    )
                assert cls.__get__ is current
                for module, path in paths.items():
                    assert Path(sys.modules[module].__file__) == path
        finally:
            sys.meta_path.remove(finder)
    result = {
        'source_revision': revision,
        'source_sha256': {
            module: hashlib.sha256(value).hexdigest()
            for module, value in source.items()
        },
        'iterations_per_sample': 100_000, 'samples': 3,
        'current_seconds': samples, 'unwrapped_seconds': baseline,
        'current_median_ns': statistics.median(samples) * 10_000,
        'unwrapped_median_ns': statistics.median(baseline) * 10_000,
        'sql': 'Prohibited; no connection opened',
        'scope': 'Loaded scalar on same unsaved SystemParameter '
                 'in one process; no application latency, throughput '
                 'or acceptance claim',
    }
    (JOB / 'outputs/record-env-scalar-cost.json').write_text(
        json.dumps(result, indent=2) + '\n'
    )
    print(json.dumps(result))


if __name__ == '__main__':
    main()
