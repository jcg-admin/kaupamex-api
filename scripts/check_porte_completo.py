#!/usr/bin/env python3
"""Mide la cobertura de símbolos de cada puerto contra su archivo de referencia.

Origen: directiva del ejecutor 2026-08-06 — *"¿se están integrando todas las
clases y métodos completos de los archivos de la referencia?"*. La respuesta
medida era **no se verifica**: había gates de layout, nombres, ciclos e
``_inherits``, pero ninguno que comparara los símbolos. ``porte-completo-no-parcial.md``
pide mecanizar la métrica cuando se pueda; esto lo hace.

Qué mide
--------

Empareja ``src/addons/<addon>/**/<archivo>.py`` con el mismo camino bajo el
árbol de la referencia y clasifica **cada archivo de la referencia** en uno de
tres estados:

- ``COMPLETO`` — todas sus clases y métodos tienen homólogo aquí;
- ``PARCIAL`` — el archivo existe pero le faltan clases o métodos;
- ``NO PORTADO`` — ninguna de sus clases existe en el addon.

Por clase hay un cuarto veredicto, ``CLASE EXTENDIDA``: la clase no existe
aquí **y el addon instala símbolos sobre ella** desde ``ready()``. Ver la
sección siguiente.

El porte por extensión cross-app (H-API-569)
---------------------------------------------

Django no fusiona dos definiciones del mismo modelo declaradas en apps
distintas, que es como la referencia materializa ``_inherit``. Este árbol lo
resuelve **instalando** sobre la clase ajena: ``chain_method`` para un método,
``add_to_class`` para un campo, los dos desde ``AppConfig.ready()``. El
símbolo portado no vive en una clase propia — vive en una función de módulo
que una llamada instala.

Una versión anterior de este gate indexaba **sólo clases**, así que reportaba
``CLASE AUSENTE`` sobre un porte que sí estaba. Lo destapó cerrar la tarea
#314: de los cuatro símbolos que declaraba ausentes en
``base_sparse_field/models/models.py``, **dos estaban portados** (``write`` →
``save``, ``_reflect_fields`` → ``reflect_fields``) y dos eran divergencias
declaradas.

``instalaciones_del_addon`` lee esas llamadas y el gate emite
``CLASE EXTENDIDA`` con lo que **sigue pendiente** tras descontar lo
instalado. **Nunca absuelve la clase entera**: ``web :: IrHttp`` instala 1 de
los 11 símbolos de su contraparte, y los 10 restantes se siguen listando.

Delta medido al cablearlo (2026-08-13, 92 addons, 671 pares de archivo):

.. code-block:: text

   estado                antes   después
   ARCHIVO NO PORTADO      469       468
   CLASE AUSENTE           123       102
   CLASE EXTENDIDA           0        15
   MÉTODOS AUSENTES        121       121
   FUERA DE SITIO            2         2
   total                   715       708

Las 21 ``CLASE AUSENTE`` que se reclasifican son las que caían sobre una
clase realmente extendida: **15** quedan como extensión parcial y **6**
desaparecen porque lo instalado las cubre entera (extensiones de sólo campos,
donde la clase de la referencia no declara ningún método). El archivo que
sale de ``ARCHIVO NO PORTADO`` es ``account/models/company.py``: pasa de
"nada portado" a ``CLASE EXTENDIDA`` con 55 métodos pendientes, que es una
descripción estrictamente mejor del mismo código.

El tercer estado es el que importa declarar: una primera versión de este gate
**saltaba** los archivos sin contraparte, así que su denominador era la
intersección y lo más ausente de todo le resultaba invisible. Es la ceguera
que ``metrica-decide-la-conclusion.md`` describe, aplicada al instrumento.

Medido 2026-08-06 sobre los 79 addons compartidos: **638 archivos de
referencia** — 11 completos, 147 parciales, 480 sin portar.

Esa cifra corrige una anterior (15 / 141 / 482): la rama de "archivo sin
contraparte" comparaba **sólo nombres de clase**, así que un archivo que en la
referencia extiende (``_inherit``) una clase ya portada salía COMPLETO con cero
métodos portados. El caso que lo destapó —``account_journal_dashboard.py``, 50
métodos allá y 0 aquí— es el peor error posible en un instrumento de cobertura:
un COMPLETO falso. Ver :ref:`h-api-350`.

Qué NO puede ver
-----------------

- Un método presente con el mismo nombre pero que **hace menos** — el conteo
  generoso que ``porte-completo-no-parcial.md`` documenta. Este gate mide
  nombres, no comportamiento.
- Un símbolo portado a **otro archivo** del mismo addon. Por eso el
  emparejamiento es por addon, no por archivo: se buscan los nombres en TODO
  el addon antes de declararlos ausentes. El precio de esa tolerancia es que
  el gate **no ve el sitio de declaración** — una función suelta donde la
  referencia tiene un método de clase pasa el conteo. Sucesor #159.
- Un renombre que el mapa de alias no declare. Los renombres conocidos van en
  ``PORTE_ALIAS``; lo no declarado sale como ausente, que es el lado seguro.
- **Una instalación cuyo receptor es una variable.** Tres addons envuelven el
  ``add_to_class`` en un ayudante y le pasan el modelo por parámetro o por
  bucle (``_add_if_absent(model, …)``), así que del AST sale el nombre de la
  variable, no el del modelo. Esas instalaciones existen y no se pueden
  atribuir: van al denominador como ``instalaciones con receptor no
  resoluble``, no al silencio.
- **Qué hace el método instalado.** ``CLASE EXTENDIDA`` dice que el addon
  instala un símbolo con ese nombre sobre esa clase; no que haga lo que hace
  el de la referencia. Es la misma ceguera de conteo que la primera viñeta,
  un nivel más arriba.

Por qué ``write`` NO se aliasa a ``save``
------------------------------------------

Es la tentación obvia —en la referencia ``write()`` es el método de
actualización del ORM y aquí es ``save()``— y está **deliberadamente
descartada**. Medido: ``write`` sale como ausente **90 veces** en el árbol.
Un alias global convertiría noventa preguntas abiertas en noventa
absoluciones silenciosas, sin que nadie compruebe que cada ``save()`` hace lo
que hacía su ``write()``.

Es exactamente la amplitud que #164 ya quitó de este gate por fabricar
coincidencias: entonces un homónimo de otro modelo absolvía 11 de 18
símbolos. ``PORTE_ALIAS`` es para renombres **decididos uno por uno** —así lo
dice su propio comentario—, no para mapear el vocabulario de dos ORM de una
vez.

Uso
---

    python3 scripts/check_porte_completo.py                  # reporte
    python3 scripts/check_porte_completo.py --addon account  # un addon
    python3 scripts/check_porte_completo.py --mapa           # inventario por archivo
    python3 scripts/check_porte_completo.py --quiet          # sólo el conteo
    python3 scripts/check_porte_completo.py --strict         # exit 1 si hay ausentes
"""
import argparse
import ast
import os
import pathlib
import sys

#: Raíz del árbol que gobierna (``odoo19c``). Ver
#: ``referencia-odoo-gobierna-las-decisiones.md``: 19 desempata, y las rutas de
#: una versión NO son válidas en la otra.
ODOO19C = pathlib.Path(
    os.environ.get(
        'ODOO19C',
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0',
    )
)

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_dirs, addon_path

#: Renombres declarados: ``nombre en la referencia -> nombre aquí``. Cada
#: entrada es una decisión, no una conveniencia — si el nombre cambió sin
#: motivo, la entrada correcta es arreglar el nombre, no añadir el alias.
PORTE_ALIAS = {
    # El prefijo ``action_`` de la referencia marca lo invocable desde su UI;
    # aquí no hay esa UI, así que el método se llama por lo que hace.
    'action_set_manual': 'set_manual',
    'action_set_auto_reconcile': 'set_auto_reconcile',
    # ``_compute_<campo>`` es la convención de su ORM para un campo calculado.
    '_compute_partner_mapping': 'compute_mapped_partner',
    # El cargador no es un modelo aquí, así que no lleva el prefijo del addon.
    'AccountChartTemplate': 'ChartTemplate',
    # El guion bajo es un artefacto de la convención de la referencia para el
    # nombre técnico; los identificadores de este árbol van en CamelCase.
    'Sparse_FieldsTest': 'SparseFieldsTest',
}


#: Receptores de ``add_to_class`` que NO son una clase resoluble en estático:
#: el ayudante recibe el modelo por parámetro o por variable de bucle, así que
#: el nombre que se lee del AST es el de la variable, no el del modelo.
_RECEPTOR_NO_RESOLUBLE = frozenset({'model', 'modelo', 'cls', 'self'})


def addon_installations(raiz):
    """``{clase_destino: {símbolos instalados}}`` — la extensión cross-app.

    Este árbol no puede fusionar dos definiciones del mismo modelo declaradas
    en apps distintas, que es como la referencia materializa ``_inherit``. En
    su lugar el addon extensor **instala** sobre la clase ajena desde
    ``ready()``: ``chain_method`` para un método, ``add_to_class`` para un
    campo. El símbolo portado no vive en una clase propia, así que indexar
    clases —lo que hace ``clases_del_addon``— es ciego a él.

    Se leen las **llamadas de instalación**, no los nombres sueltos del
    módulo. La diferencia importa: indexar toda función de nivel superior
    absolvería un método porque exista un homónimo en cualquier parte, que es
    la amplitud que #164 ya quitó por fabricar coincidencias. Una llamada
    ``chain_method(IrModelFields, 'save', …)`` es una **declaración** de qué
    se instala y sobre qué clase.

    Devuelve además ``no_resolubles``: las instalaciones cuyo receptor es una
    variable (``_add_if_absent(model, …)`` dentro de un bucle), que existen y
    no se pueden atribuir a una clase. Van al denominador, no al silencio.
    """
    mapa, no_resolubles = {}, 0
    for py in raiz.rglob('*.py'):
        if '__pycache__' in py.parts or 'migrations' in py.parts:
            continue
        try:
            arbol = ast.parse(py.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            destino, clave = _destino_y_clave(nodo)
            if clave is None:
                continue
            if destino is None or destino in _RECEPTOR_NO_RESOLUBLE:
                no_resolubles += 1
                continue
            mapa.setdefault(normaliza(destino), set()).add(clave)
    return mapa, no_resolubles


def _destino_y_clave(nodo):
    """``(clase, símbolo)`` de una llamada de instalación, o ``(None, None)``.

    Reconoce las tres formas que el árbol usa hoy: ``chain_method(C, 'x', …)``,
    ``C.add_to_class('x', …)`` y el ayudante ``_add_if_absent(C, 'x', …)`` que
    tres addons repiten para hacer idempotente el ``add_to_class``.
    """
    f = nodo.func
    name = f.id if isinstance(f, ast.Name) else (
        f.attr if isinstance(f, ast.Attribute) else None)

    if name in ('chain_method', '_add_if_absent') and len(nodo.args) >= 2:
        destino, clave = nodo.args[0], nodo.args[1]
    elif name == 'add_to_class' and nodo.args:
        # El receptor es el destino: ``ResBank.add_to_class('campo', …)``.
        destino = f.value if isinstance(f, ast.Attribute) else None
        clave = nodo.args[0]
    else:
        return None, None

    if not isinstance(clave, ast.Constant) or not isinstance(clave.value, str):
        return None, None
    if isinstance(destino, ast.Name):
        return destino.id, clave.value
    if isinstance(destino, ast.Attribute):
        return destino.attr, clave.value
    return None, clave.value


def simbolos(ruta):
    """``{clase: {métodos}}`` de un archivo Python, o ``None`` si no parsea."""
    try:
        arbol = ast.parse(ruta.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return None
    return {
        n.name: {m.name for m in n.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for n in arbol.body if isinstance(n, ast.ClassDef)
    }


def file_symbols(ruta):
    """Todos los símbolos de UN archivo: métodos de clase y funciones sueltas.

    Delimita qué cuenta como *portado en otro sitio*. Un símbolo que la
    referencia declara dentro de una clase y que aquí vive en **el archivo que
    le corresponde** —en otra clase del mismo archivo, o suelto a nivel de
    módulo— es una divergencia de sitio: existe, y hay que darle veredicto. Si
    vive en **otro archivo**, no es evidencia de nada sobre este método.

    El alcance era el addon entero hasta #164, y esa amplitud fabricaba
    coincidencias. Medido sobre los 18 símbolos que #159 destapó: **11** los
    absolvía un símbolo homónimo de **otro modelo** —los cuatro
    ``_compute_name`` de ``AccountBankStatement``/``AccountMove``/
    ``AccountMoveLine``/``AccountPayment`` los cubría uno solo, el de
    ``AccountPaymentMethodLine``— y sólo **7** estaban de verdad fuera de sitio
    dentro de su archivo. Con el alcance en el archivo, los 11 salen como
    ausentes, que es lo que son. Ver :ref:`h-api-356`.

    *Ciega a:* un método genuinamente reubicado a un archivo hermano del mismo
    puerto sale como ausente. Es el lado seguro —declara de menos, no de más—
    y se corrige declarando el alias, no ampliando el alcance.
    """
    try:
        arbol = ast.parse(ruta.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return set()
    return {n.name for n in ast.walk(arbol)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def equivalencias_declaradas(ruta):
    """Símbolos de la referencia que una ``property`` nuestra absuelve.

    Un ``compute='_compute_x'`` sin ``store`` de la referencia se porta aquí
    como ``property x``: el valor se deriva en cada acceso en vez de
    materializarse en columna. El símbolo ``_compute_x`` no existe entonces en
    nuestro archivo, y el gate —que compara por nombre— lo declaraba ausente.
    Medido sobre ``stock`` antes de este cambio: **38 de 395** ausentes eran de
    esta forma, un 10 % de falsos positivos que inflaban la deuda declarada.

    **La absolución exige que la equivalencia esté DECLARADA**, no que se pueda
    inferir. El docstring de la ``property`` debe nombrar el símbolo de la
    referencia (``_compute_x``) para que cuente. Absolver por la sola forma del
    nombre sería la trampa que este gate ya cometió tres veces: un instrumento
    que declara portado lo que no ha leído. Con la declaración exigida, un
    porte legítimo pero mudo sale como ausente — y eso **es** la señal
    correcta: ``porte-completo-no-parcial.md`` pide declarar la divergencia,
    no sólo tenerla.

    Medido en el mismo pase: de las 38, **23** citaban el compute y **15** no.
    Las 15 son trabajo real —declarar su origen—, no ruido del gate.

    *Métrica:* ``_compute_<campo>`` de la referencia cuyo ``<campo>`` es una
    ``property``/``cached_property`` de nuestro archivo Y cuyo docstring
    contiene la cadena ``_compute_<campo>``.
    *Ciega a:* el mismo porte con el campo renombrado (``_compute_qty`` →
    ``property quantity``), y a los ``_inverse_x``/``_search_x``, que la
    referencia declara junto al compute y que aquí se resuelven de otras
    formas. Ambos siguen saliendo como ausentes — el lado seguro.
    """
    try:
        arbol = ast.parse(ruta.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return set()
    # Los docstrings se ACUMULAN por nombre, no se sobreescriben: dos clases
    # del mismo archivo pueden declarar `property x` —una citando su compute y
    # otra no— y con un dict simple ganaría la última en aparecer. El
    # instrumento decidiría por orden de lectura, que es exactamente la clase
    # de arbitrariedad que este gate ha pagado antes.
    properties = {}
    for n in ast.walk(arbol):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in n.decorator_list:
            name = (dec.id if isinstance(dec, ast.Name) else
                      dec.attr if isinstance(dec, ast.Attribute) else '')
            if 'property' in name:
                properties.setdefault(n.name, []).append(
                    ast.get_docstring(n) or '')
                break
    return {f'_compute_{field}' for field, docs in properties.items()
            if any(f'_compute_{field}' in doc for doc in docs)}


def addon_classes(raiz):
    """``{clase_normalizada: {métodos}}`` de TODO el addon.

    Un archivo de la referencia puede estar portado **repartido** en varios
    archivos nuestros; buscar la clase en todo el addon antes de declararla
    ausente evita contar como no-portado lo que sólo cambió de casa.

    Devuelve **los métodos, no sólo el nombre**. Una versión anterior devolvía
    un conjunto de nombres, y con eso la rama de "archivo sin contraparte"
    declaraba COMPLETO cualquier archivo cuyas clases existieran aquí —
    aunque no se hubiera portado ni un método. Medido sobre
    ``account_journal_dashboard.py``: **50 métodos** en la referencia, **0**
    portados, y el gate lo daba por completo, porque su clase ``AccountJournal``
    existe en otro archivo. Es un COMPLETO falso, la forma más cara de error en
    un instrumento de cobertura. Ver :ref:`h-api-350`.
    """
    by_class = {}
    for py in raiz.rglob('*.py'):
        if 'migrations' in py.parts or '__pycache__' in py.parts:
            continue
        for klass, metodos in (simbolos(py) or {}).items():
            by_class.setdefault(normaliza(klass), set()).update(metodos)
    return by_class


def normaliza(name):
    """El nombre comparable: alias declarado, y sin guiones bajos de borde."""
    return PORTE_ALIAS.get(name, name).strip('_')


def _class_without_counterpart(addon, file_path, klass, metodos, instalado,
                           absueltos=frozenset()):
    """``(hallazgo|None, absoluciones)`` de una clase que no existe aquí.

    Dos estados distintos: **ausente** del todo, o **extendida** — si el addon
    instala símbolos sobre una clase con ese nombre, el porte existe pero no
    tiene clase propia, y se reporta ``CLASE EXTENDIDA`` con lo que sigue
    pendiente tras descontar lo instalado.

    ``absueltos`` son las equivalencias compute→property declaradas en NUESTRO
    archivo (ver ``equivalencias_declaradas``). Aplican aquí igual que en la
    rama de clase casada: la property vive en el archivo, no en la clase, así
    que el porte es real aunque el nombre de la clase diverja
    (``AccountTax`` → ``AccountTaxFormula``) o aunque la dueña del compute en
    la referencia sea una clase hermana sin contraparte
    (``WebsitePublishedMultiMixin``). Los dos casos se midieron: eran las **2**
    declaraciones —de 15— que el gate no contaba, porque esta función nunca
    consultaba ``absueltos``. Ver :ref:`h-api-612`.

    Si tras absolver no queda ningún método, no hay hallazgo.

    *Métrica:* ``absoluciones`` cuenta cuántos símbolos de ``metodos`` quedaron
    cubiertos por ``absueltos`` en ESTA llamada — el segundo valor del
    retorno, que ``compara()`` acumula para publicar el denominador
    ``compute absueltos por property declarada`` del reporte final.
    *Ciega a:* una absolución que ocurrió en la rama de clase casada (no la de
    clase sin contraparte) — esa la cuenta ``compara()`` por su cuenta, en el
    bucle de la clase casada, sin pasar por esta función.
    """
    puestos = instalado.get(normaliza(klass))
    ya = {normaliza(p) for p in puestos} if puestos is not None else set()
    tipo = 'CLASE AUSENTE' if puestos is None else 'CLASE EXTENDIDA'
    pendientes, absolutions = [], 0
    for m in sorted(metodos):
        n = normaliza(m)
        if n in ya:
            continue
        if n in absueltos:
            absolutions += 1
            continue
        pendientes.append(m)
    # Una clase AUSENTE con la lista vacía sigue siendo un hallazgo: la
    # referencia declara clases de sólo campos, y que no tengan método no las
    # vuelve portadas. Sólo se suprime cuando había métodos y TODOS quedaron
    # cubiertos — por lo instalado o por una equivalencia declarada. Medido al
    # introducir el cambio: sin esta guarda desaparecían 18 hallazgos de golpe
    # con sólo 4 absoluciones nuevas, que es la señal de que el instrumento
    # había dejado de ver algo en vez de resolverlo.
    if metodos and not pendientes:
        return None, absolutions
    if not metodos and tipo == 'CLASE EXTENDIDA':
        return None, absolutions
    return (addon, file_path, klass, tipo, pendientes), absolutions


def compara(addon):
    """Devuelve ``(pares, [hallazgo, ...], no_resolubles, absoluciones)``."""
    ref_raiz = ODOO19C / 'addons' / addon
    mio_raiz = addon_path(addon) or pathlib.Path('/nonexistent')
    if not ref_raiz.is_dir() or not mio_raiz.is_dir():
        return 0, [], 0, 0

    by_class = addon_classes(mio_raiz)
    instalado, no_resolubles = addon_installations(mio_raiz)
    pares, hallazgos, absolutions = 0, [], 0

    for ref_py in sorted((ref_raiz / 'models').glob('*.py')):
        if ref_py.name == '__init__.py':
            continue
        mio_py = mio_raiz / 'models' / ref_py.name
        if not mio_py.exists():
            # Un archivo sin contraparte NO se salta: saltarlo dejaba el
            # denominador en la intersección, que es la ceguera que
            # ``metrica-decide-la-conclusion.md`` describe — el instrumento no
            # veía lo más ausente de todo. Se busca por nombre de clase en todo
            # el addon, porque un puerto puede repartir un archivo en varios.
            #
            # Y se comparan **los métodos**, no sólo el nombre de la clase: en
            # la referencia muchos archivos son extensiones (``_inherit``) de
            # una clase que aquí ya existe, así que casar por nombre los daba
            # por completos con cero métodos portados.
            pares += 1
            ref_clases = simbolos(ref_py) or {}
            # Si NINGUNA de sus clases existe aquí, el archivo entero está sin
            # portar; si alguna existe, es una extensión (``_inherit``) cubierta
            # a medias. Los dos estados se cuentan distinto en el mapa.
            # "Ninguna de sus clases existe" incluye a las que existen **como
            # extensión**: un archivo cuyo único contenido es un ``_inherit``
            # portado con ``chain_method`` no está sin portar, aunque ninguna
            # clase lleve su nombre.
            if ref_clases and not any(
                    normaliza(c) in by_class or normaliza(c) in instalado
                    for c in ref_clases):
                hallazgos.append(
                    (addon, ref_py.name, '(archivo)', 'ARCHIVO NO PORTADO',
                     sorted(ref_clases)))
                continue
            for klass, metodos in ref_clases.items():
                aqui = by_class.get(normaliza(klass))
                if aqui is None:
                    # Sin archivo pareado no hay property nuestra que leer, así
                    # que aquí no se absuelve nada: el conjunto va vacío.
                    hallazgo, _ = _class_without_counterpart(
                        addon, ref_py.name, klass, metodos, instalado)
                    if hallazgo is not None:
                        hallazgos.append(hallazgo)
                    continue
                aqui_norm = {normaliza(m) for m in aqui}
                faltan = [m for m in sorted(metodos)
                          if normaliza(m) not in aqui_norm]
                if faltan:
                    hallazgos.append(
                        (addon, ref_py.name, klass, 'MÉTODOS AUSENTES', faltan))
            continue
        pares += 1
        ref_clases = simbolos(ref_py) or {}
        mias = simbolos(mio_py) or {}
        mias_norm = {normaliza(c): ms for c, ms in mias.items()}
        from_file = {normaliza(x) for x in file_symbols(mio_py)}
        # Un compute sin store portado como property, con la equivalencia
        # declarada en su docstring. Ver equivalencias_declaradas().
        absueltos = {normaliza(x) for x in equivalencias_declaradas(mio_py)}

        for klass, metodos in ref_clases.items():
            aqui = mias_norm.get(normaliza(klass))
            if aqui is None:
                hallazgo, absueltas = _class_without_counterpart(
                    addon, ref_py.name, klass, metodos, instalado, absueltos)
                absolutions += absueltas
                if hallazgo is not None:
                    hallazgos.append(hallazgo)
                continue
            aqui_norm = {normaliza(m) for m in aqui}
            faltan, out_of_place = [], []
            for m in sorted(metodos):
                n = normaliza(m)
                if n in aqui_norm:
                    continue
                if n in absueltos:
                    absolutions += 1
                    continue
                # El símbolo existe en ESTE archivo pero NO en la clase que le
                # toca: función suelta, o método de otra clase del archivo.
                # Antes esto se descartaba en silencio y el método contaba
                # como portado — el gate medía **presencia del nombre**, no su
                # sitio (#159). El alcance era el addon entero hasta #164, y
                # entonces un homónimo de otro modelo lo daba por ubicado.
                (out_of_place if n in from_file else faltan).append(m)
            if faltan:
                hallazgos.append(
                    (addon, ref_py.name, klass, 'MÉTODOS AUSENTES', faltan))
            if out_of_place:
                hallazgos.append(
                    (addon, ref_py.name, klass, 'FUERA DE SITIO',
                     out_of_place))
    return pares, hallazgos, no_resolubles, absolutions


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--addon', help='medir sólo este addon')
    p.add_argument('--mapa', action='store_true',
                   help='inventario por archivo con su estado')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--strict', action='store_true')
    args = p.parse_args()

    if not ODOO19C.is_dir():
        print(f'AVISO: no está el árbol de referencia en {ODOO19C}; '
              'sin él este gate no puede medir nada.')
        return 0

    addons = [args.addon] if args.addon else sorted(
        d.name for d in addon_dirs())

    pares_total, todos, opacas, absueltos_total = 0, [], 0, 0
    for addon in addons:
        pares, hallazgos, no_resolubles, absolutions = compara(addon)
        pares_total += pares
        todos += hallazgos
        opacas += no_resolubles
        absueltos_total += absolutions

    if args.mapa:
        # El inventario completo: cada archivo de la referencia con su estado.
        # Es lo que convierte el gate en un mapa — sin él sólo se ve la deuda,
        # no la superficie sobre la que se mide.
        estado = {}
        for addon, file_path, _klass, tipo, _s in todos:
            previo = estado.get((addon, file_path))
            estado[(addon, file_path)] = (
                'NO PORTADO' if tipo == 'ARCHIVO NO PORTADO'
                else previo or 'PARCIAL')
        for addon in addons:
            ref_dir = ODOO19C / 'addons' / addon / 'models'
            if not ref_dir.is_dir() or addon_path(addon) is None:
                continue
            for ref_py in sorted(ref_dir.glob('*.py')):
                if ref_py.name == '__init__.py':
                    continue
                print(f'{estado.get((addon, ref_py.name), "COMPLETO"):>11}  '
                      f'{addon}/models/{ref_py.name}')
    elif args.quiet:
        print(len(todos))
    else:
        for addon, file_path, klass, tipo, simbolos_ in todos:
            print(f'{addon}/models/{file_path} :: {klass} — {tipo} ({len(simbolos_)})')
            print(f'    {", ".join(simbolos_)}')
        # El denominador va SIEMPRE junto al conteo: un 0 sin alcance medido no
        # distingue "no hay deuda" de "el instrumento no vio nada".
        #
        # Y los dos estados van **separados**: uno es trabajo de porte, el otro
        # de reubicación. Sumarlos vuelve a esconder lo que #159 destapó.
        fuera = [h for h in todos if h[3] == 'FUERA DE SITIO']
        extend = [h for h in todos if h[3] == 'CLASE EXTENDIDA']
        simb_fuera = sum(len(h[4]) for h in fuera)
        print(f'\nporte incompleto: {len(todos)} hallazgos '
              f'({len(todos) - len(fuera) - len(extend)} de porte · '
              f'{len(extend)} de extensión parcial · '
              f'{len(fuera)} de sitio, {simb_fuera} símbolos) '
              f'(alcance medido: {pares_total} pares de archivo, '
              f'{len(addons)} addons; '
              f'{opacas} instalaciones con receptor no resoluble; '
              f'{absueltos_total} compute absueltos por property declarada)')
    return 1 if (args.strict and todos) else 0


if __name__ == '__main__':
    sys.exit(main())
