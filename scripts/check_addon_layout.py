#!/usr/bin/env python3
"""Gate — las capas estructurales de un addon son paquetes, no archivos planos.

Origen: **H-API-238**, con la directiva del ejecutor *"el usar archivos planos
está mal, es una corrección que se tiene que hacer; si ya tienes la referencia
tienes que copiar/adaptar lo que se tiene en odoo-tools"*. Ese hallazgo dejó el
mapa resuelto y una lista de deuda restante de 15 addons.

Y aun así reincidió: al disolver ``company`` se movieron sus ocho planos a
``platform`` **conservándolos planos** — tomando un ítem nombrado de esa lista y
cambiándole el nombre. Después se escribió H-API-255 como si fuera hallazgo
nuevo, reabriendo una pregunta (``views/`` vs ``controllers/``) que H-API-238 ya
había cerrado. Por eso esto es un script: el hallazgo existía, era greppeable, y
no detuvo nada.

**No es "todo en carpeta".** Medido en ``odoo19c: addons/`` (629 addons), la
referencia sí admite planos en la raíz — ``const.py`` 31, ``utils.py`` 12,
``tools.py`` 4, ``exceptions.py`` 2, ``controllers.py`` 2. Lo que es paquete son
las **capas estructurales**. Este gate juzga sólo esa lista cerrada.

    python3 scripts/check_addon_layout.py           # reporte
    python3 scripts/check_addon_layout.py --quiet   # sólo el conteo
    python3 scripts/check_addon_layout.py --strict  # exit 1 con deuda heredada
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_dirs
BASELINE = os.path.join(REPO_ROOT, 'scripts', 'addon_layout_baseline.txt')

# Mapa de H-API-238, verbatim. La capa de vista de DRF va a ``controllers/``
# porque ése es el nombre de la referencia — no ``views/``, que en Odoo son XML.
FLAT_TO_PACKAGE = {
    'views.py':            'controllers/',
    'serializers.py':      'controllers/',
    'urls.py':             'controllers/',
    'schema.py':           'controllers/',
    'admin_views.py':      'controllers/',
    'admin_serializers.py': 'controllers/',
    'admin_urls.py':       'controllers/',
    'webhook_urls.py':     'controllers/',
    'data.py':             'data/',
    'authz_catalog.py':    'security/',
    'backends.py':         'models/',
    'signals.py':          'models/',
    'models.py':           'models/',
}

# Nombre de la capa de vista ya decidido (H-API-238). Un ``views/`` paquete es
# drift contra esa decisión, no una alternativa: se reporta aparte para que no
# se confunda con "ya está bien porque es carpeta".
DISPUTED_PACKAGES = {'views': 'controllers/', 'serializers': 'controllers/'}


def load_baseline():
    if not os.path.isfile(BASELINE):
        return set()
    out = set()
    with open(BASELINE, encoding='utf-8') as fh:
        for line in fh:
            line = line.split('#', 1)[0].strip()
            if line:
                out.add(line)
    return out


def scan():
    """Devuelve (planos, disputados) como listas de ``addon/archivo``.

    Métrica: nombre de archivo exacto en la raíz del addon, contra la lista
    cerrada de FLAT_TO_PACKAGE.
    Ciega a: capas estructurales con otro nombre que el mapa no enumera, y a
    addons que simplemente no tienen esa capa — no distingue "plano" de
    "ausente", así que el conteo acota por abajo, no mide el total.
    """
    planos, disputados = [], []
    if not addon_dirs():
        return planos, disputados
    for _p in addon_dirs():
        addon, root = _p.name, str(_p)
        if not os.path.isdir(root) or addon.startswith('__'):
            continue
        for flat in FLAT_TO_PACKAGE:
            if os.path.isfile(os.path.join(root, flat)):
                planos.append(f'{addon}/{flat}')
        for pkg in DISPUTED_PACKAGES:
            if os.path.isdir(os.path.join(root, pkg)):
                disputados.append(f'{addon}/{pkg}/')
    return planos, disputados


def main(argv):
    quiet = '--quiet' in argv
    strict = '--strict' in argv

    planos, disputados = scan()
    baseline = load_baseline()
    nuevos = [p for p in planos if p not in baseline]
    heredados = [p for p in planos if p in baseline]

    if quiet:
        print(f'nuevos={len(nuevos)} heredados={len(heredados)} '
              f'disputados={len(disputados)}')
        return 1 if nuevos or (strict and (heredados or disputados)) else 0

    if nuevos:
        print(f'FAIL — {len(nuevos)} capa(s) estructural(es) plana(s) fuera del '
              'baseline:')
        for p in nuevos:
            flat = p.split('/', 1)[1]
            print(f'  - src/addons/{p}   →   {FLAT_TO_PACKAGE[flat]}')
        print('\nEl mapa lo fijó H-API-238; no hay que re-decidirlo. Mover un '
              'plano de un\naddon a otro NO lo saca de la deuda: lo renombra.')

    if disputados:
        print(f'\nDrift de nombre de capa ({len(disputados)}): la capa de vista '
              'se llama\n``controllers/`` (H-API-238). Estos son paquetes, pero '
              'con el nombre equivocado:')
        for d in disputados:
            print(f'  - src/addons/{d}   →   '
                  f'{DISPUTED_PACKAGES[d.split("/")[1]]}')

    if heredados:
        print(f'\nDeuda heredada de H-API-238 ({len(heredados)}), congelada en '
              'el baseline.')

    if not planos and not disputados:
        print('OK — ninguna capa estructural plana.')
    elif not nuevos:
        print('\nOK — sin capas planas nuevas.')

    return 1 if nuevos or (strict and (heredados or disputados)) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
