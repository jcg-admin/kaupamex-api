"""Validador y normalizador de fórmulas de impuesto — ``account_tax_python``.

Adaptación de ``addons/account_tax_python/tools/formula_utils.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

Porte completo: **2 clases** (``ProductUomFieldRewriter``,
``TaxFormulaValidator``) y **2 funciones** (``check_formula``,
``normalize_formula``) — los cuatro símbolos del archivo, ninguno se omite.
La lógica de validación de AST (qué nodos se permiten, qué nombres, qué
llamadas) se porta **verbatim**: es lo que hace segura la evaluación
posterior de una fórmula escrita por un usuario.

Divergencia declarada — sin ``env``
=====================================

La fuente recibe ``env`` en ``check_formula(env, formula)`` /
``normalize_formula(env, formula, field_predicate=None)`` **sólo** para
traducir los mensajes de error (``env._(...)``, resuelto por request/idioma
de Odoo). Este ORM no tiene un objeto ``env`` por request — la traducción es
a nivel de módulo (``tools.translate._``, ``gettext_lazy`` de Django, ya
usado en ``account: models/account_cash_rounding.py`` y hermanos). Se cae el
parámetro ``env`` de ambas firmas; el resto del contrato (excepción,
mensaje, forma del retorno) es idéntico.
"""
import ast
from collections import defaultdict

from exceptions import ValidationError
from tools.translate import _

#: Funciones invocables dentro de una fórmula — sólo agregados de rango.
_ALLOWED_FUNCS = ('min', 'max')
#: Identificadores de lectura permitidos en el contexto de evaluación.
_ALLOWED_NAMES = ('price_unit', 'quantity', 'base', 'product', 'uom')
#: Tipos de constante permitidos (``None`` incluido, para expresiones como
#: ``product.volume > 100 and 5 or None``).
_ALLOWED_CONSTANT_T = (int, float, type(None))


#: Nodos de AST permitidos en una fórmula validada. Cualquier otro nodo
#: (listas, sets, dicts, comprensiones, lambdas, statements…) se rechaza en
#: ``TaxFormulaValidator.visit``.
_NODE_WHITELIST = (
    ast.Expression, ast.Name, ast.Call, ast.Subscript,  # expresión base
    ast.Constant,                                       # constantes
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div,      # operadores binarios
    ast.BoolOp, ast.And, ast.Or,                         # operadores lógicos
    ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE,       # comparaciones
    ast.UnaryOp, ast.UAdd, ast.USub,                     # unarios
)


class ProductUomFieldRewriter(ast.NodeTransformer):
    """Reescribe ``product.foo`` → ``product['foo']`` (ídem para ``uom``) y
    recolecta cada campo accedido, sea por atributo o por subíndice.
    """

    #: (modelo Odoo, alias en la fórmula) — el mismo par que la fuente.
    SUB_ENTITIES = (("product.product", "product"), ("uom.uom", "uom"))

    def __init__(self) -> None:
        super().__init__()
        self.accessed_fields = defaultdict(set)

    def visit_Attribute(self, node: ast.Attribute):
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Name):
            for model, alias in self.SUB_ENTITIES:
                if node.value.id == alias:
                    # Falla temprano si el AST de Python cambia de forma.
                    assert isinstance(node.attr, str), (
                        'El nombre del atributo debe ser una cadena')
                    self.accessed_fields[model].add(node.attr)
            return ast.Subscript(
                value=node.value,
                slice=ast.Constant(node.attr),
                ctx=node.ctx,
            )
        return node

    def visit_Subscript(self, node: ast.Subscript):
        node = self.generic_visit(node)
        if (
            isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            for model, alias in self.SUB_ENTITIES:
                if node.value.id == alias:
                    self.accessed_fields[model].add(node.slice.value)
        return node


class TaxFormulaValidator(ast.NodeVisitor):
    """Recorre el AST y rechaza cualquier nodo que no sea necesario o no sea
    reproducible en pyjs (paralelo a ``account_tax.js`` en la referencia; aquí
    no hay capa JS que mantener consistente, pero la validación es la misma).

    El AST debe pasar por ``ProductUomFieldRewriter`` ANTES de llegar aquí:
    este visitor no lista ``Attribute`` en la whitelist.
    """

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if not isinstance(node, _NODE_WHITELIST):
            raise ValidationError(_(
                'Nodo de AST no permitido: %(nombre)s'
            ) % {'nombre': type(node).__name__})
        super().visit(node)

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, _ALLOWED_CONSTANT_T):
            raise ValidationError(_(
                'Sólo se permiten valores constantes int, float o None'))

    def visit_Name(self, node: ast.Name):
        if node.id not in _ALLOWED_NAMES:
            raise ValidationError(_(
                'Identificador desconocido: %(nombre)s'
            ) % {'nombre': str(node.id)})
        if not isinstance(node.ctx, ast.Load):
            raise ValidationError(_(
                'Sólo se permite acceso de lectura a los identificadores'))

    def visit_Call(self, node: ast.Call):
        if not (
            isinstance(node.func, ast.Name)
            and node.func.id in _ALLOWED_FUNCS
            and isinstance(node.func.ctx, ast.Load)
        ):
            raise ValidationError(_('Llamada a función desconocida'))
        # No se visita node.func: ya está validado y min/max no se aceptan
        # como identificadores normales.
        for arg in node.args:
            self.visit(arg)
        if node.keywords:
            raise ValidationError(_('No se permiten argumentos con nombre'))

    def visit_Subscript(self, node: ast.Subscript):
        # Sólo se permiten constantes de cadena como subíndice
        # (p. ej. product["type"]) — no se permiten en ningún otro lugar.
        if not (
            isinstance(node.value, ast.Name)
            and node.value.id in ('product', 'uom')
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
            and isinstance(node.ctx, ast.Load)
        ):
            raise ValidationError(_(
                "Sólo se permite el acceso de lectura product['cadena'] o "
                "uom['cadena']"))
        self.visit(node.value)


def check_formula(formula: str) -> None:
    """Verifica que ``formula`` sólo use nodos de AST permitidos.

    Lanza ``ValidationError`` si no. ``formula`` DEBE venir ya normalizada
    por ``normalize_formula`` (atributos reescritos a subíndices) — este
    validador no acepta ``ast.Attribute``.
    """
    assert isinstance(formula, str), 'La fórmula debe ser una cadena'
    try:
        tree = ast.parse(formula, mode='eval')
    except (SyntaxError, ValueError):
        raise ValidationError(_('Fórmula inválida'))
    TaxFormulaValidator().visit(tree)


def normalize_formula(formula: str, field_predicate=None) -> tuple[str, set[str]]:
    """Recolecta cada acceso a campo y reescribe los accesos por atributo a
    ``product``/``uom`` como accesos por subíndice.

    Ejemplo: ``product.field`` → ``product['field']``, y se recolecta el
    campo accedido.

    :param field_predicate: ``callable(model_name, field_name) -> bool``.
        Si se pasa, cada campo accedido debe pasarlo o se lanza
        ``ValidationError`` — es el gancho que ``account_tax.py`` usa para
        exigir que el campo exista y no sea relacional.
    :return: ``(fórmula normalizada, dict modelo -> set de campos accedidos)``.
    """
    assert isinstance(formula, str), 'La fórmula debe ser una cadena'
    try:
        tree = ast.parse(formula, mode='eval')
    except (SyntaxError, ValueError):
        raise ValidationError(_('Fórmula inválida'))

    transformer = ProductUomFieldRewriter()
    transformed_tree = transformer.visit(tree)
    # Repone lineno/col_offset — necesario para que compile()/eval() acepten
    # el árbol reescrito (el equivalente de "para que safe_eval lo acepte").
    ast.fix_missing_locations(transformed_tree)

    if callable(field_predicate):
        for model, campos in transformer.accessed_fields.items():
            for campo in campos:
                if not field_predicate(model, campo):
                    raise ValidationError(_(
                        "El campo '%(campo)s' no es accesible"
                    ) % {'campo': campo})

    return ast.unparse(transformed_tree), transformer.accessed_fields
