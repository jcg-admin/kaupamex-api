r"""``account.tax`` — impuesto con fórmula Python (Odoo ``account_tax_python``).

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

Diez símbolos en ``models/account_tax.py`` de la referencia (3 campos + 7
métodos, ``grep -cE "^    [a-z_]+ *= *fields\.|^    def " account_tax.py`` →
10); nueve se portan funcionales, uno queda GAP declarado
==============================================================================

============================================  =========================================
Símbolo                                         Destino en este archivo
============================================  =========================================
``amount_type`` (``selection_add``)             GAP declarado — ver abajo
``formula`` (campo)                             ``AccountTaxFormula.formula``
``formula_decoded_info`` (compute, no store)    ``AccountTaxFormula.formula_decoded_info`` (``@property``)
``_check_amount_type_code_formula`` (constrains)``AccountTaxFormula.clean``
``_eval_taxes_computation_prepare_product_fields``  monkeypatch en ``account_tax_extensions.py``
``_eval_taxes_computation_prepare_product_uom_fields`` monkeypatch en ``account_tax_extensions.py``
``_compute_formula_decoded_info``               fusionado en la ``@property`` de arriba
``_check_and_normalize_formula``                ``AccountTaxFormula._check_and_normalize_formula``
``_eval_tax_amount_formula``                     ``AccountTaxFormula._eval_tax_amount_formula``
``_eval_tax_amount_fixed_amount`` (EXTENDS)      monkeypatch en ``account_tax_extensions.py``
============================================  =========================================

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

GAP declarado — ``amount_type`` no incluye ``'code'``
=========================================================

``account.AccountTax.AMOUNT_TYPES`` es una lista literal dentro de
``account/models/account_tax.py`` (``choices=AMOUNT_TYPES`` en la propia
declaración del campo) — agregar ``('code', 'Fórmula personalizada')``
requiere editar esa lista en el archivo de OTRO addon. Verificado que la
ausencia de ``'code'`` en ``AMOUNT_TYPES`` **no bloquea** el resto del
mecanismo: Django no valida ``choices`` en ``.save()`` (sólo en
``full_clean()``/``ModelForm``, que este proyecto no invoca automáticamente
— mismo patrón ya visto en ``account: models/account_cash_rounding.py``), y
no hay ``CheckConstraint`` de BD sobre la columna (``grep -n "amount_type"
account/migrations/*.py | grep -i constraint`` → 0 hits). Así que un
``AccountTax(amount_type='code', ...)`` se persiste sin problema, y el
monkeypatch de ``_eval_tax_amount_fixed_amount`` (``account_tax_extensions.
py``) lo reconoce y despacha a la fórmula — el mecanismo corre de punta a
punta a través de ``compute_all()`` real.

Lo único que NO mutar en caliente: la lista ``AMOUNT_TYPES`` en sí (usada
por ``choices=`` de Django para formularios/admin/``drf-spectacular``,
congelada en el objeto ``Field`` al momento en que ``account`` definió la
clase). Mutar la lista de clase en runtime no reescribe ese ``Field`` ya
construido — habría sido un arreglo cosmético que aparenta cerrar el GAP sin
cerrarlo. **Sucesor exacto, de una línea**: agregar
``('code', 'Fórmula personalizada')`` a ``AMOUNT_TYPES`` en
``account/models/account_tax.py:497-502`` — sin migración (``max_length=12``
ya alcanza para ``'code'``, 4 caracteres; ``choices`` no es columna de BD).

GAP declarado — el motor base no arma ``evaluation_context['product']``/``['uom']``
=======================================================================================

``AccountTaxQuerySet._get_tax_details``/``compute_all`` (``account/models/
account_tax.py``) no aceptan ``product=``/``product_uom=`` y su ``contexto``
sólo trae ``price_unit``/``quantity`` — nunca ``product``/``uom``. La
referencia los arma con ``_eval_taxes_computation_turn_to_product_values``/
``_uom_values`` (``odoo19c: account_tax.py:733-890``), que viven en
``account``, no en ``account_tax_python``, y **tampoco están portados**
ahí. Consecuencia medida:

- Fórmulas que sólo usan ``price_unit``/``quantity``/``base``
  (``"price_unit * 0.10"``, ``"max(quantity * price_unit * 0.21, quantity *
  4.17)"``) corren de punta a punta vía ``AccountTax.taxes.all().
  compute_all(...)`` real — verificado en
  ``tests/unit/account_tax_python/test_taxes_computation.py``.
- Fórmulas que referencian ``product.*``/``uom.*`` **no** pueden invocarse
  vía ``compute_all()`` hasta que ese GAP se cierre en ``account``. El fallo
  llega como ``KeyError`` del propio ``eval``, no del guard: el
  ``assert accessed_fields['product'] <= formula_context['product'].keys()``
  **está muerto** — ``accessed_fields`` es un ``defaultdict`` con claves
  ``'product.product'``/``'uom.uom'`` (``formula_utils.py:60,64``) y el
  ``assert`` lee ``['product']``, así que siempre compara el conjunto vacío.
  El puerto es fiel: la referencia tiene la misma discordancia entre
  ``odoo19c: account_tax.py:62-63`` (escribe) y ``:105-106`` (lee). Se
  documenta en vez de "arreglarlo" en silencio porque divergir del guard de
  la referencia es una decisión, no una corrección. Ver :ref:`h-api-365`.
  Se invocan **directamente** con
  ``AccountTaxFormula.build_evaluation_context(...)`` (agregado local, no es
  un símbolo de la referencia — ver su docstring).

**Sucesor para ``account``**: agregar ``product=None, product_uom=None`` a
``_get_tax_details``/``compute_all`` y dos líneas que llenen
``contexto['product']``/``contexto['uom']`` usando los hooks
``_eval_taxes_computation_prepare_product_fields``/``_uom_fields`` que este
addon YA agrega (monkeypatch en ``account_tax_extensions.py`` — sin
``super()`` porque no existían antes). Bajo riesgo: parámetros opcionales
con default ``None``, retrocompatible con todo llamador actual.

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
            campos ya resueltos — ver ``build_evaluation_context`` si no se
            invoca a través de ``compute_all()``).
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

    # -- helper local, NO es un símbolo de la referencia --------------------

    @classmethod
    def build_evaluation_context(cls, price_unit, quantity, product=None,
                                  product_uom=None, product_fields=(),
                                  uom_fields=()):
        """Arma el ``evaluation_context`` para invocar
        ``_eval_tax_amount_formula`` DIRECTAMENTE, fuera de
        ``compute_all()`` (ver el GAP "el motor base no arma
        evaluation_context['product']/['uom']" en el docstring del módulo).

        Esto NO es un símbolo de ``account_tax_python`` — su equivalente
        (``_eval_taxes_computation_turn_to_product_values``/``_uom_values``)
        vive en ``account/models/account_tax.py`` de la referencia y no
        está portado ahí. Se agrega aquí, acotado a lo que este addon
        necesita para ser invocable y testeable con datos reales de
        producto/uom, sin inventar el mecanismo completo de la referencia
        (que resuelve valores por defecto por tipo de campo — aquí basta
        con leer el atributo del objeto o usar ``0``).
        """
        product_values = {}
        for field_name in product_fields:
            product_values[field_name] = (
                getattr(product, field_name) if product is not None else 0)
        uom_values = {}
        for field_name in uom_fields:
            uom_values[field_name] = (
                getattr(product_uom, field_name) if product_uom is not None
                else 0)
        return {
            'price_unit': price_unit,
            'quantity': quantity,
            'product': product_values,
            'uom': uom_values,
        }
