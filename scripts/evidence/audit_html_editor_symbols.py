"""Auditoria de simbolos: referencia html_editor contra nuestro arbol.

No sustituye a ``check_porte_completo``; mide otra cosa — si el NOMBRE del
simbolo de la fuente aparece en el archivo destino, sea como ``def`` o como
clave de un diccionario de instalacion. Sirve para separar *ausencia real* de
*ceguera del gate ante una llamada dentro de un bucle*.

Metrica: nombres de metodo declarados en cada ``ClassDef`` del archivo de la
referencia, buscados como texto delimitado en el archivo nuestro homologo.
Ciega a: un nombre presente que no haga lo que hace el de la fuente.
"""
import ast
import pathlib
import re
import subprocess
import sys

raiz = subprocess.run(
    [sys.executable, 'scripts/reference_roots.py', '--env'],
    capture_output=True, text=True, check=True).stdout
ODOO19C = re.search(r"ODOO19C=([^\n;\"']+)", raiz).group(1).strip().strip('"')

ref_dir = pathlib.Path(ODOO19C) / 'addons/html_editor/models'
our_dir = pathlib.Path('addons/html_editor/models')

total = faltan = 0
for ref in sorted(ref_dir.glob('*.py')):
    if ref.name == '__init__.py':
        continue
    our = our_dir / ref.name
    texto = our.read_text() if our.exists() else ''
    print(f'--- {ref.name} (destino {"existe" if our.exists() else "AUSENTE"})')
    arbol = ast.parse(ref.read_text())
    for c in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
        metodos = [n.name for n in c.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for m in metodos:
            total += 1
            if not re.search(rf'\b{re.escape(m)}\b', texto):
                faltan += 1
                print(f'    FALTA  {c.name}.{m}')
    for f in [n for n in arbol.body
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        total += 1
        if not re.search(rf'\b{re.escape(f.name)}\b', texto):
            faltan += 1
            print(f'    FALTA  <modulo>.{f.name}')
print(f'\nsimbolos de la referencia: {total} · sin rastro en el destino: {faltan}')
