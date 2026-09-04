"""Censo del contrato OpenAPI declarado sobre los controllers del monolito.

Recorre por AST cada ``*addons/**/controllers/*.py`` y clasifica sus endpoints
segun declaren o no su contrato con ``@extend_schema`` (o, a nivel de clase,
``@extend_schema_view``). Es el instrumento de la tarea #316 y la semilla del
gate de #317.

Que cuenta como endpoint
========================

- una funcion decorada con ``@api_view`` (estilo FBV del skill ``backend-drf``);
- un metodo HTTP (``get``/``post``/``put``/``patch``/``delete``/``head``/
  ``options``) de una clase que herede de ``APIView`` / ``GenericAPIView`` /
  ``*ViewSet`` o de un mixin de DRF;
- un metodo decorado con ``@action`` dentro de una de esas clases.

*Metrica:* decoradores ``extend_schema`` sobre el propio endpoint, o
``extend_schema_view`` sobre su clase nombrando ese metodo.
*Ciega a:* la CALIDAD del contrato (``responses={}`` vacio, ``request=None``
puesto por inercia) y a un endpoint servido fuera de ``controllers/``.
"""
import argparse
import ast
import pathlib
import sys


HTTP_METHODS = frozenset(
    ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'])

VIEW_BASE_HINTS = ('APIView', 'ViewSet', 'GenericAPIView', 'Mixin', 'ViewSetMixin')


def decorator_name(node):
    """El nombre del decorador, sea ``@x``, ``@x(...)``, ``@a.x`` o ``@a.x(...)``."""
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ''


def decorator_names(node):
    return {decorator_name(d) for d in node.decorator_list}


def looks_like_view_class(node):
    """Una clase es vista si alguna de sus bases lo insinua por nombre."""
    for base in node.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, 'id', '')
        if any(hint in name for hint in VIEW_BASE_HINTS):
            return True
    return False


def schema_view_targets(node):
    """Los metodos que un ``@extend_schema_view`` de clase nombra por keyword."""
    named = set()
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if decorator_name(decorator) != 'extend_schema_view':
            continue
        for keyword in decorator.keywords:
            if keyword.arg:
                named.add(keyword.arg)
    return named


def inherits_router_actions(node):
    """Un ``*ViewSet`` hereda list/retrieve/create/... del mixin de DRF.

    Esas acciones son endpoints reales —el router las publica— sin metodo
    propio en la clase, asi que el recorrido por ``ast`` no las ve. Su contrato
    solo se cura con ``@extend_schema_view`` sobre la clase.
    """
    for base in node.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, 'id', '')
        if 'ViewSet' in name and name != 'ViewSetMixin':
            return True
    return False


def endpoints_in(path):
    """Los endpoints del archivo, cada uno con su veredicto de contrato."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as error:
        print(f'ERROR — {path}: {error}', file=sys.stderr)
        raise SystemExit(2)

    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = decorator_names(node)
            if 'api_view' in names:
                found.append((node.name, 'fbv', 'extend_schema' in names, node.lineno))
        elif isinstance(node, ast.ClassDef) and looks_like_view_class(node):
            curated = schema_view_targets(node)
            if inherits_router_actions(node) and not curated:
                found.append((node.name, 'router', False, node.lineno))
            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                names = decorator_names(member)
                is_action = 'action' in names
                if member.name not in HTTP_METHODS and not is_action:
                    continue
                declared = 'extend_schema' in names or member.name in curated
                kind = 'action' if is_action else 'method'
                found.append((f'{node.name}.{member.name}', kind, declared, member.lineno))
    return found


def roots():
    """Las raices de addon del arbol, leidas de la declaracion, no a mano."""
    sys.path.insert(0, 'scripts')
    import addons_roots
    return [pathlib.Path(root) for root in addons_roots.ADDONS_PATHS]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--missing-only', action='store_true',
                        help='listar solo los endpoints sin contrato declarado')
    args = parser.parse_args()

    files = sorted(
        path
        for root in roots()
        for path in root.glob('*/controllers/*.py')
        if path.name != '__init__.py')

    declared = 0
    missing = []
    for path in files:
        for name, kind, has_schema, line in endpoints_in(path):
            if has_schema:
                declared += 1
            else:
                missing.append((path, name, kind, line))

    total = declared + len(missing)
    for path, name, kind, line in missing:
        print(f'{path}:{line}  {name}  [{kind}]')
    if not args.missing_only:
        print(f'\ncontrato declarado: {declared} de {total} endpoint(s) '
              f'(alcance medido: {len(files)} archivo(s) de controllers)')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
