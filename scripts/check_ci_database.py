"""Rehúsa recrear una base que no sea explícitamente desechable para CI."""
import os
import sys

from django.conf import settings


def refusal(database, acknowledged, settings_module):
    """Valida el destino efectivo de Django, no sólo variables sin resolver."""
    if settings_module != 'config.settings.testing':
        return 'CI requiere config.settings.testing.'
    if database.get('ENGINE') != 'django.db.backends.postgresql':
        return 'CI requiere PostgreSQL real.'
    name = database.get('NAME')
    if not isinstance(name, str) or not name.startswith(
            ('kaupamex_ci_', 'orm_bootstrap_')):
        return 'CI requiere una base exclusiva kaupamex_ci_* (o del harness orm_bootstrap_*).'
    if database.get('TEST', {}).get('NAME') != name:
        return 'El destino TEST.NAME debe coincidir con la base desechable.'
    if not acknowledged or acknowledged != name:
        return 'CI_DATABASE_DISPOSABLE debe autorizar el nombre exacto de la base a recrear.'
    return None


def main():
    reason = refusal(settings.DATABASES['default'],
                     os.environ.get('CI_DATABASE_DISPOSABLE'),
                     os.environ.get('DJANGO_SETTINGS_MODULE'))
    if reason:
        print(f'BLOCKED: {reason}', file=sys.stderr)
        return 2
    print('PASS: destino PostgreSQL desechable autorizado; QA compartida excluida.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
