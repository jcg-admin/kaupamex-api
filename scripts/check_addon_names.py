#!/usr/bin/env python3
"""Gate — todo addon declara su procedencia; ninguno nace sin decisión.

Origen: H-API-119 (``users`` era un nombre que la referencia no tiene) y su
reincidencia, H-API-256 (``platform``, inventado en la misma sesión que citaba
H-API-119). Las dos veces el defecto fue idéntico: se verificó que el *dominio*
existía y no *dónde lo pone la referencia*, y el nombre se inventó.

Por qué es un script y no una regla en prosa: H-API-119 estaba escrito,
fechado y era greppeable cuando se creó ``platform``. El precedente del
proyecto lo dice sin rodeos (``gitlink-bump-gate.md``): *"La lección escrita no
previene la reincidencia. Solo un gate ejecutable integrado en el flujo lo
hace."*

**El eje NO es "existe en la referencia".** Esa fue la primera versión de este
script y estaba mal: el proyecto va a tener addons propios, y eso es legítimo.
Lo que no es legítimo es crear uno **sin decisión documentada**. Medirlo por
ausencia de nombre castiga lo correcto (un addon propio decidido) y, peor, da
por bueno lo incorrecto en cuanto alguien añade una línea al archivo.

Lo destapó el ejecutor con dos ejemplos: ``auto_backup`` —que este script marcó
"sin contraparte, pendiente de decisión" cuando ``analisis-familia-backups.rst``
lo documenta como **home-map correcto** contra ``app_auto_backup``, un árbol
community fuera de los cuatro alias— y la pregunta de fondo: *"¿qué pasa cuando
nosotros queremos nuestros propios addons?"*.

Qué hace ahora: cada addon debe resolver por **una** de tres vías.

1. **Puerto por nombre** — el nombre existe en la unión de los cuatro árboles
   con alias, aplicando los renames que el framework destino fuerza. Resuelve
   solo, sin entrada en el registro.
2. **Procedencia declarada** — entrada en ``scripts/addon_provenance.txt`` con
   clase (``puerto`` | ``propio`` | ``drift`` | ``pendiente``) y cita a un
   documento que debe existir. Para las clases que **aprueban** (``puerto`` y
   ``propio``) la cita debe ser además un **análisis**: de familia
   (``analisis-familia-*.rst``) **o del addon** (``analisis-*<addon>*.rst``).
   No vale cualquier archivo — sin ese requisito bastaba citar un README para
   pasar. Es el artefacto que la iniciativa
   ``adaptar-familias-odoo-monolito-modular`` exige antes de decidir el hogar
   de nada, y existe en las dos formas.
   El gate verifica la existencia y el **tipo** del archivo citado, no su
   contenido: así el veredicto no depende de que quien escribió la línea
   resumiera bien.
3. **Nada de lo anterior** → exit 1.

Dos clases marcan deuda y **fallan con** ``--strict``, pasando en modo normal:
``drift`` (el análisis ya dictaminó que el nombre está mal y hay tarea abierta)
y ``pendiente`` (el documento existe, falta leerlo y clasificar).
Es la graduación de ``artefactos-minimos-iniciativa.md``: se cablea a CI cuando
el conteo llegue a 0.

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
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_names
REGISTRY = os.path.join(REPO_ROOT, 'scripts', 'addon_provenance.txt')
DOCS_ROOT = os.path.join(os.path.dirname(REPO_ROOT), 'kaupamex-docs')


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


def load_registry():
    """``<addon> | <clase> | <cita>`` — clase en puerto|propio|pendiente."""
    if not os.path.isfile(REGISTRY):
        return {}
    entries = {}
    with open(REGISTRY, encoding='utf-8') as fh:
        for line in fh:
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) != 3:
                continue
            name, clase, cita = parts
            entries[name] = (clase, cita)
    return entries


ANALYSIS_PREFIX = 'analisis-'
FAMILY_ANALYSIS_PREFIX = 'analisis-familia-'


def citation_exists(cita):
    """La cita apunta a un archivo real (relativo a docs o al repo)."""
    if not cita:
        return False
    return any(os.path.exists(os.path.join(base, cita))
               for base in (DOCS_ROOT, REPO_ROOT))


def is_valid_analysis(cita, addon):
    """El documento citado es un análisis **de familia o del addon**.

    Las dos formas valen, porque las dos existen en el repo: el hogar se decide
    a veces para una familia entera (``analisis-familia-sale.rst``, que cubre
    ``sale``, ``sale_stock``, ``sale_crm``…) y a veces para un addon suelto
    (``analisis-users-no-es-un-addon-en-la-referencia.rst``). Exigir sólo la
    primera daría 10/65 por nombre exacto — métrica equivocada; exigir sólo la
    segunda obligaría a duplicar el análisis de familia por cada miembro.

    Métrica: basename que empieza con ``analisis-`` y que, o bien es
    ``analisis-familia-*``, o bien menciona el nombre del addon (normalizando
    ``_`` y ``-``).
    Ciega a: un análisis guardado con otro prefijo, y al *contenido* — que el
    documento cubra de verdad a este addon no lo juzga el gate. Lo que impide
    es aprobar citando un README o un progreso.
    """
    base = os.path.basename(cita)
    if not base.startswith(ANALYSIS_PREFIX):
        return False
    if base.startswith(FAMILY_ANALYSIS_PREFIX):
        return True
    norm = lambda t: t.replace('_', '-')
    return norm(addon) in norm(base)


def our_names():
    if not addon_names():
        return []
    return addon_names()


def main(argv):
    quiet = '--quiet' in argv
    strict = '--strict' in argv

    reference, missing = reference_names()
    if not reference:
        print('check_addon_names: odoo-tools no está montado '
              f'({"; ".join(missing) or "sin raíces"}); '
              'el gate no puede medir — estado DESCONOCIDO, no OK.')
        return 0

    registry = load_registry()
    absent = [n for n in our_names() if reference_name_of(n) not in reference]

    sin_declarar, cita_rota, sin_familia = [], [], []
    declarados, pendientes = [], []
    for name in absent:
        if name not in registry:
            sin_declarar.append(name)
            continue
        clase, cita = registry[name]
        if not citation_exists(cita):
            cita_rota.append((name, cita))
        elif clase in ('pendiente', 'drift'):
            pendientes.append((name, clase, cita))
        elif not is_valid_analysis(cita, name):
            sin_familia.append((name, clase, cita))
        else:
            declarados.append((name, clase, cita))

    fail = bool(sin_declarar or cita_rota or sin_familia)

    if quiet:
        print(f'sin_declarar={len(sin_declarar)} cita_rota={len(cita_rota)} '
              f'sin_familia={len(sin_familia)} declarados={len(declarados)} '
              f'pendientes={len(pendientes)}')
        return 1 if fail or (strict and pendientes) else 0

    print(f'check_addon_names — referencia: {len(reference)} nombres '
          f'(unión de {len(REFERENCE_ROOTS)} árboles con alias)')
    renombrados = [n for n in our_names()
                   if reference_name_of(n) != n and reference_name_of(n) in reference]
    if renombrados:
        print(f'Renames forzados que SÍ resuelven ({len(renombrados)}): '
              + ', '.join(f'{n}→{reference_name_of(n)}' for n in renombrados))

    if sin_declarar:
        print(f'\nFAIL — {len(sin_declarar)} addon(s) sin procedencia declarada:')
        for name in sin_declarar:
            print(f'  - src/addons/{name}')
        print('\nNo se pide que el nombre exista en la referencia: se pide '
              'saber POR QUÉ\nes propio. Antes de crearlo, medir dónde declara '
              'la referencia el dominio\n(H-API-119). Si de verdad no lo cubre, '
              'la decisión se documenta y se cita\nen scripts/addon_provenance.txt.')

    if cita_rota:
        print(f'\nFAIL — {len(cita_rota)} cita(s) que no apuntan a un archivo real:')
        for name, cita in cita_rota:
            print(f'  - {name}  →  {cita}')

    if sin_familia:
        print(f'\nFAIL — {len(sin_familia)} addon(s) que aprueban citando algo '
              'que NO es un\nanálisis (ni de familia ni del addon):')
        for name, clase, cita in sin_familia:
            print(f'  - {name:22} [{clase}]  {cita}')
        print('\nEl hogar se decide en un analisis-familia-*.rst o en un '
              'analisis-*<addon>*.rst,\nno en un README ni en un progreso. Si '
              'ese análisis no existe, la clase\nhonesta es ``pendiente`` — no '
              'aprobar citando otra cosa.')

    if declarados:
        print(f'\nProcedencia declarada y verificada ({len(declarados)}):')
        for name, clase, cita in declarados:
            print(f'  - {name:22} [{clase}]  {cita}')

    if pendientes:
        print(f'\nDeuda declarada ({len(pendientes)}) — pasa en modo normal, '
              'falla con --strict:')
        for name, clase, cita in pendientes:
            print(f'  - {name:22} [{clase}]  {cita}')

    if not absent:
        print('\nOK — todos los addons resuelven por nombre contra la referencia.')
    elif not fail:
        print('\nOK — todo addon propio tiene procedencia declarada.')

    return 1 if fail or (strict and pendientes) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
