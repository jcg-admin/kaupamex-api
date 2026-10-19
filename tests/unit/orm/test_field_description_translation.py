"""Contrato de TASK-API-0283: la etiqueta de campo declara traducción.

Referencia: odoo19c@abe4040ec1, odoo/addons/base/models/ir_model.py,
IrModelFields.field_description. Se evalúa la declaración AST real con la
fábrica pública del Consumer; no se inventa una copia del modelo ni se abre
la base de datos. Esto mide metadata, no almacenamiento multilingüe.
"""
import ast
import copy
from pathlib import Path

import fields


SOURCE = Path(__file__).resolve().parents[3] / 'src/addons/base/models/ir_model.py'


def field_declaration():
    """La expresión exacta de la declaración vigente, no un fixture duplicado."""
    tree = ast.parse(SOURCE.read_text())
    model = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == 'IrModelFields')
    assignment = next(node for node in model.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name)
                              and target.id == 'field_description'
                              for target in node.targets))
    assert isinstance(assignment.value, ast.Call)
    return copy.deepcopy(assignment.value)


def build_field(call):
    """Ejecuta sólo el constructor público extraído de la declaración."""
    expression = ast.fix_missing_locations(ast.Expression(body=call))
    return eval(compile(expression, str(SOURCE), 'eval'), {'fields': fields})


def without_translation(call):
    call.keywords = [kw for kw in call.keywords if kw.arg != 'translate']
    return call


def test_field_description_is_marked_translatable():
    assert build_field(field_declaration()).translate is True


def test_removing_the_flag_loses_the_translation_contract():
    assert build_field(without_translation(field_declaration())).translate is False


def test_the_annotation_does_not_claim_multilingual_storage():
    translated = build_field(field_declaration())
    plain = build_field(without_translation(field_declaration()))
    assert translated.deconstruct() == plain.deconstruct()
