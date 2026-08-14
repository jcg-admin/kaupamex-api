#!/usr/bin/env python3
"""Verifica que cada símbolo viva del lado del árbol donde la referencia lo declara.

Origen: :ref:`h-api-556` — el porte de ``base_sparse_field`` aterrizó en
``src/orm/`` (núcleo) cuando la referencia lo declara en un addon instalable.
Lo detectó el ejecutor, no una medición. Directiva del mismo turno:
*"asegúrate de que no vuelva a pasar"* — y en este proyecto eso significa un
gate, no un párrafo: ``gitlink-bump-gate.md`` lo dejó dicho tras dos fallos en
la misma sesión (*"la lección escrita no previene la reincidencia"*).

Qué mide
--------

Por cada **clase de nivel superior** declarada en nuestro árbol, busca dónde
declara la referencia una clase con ese nombre y compara los dos lados:

===================  =========================  ==========================
Nuestro archivo      Referencia lo declara en   Veredicto
===================  =========================  ==========================
``src/orm/``         ``odoo/``                  correcto (núcleo ↔ núcleo)
``src/orm/``         ``addons/``                **FUERA DE SITIO**
``src/addons/``      ``addons/``                correcto (addon ↔ addon)
``src/addons/``      ``odoo/``                  **FUERA DE SITIO**
===================  =========================  ==========================

El caso que lo origina, medido sobre ``odoo19c``::

    class Serialized  ->  odoo/orm/            0 hits
                          addons/base_sparse_field/models/fields.py

mientras que el precedente que se generalizó mal **sí** es núcleo::

    grep -c "store" odoo/orm/fields.py         66

Los dos son campos con descriptor y sin columna; sólo uno lo declara el
núcleo. La pregunta que este gate hace —y que faltó— no es *"¿qué clase de
mecanismo es?"* sino **"¿dónde lo declara la referencia?"**.

Qué NO puede ver
-----------------

- **Un símbolo que la referencia no declara.** Un modelo propio del producto
  no tiene lado que comparar; sale ``sin contraparte`` y no es un fallo. El
  gate mide ubicación, no procedencia — de eso se ocupa
  ``check_addon_names.py``.
- **El archivo exacto.** Compara ``odoo/`` contra ``addons/``, no la ruta
  completa. Un símbolo en el addon equivocado *dentro* de ``addons/`` pasa.
- **Un renombre no declarado.** Si el nombre cambió, el símbolo sale ``sin
  contraparte`` en vez de fuera de sitio — el lado seguro, y el mismo criterio
  que ``PORTE_ALIAS`` en ``check_porte_completo.py``.
- **Un nombre que la referencia declara en los dos lados.** Sale
  ``ambiguo`` y no se juzga: el instrumento no puede desempatar por nombre.

*Métrica:* nombre de clase de nivel superior, en nuestro árbol y en el de la
referencia.
*Ciega a:* todo lo de arriba; en particular, un símbolo movido al addon
**correcto por lado** pero **equivocado por addon**.

Uso
---

    python3 scripts/check_symbol_home.py                 # reporte
    python3 scripts/check_symbol_home.py --quiet         # sólo el conteo
    python3 scripts/check_symbol_home.py --strict        # exit 1 si hay nuevos
    python3 scripts/check_symbol_home.py --todos         # incluye los aceptados

Sin el árbol de la referencia el gate **no falla**: informa y sale 0. Un gate
que bloquea el commit de quien no clonó ``odoo-tools`` mide el entorno, no el
código.
"""
import argparse
import ast
import os
import pathlib
import re
import sys

#: Raíz del árbol que gobierna (``odoo19c``). Misma convención y misma
#: variable de entorno que ``check_porte_completo.py``.
ODOO19C = pathlib.Path(
    os.environ.get(
        'ODOO19C',
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0',
    )
)

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / 'src'

#: Nombres que el stack impone y que no describen una decisión de ubicación:
#: el nombre no lo elige quien escribe el archivo, así que su lado no dice nada
#: sobre dónde debe vivir el mecanismo.
#:
#: ``Command`` entra aquí porque el descubrimiento de Django exige esa clase,
#: con ese nombre, en ``management/commands/<nombre>.py``. La ``Command`` de la
#: referencia es otra cosa —el centinela del ORM
#: (``odoo19c: odoo/orm/commands.py``) y la base de su CLI
#: (``odoo/cli/command.py``)—, así que los 19 hits eran colisión, no ubicación.
NOMBRES_IMPUESTOS = frozenset({'Migration', 'Meta', 'Config', 'Command'})

#: Ubicaciones ya juzgadas, con su motivo. Es el ratchet del gate: la deuda
#: heredada no bloquea cada commit, pero una ubicación NUEVA sí. Mismo patrón
#: que ``INVERSIONES_CONOCIDAS`` de ``check_addon_cycles.py``.
#:
#: Una entrada aquí es una **decisión declarada**, no una excepción de
#: conveniencia: si el símbolo está mal ubicado, lo correcto es moverlo.
UBICACIONES_ACEPTADAS = {
    'Module': (
        'colisión de nombre genérico, no de ubicación: la Module de la '
        'referencia es un nodo del grafo de addons (odoo19c: '
        'odoo/modules/module_graph.py); la nuestra agrupa capacidades por '
        'dominio para el menú (authz/models.py). Si el NOMBRE es el adecuado '
        'es otra pregunta — este gate mide el lado, no el vocabulario.'
    ),
}

_CLASE = re.compile(r'^class\s+(\w+)', re.MULTILINE)


def lado_de(partes):
    """``'addons'`` si la ruta atraviesa un directorio ``addons``, si no ``'odoo'``.

    **El primer directorio NO sirve como criterio**, y medirlo así produjo 68
    falsos positivos en la primera corrida de este gate: el addon ``base`` de
    la referencia vive en ``odoo/addons/base/``, no en ``addons/base/``, así
    que todo ``src/addons/base/**`` salía "declarado en el núcleo".

    .. code-block:: text

       grep -rln "^class ResDevice" $ODOO19C  ->  odoo/addons/base/models/res_device.py
       ls -d $ODOO19C/addons/base             ->  No such file or directory

    Es el mismo defecto que el gate persigue, un nivel más arriba: una
    conclusión sobre ubicación sacada de un instrumento que no mide ubicación.
    """
    return 'addons' if 'addons' in partes else 'odoo'


def indexar_referencia(raiz):
    """Mapa ``nombre de clase -> {'odoo', 'addons'}`` de todo el árbol.

    Se indexa con expresión regular y no con ``ast``: son decenas de miles de
    archivos y sólo interesa el nombre a columna 0, que es exactamente lo que
    ``^class`` captura. Un archivo que no parsea no rompe el índice.
    """
    indice = {}
    for archivo in raiz.rglob('*.py'):
        partes = archivo.relative_to(raiz).parts
        if '__pycache__' in partes:
            continue
        try:
            texto = archivo.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        lado = lado_de(partes)
        for nombre in _CLASE.findall(texto):
            indice.setdefault(nombre, set()).add(lado)
    return indice


def clases_propias(raiz):
    """Clases de nivel superior de nuestro árbol, con su lado y su archivo.

    Aquí sí se usa ``ast``: son ~1400 archivos, y la distinción entre una
    clase de nivel superior y una anidada (``class Meta``) es justo lo que la
    expresión regular no da.
    """
    encontradas = []
    for archivo in raiz.rglob('*.py'):
        partes = archivo.relative_to(raiz).parts
        if 'migrations' in partes or '__pycache__' in partes:
            continue
        if partes[0] == 'orm':
            lado = 'odoo'
        elif partes[0] == 'addons':
            lado = 'addons'
        else:
            continue          # config/, tools/ y demás no tienen lado que comparar
        try:
            arbol = ast.parse(archivo.read_text(encoding='utf-8'))
        except (OSError, SyntaxError):
            continue
        for nodo in arbol.body:
            if isinstance(nodo, ast.ClassDef):
                encontradas.append((nodo.name, lado, archivo))
    return encontradas


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--quiet', action='store_true',
                        help='sólo la línea de conteo')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay ubicaciones nuevas fuera de sitio')
    parser.add_argument('--todos', action='store_true',
                        help='listar también las ya aceptadas')
    args = parser.parse_args()

    if not ODOO19C.is_dir():
        print(f'check_symbol_home: árbol de referencia ausente ({ODOO19C}) '
              '— gate omitido, no es un fallo.')
        return 0

    indice = indexar_referencia(ODOO19C)
    propias = clases_propias(SRC)

    fuera, aceptadas, ambiguas, sin_contraparte = [], [], [], 0
    for nombre, lado, archivo in propias:
        if nombre in NOMBRES_IMPUESTOS:
            continue
        lados_ref = indice.get(nombre)
        if not lados_ref:
            sin_contraparte += 1
            continue
        if len(lados_ref) > 1:
            ambiguas.append((nombre, archivo))
            continue
        (lado_ref,) = lados_ref
        if lado_ref == lado:
            continue
        registro = (nombre, lado, lado_ref, archivo.relative_to(REPO))
        if nombre in UBICACIONES_ACEPTADAS:
            aceptadas.append(registro)
        else:
            fuera.append(registro)

    medidas = len(propias) - sin_contraparte - len(ambiguas)
    if not args.quiet:
        for nombre, lado, lado_ref, ruta in sorted(fuera):
            print(f'FUERA DE SITIO  {nombre}')
            print(f'    aquí:       {ruta}  (lado {lado})')
            print(f'    referencia: lo declara bajo {lado_ref}/')
        if args.todos:
            for nombre, lado, lado_ref, ruta in sorted(aceptadas):
                print(f'aceptada        {nombre}  ({ruta}) — '
                      f'{UBICACIONES_ACEPTADAS[nombre]}')

    # El denominador va junto al conteo: sin él, un instrumento ciego y uno
    # correcto publican el mismo cero (``hallazgo-abierto-genera-sucesor.md``).
    print(f'check_symbol_home: {len(fuera)} fuera de sitio, '
          f'{len(aceptadas)} aceptadas '
          f'(alcance medido: {medidas} de {len(propias)} clases; '
          f'{sin_contraparte} sin contraparte, {len(ambiguas)} ambiguas).')

    if fuera and args.strict:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
