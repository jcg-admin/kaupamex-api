#!/usr/bin/env python3
"""Gate: cada opción registrada en ``config.settings.options`` debe estar
documentada en ``src/.env.example``, y ningún ``.py`` de settings debe leer
``decouple.config`` directo — el registro es el único punto de acceso
(patrón ``conf[]``, ver docs: analisis-flujo-arranque-odoo-conf.rst §5).

Uso:
    python3 scripts/check_options_registry.py

Exit 0 si está sincronizado, 1 si hay opciones sin documentar o llamadas a
``config(`` fuera del registro.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_DIR = ROOT / 'src' / 'config' / 'settings'
ENV_EXAMPLE = ROOT / 'src' / '.env.example'
OPTIONS_MODULE = SETTINGS_DIR / 'options.py'


def registered_env_names():
    text = OPTIONS_MODULE.read_text(encoding='utf-8')
    return set(re.findall(r"Option\(\s*'([A-Z0-9_]+)'", text))


def documented_env_names():
    text = ENV_EXAMPLE.read_text(encoding='utf-8')
    return set(re.findall(r'^([A-Z0-9_]+)=', text, re.MULTILINE))


def stray_config_calls():
    """Archivos de settings fuera de options.py que aún llaman decouple.config()."""
    offenders = []
    for f in SETTINGS_DIR.glob('*.py'):
        if f.name in ('options.py', '__init__.py'):
            continue
        text = f.read_text(encoding='utf-8')
        if re.search(r'\bconfig\(', text):
            offenders.append(f.relative_to(ROOT))
    return offenders


def main():
    errors = []

    registered = registered_env_names()
    documented = documented_env_names()
    missing = sorted(registered - documented)
    if missing:
        errors.append(
            f"{len(missing)} opción(es) registradas en options.py sin documentar "
            f"en src/.env.example: {', '.join(missing)}"
        )

    offenders = stray_config_calls()
    if offenders:
        errors.append(
            "Llamadas a decouple.config() fuera de options.py (deben pasar por "
            f"el registro): {', '.join(str(o) for o in offenders)}"
        )

    if errors:
        print("check_options_registry: FALLÓ")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"OK: registro sincronizado ({len(registered)} opciones, "
        f"todas documentadas en .env.example; sin config() fuera de options.py)"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
