#!/usr/bin/env python3
"""Deriva el ``depends`` de un addon midiendo lo que su código usa de verdad.

Existe porque la convención local lo exige explícitamente — el manifiesto de
``analytic`` lo dice en su propio comentario: *"`depends` MEDIDO contra los
imports reales de este addon (no copiado de la referencia, que además declara
`mail`/`web` como deps de la UI que no aplican a este monolito Django)"*.

Dos señales, ambas por AST:

1. **import** — ``from addons.<x> import ...`` / ``import addons.<x>``.
2. **cadena de modelo** — una constante ``'<addon>.<Modelo>'`` (FK por cadena,
   ``_inherit``, ``add_to_class``). Se leen **constantes del AST**, nunca texto
   crudo: así el comentario queda fuera por construcción, y el docstring se
   excluye a mano porque sí es una constante.

Por qué hacen falta las dos: medido sobre los 91 addons, la señal-cadena aporta
**26 aristas en 21 addons** que el import no ve — entre ellas ``analytic → uom``,
que el manifiesto escrito a mano sí declara. Sólo-imports produciría un
``depends`` que sub-declara.

*Métrica:* aristas ``addon → addon`` dentro del árbol, por import de módulo y por
constante ``'<addon>.<Modelo>'``, excluyendo ``migrations/``.
*Ciega a:*

- **la intención**. Mide lo que el código hace, no lo que debe declarar. El caso
  medido: ``sale`` importa ``sale_loyalty`` y su manifiesto lo omite **a
  propósito**, porque declararlo legitimaría una inversión que
  ``check_addon_cycles.py`` vigila. Escribir la salida de este guion encima de
  ese manifiesto desharía una decisión deliberada.
- **el cableado pendiente**. ``account_qr_code_sepa`` declara ``account`` y
  ``base_iban`` y su código no los usa: el manifiesto va por delante del código
  (H-API-293, sus cinco métodos no están cableados al dispatcher real).
- **el destino muerto**. Detecta que un ``depends`` declarado no se usa, no que
  el addon destino haya dejado de existir. Eso lo cubre ``--auditar``.

Por eso la salida es **insumo con revisión**, no un escritor de manifiestos.

Uso::

    python3 scripts/derivar_depends.py                 # depends medido de cada addon
    python3 scripts/derivar_depends.py <addon> [...]   # sólo esos
    python3 scripts/derivar_depends.py --auditar       # medido vs declarado + destinos muertos
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addons_roots import addon_dirs

# Una constante que nombra un modelo de otro addon: 'sale.SaleOrder'.
CADENA = re.compile(r'^([a-z_0-9]+)\.([A-Z][A-Za-z0-9_]*)$')


def _docstrings(tree):
    """ids de las constantes que son docstring — prosa, no referencia de código."""
    marcados = set()
    for nodo in ast.walk(tree):
        if not isinstance(nodo, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (nodo.body and isinstance(nodo.body[0], ast.Expr)
                and isinstance(nodo.body[0].value, ast.Constant)
                and isinstance(nodo.body[0].value.value, str)):
            marcados.add(id(nodo.body[0].value))
    return marcados


def depends_medido(addon, raiz, universo):
    """Aristas salientes de ``addon``, con el sitio que las produce."""
    aristas = {}
    for carpeta, _, archivos in os.walk(raiz):
        if 'migrations' in carpeta.split(os.sep):
            continue
        for nombre in archivos:
            if not nombre.endswith('.py'):
                continue
            ruta = os.path.join(carpeta, nombre)
            try:
                arbol = ast.parse(open(ruta, encoding='utf-8').read())
            except SyntaxError:
                continue
            docs = _docstrings(arbol)
            for nodo in ast.walk(arbol):
                destino = senal = None
                if isinstance(nodo, ast.ImportFrom) and nodo.module:
                    modulos = [nodo.module]
                elif isinstance(nodo, ast.Import):
                    modulos = [a.name for a in nodo.names]
                else:
                    modulos = []
                for modulo in modulos:
                    if modulo.startswith('addons.'):
                        partes = modulo.split('.')
                        if len(partes) > 1:
                            destino, senal = partes[1], 'import'
                if (destino is None and isinstance(nodo, ast.Constant)
                        and isinstance(nodo.value, str) and id(nodo) not in docs):
                    casa = CADENA.match(nodo.value.strip())
                    if casa:
                        destino, senal = casa.group(1), 'cadena'
                if destino and destino in universo and destino != addon:
                    aristas.setdefault(destino, []).append(
                        f'{os.path.relpath(ruta)}:{nodo.lineno} ({senal})')
    return aristas


def main(argv):
    dirs = {p.name: str(p) for p in addon_dirs()}
    universo = set(dirs)
    auditar = '--auditar' in argv
    pedidos = [a for a in argv if not a.startswith('--')] or sorted(dirs)

    if not auditar:
        for addon in pedidos:
            if addon not in dirs:
                print(f'{addon}: no existe en ninguna raíz', file=sys.stderr)
                continue
            medido = depends_medido(addon, dirs[addon], universo)
            print(f'{addon}: {sorted(medido)}')
        print(f'\n(alcance medido: {len(pedidos)} de {len(dirs)} addons)',
              file=sys.stderr)
        return 0

    exacto = con_dif = sin_manifiesto = 0
    muertos = []
    for addon in sorted(dirs):
        ruta_mf = os.path.join(dirs[addon], '__manifest__.py')
        if not os.path.exists(ruta_mf):
            sin_manifiesto += 1
            continue
        declarado = set(ast.literal_eval(
            open(ruta_mf, encoding='utf-8').read()).get('depends', []))
        medido = set(depends_medido(addon, dirs[addon], universo))
        fantasma = sorted(d for d in declarado if d not in universo)
        if fantasma:
            muertos.append((addon, fantasma))
        solo_decl = sorted(declarado - medido - set(fantasma))
        solo_med = sorted(medido - declarado)
        if not solo_decl and not solo_med and not fantasma:
            exacto += 1
        else:
            con_dif += 1
            print(f'  {addon:26s}'
                  f' declarado-no-usado:{solo_decl or "—"}'
                  f'  usado-no-declarado:{solo_med or "—"}'
                  f'{"  DESTINO MUERTO:" + str(fantasma) if fantasma else ""}')
    total = exacto + con_dif
    print(f'\ncoinciden: {exacto}/{total} con manifiesto'
          f' · difieren: {con_dif} · sin manifiesto: {sin_manifiesto}'
          f' (alcance medido: {total + sin_manifiesto} addons)')
    if muertos:
        print(f'\nDESTINOS MUERTOS — depends que apunta a un addon inexistente:')
        for addon, f in muertos:
            print(f'  {addon}: {f}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
