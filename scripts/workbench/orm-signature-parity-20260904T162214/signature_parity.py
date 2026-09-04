"""Paridad de FIRMA entre ``odoo/orm`` y ``src/orm``.

El cuarto eje de la directiva —archivos, clases, funciones y **firmas de
funcion**— es el unico que ningun instrumento del arbol medía. Los dos censos
del eje ORM lo declaran como ceguera, y el manifiesto del censo de raiz lo
dice verbatim:

    La firma. Un simbolo con el mismo nombre y otros parametros cuenta como
    presente.

``check_porte_completo``, que cubre el resto del arbol, tampoco la compara.
Consecuencia: un puerto con el nombre correcto y otros parametros pasa los dos
gates, que es el conteo generoso contra el que ``porte-completo-no-parcial.md``
ya advierte sin instrumento que lo vea.

Que mide y que NO
=================

Compara, por AST y sólo para los simbolos que **ya estan portados**, la firma
declarada aqui contra la de su contraparte:

- los parametros positionals, **en orden** (``posonly`` + ``args``);
- los ``keyword-only`` como **conjunto** — a nivel de llamada su orden no es
  observable, asi que exigirlo fabricaria divergencias que no existen;
- ``*args`` y ``**kwargs``, por su presencia y su nombre;
- que parametros **llevan default**, no cual es su valor.

El porte ausente NO es asunto de este instrumento: lo mide el censo, y sumar
las dos cifras infla el eje de firma con deuda que ya tiene su propio cubo
—el sub-patron A de ``metrica-decide-la-conclusion.md``—. Lo que no se pudo
comparar sale en ``not_ported``, con su propio conteo.

Un veredicto por simbolo, no una lista de defectos
===================================================

Cuando una firma diverge por varias razones a la vez se publica **la mas
estructural**: un parametro que falta explica por si solo que el orden no
coincida, y publicar los dos hincharia el conteo con la misma divergencia
contada dos veces.
"""
import argparse
import ast
import dataclasses
import os
import pathlib
import sys

#: Prioridad de veredicto. La primera que aplica es la que se publica.
KINDS = (
    'varargs_divergente',
    'renombre',
    'parametro_ausente',
    'parametro_extra',
    'orden_distinto',
    'default_perdido',
    'default_anadido',
)


@dataclasses.dataclass(frozen=True)
class Signature:
    """La firma de una funcion, en las cinco categorias que Python distingue."""
    posonly: tuple
    args: tuple
    vararg: str | None
    kwonly: tuple
    kwarg: str | None
    defaults: frozenset

    @property
    def positional(self):
        """Los positionals en orden — la unica categoria donde el orden pesa."""
        return self.posonly + self.args

    def render(self):
        """La firma como se leeria en el fuente, sin anotaciones ni valores."""
        parts = []
        parts += [f'{n}=' if n in self.defaults else n for n in self.posonly]
        if self.posonly:
            parts.append('/')
        parts += [f'{n}=' if n in self.defaults else n for n in self.args]
        if self.vararg:
            parts.append(f'*{self.vararg}')
        elif self.kwonly:
            parts.append('*')
        parts += [f'{n}=' if n in self.defaults else n for n in self.kwonly]
        if self.kwarg:
            parts.append(f'**{self.kwarg}')
        return f'({", ".join(parts)})'


@dataclasses.dataclass
class Divergence:
    """Una firma que no coincide, con LOS DOS lados a la vista."""
    symbol: str
    kind: str
    reference: str
    mine: str


@dataclasses.dataclass
class FileRow:
    """El veredicto de firma de UN archivo de la referencia."""
    name: str
    identical: list
    divergences: list
    not_ported: list
    ambiguous: list

    @property
    def comparable(self):
        return len(self.identical) + len(self.divergences)


def _parse(path):
    try:
        return ast.parse(pathlib.Path(path).read_text())
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return None


def _signature(node):
    """La firma de un nodo de funcion, con los defaults por NOMBRE.

    El default se guarda por el nombre del parametro y no por posicion: asi un
    parametro insertado antes no desplaza la lectura de quien lleva default.
    """
    a = node.args
    posonly = tuple(p.arg for p in a.posonlyargs)
    args = tuple(p.arg for p in a.args)
    kwonly = tuple(p.arg for p in a.kwonlyargs)
    # Los defaults positionals se alinean por la derecha; los kwonly, uno a uno.
    positionals = posonly + args
    with_default = set(positionals[len(positionals) - len(a.defaults):]) if a.defaults else set()
    with_default |= {p.arg for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None}
    return Signature(
        posonly=posonly,
        args=args,
        vararg=a.vararg.arg if a.vararg else None,
        kwonly=kwonly,
        kwarg=a.kwarg.arg if a.kwarg else None,
        defaults=frozenset(with_default),
    )


def _is_overload(node):
    """¿Es un stub de ``@typing.overload``?

    La referencia declara ``constrains`` y ``depends`` tres veces cada uno: dos
    stubs de ``@overload`` y la implementacion real. Leer el primero publica
    ``(func, /)`` como firma de un simbolo cuya firma real es ``(*args)`` — una
    divergencia fabricada por el instrumento, no del arbol. El control real la
    destapo en la primera corrida.
    """
    for d in node.decorator_list:
        name = d.attr if isinstance(d, ast.Attribute) else getattr(d, 'id', '')
        if name == 'overload':
            return True
    return False


def signatures(path):
    """``{nombre: Signature}`` de un archivo — la PRIMERA declaracion gana.

    El nombre es el bare name, sin la clase que lo contiene: es lo que hace
    comparable un metodo de la fuente con la funcion de modulo en que este
    arbol lo declara (``BaseModel`` no existe aqui como clase).

    Los stubs de ``@overload`` se saltan: no son la firma del simbolo, son su
    declaracion de tipo para el verificador.
    """
    tree = _parse(path)
    if tree is None:
        return {}
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_overload(node):
                continue
            out.setdefault(node.name, _signature(node))
    return out


def repeated_names(path):
    """Los nombres declarados mas de una vez — la ceguera se publica, no se calla."""
    tree = _parse(path)
    if tree is None:
        return []
    visto, repetido = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_overload(node):
                continue
            (repetido if node.name in visto else visto).add(node.name)
    return sorted(repetido)


def signature_of(path, name):
    """La firma de UN simbolo, o ``None`` si el archivo no lo declara como funcion."""
    return signatures(path).get(name)


def classify(ref, mine):
    """El veredicto de un par de firmas, o ``None`` si coinciden."""
    if ref.vararg != mine.vararg or ref.kwarg != mine.kwarg:
        return 'varargs_divergente'

    faltan = [p for p in ref.positional if p not in mine.positional]
    sobran = [p for p in mine.positional if p not in ref.positional]
    faltan_kw = set(ref.kwonly) - set(mine.kwonly)
    sobran_kw = set(mine.kwonly) - set(ref.kwonly)

    if (faltan or faltan_kw) and (sobran or sobran_kw) and \
            len(faltan) + len(faltan_kw) == len(sobran) + len(sobran_kw):
        return 'renombre'
    if faltan or faltan_kw:
        return 'parametro_ausente'
    if sobran or sobran_kw:
        return 'parametro_extra'
    if ref.positional != mine.positional:
        return 'orden_distinto'

    # Los defaults se comparan sólo sobre los parametros que ambos declaran.
    comunes = set(ref.positional) | set(ref.kwonly)
    if {p for p in ref.defaults if p in comunes} - mine.defaults:
        return 'default_perdido'
    if {p for p in mine.defaults if p in comunes} - ref.defaults:
        return 'default_anadido'
    return None


def compare_file(ref_path, mine_path):
    """El veredicto de firma de un archivo contra su contraparte."""
    ref_sigs = signatures(ref_path)
    mine_sigs = signatures(mine_path)
    # El nombre declarado dos veces NO entra en la comparacion. Comparar el
    # convert_to_column de la clase A de la fuente contra el que aqui aparece
    # primero es medir un par que nadie eligio: su veredicto no informa ni de
    # coincidencia ni de divergencia. Sale en su propio cubo, con su conteo.
    ambiguous = sorted(set(repeated_names(ref_path)) | set(repeated_names(mine_path)))
    ambiguous_names = set(ambiguous)

    identical, divergences, not_ported = [], [], []
    for name, ref_sig in ref_sigs.items():
        if name in ambiguous_names:
            continue
        mine_sig = mine_sigs.get(name)
        if mine_sig is None:
            not_ported.append(name)
            continue
        kind = classify(ref_sig, mine_sig)
        if kind is None:
            identical.append(name)
        else:
            divergences.append(Divergence(name, kind, ref_sig.render(), mine_sig.render()))
    return FileRow(
        name=pathlib.Path(ref_path).name,
        identical=identical,
        divergences=divergences,
        not_ported=not_ported,
        ambiguous=ambiguous,
    )


def parity(ref_dir, mine_dir):
    """``{archivo: FileRow}`` — sólo los archivos con contraparte."""
    ref_dir, mine_dir = pathlib.Path(ref_dir), pathlib.Path(mine_dir)
    rows = {}
    for ref_py in sorted(ref_dir.glob('*.py')):
        if ref_py.name == '__init__.py':
            continue
        mine_py = mine_dir / ref_py.name
        if not mine_py.exists():
            continue
        rows[ref_py.name] = compare_file(ref_py, mine_py)
    return rows


def _report(rows, detail=False):
    lines = ['=== paridad de firma: odoo/orm <-> src/orm ===', '']
    lines.append(f'{"archivo":<28}{"comp":>6}{"igual":>7}{"difiere":>9}'
                  f'{"sin portar":>12}{"ambiguo":>9}')
    tot_comparable = tot_identical = tot_divergent = tot_not_ported = 0
    by_kind = {k: 0 for k in KINDS}
    for name, row in rows.items():
        tot_comparable += row.comparable
        tot_identical += len(row.identical)
        tot_divergent += len(row.divergences)
        tot_not_ported += len(row.not_ported)
        for d in row.divergences:
            by_kind[d.kind] += 1
        lines.append(f'{name:<28}{row.comparable:>6}{len(row.identical):>7}'
                      f'{len(row.divergences):>9}{len(row.not_ported):>12}'
                      f'{len(row.ambiguous):>9}')
    lines.append('')
    if tot_comparable:
        lines.append(f'firmas comparables: {tot_comparable} · identicas: {tot_identical} '
                      f'({tot_identical * 100.0 / tot_comparable:.1f} %) · divergentes: {tot_divergent}')
    else:
        lines.append('firmas comparables: 0 — NO se emite porcentaje: '
                      'un 0 aqui no distingue «coinciden» de «no se midio»')
    lines.append(f'(alcance medido: {len(rows)} archivo(s) con contraparte; '
                  f'{tot_not_ported} simbolo(s) sin portar quedan FUERA — los mide el censo)')
    lines.append('')
    lines.append('divergencias por tipo: ' + ' · '.join(
        f'{k} {v}' for k, v in by_kind.items() if v))
    ambiguous_names = sorted({n for f in rows.values() for n in f.ambiguous})
    lines.append(f'FUERA de la comparacion por nombre declarado mas de una vez: '
                  f'{len(ambiguous_names)} nombre(s) distinto(s). No se comparan: el par '
                  f'seria arbitrario. Su cierre exige calificar por clase, que '
                  f'este arbol no puede en models.py — BaseModel no existe aqui '
                  f'como clase.')
    if detail:
        for name, row in rows.items():
            if not row.divergences:
                continue
            lines += ['', f'--- {name} ---']
            for d in sorted(row.divergences, key=lambda x: (x.kind, x.symbol)):
                lines.append(f'  {d.kind:<22} {d.symbol}')
                lines.append(f'      ref  {d.reference}')
                lines.append(f'      aqui {d.mine}')
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--ref', help='raiz de la referencia (default: $ODOO19C/odoo/orm)')
    p.add_argument('--mine', default='src/orm', help='nuestra raiz espejada')
    p.add_argument('--detail', action='store_true', help='cada divergencia, con ambos lados')
    args = p.parse_args(argv)

    ref = args.ref
    if not ref:
        base = os.environ.get('ODOO19C')
        if not base:
            print('ERROR — falta $ODOO19C. Exportalo con:\n'
                  '  eval "$(python3 scripts/reference_roots.py --env)"\n'
                  'NO se emite conteo: un 0 sin la referencia seria un verde falso.',
                  file=sys.stderr)
            return 2
        ref = pathlib.Path(base) / 'odoo' / 'orm'
    if not pathlib.Path(ref).is_dir():
        print(f'ERROR — la raiz de referencia no existe: {ref}', file=sys.stderr)
        return 2
    print(_report(parity(ref, args.mine), detail=args.detail))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
