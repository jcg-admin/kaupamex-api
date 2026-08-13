#!/usr/bin/env python3
"""Gate de dirección de dependencias entre addons (T-036).

**Qué vigila y por qué no vigila el número de ciclos.**

El plan pedía un gate de aciclicidad con umbral sobre el componente
fuertemente conexo. La medición lo desmintió (H-API-55, H-API-56): el
componente no lo sostiene ningún addon en particular, y una arista escrita en
la dirección **correcta** puede hacerlo *crecer* — T-035 lo hizo subir de 21 a
22 al añadir ``payment -> mail``, que es exactamente lo que la referencia
prescribe. Un gate de "el número no crece" habría bloqueado un cambio correcto.

Lo que sí es estable es la **dirección**. En la referencia Odoo la dependencia
apunta siempre hacia abajo: ``base`` 0, ``mail`` 4, ``product`` 5, ``payment``
7, ``stock``/``website`` 8, ``sale`` 10, ``delivery``/``sale_stock`` 11,
``website_sale`` 12. Ningún addon de infraestructura declara ``depends`` sobre
uno de negocio. Este gate prohíbe esa inversión.

**Ratchet:** las inversiones que ya existen están en ``KNOWN_INVERSIONS``
con su motivo. El gate falla si aparece **una nueva**. Al cerrar una, se borra
de la lista — la lista sólo puede encoger.

Uso:
    python3 scripts/check_addon_cycles.py            # reporte + gate
    python3 scripts/check_addon_cycles.py --report   # sólo reporte, exit 0
"""
import ast
import os
import sys
from collections import defaultdict

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_dirs

# {nombre: ruta} sobre las DOS raices — un addon vive en una u otra.
DIRS = {p.name: str(p) for p in addon_dirs()}

# Addons de infraestructura: identidad, acceso, correo y catálogo base. En la
# referencia viven entre profundidad 0 y 5, por debajo de todo el negocio.
FUNDACIONALES = frozenset({
    'base', 'users', 'authz', 'authz_reauth', 'auth_totp', 'company',
    'mail', 'catalogue', 'chartsize', 'questions', 'website',
    # Nivel 0 del árbol de referencia, portados por `alinear-arbol-addons`:
    # `uom` sólo importa `base`; `bus` importa `base` y `authz` (su endpoint
    # va gateado por capacidad). Ninguno apunta a negocio.
    'uom', 'bus',
})

# Addons de negocio: el O2C y sus satélites. Referencia: 7 a 12.
NEGOCIO = frozenset({
    'sale', 'sale_loyalty', 'sale_stock', 'orders', 'cart', 'payment',
    'payments', 'payment_mercado_pago', 'payment_paypal', 'stock',
    'inventory', 'delivery', 'loyalty', 'helpdesk', 'returns', 'reviews',
    'wishlist', 'referral', 'reports', 'settings_app',
})

# Inversiones fundacional -> negocio ya presentes. El gate falla ante una nueva.
# Formato: (origen, destino): motivo / tarea que la cierra.
KNOWN_INVERSIONS = {
    ('users', 'sale'): 'admin_views compone dinero de la venta — H-API-40',
    ('users', 'cart'): 'views enlaza el carrito del usuario',
    ('catalogue', 'sale'): 'views consulta líneas de venta del producto',
    ('catalogue', 'delivery'): 'seed de catálogo siembra zonas de envío',
    ('chartsize', 'sale'): 'views consulta líneas de venta',
    ('chartsize', 'delivery'): 'views consulta envío',
    ('catalogue', 'payment'): 'seed de catálogo siembra PaymentGateway — api@df99c5c',
}


def build_graph():
    """Devuelve (addons, aristas, sitios) leyendo los imports con AST."""
    addons = sorted(DIRS)
    index = set(addons)
    edges = defaultdict(set)
    sites = defaultdict(list)
    for addon in addons:
        for folder, _, files in os.walk(DIRS[addon]):
            if 'migrations' in folder.split(os.sep):
                continue
            for filename in files:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(folder, filename)
                try:
                    tree = ast.parse(open(path, encoding='utf-8').read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        modules = [node.module]
                    elif isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    else:
                        continue
                    for module in modules:
                        if not module.startswith('addons.'):
                            continue
                        parts = module.split('.')
                        if len(parts) > 1 and parts[1] in index and parts[1] != addon:
                            edges[addon].add(parts[1])
                            sites[(addon, parts[1])].append(
                                f'{os.path.relpath(path, os.getcwd())}:{node.lineno}')
    return addons, edges, sites


def componentes_ciclicos(addons, edges):
    """Tarjan iterativo; devuelve los componentes de tamaño > 1."""
    index, bajo, en_pila, pila, contador, output = {}, {}, {}, [], [0], []

    def recorrer(inicio):
        trabajo = [(inicio, 0)]
        while trabajo:
            node, i = trabajo[-1]
            if i == 0:
                index[node] = bajo[node] = contador[0]
                contador[0] += 1
                pila.append(node)
                en_pila[node] = True
            descendio = False
            vecinos = sorted(edges[node])
            for j in range(i, len(vecinos)):
                vecino = vecinos[j]
                if vecino not in index:
                    trabajo[-1] = (node, j + 1)
                    trabajo.append((vecino, 0))
                    descendio = True
                    break
                if en_pila.get(vecino):
                    bajo[node] = min(bajo[node], index[vecino])
            if descendio:
                continue
            if bajo[node] == index[node]:
                component = []
                while True:
                    w = pila.pop()
                    en_pila[w] = False
                    component.append(w)
                    if w == node:
                        break
                output.append(component)
            trabajo.pop()
            if trabajo:
                bajo[trabajo[-1][0]] = min(bajo[trabajo[-1][0]], bajo[node])

    for addon in addons:
        if addon not in index:
            recorrer(addon)
    return [c for c in output if len(c) > 1]


def main():
    report_only = '--report' in sys.argv
    addons, edges, sites = build_graph()

    actuales = {
        (source, target)
        for source in FUNDACIONALES & set(addons)
        for target in edges[source] & NEGOCIO
    }
    nuevas = actuales - set(KNOWN_INVERSIONS)
    cerradas = set(KNOWN_INVERSIONS) - actuales

    print(f'Addons: {len(addons)}')
    for component in sorted(componentes_ciclicos(addons, edges), key=len, reverse=True):
        print(f'  ciclo de {len(component)}: {" ".join(sorted(component))}')
    print(f'Inversiones fundacional -> negocio: {len(actuales)} '
          f'(conocidas: {len(KNOWN_INVERSIONS)})')

    for source, target in sorted(cerradas):
        print(f'  CERRADA  {source} -> {target} — bórrala de KNOWN_INVERSIONS')
    for source, target in sorted(nuevas):
        print(f'  NUEVA    {source} -> {target}')
        for sitio in sites[(source, target)]:
            print(f'             {sitio}')

    if report_only:
        return 0
    if nuevas:
        print(f'\nFALLO: {len(nuevas)} inversión(es) nueva(s). Un addon fundacional no '
              f'importa uno de negocio: la dependencia apunta hacia abajo (referencia '
              f'Odoo: mail 4, payment 7, sale 10). Invierte con señal o registro por '
              f'inscripción, como T-033/T-034/T-035.')
        return 1
    print('\nOK: sin inversiones nuevas.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
