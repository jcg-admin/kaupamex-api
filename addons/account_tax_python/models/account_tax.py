r"""``account.tax`` — impuesto con fórmula Python (``account_tax_python``).

Adaptación de ``addons/account_tax_python/models/account_tax.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

Qué hace la referencia
=======================

``account_tax_python`` agrega un quinto ``amount_type`` (``'code'``) al
impuesto: en vez de porcentaje/fijo/división/grupo, el monto se calcula
evaluando una fórmula Python escrita por el usuario (``price_unit * 0.10``,
``max(quantity * price_unit * 0.21, quantity * 4.17)``, campos del producto
o de su unidad de medida). La fórmula se valida por AST (``tools/
formula_utils.py``, ya portado) antes de evaluarse con ``safe_eval`` — nunca
con el ``eval`` desnudo de Python.

Diez símbolos, nueve funcionales y uno GAP declarado
====================================================

Diez símbolos en ``models/account_tax.py`` de la referencia (3 campos + 7
métodos, ``grep -cE "^    [a-z_]+ *= *fields\.|^    def " account_tax.py`` →
10), con su destino en este addon:

- ``amount_type`` (``selection_add``) — ``add_code_amount_type``.
- ``formula`` (campo) — ``AccountTaxFormula.formula``.
- ``formula_decoded_info`` (compute, no store) —
  ``AccountTaxFormula.formula_decoded_info`` (``@property``).
- ``_check_amount_type_code_formula`` (constrains) —
  ``AccountTaxFormula.clean``.
- ``_eval_taxes_computation_prepare_product_fields`` y
  ``_eval_taxes_computation_prepare_product_uom_fields`` — extensión
  encadenada con la base de ``account`` en ``account_tax_extensions.py``.
- ``_compute_formula_decoded_info`` — fusionado en la ``@property`` de
  arriba.
- ``_check_and_normalize_formula`` —
  ``AccountTaxFormula._check_and_normalize_formula``.
- ``_eval_tax_amount_formula`` —
  ``AccountTaxFormula._eval_tax_amount_formula``.
- ``_eval_tax_amount_fixed_amount`` (EXTENDS) — extensión en
  ``account_tax_extensions.py``.

Por qué es una tabla satélite (OneToOne), no un campo en ``AccountTax``
==========================================================================

Este ORM es Django puro (``import fields``/``import models`` son alias del
vocabulario Odoo — ver ``orm/models.py``): no tiene ``_inherit``. Django
**sí** permite colgar un campo real en un modelo de otro addon con
``Modelo.add_to_class(nombre, campo)`` desde ``AppConfig.ready()``
—precedente exacto: ``l10n_mx: models/account_tax.py`` cuelga
``l10n_mx_factor_type``/``l10n_mx_tax_type`` sobre ``account.AccountTax``
así—, pero ese mecanismo generó su migración en
``account/migrations/0016_accounttax_l10n_mx_factor_type_and_more.py``: el
``AddField`` de una migración pertenece SIEMPRE a la app de su propio
archivo (Django resuelve ``model_name`` contra el ``app_label`` de la
migración, no contra dónde vive el ``models.py`` que declaró el campo en
Python). Persistir ``formula`` exige entonces una migración en
``account/migrations/`` — fuera del alcance de este porte ("no tocar ningún
otro addon"). Se modela como tabla satélite propia (``AccountTaxFormula``,
``OneToOne`` a ``account.AccountTax``), el mismo criterio que
``account_add_gln.PartnerGln`` ya fijó para el mismo problema sin campo
nuevo que exigiera tocar la tabla ajena.

``amount_type`` incluye ``'code'`` — cerrado
=============================================

La referencia lo amplía con ``selection_add`` y la política
``{'code': …}`` que pasa el impuesto a porcentaje y lo archiva
(``odoo19c: account_tax_python/models/account_tax.py:15-18``). Aquí lo hace
``add_code_amount_type`` (``account_tax_extensions.py``) con
``extend_selection_choices``, desde ``ready()``. Hacía falta: desde que
``Selection`` es la clase de la referencia, escribir ``'code'`` sin la
ampliación levanta ``ValueError('Wrong value for …')``, igual que allá. Antes
pasaba porque Django sólo comprueba ``choices`` en ``full_clean``.

El contexto de evaluación con ``product``/``uom`` — cerrado
============================================================

``AccountTaxQuerySet._get_tax_details`` recibe ``product=``/``product_uom=`` y
llena ``evaluation_context['product']``/``['uom']`` con
``_eval_taxes_computation_turn_to_product_values``/``_uom_values``
(``odoo19c: account_tax.py:731-895``), portados en ``account``; ``compute_all``
le pasa su ``product``. Este addon extiende los dos ganchos de campos
encadenando con la base (``account_tax_extensions.py``), y las fórmulas que
leen ``product.*`` corren por ``compute_all``. El sustituto local que armaba
ese contexto a mano (``build_evaluation_context``) se retiró.

Lo que sigue vigente: sin producto en el contexto, el fallo llega como
``KeyError`` del propio ``eval``, no del guard. El
``assert accessed_fields['product'] <= formula_context['product'].keys()``
**está muerto** — ``accessed_fields`` es un ``defaultdict`` con claves
``'product.product'``/``'uom.uom'`` (``formula_utils.py:60,64``) y el
``assert`` lee ``['product']``, así que siempre compara el conjunto vacío.
El puerto es fiel: la referencia tiene la misma discordancia entre
``odoo19c: account_tax.py:62-63`` (escribe) y ``:105-106`` (lee). Se
documenta en vez de "arreglarlo" en silencio porque divergir del guard de
la referencia es una decisión, no una corrección. Ver :ref:`h-api-365`.

Divergencia declarada — Decimal en la frontera, float dentro de la fórmula
=============================================================================

``account: AccountTaxQuerySet`` opera en ``Decimal`` (ver el docstring de
ese archivo: *"la referencia calcula en float... aquí todo el motor opera
en Decimal"*). La fórmula de ``account_tax_python``, en cambio, hace el
``json.loads(json.dumps(...))`` de la referencia — un ``Decimal`` no es
JSON-serializable, así que pasarlo tal cual rompería CUALQUIER fórmula con
``TypeError``. La conversión Decimal↔float vive en el monkeypatch de
``account_tax_extensions.py`` (frontera de integración, no símbolo propio
de ``account_tax_python``): ``_eval_tax_amount_formula`` en sí queda fiel a
la referencia, recibiendo y evaluando en ``float``/``int`` puros.
"""
import json

from exceptions import ValidationError
from tools.translate import _

import fields
import models
from addons.account_tax_python.tools.formula_utils import (
    check_formula,
    normalize_formula,
)
from addons.product.models.product_product import ProductProduct
from addons.uom.models.uom_uom import Uom
from django.core.exceptions import FieldDoesNotExist

#: Mapeo modelo Odoo (string, el que usa ``ProductUomFieldRewriter``) → clase
#: Django real de este árbol. Sustituye a ``self.env[model]`` de la
#: referencia (aquí no hay registro de env; se resuelve por import directo,
#: igual que ``product_template.py`` importa ``Uom`` de ``addons.uom``).
_SERIALIZABLE_MODELS = {
    'product.product': ProductProduct,
    'uom.uom': Uom,
}

#: Builtins disponibles al evaluar una fórmula ya validada por AST — vacíos
#: salvo ``min``/``max`` (los únicos ``_ALLOWED_FUNCS`` de
#: ``tools/formula_utils.py``). Sin ``__builtins__`` reales: nada de
#: ``__import__``/``open``/etc.
_SAFE_GLOBALS = {'__builtins__': {}, 'min': min, 'max': max}


def _safe_eval(formula, formula_context):
    """Evalúa ``formula`` (ya validada por AST) contra ``formula_context``.

    Reemplaza ``from odoo.tools.safe_eval import safe_eval`` de la
    referencia. ``api: src/tools/safe_eval.py`` de este árbol es una
    adaptación MÁS ESTRECHA —su propio docstring lo declara: *"el único
    consumidor es ir.rule"*, acotada a la forma de un dominio (listas/tuplas
    de leaves)— y ampliarla es tocar un módulo compartido fuera de
    ``account_tax_python/`` (fuera de este alcance). Como
    ``tools.formula_utils.check_formula`` YA validó el AST completo contra
    la misma whitelist que la fuente (nodos, nombres, llamadas), evaluar con
    ``compile()``/``eval()`` con builtins vacíos es seguro y equivalente:
    el AST no puede contener nada fuera de aritmética, comparaciones,
    booleanos y ``min``/``max``.
    """
    try:
        codigo = compile(formula, '<tax_formula>', 'eval')
    except (SyntaxError, ValueError, TypeError) as exc:
        raise ValidationError(_('Fórmula inválida')) from exc
    return eval(codigo, _SAFE_GLOBALS, formula_context)  # noqa: S307 — AST ya validado


class AccountTaxFormula(models.Model):
    """Fórmula Python de un impuesto — ≙ los campos ``formula``/
    ``formula_decoded_info`` que la referencia agrega a ``account.tax``.

    Existe UN registro por impuesto que usa ``amount_type == 'code'`` — la
    tabla satélite es la forma de este ORM de decir "este impuesto usa una
    fórmula Python", donde la referencia lo dice con dos campos sueltos
    sobre la misma fila.
    """

    tax = models.OneToOneField(
        'account.AccountTax', on_delete=models.CASCADE,
        related_name='formula_record',
        help_text='Impuesto al que pertenece esta fórmula (Odoo _inherit '
                  'account.tax vía los campos formula/formula_decoded_info).'
                  ' OneToOne: un impuesto tiene a lo sumo una fórmula — '
                  'mismo criterio que account_add_gln.PartnerGln.partner.',
    )
    formula = fields.Text(
        default='price_unit * 0.10',
        help_text='Calcula el monto del impuesto (Odoo formula).\n\n'
                  ':param base: float, monto real sobre el que se aplica el impuesto\n'
                  ':param price_unit: float\n'
                  ':param quantity: float\n'
                  ':param product: un objeto que representa el producto\n',
    )

    class Meta:
        db_table = 'account_tax_python_formula'
        verbose_name = 'Fórmula de impuesto (Python)'
        verbose_name_plural = 'Fórmulas de impuesto (Python)'

    def __str__(self) -> str:
        return f'{self.tax}: {self.formula}'

    # -- validación -----------------------------------------------------

    def clean(self):
        """≙ ``_check_amount_type_code_formula`` (``@api.constrains``).

        Sólo valida cuando el impuesto vinculado usa ``amount_type ==
        'code'`` — igual que la fuente: una fórmula "dormida" (impuesto en
        otro ``amount_type``, texto obsoleto en el campo) no bloquea el
        guardado.
        """
        if self.tax.amount_type == 'code':
            self._check_and_normalize_formula(self.formula)

    @staticmethod
    def _check_and_normalize_formula(formula):
        """≙ ``_check_and_normalize_formula`` (``@api.model``).

        Verifica que la fórmula pase el chequeo mínimo que garantiza la
        compatibilidad entre la evaluación en Python y en JavaScript de la
        referencia. Aquí no hay evaluación JS que mantener consistente —el
        chequeo AST se conserva igual porque es lo que hace segura la
        evaluación, no sólo lo que las mantenía sincronizadas.
        """
        def is_field_serializable(model, field_name):
            assert isinstance(field_name, str), (
                'El nombre del campo debe ser una cadena')
            model_cls = _SERIALIZABLE_MODELS.get(model)
            if model_cls is None:
                return False
            try:
                field = model_cls._meta.get_field(field_name)
            except FieldDoesNotExist:
                return False
            return not field.is_relation

        transformed_formula, accessed_fields = normalize_formula(
            (formula or '0.0').strip(),
            field_predicate=is_field_serializable,
        )
        check_formula(transformed_formula)
        return transformed_formula, accessed_fields

    # -- lectura ----------------------------------------------------------

    @property
    def formula_decoded_info(self):
        """≙ ``formula_decoded_info`` / ``_compute_formula_decoded_info``
        (``:28``, ``:51-64``).

        ``fields.Json``, compute, no
        almacenado — de ahí la ``@property`` en vez de una columna, mismo
        criterio que ``account: account_bank_statement_line.py`` documenta
        para computes sin ``store=True``).
        """
        if self.tax.amount_type != 'code':
            return None
        py_formula, accessed_fields = self._check_and_normalize_formula(
            self.formula)
        return {
            'js_formula': py_formula,
            'py_formula': py_formula,
            'product_fields': list(accessed_fields['product.product']),
            'product_uom_fields': list(accessed_fields['uom.uom']),
        }

    # -- evaluación ---------------------------------------------------------

    def _eval_tax_amount_formula(self, raw_base, evaluation_context):
        """≙ ``_eval_tax_amount_formula``. Evalúa la fórmula de este
        impuesto.

        :param raw_base: float — el monto base (≙ ``raw_base`` de la
            referencia; aquí SIEMPRE ``float``, ver la divergencia Decimal
            declarada en el docstring del módulo).
        :param evaluation_context: dict con ``price_unit``/``quantity``
            (obligatorios) y opcionalmente ``product``/``uom`` (dicts de
            campos ya resueltos, como los arma ``_get_tax_details``).
        :return: el monto base del impuesto (float).
        """
        normalized_formula, accessed_fields = self._check_and_normalize_formula(
            self.formula_decoded_info['py_formula'])

        formula_context = {
            'price_unit': evaluation_context['price_unit'],
            'quantity': evaluation_context['quantity'],
            'product': evaluation_context.get('product', {}),
            'uom': evaluation_context.get('uom', {}),
            'base': raw_base,
        }
        assert accessed_fields['product'] <= formula_context['product'].keys(), (
            'los campos de producto usados en la fórmula deben estar '
            'presentes en el dict de producto')
        assert accessed_fields['uom'] <= formula_context['uom'].keys(), (
            'los campos de uom usados en la fórmula deben estar presentes '
            'en el dict de producto')
        try:
            formula_context = json.loads(json.dumps(formula_context))
        except TypeError:
            raise ValidationError(_(
                'Sólo se permiten tipos primitivos en el contexto de la '
                'fórmula de impuesto Python.'))
        try:
            return _safe_eval(normalized_formula, formula_context)
        except ZeroDivisionError:
            return 0.0
