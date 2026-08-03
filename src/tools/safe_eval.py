"""``safe_eval`` — fiel a ``odoo/tools/safe_eval.py`` (Odoo 19), acotado.

Adaptación de ``odoo/tools/safe_eval.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3 → copia con atribución, DEC-KX-03). La referencia
valida los **opcodes** del bytecode compilado (``_SAFE_OPCODES``,
``safe_eval.py:135``) y evalúa con builtins acotados; su ``safe_eval``
(``:369``) acepta expresiones y hasta statements en modo ``exec``.

Aquí el único consumidor es ``ir.rule`` (``build_domain`` evalúa el
``domain_force`` almacenado contra el ``_eval_context``), así que la
adaptación valida el **AST** con una whitelist más estrecha que la fuente:
sólo la forma de un dominio — listas/tuplas de leaves con constantes,
nombres del contexto y atributos simples (``user.id``). Divergencia
declarada: **más restrictivo** que la fuente, nunca menos. Si un consumidor
futuro necesita ``mode='exec'`` (``ir.actions.server`` code, ``ir_cron``),
ese pase amplía este módulo con la validación de opcodes de la referencia —
no la esquiva.

Guardas que se conservan de la fuente:

- builtins vacíos en la evaluación (nada de ``__import__``/``open``);
- atributos con guion bajo prohibidos (la fuente bloquea el acceso a
  ``_*``/dunder en sus checks de nombres).
"""
import ast

__all__ = ['const_eval', 'safe_eval']

#: Nodos que forman un dominio almacenado — y nada más. ``Load`` es el ctx
#: de lectura de ``Name``/``Attribute``; ``UnaryOp``/``USub`` cubren los
#: negativos literales (``-1``).
_ALLOWED_NODES = (
    ast.Expression, ast.List, ast.Tuple, ast.Constant,
    ast.Name, ast.Load, ast.Attribute, ast.UnaryOp, ast.USub,
)


def _assert_valid_ast(tree, expr):
    """Rechaza cualquier nodo fuera de la forma de un dominio.

    El análogo de ``assert_valid_codeobj`` de la fuente (``safe_eval.py:405``),
    aplicado al AST en vez de a los opcodes: mismo rol —validar ANTES de
    ejecutar—, superficie menor.
    """
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(
                'safe_eval: nodo no permitido %s en %r'
                % (type(node).__name__, expr))
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError(
                'safe_eval: atributo privado prohibido %r en %r'
                % (node.attr, expr))


def const_eval(expr):
    """Evalúa una expresión de SOLO constantes — el ``const_eval`` de la fuente.

    Delegado en ``ast.literal_eval``, que es exactamente esa garantía.
    """
    return ast.literal_eval(expr)


def safe_eval(expr, context=None):
    """Evalúa una expresión de dominio almacenada contra un contexto acotado.

    Los nombres disponibles son EXACTAMENTE los del ``context`` (el
    ``_eval_context`` de ``ir.rule``: ``user``/``company_ids``/``company_id``).
    Un nombre fuera del contexto es ``NameError``; un nodo fuera de la forma
    de dominio es ``ValueError`` antes de ejecutar nada.
    """
    tree = ast.parse(expr, mode='eval')
    _assert_valid_ast(tree, expr)
    code = compile(tree, '<domain_force>', 'eval')
    return eval(code, {'__builtins__': {}}, dict(context or {}))
