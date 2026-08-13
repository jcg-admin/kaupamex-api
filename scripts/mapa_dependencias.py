#!/usr/bin/env python3
"""Mapa de dependencias del porte — tres grafos, cierre transitivo y orden topologico.

Por que tres y no uno
---------------------

Un analisis de ``depends`` es el obvio, y es el que **menos dano ha hecho**. Los
dos episodios caros de la sesion 2026-08-07 no los habria visto ninguno:

===  ==========================  ===============================================
 #   Grafo                       Episodio que produjo
===  ==========================  ===============================================
 1   ``depends`` del manifiesto  ``base_iban`` (#74) y los huecos de este script
 2   co-tenencia de modelo       H-API-364 — ``account_check_printing`` y
                                 ``account_payment`` comparten cuatro modelos y
                                 **ninguno depende del otro**
 3   mecanismo del stack         #192 (barcode), #136 (motor de formulas),
                                 #191 (motor de ``@api.depends``)
===  ==========================  ===============================================

El grafo 2 es el traicionero: un analisis de dependencias **es ciego a el por
construccion**, porque la co-tenencia no *es* una dependencia. El grafo 3 no
aparece en ningun manifiesto, porque para la referencia esas piezas existen.

Instrumento
-----------

``ast.literal_eval`` sobre el ``__manifest__.py`` — el mismo instrumento que la
fase de refutacion de H-DOCS-94 uso con exito frente a ``grep -oP``. Un manifest
que no evalua se reporta, no se omite en silencio.

Uso
---

    python3 scripts/mapa_dependencias.py               # reporte completo
    python3 scripts/mapa_dependencias.py --quiet       # solo el conteo de huecos
    python3 scripts/mapa_dependencias.py --strict      # exit 1 si hay huecos
    python3 scripts/mapa_dependencias.py --json        # para consumo por un guion
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict, deque

AQUI = os.path.dirname(os.path.abspath(__file__))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_dirs, addon_names, addon_path, py_files

# La raiz sale del alias de convencion-cita-referencia-odoo.rst, no de memoria.
# El arbol esta triplicado en el repo (artefacto de empaquetado, no diseno).
ODOO19C = '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0/addons'
ODOO_TOOLS = '/home/user/odoo-tools'

# SOSPECHA de absorción con otro nombre. **NO se descuenta del conteo de
# huecos** — la absorción es un VEREDICTO que se emite con evidencia, no una
# precondición de la medición.
#
# La versión anterior de este bloque se llamaba ABSORBIDOS y sí descontaba. El
# ejecutor midió que una de sus filas era falsa: `portal_rating` → `rating`.
# En la referencia son DOS addons distintos — `rating` declara los tres modelos
# (`rating.rating`, `rating.mixin`, `rating.parent.mixin`, 15 .py) y
# `portal_rating` es la capa de portal encima, con **0 `_name`** en sus 9 .py.
# Nuestro `rating` tampoco es el suyo: sus clases son `Review`,
# `ReviewHelpfulVote`, `RatingConfig` — implementación REST propia. La fila
# afirmaba una equivalencia que nadie había medido, y `website_sale` y
# `website_slides` exigen `portal_rating`, así que descontarlo escondía un
# hueco real.
#
# Sólo 2 de las 7 filas llegaban a disparar; las otras cinco eran filas muertas
# sobre addons fuera del cierre transitivo. Un mapa cuyo denominador depende de
# siete afirmaciones sin medir no es un mapa.
SOSPECHA_ABSORCION = {
    'auth_signup': 'authz_signup',
    'auth_totp': 'authz_totp',
    'auth_totp_mail': 'authz_totp_mail',
    'auth_ldap': 'authz_ldap',
    'auth_oauth': 'authz_oauth',
    'auth_passkey': 'authz_passkey',
}

RE_NAME = re.compile(r"^\s*_name\s*=\s*['\"]([\w.]+)['\"]", re.M)
RE_INHERIT_SIMPLE = re.compile(r"^\s*_inherit\s*=\s*['\"]([\w.]+)['\"]", re.M)
RE_INHERIT_LISTA = re.compile(r"^\s*_inherit\s*=\s*\[([^\]]*)\]", re.M)
RE_COMODEL = re.compile(r"comodel_name\s*=\s*['\"]([\w.]+)['\"]")
RE_ENV = re.compile(r"env\[['\"]([\w.]+)['\"]\]")
RE_STR = re.compile(r"['\"]([\w.]+)['\"]")
RE_CLASE = re.compile(r'^class\s+(\w+)\s*\(', re.M)
RE_DEF = re.compile(r'^\s*def \w+', re.M)


def commit_referencia():
    """El commit de odoo-tools sobre el que se midio — se anota, no se supone."""
    try:
        out = subprocess.run(['git', '-C', ODOO_TOOLS, 'log', '-1', '--format=%H'],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()[:8] or '<desconocido>'
    except Exception:
        return '<desconocido>'


def leer_manifest(ruta):
    """depends del manifiesto. Devuelve (lista, error) — el error no se traga."""
    try:
        texto = open(ruta, encoding='utf-8').read()
    except OSError as exc:
        return [], f'no legible: {exc}'
    # El manifest es un dict literal; literal_eval lo evalua sin ejecutarlo.
    try:
        datos = ast.literal_eval(texto.strip())
    except (ValueError, SyntaxError) as exc:
        return [], f'no evalua como literal: {exc}'
    if not isinstance(datos, dict):
        return [], f'no es dict, es {type(datos).__name__}'
    dep = datos.get('depends') or []
    if not isinstance(dep, list):
        return [], f"'depends' no es lista, es {type(dep).__name__}"
    return [d for d in dep if isinstance(d, str)], None


def addons_de(raiz):
    """Directorios con __manifest__.py bajo raiz, a profundidad 1."""
    if not os.path.isdir(raiz):
        return {}
    res = {}
    for nombre in sorted(os.listdir(raiz)):
        man = os.path.join(raiz, nombre, '__manifest__.py')
        if os.path.isfile(man):
            res[nombre] = man
    return res


def nuestros_addons():
    """Los addons de src/addons. NO exigimos __manifest__: el porte no siempre lo trae.

    **El directorio prueba PRESENCIA, no cobertura.** Un addon presente puede ser
    una cáscara — medido: ``crm`` tiene 5 ``def`` contra 414 de la referencia. Por
    eso el grafo 4 mide la masa de cada addon presente; sin él, los grafos 1-3
    tratan "el directorio existe" como "la dependencia está satisfecha", que es la
    premisa que H-API-369 invalidó.
    """
    return set(addon_names())


def cuenta_defs(raiz, addon):
    """Número de ``def`` de PRODUCCIÓN de un addon. Insumo del grafo 4.

    Se cuenta la MASA, no la identidad: un símbolo renombrado al inglés sigue
    contando. Es lo que distingue esta métrica de un cotejo por nombre, que
    reporta 0 % ante un rename y no puede separar 'ausente' de 'renombrado'.

    **``tests/`` queda fuera en AMBOS lados.** La suite de la referencia usa su
    propio framework y no se porta verbatim — los nuestros son pytest en
    ``tests/unit/<addon>/``, fuera del árbol del addon. Incluirla inflaba el
    denominador un **41.4 %** (6563 de 15849 ``def`` en los 34 addons de
    DEC-FW-04) con trabajo que nunca se hará en esa forma, y hundía el ratio de
    los addons cuya referencia está bien testeada. La cobertura de nuestra
    suite es un eje aparte; ésta mide código de producción contra código de
    producción.
    """
    total = 0
    base = os.path.join(raiz, addon)
    for dirpath, _, ficheros in os.walk(base):
        if '__pycache__' in dirpath:
            continue
        if os.sep + 'tests' in dirpath + os.sep:
            continue
        for f in ficheros:
            if not f.endswith('.py'):
                continue
            try:
                t = open(os.path.join(dirpath, f), encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            total += len(RE_DEF.findall(t))
    return total


def modelos_de_addon(raiz, addon):
    """(_name declarados, _inherit extendidos) de un addon. Grafo 2."""
    declara, extiende = set(), set()
    base = os.path.join(raiz, addon)
    for dirpath, _, ficheros in os.walk(base):
        for f in ficheros:
            if not f.endswith('.py'):
                continue
            try:
                t = open(os.path.join(dirpath, f), encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            declara.update(RE_NAME.findall(t))
            extiende.update(RE_INHERIT_SIMPLE.findall(t))
            for bloque in RE_INHERIT_LISTA.findall(t):
                extiende.update(RE_STR.findall(bloque))
    return declara, extiende


def modelos_referenciados(raiz, addon):
    """Modelos que el addon USA sin declarar: comodel_name y env['...']. Grafo 3."""
    usa = set()
    base = os.path.join(raiz, addon)
    for dirpath, _, ficheros in os.walk(base):
        for f in ficheros:
            if not f.endswith('.py'):
                continue
            try:
                t = open(os.path.join(dirpath, f), encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            usa.update(RE_COMODEL.findall(t))
            usa.update(RE_ENV.findall(t))
    return {m for m in usa if '.' in m}


def clases_nuestras():
    """Nombres de clase declarados en src/addons — nuestro árbol es Django.

    **Por qué no se buscan** ``_name``. La primera versión de este script midió
    el grafo 3 con ``_name = 'x.y'``, el idioma de la referencia. Nuestro árbol
    lo tiene **2 veces en 85 addons**, contra 1104 en odoo19c: los modelos son
    ``class AccountMove(models.Model)``. Resultado: 411 falsos "mecanismos
    ausentes", entre ellos ``account.move`` y ``account.journal``, que sí
    existen. Un instrumento que no puede registrar X reporta X como ausente, y
    su silencio se lee como evidencia — ``metrica-decide-la-conclusion.md``.
    """
    clases = set()
    for _raiz in addon_dirs():
      for dirpath, _, ficheros in os.walk(str(_raiz)):
        for f in ficheros:
            if not f.endswith('.py'):
                continue
            try:
                t = open(os.path.join(dirpath, f), encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            clases.update(RE_CLASE.findall(t))
    return clases


def nombres_de_clase(dotted):
    """``account.move`` → {AccountMove}; ``uom.uom`` → {UomUom, Uom}.

    Las dos formas, porque la deduplicada es real: la tarea #188 registró que
    ``uom.uom`` se llama ``Uom`` aquí, no ``UomUom``. Exigir sólo la forma
    completa habría marcado la familia entera como ausente.
    """
    partes = dotted.split('.')
    completa = ''.join(p.title().replace('_', '') for p in partes)
    formas = {completa}
    if len(partes) > 1 and partes[0] == partes[1]:
        formas.add(''.join(p.title().replace('_', '') for p in partes[1:]))
    return formas


def cierre_transitivo(semillas, depends):
    """Todo lo que las semillas exigen, directa o indirectamente."""
    visto, cola = set(), deque(semillas)
    while cola:
        a = cola.popleft()
        if a in visto:
            continue
        visto.add(a)
        for d in depends.get(a, []):
            if d not in visto:
                cola.append(d)
    return visto


def orden_topologico(nodos, depends):
    """Kahn sobre el subgrafo: qué puede ir antes que qué.

    Devuelve (capas, ciclo). Una capa N sólo depende de capas < N, así que sus
    addons son independientes entre sí y pueden portarse en paralelo.
    """
    dentro = {n: {d for d in depends.get(n, []) if d in nodos} for n in nodos}
    capas, pendiente = [], dict(dentro)
    while pendiente:
        libres = sorted(n for n, d in pendiente.items() if not d)
        if not libres:
            return capas, sorted(pendiente)          # ciclo: nadie queda libre
        capas.append(libres)
        for n in libres:
            del pendiente[n]
        for d in pendiente.values():
            d.difference_update(libres)
    return capas, []


def construir():
    ref = addons_de(ODOO19C)
    nuestros = nuestros_addons()
    depends, malos = {}, {}
    for nombre, man in ref.items():
        dep, err = leer_manifest(man)
        depends[nombre] = dep
        if err:
            malos[nombre] = err

    # Grafo 1 — depends
    portados_en_ref = sorted(nuestros & set(ref))
    cierre = cierre_transitivo(portados_en_ref, depends)
    huecos = sorted(a for a in cierre if a not in nuestros and a in ref)
    # Los huecos son TODOS. La sospecha se anota al lado, no se descuenta.
    huecos_reales = list(huecos)
    sospechosos = [h for h in huecos if h in SOSPECHA_ABSORCION]

    # Grafo 2 — co-tenencia sin dependencia, restringida a lo que ya tenemos
    por_modelo = defaultdict(set)
    for a in portados_en_ref:
        decl, ext = modelos_de_addon(ODOO19C, a)
        for m in decl | ext:
            por_modelo[m].add(a)
    cotenencia = []
    for modelo, duenos in sorted(por_modelo.items()):
        if len(duenos) < 2:
            continue
        for x in sorted(duenos):
            for y in sorted(duenos):
                if x >= y:
                    continue
                # ¿alguno alcanza al otro por depends?
                if y in cierre_transitivo([x], depends) or x in cierre_transitivo([y], depends):
                    continue
                cotenencia.append((modelo, x, y))

    # Grafo 3 — modelos que lo portado USA y que NUESTRO árbol no declara.
    # Se mide contra los NOMBRES DE CLASE, no contra _name: ver clases_nuestras().
    clases = clases_nuestras()
    usados = set()
    for a in portados_en_ref:
        usados |= modelos_referenciados(ODOO19C, a)
    mecanismos = sorted(m for m in usados if not (nombres_de_clase(m) & clases))

    # Grafo 4 — cobertura de lo que YA está presente. Los grafos 1-3 asumen que un
    # directorio presente satisface la dependencia; éste mide si eso es cierto.
    masa = []
    for a in portados_en_ref:
        _d = addon_path(a)
        mio = cuenta_defs(str(_d.parent), a) if _d else 0
        suyo = cuenta_defs(ODOO19C, a)
        masa.append({'addon': a, 'nuestros': mio, 'referencia': suyo,
                     'ratio': (mio / suyo) if suyo else None})
    masa.sort(key=lambda x: (x['ratio'] is None, x['ratio']))
    m_tot = sum(x['nuestros'] for x in masa)
    r_tot = sum(x['referencia'] for x in masa)

    capas, ciclo = orden_topologico(set(huecos_reales) |
                                    cierre_transitivo(huecos_reales, depends) & set(ref),
                                    depends)
    capas = [[a for a in c if a not in nuestros] for c in capas]
    capas = [c for c in capas if c]

    return {
        'commit_referencia': commit_referencia(),
        'ref_total': len(ref),
        'nuestros_total': len(nuestros),
        'portados_en_ref': portados_en_ref,
        'cierre_transitivo': len(cierre),
        'huecos': huecos_reales,
        'sospecha_absorcion': {h: SOSPECHA_ABSORCION[h] for h in sospechosos},
        'manifiestos_ilegibles': malos,
        'cotenencia': cotenencia,
        'mecanismos_ausentes': mecanismos,
        'modelos_usados': len(usados),
        'masa': masa,
        'masa_total': {'nuestros': m_tot, 'referencia': r_tot,
                       'ratio': (m_tot / r_tot) if r_tot else None},
        'orden_topologico': capas,
        'ciclo': ciclo,
    }


def imprimir(d):
    ref, nue = d['ref_total'], d['nuestros_total']
    print(f"Mapa de dependencias — odoo19c @ odoo-tools@{d['commit_referencia']}")
    print(f"  referencia: {ref} addons con manifest · nuestro árbol: {nue} addons")
    print(f"  con contraparte en la referencia: {len(d['portados_en_ref'])} de {nue}")
    print(f"  cierre transitivo de lo ya portado: {d['cierre_transitivo']} addons\n")

    if d['manifiestos_ilegibles']:
        print(f"MANIFIESTOS QUE NO EVALÚAN ({len(d['manifiestos_ilegibles'])}):")
        for a, e in sorted(d['manifiestos_ilegibles'].items()):
            print(f"  {a}: {e}")
        print()

    print(f"GRAFO 1 — depends: {len(d['huecos'])} huecos "
          f"(exigidos por lo portado, ausentes de src/addons)")
    print("  Métrica: 'depends' del __manifest__.py de odoo19c resuelto contra los")
    print("  directorios de src/addons/.")
    print("  Ciega a: (a) absorción con otro nombre, (b) recortes de capa de vista")
    print("  deliberados, (c) lo inverso — un addon que usa algo sin declararlo.")
    for h in d['huecos']:
        print(f"    - {h}")
    if d['sospecha_absorcion']:
        print(f"\n  SOSPECHA de absorción ({len(d['sospecha_absorcion'])}) — "
              f"NO descontados: la absorción es un veredicto con evidencia,")
        print("  no una precondición del conteo (ver el bloque SOSPECHA_ABSORCION).")
        for h, n in sorted(d['sospecha_absorcion'].items()):
            print(f"    - {h} ¿→ {n}?")

    print(f"\nGRAFO 2 — co-tenencia sin dependencia: {len(d['cotenencia'])} pares")
    print("  Un análisis de depends es CIEGO a esto por construcción: dos addons")
    print("  extienden el mismo modelo y ninguno alcanza al otro. Es H-API-364.")
    for m, x, y in d['cotenencia'][:40]:
        print(f"    {m:38s} {x} ⟂ {y}")
    if len(d['cotenencia']) > 40:
        print(f"    … {len(d['cotenencia']) - 40} pares más (usar --json)")

    print(f"\nGRAFO 3 — mecanismos ausentes: {len(d['mecanismos_ausentes'])} de "
          f"{d['modelos_usados']} modelos usados")
    print("  Modelos que lo portado USA (comodel_name / env['...']) y para los que")
    print("  NUESTRO árbol no declara clase. No aparecen en ningún manifiesto.")
    print("  Métrica: nombre punteado → CamelCase (dos formas, por el caso uom.uom→Uom)")
    print("  buscado como 'class X(' en src/addons.")
    print("  Ciega a: una clase renombrada fuera de esas dos formas; y al caso inverso")
    print("  — una clase que existe pero no implementa el mecanismo (H-API-350).")
    for m in d['mecanismos_ausentes'][:40]:
        print(f"    - {m}")
    if len(d['mecanismos_ausentes']) > 40:
        print(f"    … {len(d['mecanismos_ausentes']) - 40} más (usar --json)")

    mt = d['masa_total']
    print(f"\nGRAFO 4 — cobertura de lo presente: {mt['nuestros']} def nuestros contra "
          f"{mt['referencia']} de la referencia = {mt['ratio']:.1%}")
    print("  Los grafos 1-3 tratan 'el directorio existe' como 'la dependencia está")
    print("  satisfecha'. Este grafo mide si eso es cierto. Es H-API-369.")
    print("  Métrica: conteo de 'def' por árbol de addon — MASA, no identidad, así que")
    print("  un símbolo renombrado al inglés sigue contando.")
    print("  Ciega a: (a) una descomposición distinta (menos métodos más grandes),")
    print("  (b) los addons de forma propia deliberada (rating→Review, catalogue),")
    print("  (c) un método presente pero HUECO — el defecto de H-API-350.")
    cascaras = [x for x in d['masa'] if x['ratio'] is not None and x['ratio'] < 0.15]
    print(f"\n  CÁSCARAS (<15% de la masa de su contraparte): {len(cascaras)} de "
          f"{len(d['masa'])} addons presentes")
    for x in cascaras[:20]:
        print(f"    {x['addon']:<28} {x['nuestros']:>4} / {x['referencia']:>5} = "
              f"{x['ratio']:.3f}")
    if len(cascaras) > 20:
        print(f"    … {len(cascaras) - 20} más (usar --json)")

    print(f"\nORDEN TOPOLÓGICO del pendiente — {len(d['orden_topologico'])} capas")
    print("  Una capa sólo depende de capas anteriores: sus addons son")
    print("  independientes entre sí y admiten fan-out.")
    for i, capa in enumerate(d['orden_topologico']):
        print(f"    capa {i}: {' '.join(capa)}")
    if d['ciclo']:
        print(f"  CICLO sin resolver: {' '.join(d['ciclo'])}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quiet', action='store_true', help='sólo el conteo de huecos')
    p.add_argument('--strict', action='store_true', help='exit 1 si hay huecos')
    p.add_argument('--json', action='store_true', help='salida JSON')
    args = p.parse_args()

    if not os.path.isdir(ODOO19C):
        print(f'ERROR: la referencia no está montada en {ODOO19C}', file=sys.stderr)
        print('El mapa NO se emite sin árbol — un cero aquí no sería un cero real.',
              file=sys.stderr)
        return 2

    d = construir()
    if args.json:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    elif args.quiet:
        print(f"{len(d['huecos'])} huecos (alcance medido: {d['cierre_transitivo']} "
              f"addons del cierre transitivo, sobre {d['ref_total']} de odoo19c)")
    else:
        imprimir(d)
    return 1 if (args.strict and d['huecos']) else 0


if __name__ == '__main__':
    sys.exit(main())
