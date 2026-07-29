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

**Ratchet:** las inversiones que ya existen están en ``INVERSIONES_CONOCIDAS``
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

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'addons')

# Addons de infraestructura: identidad, acceso, correo y catálogo base. En la
# referencia viven entre profundidad 0 y 5, por debajo de todo el negocio.
FUNDACIONALES = frozenset({
    'base', 'users', 'authz', 'authz_reauth', 'auth_totp', 'company',
    'mail', 'catalogue', 'chartsize', 'questions', 'website',
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
INVERSIONES_CONOCIDAS = {
    ('users', 'orders'): 'serializers/admin_views leen el espejo — cierra con el bloque E',
    ('users', 'sale'): 'admin_views compone dinero de la venta — H-API-40',
    ('users', 'cart'): 'views enlaza el carrito del usuario',
    ('catalogue', 'sale'): 'views consulta líneas de venta del producto',
    ('catalogue', 'delivery'): 'seed de catálogo siembra zonas de envío',
    ('chartsize', 'sale'): 'views consulta líneas de venta',
    ('chartsize', 'delivery'): 'views consulta envío',
    ('catalogue', 'payment'): 'seed de catálogo siembra PaymentGateway — api@df99c5c',
}


def construir_grafo():
    """Devuelve (addons, aristas, sitios) leyendo los imports con AST."""
    addons = sorted(d for d in os.listdir(RAIZ) if os.path.isdir(os.path.join(RAIZ, d)))
    indice = set(addons)
    aristas = defaultdict(set)
    sitios = defaultdict(list)
    for addon in addons:
        for carpeta, _, archivos in os.walk(os.path.join(RAIZ, addon)):
            if 'migrations' in carpeta.split(os.sep):
                continue
            for archivo in archivos:
                if not archivo.endswith('.py'):
                    continue
                ruta = os.path.join(carpeta, archivo)
                try:
                    arbol = ast.parse(open(ruta, encoding='utf-8').read())
                except SyntaxError:
                    continue
                for nodo in ast.walk(arbol):
                    if isinstance(nodo, ast.ImportFrom) and nodo.module:
                        modulos = [nodo.module]
                    elif isinstance(nodo, ast.Import):
                        modulos = [alias.name for alias in nodo.names]
                    else:
                        continue
                    for modulo in modulos:
                        if not modulo.startswith('addons.'):
                            continue
                        partes = modulo.split('.')
                        if len(partes) > 1 and partes[1] in indice and partes[1] != addon:
                            aristas[addon].add(partes[1])
                            sitios[(addon, partes[1])].append(
                                f'{os.path.relpath(ruta, os.getcwd())}:{nodo.lineno}')
    return addons, aristas, sitios


def componentes_ciclicos(addons, aristas):
    """Tarjan iterativo; devuelve los componentes de tamaño > 1."""
    indice, bajo, en_pila, pila, contador, salida = {}, {}, {}, [], [0], []

    def recorrer(inicio):
        trabajo = [(inicio, 0)]
        while trabajo:
            nodo, i = trabajo[-1]
            if i == 0:
                indice[nodo] = bajo[nodo] = contador[0]
                contador[0] += 1
                pila.append(nodo)
                en_pila[nodo] = True
            descendio = False
            vecinos = sorted(aristas[nodo])
            for j in range(i, len(vecinos)):
                vecino = vecinos[j]
                if vecino not in indice:
                    trabajo[-1] = (nodo, j + 1)
                    trabajo.append((vecino, 0))
                    descendio = True
                    break
                if en_pila.get(vecino):
                    bajo[nodo] = min(bajo[nodo], indice[vecino])
            if descendio:
                continue
            if bajo[nodo] == indice[nodo]:
                componente = []
                while True:
                    w = pila.pop()
                    en_pila[w] = False
                    componente.append(w)
                    if w == nodo:
                        break
                salida.append(componente)
            trabajo.pop()
            if trabajo:
                bajo[trabajo[-1][0]] = min(bajo[trabajo[-1][0]], bajo[nodo])

    for addon in addons:
        if addon not in indice:
            recorrer(addon)
    return [c for c in salida if len(c) > 1]


def main():
    solo_reporte = '--report' in sys.argv
    addons, aristas, sitios = construir_grafo()

    actuales = {
        (origen, destino)
        for origen in FUNDACIONALES & set(addons)
        for destino in aristas[origen] & NEGOCIO
    }
    nuevas = actuales - set(INVERSIONES_CONOCIDAS)
    cerradas = set(INVERSIONES_CONOCIDAS) - actuales

    print(f'Addons: {len(addons)}')
    for componente in sorted(componentes_ciclicos(addons, aristas), key=len, reverse=True):
        print(f'  ciclo de {len(componente)}: {" ".join(sorted(componente))}')
    print(f'Inversiones fundacional -> negocio: {len(actuales)} '
          f'(conocidas: {len(INVERSIONES_CONOCIDAS)})')

    for origen, destino in sorted(cerradas):
        print(f'  CERRADA  {origen} -> {destino} — bórrala de INVERSIONES_CONOCIDAS')
    for origen, destino in sorted(nuevas):
        print(f'  NUEVA    {origen} -> {destino}')
        for sitio in sitios[(origen, destino)]:
            print(f'             {sitio}')

    if solo_reporte:
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
