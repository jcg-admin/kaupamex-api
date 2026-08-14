#!/usr/bin/env python3
"""Gate: un par ``_inherits`` de la referencia debe nacer con su delegación.

Odoo declara ``_inherits = {'modelo.padre': 'campo_id'}`` cuando el hijo
**delega** parte de su superficie en el padre: el "qué ejecutar" de ``ir.cron``
vive en ``ir.actions.server``; el ``subject`` de ``mail.mail`` vive en
``mail.message``. Al portar, esa delegación se traduce como **FK real +
delegación por propiedad** — nunca como herencia multi-tabla de Django, que
crea un ``OneToOneField(parent_link=True)`` (una hija por padre) cuando el
``_inherits`` de Odoo es un ``Many2one``.

Este gate detecta el defecto que H-API-202 midió: un par cuyos dos modelos
existen en ``src/addons/`` y donde el hijo **no declara FK al padre** — la
delegación quedó aplanada, con las columnas del padre copiadas en el hijo.

Salida: reporte legible. Con ``--strict``, exit 1 si hay algún par aplanado.
Si el árbol de referencia no está disponible, el gate **se salta** (exit 0) —
no rompe un clon que no tenga ``odoo-tools``.

Uso:
    python3 scripts/check_inherits_delegation.py
    python3 scripts/check_inherits_delegation.py --strict
    ODOO19C=/ruta/al/arbol python3 scripts/check_inherits_delegation.py
"""
import ast
import os
import pathlib
import re
import sys

# Raíz de la referencia. La convención la fija
# docs: source/normativa/.../convencion-cita-referencia-odoo.rst (alias odoo19c:).
DEFAULT_ODOO19C = (
    '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0'
)
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import py_files


def clase_esperada(modelo_odoo):
    """``ir.actions.server`` → ``IrActionsServer`` (CamelCase por segmento)."""
    return ''.join(p.capitalize() for p in re.split(r'[._]', modelo_odoo))


def pares_inherits(raiz):
    """Los ``_inherits`` de la referencia, excluyendo módulos de test.

    Devuelve [(archivo, hijo_modelo, padre_modelo)]. El nombre del hijo sale
    de su ``_name``; si la clase no lo declara, se usa el nombre del archivo.
    """
    fuera = []
    for base in ('addons', 'odoo/addons'):
        d = raiz / base
        if d.is_dir():
            fuera.extend(d.glob('*/models/*.py'))
    pares = []
    for p in sorted(fuera):
        if '/test_' in str(p):
            continue
        try:
            arbol = ast.parse(p.read_text(errors='replace'))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef):
                continue
            hijo = padres = None
            for st in nodo.body:
                if not (isinstance(st, ast.Assign) and len(st.targets) == 1):
                    continue
                destino = st.targets[0]
                if not isinstance(destino, ast.Name):
                    continue
                if destino.id == '_name' and isinstance(st.value, ast.Constant):
                    hijo = st.value.value
                elif destino.id == '_inherits' and isinstance(st.value, ast.Dict):
                    padres = [
                        k.value for k in st.value.keys
                        if isinstance(k, ast.Constant)
                    ]
            if padres:
                for padre in padres:
                    pares.append((str(p), hijo or p.stem, padre))
    return pares


def declara_fk(ruta_clase, clase_padre):
    """¿La clase declara un campo cuyo primer argumento es ``clase_padre``?

    Cubre las dos formas del árbol: ``fields.Many2one(Padre, ...)`` con la
    clase importada, y la referencia por string ``'app.Padre'``.
    """
    archivo, nombre_clase = ruta_clase
    try:
        arbol = ast.parse(pathlib.Path(archivo).read_text(errors='replace'))
    except SyntaxError:
        return False
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.ClassDef) and nodo.name == nombre_clase):
            continue
        for st in ast.walk(nodo):
            if not (isinstance(st, ast.Call) and st.args):
                continue
            f = st.func
            if getattr(getattr(f, 'value', None), 'id', None) not in ('fields', 'models'):
                continue
            arg = st.args[0]
            if isinstance(arg, ast.Name) and arg.id == clase_padre:
                return True
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.split('.')[-1] == clase_padre:
                    return True
    return False


def localizar(nombre_clase):
    """Primer archivo de ``src/addons/`` que declara ``class <nombre>``."""
    patron = re.compile(rf'^class {re.escape(nombre_clase)}[(:]', re.M)
    for p in py_files():
        if '__pycache__' in str(p) or '/migrations/' in str(p):
            continue
        if patron.search(p.read_text(errors='replace')):
            return (str(p), nombre_clase)
    return None


def main():
    estricto = '--strict' in sys.argv
    raiz = pathlib.Path(os.environ.get('ODOO19C', DEFAULT_ODOO19C))
    if not raiz.is_dir():
        print(f'check_inherits_delegation: referencia ausente ({raiz}) — gate omitido.')
        return 0

    pares = pares_inherits(raiz)
    aplanados, ok, sin_medir = [], [], []
    for _archivo, hijo_modelo, padre_modelo in pares:
        hijo_cls = clase_esperada(hijo_modelo)
        padre_cls = clase_esperada(padre_modelo)
        hijo = localizar(hijo_cls)
        padre = localizar(padre_cls)
        if not hijo or not padre:
            sin_medir.append((hijo_modelo, padre_modelo,
                              'hijo' if not hijo else 'padre'))
            continue
        (ok if declara_fk(hijo, padre_cls) else aplanados).append(
            (hijo_modelo, padre_modelo, hijo[0])
        )

    print(f'_inherits en la referencia: {len(pares)} (sin módulos de test)')
    print(f'  delegación declarada : {len(ok)}')
    print(f'  APLANADOS            : {len(aplanados)}')
    print(f'  no medibles          : {len(sin_medir)} (falta uno de los dos modelos)')
    for hijo, padre, motivo in sin_medir:
        print(f'    · {hijo} → {padre} (falta el {motivo})')
    for hijo, padre, archivo in aplanados:
        print(f'\n  APLANADO: {hijo} → {padre}')
        print(f'    {archivo} no declara FK a {clase_esperada(padre)}.')
        print('    La referencia delega ahí. Portar como FK real + @property,')
        print('    no como columnas propias. Ver H-API-202 y el principio')
        print('    normativa/principios/principio-separacion-de-ejes.')

    if aplanados and estricto:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
