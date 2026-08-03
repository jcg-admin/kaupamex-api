#!/usr/bin/env python3
"""Gate — un addon nuestro no puede llamarse como ninguno de la referencia.

Origen: H-API-119 (``users`` era un nombre que la referencia no tiene) y su
reincidencia, H-API-256 (``platform``, inventado en la misma sesión que citaba
H-API-119). Las dos veces el defecto fue idéntico: se verificó que el *dominio*
existía y no *dónde lo pone la referencia*, y el nombre se inventó.

Por qué es un script y no una regla en prosa: H-API-119 estaba escrito,
fechado y era greppeable cuando se creó ``platform``. El precedente del
proyecto lo dice sin rodeos (``gitlink-bump-gate.md``): *"La lección escrita no
previene la reincidencia. Solo un gate ejecutable integrado en el flujo lo
hace."*

Qué hace: compara ``src/addons/*`` contra la unión de los cuatro árboles con
alias de ``odoo-tools``. Un nombre ausente que **no** esté en el baseline es un
nombre nuevo inventado → exit 1. El baseline congela la deuda heredada para que
el gate bloquee lo próximo sin marcar rojo por lo de antes.

    python3 scripts/check_addon_names.py           # reporte
    python3 scripts/check_addon_names.py --quiet   # sólo el conteo
    python3 scripts/check_addon_names.py --strict  # exit 1 con deuda heredada

Sin ``odoo-tools`` montado el gate no puede medir: sale 0 con aviso, en vez de
inventar un veredicto (``react-verification-gate.md`` — sin Observation el
estado es DESCONOCIDO, no "éxito").
"""
import os
import sys

# Raíces canónicas — ``convencion-cita-referencia-odoo.rst``. 19c aporta dos
# porque el núcleo (``base``, ``web``…) vive en ``odoo/addons/``, no en
# ``addons/``. Los empaquetados sin alias de Enterprise 18 quedan fuera a
# propósito: son la misma población que ``odoo18e:`` y contarlos dos veces
# infla el universo (H-API-76).
REFERENCE_ROOTS = {
    'odoo19c': [
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0/addons',
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0/odoo/addons',
    ],
    'odoo19e': [
        '/home/user/odoo-tools/19.x/odoo19-enterprise-main/'
        'odoo19-enterprise-main/odoo19-enterprise-main',
    ],
    'odoo18c': ['/home/user/odoo-tools/18.x/odoo-18/addons'],
    'odoo18e': ['/home/user/odoo-tools/18.x/odoo.enterprise'],
}

# Renames forzados por el entorno, no elegidos. El nombre de la referencia se
# recupera aplicando el mapeo antes de juzgar la ausencia; sin esto el gate
# marcaría como "inventados" siete addons que son puertos fieles.
#
# ``auth`` -> ``authz``: ``django.contrib.auth`` ya ocupa el label ``auth``
# (``config/settings/base.py:30``) y dos apps de Django no pueden compartir
# label. La colisión es del framework destino, no una divergencia con la
# referencia.
FORCED_PREFIX_RENAMES = [('authz', 'auth')]


def reference_name_of(ours):
    """Nombre que la referencia usaría para un addon nuestro."""
    for mine, theirs in FORCED_PREFIX_RENAMES:
        if ours == mine:
            return theirs
        if ours.startswith(mine + '_'):
            return theirs + ours[len(mine):]
    return ours


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS_DIR = os.path.join(REPO_ROOT, 'src', 'addons')
BASELINE = os.path.join(REPO_ROOT, 'scripts', 'addon_names_baseline.txt')


def reference_names():
    """Nombres de addon de la referencia: directorios con ``__manifest__.py``.

    Métrica: directorio a profundidad 1 bajo una raíz con alias que contiene un
    ``__manifest__.py``.
    Ciega a: manifiestos anidados más abajo, y a addons que la referencia
    declara con otro nombre para el mismo dominio — el gate juzga el nombre, no
    la cobertura funcional.
    """
    names, missing = {}, []
    for alias, roots in REFERENCE_ROOTS.items():
        for root in roots:
            if not os.path.isdir(root):
                missing.append(f'{alias}: {root}')
                continue
            for entry in os.listdir(root):
                manifest = os.path.join(root, entry, '__manifest__.py')
                if os.path.isfile(manifest):
                    names.setdefault(entry, set()).add(alias)
    return names, missing


def load_baseline():
    """Deuda congelada: ``<nombre>  # <por qué sigue viva>``."""
    if not os.path.isfile(BASELINE):
        return {}
    entries = {}
    with open(BASELINE, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, _, reason = line.partition('#')
            entries[name.strip()] = reason.strip()
    return entries


def our_names():
    if not os.path.isdir(ADDONS_DIR):
        return []
    return sorted(
        d for d in os.listdir(ADDONS_DIR)
        if os.path.isdir(os.path.join(ADDONS_DIR, d)) and not d.startswith('__')
    )


def main(argv):
    quiet = '--quiet' in argv
    strict = '--strict' in argv

    reference, missing = reference_names()
    if not reference:
        print('check_addon_names: odoo-tools no está montado '
              f'({"; ".join(missing) or "sin raíces"}); '
              'el gate no puede medir — estado DESCONOCIDO, no OK.')
        return 0

    baseline = load_baseline()
    absent = [n for n in our_names() if reference_name_of(n) not in reference]
    nuevos = [n for n in absent if n not in baseline]
    heredados = [n for n in absent if n in baseline]

    if quiet:
        print(f'nuevos={len(nuevos)} heredados={len(heredados)}')
        return 1 if nuevos or (strict and heredados) else 0

    print(f'check_addon_names — referencia: {len(reference)} nombres '
          f'(unión de {len(REFERENCE_ROOTS)} árboles con alias)')
    renombrados = [n for n in our_names()
                   if reference_name_of(n) != n and reference_name_of(n) in reference]
    if renombrados:
        print(f'Renames forzados que SÍ resuelven ({len(renombrados)}): '
              + ', '.join(f'{n}→{reference_name_of(n)}' for n in renombrados))

    if nuevos:
        print(f'\nFAIL — {len(nuevos)} nombre(s) de addon que la referencia '
              'no tiene y que no están en el baseline:')
        for name in nuevos:
            print(f'  - src/addons/{name}')
        print('\nLa operación correcta no es inventar el nombre: es disolver el '
              'dominio\nen el addon donde la referencia lo declara (H-API-119). '
              'Si de verdad no\nhay contraparte, la excepción se decide y se '
              'documenta ANTES, y se anota\nen scripts/addon_names_baseline.txt '
              'con su hallazgo.')

    if heredados:
        print(f'\nDeuda heredada ({len(heredados)}), congelada en el baseline:')
        for name in heredados:
            print(f'  - {name}  ({baseline[name] or "sin motivo anotado"})')

    if not absent:
        print('\nOK — ningún addon con nombre ajeno a la referencia.')
    elif not nuevos:
        print('\nOK — sin nombres nuevos inventados.')

    return 1 if nuevos or (strict and heredados) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
