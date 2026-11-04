"""``account.tax`` — impuesto y su **motor de cálculo** (Odoo ``account``).

Adaptación de ``addons/account/models/account_tax.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``).

El motor, no sólo el modelo
============================

Hasta H-API-340 este archivo declaraba el modelo y un ``compute_amount`` que
calcula **un** impuesto sobre **una** base. Eso no alcanza para una línea real:
un producto puede llevar varios impuestos, unos incluidos en el precio y otros
no, unos que afectan la base de los siguientes y otros que no. Resolver eso es
lo que la referencia llama ``compute_all``, y su motor de verdad es
``_get_tax_details`` (``odoo19c: account_tax.py:1139``) — el mismo que usa la
tubería de facturación por dentro (``_add_tax_details_in_base_line:1766`` lo
invoca).

Aquí se porta **ese motor**, con sus tres pasadas y su propagación de base. Lo
que queda fuera es la **envoltura** de base-lines, no el cálculo: ver
"Qué no se porta" abajo.

Las tres pasadas, y por qué son tres
=====================================

El orden no es estilístico: cada pasada necesita el resultado de la anterior.

1. **Fijos, en orden descendente.** Un impuesto fijo puede afectar la base de
   un lote incluido-en-precio que va justo después, así que su importe debe
   conocerse antes. Ejemplo de la referencia: ``t1`` fijo de 1 con
   ``include_base_amount``, ``t2`` 21 % incluido; sobre 121, la base de ``t1``
   sale de 121/1.1 = 110, y para calcular la de ``t2`` hay que volver a sumar
   el importe de ``t1``.
2. **Incluidos en precio, en orden descendente.** Se extraen del total: el
   último declarado es el más externo, así que se descuenta primero.
3. **Excluidos, en orden ascendente.** Se suman sobre la base ya limpia.

Entre pasada y pasada, ``_propagate_extra_taxes_base`` reparte el importe de
cada impuesto como ``extra_base`` de los demás según cuatro casos
(``price_include`` × ``special_mode``), portados verbatim de
``odoo19c: account_tax.py:978-1083``.

Lotes (*batches*) — por qué no basta con recorrer impuestos
============================================================

Dos impuestos porcentuales incluidos en el precio **no** se extraen uno tras
otro: se extraen **juntos**, contra la suma de sus tasas. Con 10 % y 6 %
incluidos sobre 116, la base es 116/1.16 = 100, no 116/1.1/1.06 = 99,45. Por
eso ``_batch_for_taxes_computation`` agrupa los consecutivos que comparten
``amount_type``, ``price_include`` e ``include_base_amount``, y
``_eval_tax_amount_price_included`` divide entre ``1 + Σ tasas del lote``.

El motor vive en el QuerySet, no en la instancia
=================================================

En la referencia ``compute_all`` es un método de **recordset**: se llama sobre
el conjunto de impuestos de la línea. El equivalente exacto en este ORM es un
``QuerySet`` a medida, de modo que::

    producto.taxes.all().compute_all(precio)

lee igual que su original. Los tres evaluadores por impuesto
(``_eval_tax_amount_*``) sí son de instancia, como allá.

Divergencia declarada: ``Decimal``, no ``float``
=================================================

La referencia calcula en ``float`` y redondea con ``float_round``. Aquí todo
el motor opera en ``Decimal`` y redondea con ``quantize``. Es la convención
medida de este árbol —``fields.Monetary`` es ``DecimalField``— y la razón es
la de siempre: un ``float`` binario no representa ``0.10`` exactamente, y en
un motor que suma decenas de importes por factura eso se acumula. Mismo
criterio ya declarado en ``product_template.py`` (H-API-168).

Consecuencia práctica: los importes de este motor son **comparables** con los
de ``SaleOrderLine`` y ``AccountMoveLine``, que ya son ``Decimal``. Con
``float`` habría que decidir dónde se convierte, y esa frontera es donde
aparecen los descuadres de un centavo.

Qué no se porta, con su medición
=================================

- **La mitad contable de la envoltura de base-lines** —
  ``_add_accounting_data_to_base_line_tax_details`` y
  ``_add_accounting_data_in_base_lines_tax_details`` (``:2368-2510``)—. No es
  cálculo: es el sobre que lleva el resultado a la contabilidad (cuenta
  destino por línea de reparto, etiquetas CABA, agrupación por
  ``account.tax.group``).

  La mitad de cálculo **sí** está, y produce la estructura que la agregación
  consume: ``_prepare_base_line_for_taxes_computation`` (``:1593``),
  ``_add_tax_details_in_base_line`` (``:1737``), el reparto del delta
  (``:1824-1893``), el redondeo contractual de los cuatro
  ``_round_*`` (``:1895-2293``) y la agregación
  ``_aggregate_base_line_tax_details``,
  ``_aggregate_base_lines_tax_details`` y
  ``_aggregate_base_lines_aggregated_values`` (``:2512-2712``). El motor es el
  mismo a ambos lados: ``_add_tax_details_in_base_line`` llama a
  ``base_line['tax_ids']._get_tax_details(...)`` (``odoo19c: :1766``).
- **``special_mode`` completo.** Se portan los tres valores
  (``False``/``'total_included'``/``'total_excluded'``) porque la propagación
  de base los necesita; lo que no se porta es su entrada por
  ``env.context['force_price_include']``, que es un canal de Odoo sin análogo.
- **``has_negative_factor`` / cargo revertido.** La referencia duplica cada
  impuesto con factor negativo en un segundo apunte
  (``reverse_charge_taxes_data``). Aquí se **detecta** —la propiedad existe y
  lee las líneas de reparto— pero no se duplica el importe: eso pertenece al
  reparto contable, que es la envoltura de arriba. Declarado en H-API-342.
- **``analytic``, ``tax_exigibility``, ``tag_ids`` en el resultado.** Salen del
  reparto, no del cálculo. El dict de ``compute_all`` los omite en vez de
  devolverlos en cero, que sería peor: un cero se lee como dato.

Los M2M de sustitución — ``original_tax_ids``/``replacing_tax_ids`` (H-API-322)
=================================================================================

Portados enteros: ambas direcciones de la relación ``account_tax_alternatives``
(``odoo19c: :102-121``). Sin ellos ``AccountFiscalPosition._compute_tax_map``
devolvía ``{}`` **siempre** — la rama de sustitución de ``map_tax`` (cambiar el
impuesto A por B) quedaba inerte aunque el resto del método (identidad y
filtro por universales) funcionara. Ver
``docs: hallazgo-H-API-322-mapa-de-impuestos-inerte.rst``.

La referencia declara los dos M2M como campos independientes de
``AccountTax``, ambos leyendo la MISMA tabla ``account_tax_alternatives``
en direcciones opuestas (``dest_tax_id``/``src_tax_id`` invertidos) — es el
patrón Odoo de un M2M "de ida" más su reverso explícito (``readonly=True``)
en vez de dejarlo implícito. El M2M "simple" de este ORM (el que ya usa
``children``, una sola dirección con ``db_table``) no alcanza para expresar
dos campos sobre el mismo par de columnas: hace falta un ``through`` explícito
con ``through_fields`` para desambiguar qué FK es "origen" y cuál "destino"
en cada dirección. Por eso aparece ``AccountTaxAlternative`` — no es un modelo
Odoo (``account_tax_alternatives`` no tiene ``_name`` propio en la
referencia: es la tabla que Odoo autogenera *desde* el campo); es la pieza de
plomería que este ORM exige para portar fielmente las dos direcciones.

**Declarado, no portado — el ``domain=`` de selección de ``original_tax_ids``**
(``odoo19c: :108-111``: ``[('type_tax_use', '=', type_tax_use),
('is_domestic', '=', True)]``). Es una restricción de **qué aparece en el
selector del cliente web** al elegir un impuesto a reemplazar — no participa
en ``_compute_tax_map`` ni en ``map_tax``, que es el mecanismo que este pase
cierra. Este ORM no tiene cliente web ni concepto de ``domain`` declarativo
sobre un M2M: no hay dónde aplicarlo. Es divergencia de mecanismo (no hay
UI que filtrar), no una omisión del cálculo. Con ella va ``is_domestic``
(``odoo19c: :331-334``, compute sobre
``company_id.domestic_fiscal_position_id``): sólo la consume ese ``domain=``
y ``_compute_display_alternative_taxes_field`` (``:336-343``, un booleano de
UI que decide si mostrar el widget de alternativas) — ninguno de los dos
altera el resultado de ``map_tax``. Grep de consumidores dentro de
``odoo19c: account_tax.py`` de ambos: 0 usos fuera de esas dos secciones UI.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import models as django_models

import fields
import models
from orm.environments import env
from orm.models import _create_field_lookup
from tools.float_utils import float_is_zero
from tools.misc import frozendict

#: Precisión por defecto del redondeo por línea, igual que la referencia
#: (``float_round(..., precision_rounding=0.01)``).
DEFAULT_ROUNDING = Decimal('0.01')

_CIEN = Decimal('100')


def _d(valor):
    """A ``Decimal`` sin pasar por ``float`` — la conversión que corrompe."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def _round_to_digits(value, precision_digits):
    """≙ ``float_round(value, precision_digits=n)`` en ``Decimal``: mitad
    hacia fuera del cero, como la fuente."""
    return _d(value).quantize(Decimal(1).scaleb(-precision_digits),
                              rounding=ROUND_HALF_UP)


def _base_line_field_value(record, field):
    """El valor de ``field`` en ``record`` como lo lee la fuente.

    ≙ ``record[field]`` de ``_get_base_line_field_value_from_record``
    (``odoo19c: account_tax.py:1584``), que allá devuelve un registro para una
    relación. Aquí una FK se lee por su nombre de campo —no por su
    ``attname``, que da el entero—, un M2M sale como el ``QuerySet`` de sus
    registros y el resto, como el valor crudo.
    """
    if field.many_to_many:
        return getattr(record, field.name).all()
    if field.is_relation and (field.many_to_one or field.one_to_one):
        return getattr(record, field.name)
    return getattr(record, field.attname)


#: ≙ ``default_value_map`` de los dos ``*_default_values`` (``odoo19c:
#: account_tax.py:763-767, 845-849``).
_DEFAULT_VALUE_BY_TYPE = {
    'integer': 0,
    'float': 0.0,
    'monetary': 0.0,
}


def _default_values_by_type(model_name, field_names):
    """Por campo, su tipo y el valor que toma sin registro.

    El cuerpo común de los dos ``*_default_values`` de producto y de unidad:
    la fuente repite el bucle con ``product.product`` y con ``uom.uom``.
    """
    model_fields = env()[model_name]._fields
    values = {}
    for field_name in field_names:
        field = model_fields[field_name]
        values[field_name] = {
            'type': field.type,
            'default_value': _DEFAULT_VALUE_BY_TYPE[field.type],
        }
    return values


def _record_values(default_values, record):
    """≙ ``record and record[field_name] or field_info['default_value']``."""
    return {
        field_name: (getattr(record, field_name) if record else None)
        or field_info['default_value']
        for field_name, field_info in default_values.items()
    }


class AccountTaxQuerySet(models.AccessQuerySet):
    """El motor. ≙ los métodos de recordset de ``odoo19c: account.tax``.

    Un ``QuerySet`` es el análogo exacto del recordset sobre el que la
    referencia llama ``compute_all``: el conjunto de impuestos de UNA línea.

    **Divergencia de sitio, declarada (#164).** La referencia declara estos
    cinco dentro de ``AccountTax`` —``compute_all``,
    ``_batch_for_taxes_computation``, ``_flatten_taxes_and_sort_them``,
    ``_get_tax_details`` y ``_propagate_extra_taxes_base``— porque en su ORM
    ``self`` **es** el conjunto. Aquí el conjunto es el ``QuerySet``, así que
    ponerlos en el modelo obligaría a cada uno a recibir la lista de impuestos
    como argumento: la misma operación con el receptor equivocado. El gate de
    porte los reporta como ``FUERA DE SITIO`` y tiene razón en verlos; el
    veredicto es que la ubicación es correcta y lo que faltaba era decirlo.
    """

    # -- ordenamiento y aplanado -------------------------------------------

    def _flatten_taxes_and_sort_them(self):
        """≙ ``_flatten_taxes_and_sort_them`` (``odoo19c: :897``).

        Devuelve ``(ordenados, grupo_por_impuesto)``. Un impuesto de tipo
        ``group`` se sustituye por sus hijos, **en el lugar que ocupa el
        padre**: la secuencia que manda es la del grupo, no la del hijo. El
        ejemplo de la referencia lo dice entero — ``[G, B([A, D, F]), E, C]``
        se evalúa como ``[A, D, F, C, E, G]``.
        """

        def clave(tax):
            return (tax.sequence, tax.pk or 0)

        ordenados = []
        group_by_tax = {}
        for tax in sorted(self, key=clave):
            if tax.amount_type == 'group':
                hijos = sorted(tax.children.all(), key=clave)
                for hijo in hijos:
                    if hijo not in ordenados:
                        ordenados.append(hijo)
                    group_by_tax[hijo.pk] = tax
            elif tax not in ordenados:
                ordenados.append(tax)
        return ordenados, group_by_tax

    def _batch_for_taxes_computation(
        self, special_mode=False, filter_tax_function=None
    ):
        """≙ ``_batch_for_taxes_computation`` (``odoo19c: :924``).

        Agrupa los impuestos **consecutivos** que se evalúan juntos. Recorre
        en orden inverso, igual que la referencia: el corte de lote depende de
        si el impuesto *siguiente* acepta ser afectado (``is_base_affected``),
        y eso sólo se sabe viniendo desde el final.
        """
        ordenados, group_by_tax = self._flatten_taxes_and_sort_them()
        if filter_tax_function:
            ordenados = [t for t in ordenados if filter_tax_function(t)]

        lote_por_impuesto = {}
        lote = []
        base_afectada = False
        for tax in reversed(ordenados):
            if lote:
                same_batch = (
                    tax.amount_type == lote[0].amount_type
                    and (
                        special_mode
                        or tax.price_include == lote[0].price_include
                    )
                    and tax.include_base_amount == lote[0].include_base_amount
                    and (
                        (tax.include_base_amount and not base_afectada)
                        or not tax.include_base_amount
                    )
                )
                if not same_batch:
                    for miembro in lote:
                        lote_por_impuesto[miembro.pk] = lote
                    lote = []
            base_afectada = tax.is_base_affected
            lote.append(tax)
        if lote:
            for miembro in lote:
                lote_por_impuesto[miembro.pk] = lote

        return {
            'batch_per_tax': lote_por_impuesto,
            'group_per_tax': group_by_tax,
            'sorted_taxes': ordenados,
        }

    # -- propagación de base ------------------------------------------------

    @staticmethod
    def _propagate_extra_taxes_base(
        ordenados, tax, taxes_data, special_mode=False
    ):
        """≙ ``_propagate_extra_taxes_base`` (``odoo19c: :978``).

        Los cuatro casos van verbatim de la referencia. No se simplifican
        aunque dos parezcan simétricos: los comentarios de la fuente traen los
        contraejemplos que muestran que no lo son.
        """

        def antes():
            for otro in ordenados:
                if otro in taxes_data[tax.pk]['batch']:
                    break
                yield otro

        def despues():
            for otro in reversed(ordenados):
                if otro in taxes_data[tax.pk]['batch']:
                    break
                yield otro

        def sumar_base(otro, signo):
            importe = taxes_data[tax.pk]['tax_amount']
            if 'tax_amount' not in taxes_data[otro.pk]:
                taxes_data[otro.pk]['extra_base_for_tax'] += signo * importe
            taxes_data[otro.pk]['extra_base_for_base'] += signo * importe

        if tax.price_include:
            if special_mode in (False, 'total_included'):
                if tax.include_base_amount:
                    for otro in despues():
                        if not otro.is_base_affected:
                            sumar_base(otro, -1)
                else:
                    for otro in despues():
                        sumar_base(otro, -1)
                for otro in antes():
                    sumar_base(otro, -1)
            else:  # special_mode == 'total_excluded'
                if tax.include_base_amount:
                    for otro in despues():
                        if otro.is_base_affected:
                            sumar_base(otro, 1)
        else:
            if special_mode in (False, 'total_excluded'):
                if tax.include_base_amount:
                    for otro in despues():
                        if otro.is_base_affected:
                            sumar_base(otro, 1)
            else:  # special_mode == 'total_included'
                if not tax.include_base_amount:
                    for otro in despues():
                        sumar_base(otro, -1)
                for otro in antes():
                    sumar_base(otro, -1)

    # -- valores de producto y unidad (odoo19c: :731-895) ------------------
    #
    # Son métodos de recordset de ``account.tax``: aquí del ``QuerySet``. Los
    # dos ganchos de campos devuelven el conjunto vacío en ``account``;
    # ``account_tax_python`` los extiende encadenando, como su ``super()``.
    # Divergencia: el ``sudo()`` de la fuente (*"tax computation may depend
    # on restricted fields"*) no tiene sujeto aquí: una instancia de Django
    # se lee por atributo, sin regla de fila en medio.

    def _eval_taxes_computation_prepare_product_fields(self):
        """ Get the fields to create the evaluation context from the product
        for the taxes computation.

        ≙ ``:732-742``: el conjunto vacío; lo extiende quien necesita leer el
        producto (``account_tax_python``).
        """
        return set()

    def _eval_taxes_computation_prepare_product_default_values(self,
                                                               field_names):
        """ Prepare the default values for the product according the fields
        passed as parameter.

        ≙ ``:744-774``: por campo, su tipo y el valor por omisión de ese tipo
        para cuando no hay producto.
        """
        return _default_values_by_type('product.product', field_names)

    def _eval_taxes_computation_prepare_product_values(self,
                                                       default_product_values,
                                                       product=None):
        """ Convert the product passed as parameter to a dictionary to be
        passed to '_eval_taxes_computation_prepare_context'.

        ≙ ``:776-794``.
        """
        return _record_values(default_product_values, product)

    def _eval_taxes_computation_turn_to_product_values(self, product=None):
        """ Helper purely in Python to call the three product helpers all at
        once. ≙ ``:796-813``.
        """
        product_fields = self._eval_taxes_computation_prepare_product_fields()
        default_product_values = (
            self._eval_taxes_computation_prepare_product_default_values(
                product_fields))
        return self._eval_taxes_computation_prepare_product_values(
            default_product_values=default_product_values,
            product=product,
        )

    def _eval_taxes_computation_prepare_product_uom_fields(self):
        """ Get the fields to create the evaluation context from the product
        uom for the taxes computation. ≙ ``:815-826``.
        """
        return set()

    def _eval_taxes_computation_prepare_product_uom_default_values(
            self, field_names):
        """ Prepare the default values for the product uom according the
        fields passed as parameter. ≙ ``:828-856``.
        """
        return _default_values_by_type('uom.uom', field_names)

    def _eval_taxes_computation_prepare_product_uom_values(
            self, default_product_uom_values, product_uom=None):
        """ Convert the product uom passed as parameter to a dictionary.
        ≙ ``:858-876``.
        """
        return _record_values(default_product_uom_values, product_uom)

    def _eval_taxes_computation_turn_to_product_uom_values(self,
                                                           product_uom=None):
        """ Helper purely in Python to call the three uom helpers all at
        once. ≙ ``:878-895``.
        """
        product_uom_fields = (
            self._eval_taxes_computation_prepare_product_uom_fields())
        default_product_uom_values = (
            self._eval_taxes_computation_prepare_product_uom_default_values(
                product_uom_fields))
        return self._eval_taxes_computation_prepare_product_uom_values(
            default_product_uom_values=default_product_uom_values,
            product_uom=product_uom,
        )

    # -- el motor -----------------------------------------------------------

    def _get_tax_details(
        self,
        price_unit,
        quantity=1,
        precision_rounding=DEFAULT_ROUNDING,
        rounding_method='round_per_line',
        product=None,
        product_uom=None,
        special_mode=False,
        filter_tax_function=None,
    ):
        """≙ ``_get_tax_details`` (``odoo19c: :1139``). Las tres pasadas.

        Devuelve ``{'total_excluded', 'total_included', 'taxes_data'}``, donde
        cada entrada de ``taxes_data`` trae su ``tax``, su ``base`` y su
        ``tax_amount``.
        """
        price_unit = _d(price_unit)
        quantity = _d(quantity)
        redondear = rounding_method == 'round_per_line'

        lotes = self._batch_for_taxes_computation(
            special_mode=special_mode, filter_tax_function=filter_tax_function
        )
        ordenados = lotes['sorted_taxes']

        taxes_data = {}
        for tax in ordenados:
            if special_mode == 'total_included':
                price_include = True
            elif special_mode == 'total_excluded':
                price_include = False
            else:
                price_include = tax.price_include
            taxes_data[tax.pk] = {
                'tax': tax,
                'price_include': price_include,
                'extra_base_for_tax': Decimal('0'),
                'extra_base_for_base': Decimal('0'),
                'batch': lotes['batch_per_tax'][tax.pk],
                'group': lotes['group_per_tax'].get(tax.pk),
            }

        raw_base = quantity * price_unit
        if redondear:
            raw_base = raw_base.quantize(precision_rounding)

        # ≙ ``evaluation_context`` (``:1241-1246``): el producto y la unidad
        # con los campos que piden los ganchos.
        contexto = {
            'product': self._eval_taxes_computation_turn_to_product_values(
                product=product),
            'uom': self._eval_taxes_computation_turn_to_product_uom_values(
                product_uom=product_uom),
            'price_unit': price_unit,
            'quantity': quantity,
        }

        def evaluar(funcion, tax):
            if 'tax_amount' in taxes_data[tax.pk]:
                return
            importe = funcion(
                taxes_data[tax.pk]['batch'],
                raw_base + taxes_data[tax.pk]['extra_base_for_tax'],
                contexto,
            )
            if importe is None:
                return
            if redondear:
                importe = importe.quantize(precision_rounding)
            taxes_data[tax.pk]['tax_amount'] = importe
            self._propagate_extra_taxes_base(
                ordenados, tax, taxes_data, special_mode=special_mode
            )

        # Pasada 1 — fijos (descendente): pueden afectar la base del lote
        # incluido-en-precio que viene después.
        for tax in reversed(ordenados):
            evaluar(tax._eval_tax_amount_fixed_amount, tax)
        # Pasada 2 — incluidos en precio (descendente): se extraen del total.
        for tax in reversed(ordenados):
            if taxes_data[tax.pk]['price_include']:
                evaluar(tax._eval_tax_amount_price_included, tax)
        # Pasada 3 — excluidos (ascendente): se suman sobre la base limpia.
        for tax in ordenados:
            if not taxes_data[tax.pk]['price_include']:
                evaluar(tax._eval_tax_amount_price_excluded, tax)

        # Bases, en descendente: con special_mode='total_included' el orden
        # importa, y en los otros dos es indiferente — así que se usa uno solo.
        posteriores = []
        for tax in reversed(ordenados):
            datos = taxes_data[tax.pk]
            if 'tax_amount' not in datos:
                continue
            total_batch = sum(
                (
                    taxes_data[otro.pk].get('tax_amount', Decimal('0'))
                    for otro in datos['batch']
                ),
                Decimal('0'),
            )
            base = raw_base + datos['extra_base_for_base']
            if datos['price_include'] and special_mode in (
                False,
                'total_included',
            ):
                base -= total_batch
            datos['base'] = base
            datos['taxes'] = (
                list(posteriores) if tax.include_base_amount else []
            )
            if tax.is_base_affected:
                posteriores.append(tax)

        lista = [d for d in taxes_data.values() if 'tax_amount' in d]
        if lista:
            total_excluded = lista[0]['base']
            total_included = total_excluded + sum(
                (d['tax_amount'] for d in lista), Decimal('0')
            )
        else:
            total_excluded = total_included = raw_base

        # ≙ la proyección pública de la fuente (``:1320-1336``): por impuesto,
        # sólo lo que consumen la envoltura de base-lines y ``compute_all``,
        # con la base bajo ``base_amount``. El cargo revertido no se duplica
        # aquí (ver «Qué no se porta»), así que ``is_reverse_charge`` es
        # siempre ``False``; ``group`` vale ``None`` sin grupo, donde la
        # fuente pone el recordset vacío.
        return {
            'total_excluded': total_excluded,
            'total_included': total_included,
            'taxes_data': [
                {
                    'tax': datos['tax'],
                    'taxes': datos['taxes'],
                    'group': datos['group'],
                    'batch': datos['batch'],
                    'tax_amount': datos['tax_amount'],
                    'price_include': datos['price_include'],
                    'base_amount': datos['base'],
                    'is_reverse_charge': datos.get('is_reverse_charge',
                                                   False),
                }
                for datos in lista
            ],
        }

    # -- la API pública -----------------------------------------------------

    def compute_all(
        self,
        price_unit,
        currency=None,
        quantity=1,
        product=None,
        partner=None,
        is_refund=False,
        handle_price_include=True,
        rounding_method='round_per_line',
    ):
        """≙ ``compute_all`` (``odoo19c: :4960``). El contrato clásico.

        :returns: ``{'total_excluded', 'total_included', 'total_void',
                     'taxes': [{'id', 'name', 'amount', 'base', 'sequence',
                                'price_include', 'group'}]}``

        ``total_void`` es igual a ``total_excluded``, como en la referencia
        cuando ningún impuesto tiene cuenta asignada — aquí siempre, porque la
        cuenta la pone el reparto y ése es la envoltura que no se porta.

        ``currency``, ``product``, ``partner`` e ``is_refund`` se aceptan para
        preservar la firma y **no** se usan todavía: en la referencia sirven
        para el idioma del nombre, las etiquetas del producto y el reparto de
        nota de crédito, los tres en la envoltura. Aceptarlos y no usarlos es
        mejor que omitirlos —el llamador no cambia cuando lleguen— siempre que
        se diga, que es lo que hace esta línea.
        """
        special_mode = False if handle_price_include else 'total_excluded'
        precision = (
            currency.rounding if currency is not None else DEFAULT_ROUNDING
        )
        detalle = self._get_tax_details(
            price_unit,
            quantity=quantity,
            precision_rounding=_d(precision),
            rounding_method=rounding_method,
            product=product,
            special_mode=special_mode,
        )
        return {
            'total_excluded': detalle['total_excluded'],
            'total_included': detalle['total_included'],
            'total_void': detalle['total_excluded'],
            'taxes': [
                {
                    'id': d['tax'].pk,
                    'name': d['tax'].name,
                    'amount': d['tax_amount'],
                    'base': d['base_amount'],
                    'sequence': d['tax'].sequence,
                    'price_include': d['price_include'],
                    'group': d['group'],
                }
                for d in detalle['taxes_data']
            ],
        }


class AccountTaxAlternative(models.Model):
    """Tabla de sustitución de impuestos — ≙ ``account_tax_alternatives``
    (``odoo19c: account_tax.py:102-121``).

    NO es un modelo Odoo (sin ``_name`` propio en la referencia): es la tabla
    que Odoo autogenera *desde* los campos ``original_tax_ids``/
    ``replacing_tax_ids``. Se explicita aquí porque el M2M "simple" de este
    ORM sólo declara una tabla por campo, y ambos campos leen el MISMO par de
    columnas en direcciones opuestas — ``through_fields`` es la única forma
    de decir "cuál FK es el origen" por dirección.
    """

    src_tax = fields.Many2one(
        'account.AccountTax',
        null=False, on_delete=models.CASCADE,
        related_name='+',
        help_text='Impuesto doméstico a reemplazar (Odoo src_tax_id).',
    )
    dest_tax = fields.Many2one(
        'account.AccountTax',
        null=False, on_delete=models.CASCADE,
        related_name='+',
        help_text=(
            'Impuesto de reemplazo — "this Replacement tax" en la '
            'referencia (Odoo dest_tax_id).'
        ),
    )

    class Meta:
        db_table = 'account_tax_alternatives'
        constraints = [
            models.UniqueConstraint(
                fields=['src_tax', 'dest_tax'],
                name='unique_account_tax_alternative',
            ),
        ]
        verbose_name = 'Alternativa de impuesto'
        verbose_name_plural = 'Alternativas de impuesto'

    def __str__(self) -> str:
        return f'{self.src_tax} → {self.dest_tax}'


class AccountTax(models.Model):
    """``account.tax`` — definición de un impuesto aplicable."""

    #: Los siete atributos de clase de la fuente
    #: (``odoo19c: account_tax.py:72-78``). Sin ``_name`` el modelo no entra
    #: en ``orm.registry.MODELS_BY_NAME`` y ``env['account.tax']`` no
    #: resuelve.
    _name = 'account.tax'
    #: ≙ ``_inherit = ['mail.thread']`` (``:73``), verbatim: nombra la
    #: extensión aunque el hilo de mensajes sobre impuestos no esté cableado.
    _inherit = ['mail.thread']
    _description = 'Tax'
    #: ≙ ``_order`` (``:75``); ``Meta.ordering`` lo expresa en Django.
    _order = 'sequence,id'
    #: ≙ ``_check_company_auto = True`` (``:76``). Sin efecto todavía, por
    #: dos razones medidas: esta clase no hereda ``CheckCompanyMixin`` (es un
    #: ``models.Model`` de Django, no ``TimeStampedModel``), que es quien lo
    #: lee al guardar; y los cinco campos ``check_company=True`` de la fuente
    #: (``tax_payable_account_id``, ``tax_receivable_account_id``,
    #: ``advance_tax_payment_account_id``, ``children_tax_ids`` y
    #: ``cash_basis_transition_account_id``) no están portados.
    _check_company_auto = True
    #: ≙ ``_rec_names_search`` (``:77``).
    _rec_names_search = ['name', 'description', 'invoice_label']
    #: ≙ ``_check_company_domain`` (``:78``); ``classmethod`` por la misma
    #: razón que en ``account.journal``: aquí se invoca sobre la clase.
    _check_company_domain = classmethod(models.check_company_domain_parent_of)

    AMOUNT_TYPES = [
        ('group', 'Grupo de impuestos'),
        ('fixed', 'Fijo'),
        ('percent', 'Porcentaje'),
        ('division', 'Porcentaje impuesto incluido'),
    ]
    TYPE_TAX_USE = [
        ('sale', 'Ventas'),
        ('purchase', 'Compras'),
        ('none', 'Ninguno'),
    ]

    objects = AccountTaxQuerySet.as_manager()

    name = fields.Char(
        max_length=255,
        help_text='Nombre del impuesto (Odoo name, requerido).',
    )
    amount = fields.Monetary(
        max_digits=16,
        decimal_places=4,
        default=Decimal('0.0'),
        help_text='Monto/porcentaje del impuesto (Odoo amount).',
    )
    amount_type = fields.Selection(
        max_length=12,
        choices=AMOUNT_TYPES,
        default='percent',
        help_text='Forma de cómputo (Odoo amount_type, requerido).',
    )
    #: ≙ ``description = fields.Html(string='Description',
    #: translate=html_translate)`` (``odoo19c: :134``). ``translate`` no se
    #: declara: ``tools.translate.html_translate`` no está portado (0
    #: definiciones) y el almacenamiento por idioma que esa llamada sirve
    #: tampoco existe (ver el aviso de ``fields.Char`` en
    #: ``orm/fields_textual.py``). Se declara en cuanto exista ese
    #: almacenamiento.
    description = fields.Html(string='Description', blank=True, null=True)
    #: ≙ ``invoice_label`` (``:135``); ``translate=True`` queda anotado en el
    #: campo, como en los demás ``Char`` traducibles del árbol.
    invoice_label = fields.Char(string='Label on Invoices', translate=True,
                                max_length=255, blank=True, null=True)
    type_tax_use = fields.Selection(
        max_length=12,
        choices=TYPE_TAX_USE,
        default='sale',
        help_text='Uso del impuesto (Odoo type_tax_use, requerido).',
    )
    price_include = fields.Boolean(
        default=False,
        help_text=(
            'Precio con impuesto incluido (Odoo price_include). En la '
            'referencia es un compute sobre price_include_override + '
            'company_price_include; aquí es el booleano directo.'
        ),
    )
    sequence = fields.Integer(
        default=1,
        db_index=True,
        help_text=(
            'Orden de aplicación de los impuestos de una línea (Odoo '
            'sequence). NO es decorativo: el motor evalúa por este '
            'orden y de él dependen los lotes.'
        ),
    )
    include_base_amount = fields.Boolean(
        default=False,
        help_text=(
            'Afecta la base de los impuestos posteriores (Odoo '
            'include_base_amount).'
        ),
    )
    is_base_affected = fields.Boolean(
        default=True,
        help_text=(
            'Su base puede ser afectada por impuestos anteriores (Odoo '
            'is_base_affected).'
        ),
    )
    children = fields.Many2many(
        'account.AccountTax',
        blank=True,
        symmetrical=False,
        related_name='parent_taxes',
        db_table='account_tax_filiation_rel',
        help_text=(
            'Sub-impuestos cuando amount_type=group (Odoo '
            'children_tax_ids). symmetrical=False: la relación es '
            'dirigida, padre → hijos.'
        ),
    )
    active = fields.Boolean(
        default=True,
        help_text='Impuesto activo (Odoo active).',
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=False, on_delete=models.CASCADE,
        related_name='taxes',
        help_text='Empresa (Odoo company_id).',
    )
    tax_group = fields.Many2one(
        'account.AccountTaxGroup',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='taxes',
        help_text=(
            'Grupo al que pertenece el impuesto (Odoo tax_group_id); '
            'agrupa los subtotales del documento.'
        ),
    )
    original_tax_ids = fields.Many2many(
        'account.AccountTax',
        through='account.AccountTaxAlternative',
        through_fields=('dest_tax', 'src_tax'),
        related_name='+',
        blank=True,
        verbose_name='Reemplaza a',
        help_text=(
            'Impuestos que ESTE reemplaza al aplicar cualquiera de las '
            'posiciones fiscales estipuladas (Odoo original_tax_ids, '
            'string "Replaces"). Es la mitad de escritura del mecanismo '
            'de sustitución: sin ella, '
            'AccountFiscalPosition._compute_tax_map devuelve siempre '
            '{} (H-API-322).'
        ),
    )
    replacing_tax_ids = fields.Many2many(
        'account.AccountTax',
        through='account.AccountTaxAlternative',
        through_fields=('src_tax', 'dest_tax'),
        related_name='+',
        editable=False,
        verbose_name='Reemplazado por',
        help_text=(
            'Reverso de original_tax_ids: impuestos que reemplazan a '
            'ESTE (Odoo replacing_tax_ids, string "Replaced by", '
            'readonly=True en la referencia — de ahí editable=False).'
        ),
    )

    class Meta:
        db_table = 'account_tax'
        ordering = ['sequence', 'id']
        verbose_name = 'Impuesto'
        verbose_name_plural = 'Impuestos'

    def __str__(self) -> str:
        return f'{self.name} ({self.amount})'

    @property
    def has_negative_factor(self):
        """≙ ``_compute_has_negative_factor`` (``odoo19c: :508``).

        Marca el cargo revertido. Se **detecta**; su efecto (duplicar el
        importe con signo opuesto) pertenece al reparto contable, que es la
        envoltura no portada. Ver H-API-342.
        """
        return self.repartition_lines.filter(factor__lt=0).exists()

    # -- los tres evaluadores, uno por pasada -------------------------------

    def _eval_tax_amount_fixed_amount(self, batch, raw_base, contexto):
        """≙ ``_eval_tax_amount_fixed_amount`` (``odoo19c: :1084``).

        Devuelve ``None`` si este impuesto no es fijo — es la señal de "aún no
        me toca", no un cero. Un cero lo daría por evaluado y las pasadas 2 y
        3 lo saltarían.
        """
        if self.amount_type != 'fixed':
            return None
        signo = Decimal('-1') if contexto['price_unit'] < 0 else Decimal('1')
        return signo * contexto['quantity'] * _d(self.amount)

    def _eval_tax_amount_price_included(self, batch, raw_base, contexto):
        """≙ ``_eval_tax_amount_price_included`` (``odoo19c: :1099``).

        El lote entero se extrae de una vez: dos porcentajes incluidos del
        10 % y 6 % sobre 116 dan base 100, no 99,45.
        """
        if self.amount_type == 'percent':
            total = sum((_d(t.amount) for t in batch), Decimal('0')) / _CIEN
            factor = (
                Decimal('1') / (Decimal('1') + total)
                if total != Decimal('-1')
                else Decimal('0')
            )
            return raw_base * factor * _d(self.amount) / _CIEN
        if self.amount_type == 'division':
            return raw_base * _d(self.amount) / _CIEN
        return None

    def _eval_tax_amount_price_excluded(self, batch, raw_base, contexto):
        """≙ ``_eval_tax_amount_price_excluded`` (``odoo19c: :1119``)."""
        if self.amount_type == 'percent':
            return raw_base * _d(self.amount) / _CIEN
        if self.amount_type == 'division':
            total = sum((_d(t.amount) for t in batch), Decimal('0')) / _CIEN
            divisor = (
                Decimal('1') if total == Decimal('1') else Decimal('1') - total
            )
            return raw_base * _d(self.amount) / _CIEN / divisor
        return None

    def compute_amount(self, base_amount):
        """Impuesto de UN ``base_amount`` — atajo de un solo impuesto.

        Delega en los mismos evaluadores que usa ``compute_all``, con el lote
        reducido a ``[self]``, así que el atajo y el motor **no pueden
        divergir**: si mañana cambia una fórmula, cambia en un solo sitio.
        Lo que el atajo sigue sin ver es lo que depende de haber más de un
        impuesto — lotes de dos porcentuales incluidos,
        ``include_base_amount``,
        propagación de base. Para una línea real, ``compute_all``.

        **``division`` cambió de semántica aquí (H-API-342).** Antes calculaba
        ``base - base/(1+amount/100)``, que es la extracción de un *porcentaje*
        incluido en precio, no lo que la referencia entiende por ``division``
        (``odoo19c: :88-95``: *"e.g 180 / (1 - 10%) = 200 (not price included);
        e.g 200 * (1 - 10%) = 180 (price included)"*). El resultado viejo
        coincidía con el nuevo sólo cuando ``amount`` era 0.

        **Y ahora honra ``price_include``**, que antes ignoraba: un 16 %
        marcado
        como incluido devuelve el impuesto *contenido* en el precio, no un 16 %
        añadido encima. Es la diferencia entre las dos ramas de la referencia
        (``:1110`` vs ``:1130``), y confundirlas era el defecto de fondo.
        """
        base = _d(base_amount)
        if self.amount_type == 'fixed':
            return _d(self.amount)
        contexto = {'price_unit': base, 'quantity': Decimal('1')}
        if self.price_include:
            monto = self._eval_tax_amount_price_included(
                [self], base, contexto
            )
        else:
            monto = self._eval_tax_amount_price_excluded(
                [self], base, contexto
            )
        return monto if monto is not None else Decimal('0')

    # -- preparación de la base-line (odoo19c: :1430-1691) -----------------
    #
    # Divergencia de forma, común a las tres: la fuente lee
    # ``record[field]`` con sus nombres (``product_id``, ``tax_ids``) y
    # recibe registros, y su respaldo es un recordset vacío
    # (``self.env['product.product']``) que sirve igual para uno y para
    # muchos. Aquí ``line['product_id']`` es el ``attname`` de la FK —un
    # entero— y ``line['tax_ids']`` un gestor de Django; el nombre se traduce
    # con ``_create_field_lookup``, el resolutor que el alta de registros ya
    # usa, y el valor sale como registro (FK), ``QuerySet`` (M2M) o valor
    # crudo. Sin registro, el respaldo de un campo de uno es ``None`` y el de
    # uno de muchos, el ``QuerySet`` vacío del modelo.

    @classmethod
    def _get_base_line_field_value_from_record(cls, record, field,
                                               extra_values, fallback,
                                               from_base_line=False):
        """ Helper to extract a default value for a record or something
        looking like a record.

        ≙ ``_get_base_line_field_value_from_record`` (``odoo19c:
        :1560-1590``). Mismo orden de la fuente: ``extra_values`` gana (con
        el respaldo si su valor es falso); luego el campo del registro, salvo
        con ``from_base_line``; luego la clave del diccionario; luego el
        respaldo. El ``_origin`` de la fuente no tiene equivalente que
        aplicar: una instancia leída por su descriptor ya es la fila
        guardada.
        """
        if field in extra_values:
            return extra_values[field] or fallback
        if isinstance(record, django_models.Model) and not from_base_line:
            lookup = _create_field_lookup(type(record), field)
            if lookup is not None:
                return _base_line_field_value(record, lookup[0])
            return fallback
        if isinstance(record, dict):
            return record.get(field, fallback)
        return fallback

    @classmethod
    def _import_base_line_extra_tax_data(cls, base_line, extra_tax_data):
        """ Import the 'extra_tax_data' json value into the base line passed
        as parameter.

        ≙ ``_import_base_line_extra_tax_data`` (``odoo19c: :1430-1482``):
        *"For 'manual_tax_amounts', if the setup of the base line has been
        manually edited, we don't import the custom tax amounts from
        'extra_tax_data'."* Los importes locales se llevan a la tasa actual
        de la línea con ``delta_rate``.
        """
        results = {}
        if extra_tax_data and extra_tax_data.get('computation_key'):
            results['computation_key'] = extra_tax_data['computation_key']

        manual_tax_amounts = (extra_tax_data.get('manual_tax_amounts') or {}
                              if extra_tax_data else None)
        extra_tax_data_tax_ids = set(manual_tax_amounts or {})
        sorted_taxes = base_line['tax_ids']._flatten_taxes_and_sort_them()[0]
        currency = base_line['currency_id']
        if (
            extra_tax_data
            and extra_tax_data.get('manual_tax_amounts')
            and currency is not None
            and currency.id == extra_tax_data['currency_id']
            and currency.compare_amounts(
                base_line['price_unit'], extra_tax_data['price_unit']) == 0
            and currency.compare_amounts(
                base_line['discount'], extra_tax_data['discount']) == 0
            and currency.compare_amounts(
                base_line['quantity'], extra_tax_data['quantity']) == 0
            and len(sorted_taxes) == len(extra_tax_data_tax_ids)
            and all(str(tax.id) in extra_tax_data_tax_ids
                    for tax in sorted_taxes)
        ):
            results['price_unit'] = extra_tax_data['price_unit']

            if base_line['rate'] and extra_tax_data.get('rate'):
                delta_rate = base_line['rate'] / extra_tax_data['rate']
            else:
                delta_rate = 1.0

            if 'manual_total_excluded_currency' in extra_tax_data:
                results['manual_total_excluded_currency'] = (
                    extra_tax_data['manual_total_excluded_currency'])
            if 'manual_total_excluded' in extra_tax_data:
                results['manual_total_excluded'] = (
                    extra_tax_data['manual_total_excluded'] / delta_rate)

            if manual_tax_amounts:
                results['manual_tax_amounts'] = {}
                for tax_id_str, amounts in (
                        extra_tax_data['manual_tax_amounts'].items()):
                    results['manual_tax_amounts'][tax_id_str] = dict(amounts)
                    if 'tax_amount' in amounts:
                        results['manual_tax_amounts'][tax_id_str][
                            'tax_amount'] /= delta_rate
                    if 'base_amount' in amounts:
                        results['manual_tax_amounts'][tax_id_str][
                            'base_amount'] /= delta_rate

        return results

    @classmethod
    def _prepare_base_line_for_taxes_computation(cls, record, **kwargs):
        """ Convert any representation of a business object ('record') into a
        base line being a python dictionary that will be used to use the
        generic helpers for the taxes computation.

        ≙ ``_prepare_base_line_for_taxes_computation`` (``odoo19c:
        :1593-1691``), clave por clave. Divergencias, todas de la forma
        declarada arriba: el respaldo de ``product_id``,
        ``product_uom_id``, ``partner_id`` y ``account_id`` es ``None`` y
        el de ``tax_ids`` el ``QuerySet`` vacío de ``account.tax``; sin
        moneda ni compañía, ``currency_id`` es ``None``.
        """
        def load(field, fallback):
            return cls._get_base_line_field_value_from_record(
                record, field, kwargs, fallback)

        company = load('company_id', None)
        currency = (
            load('currency_id', None)
            or load('company_currency_id', None)
            or (company.currency if company is not None else None)
        )

        base_line = {
            **kwargs,
            'record': record,
            'id': load('id', 0),

            # Basic fields:
            'product_id': load('product_id', None),
            'product_uom_id': load('product_uom_id', None),
            'tax_ids': load('tax_ids', cls._default_manager.none()),
            'price_unit': load('price_unit', 0.0),
            'quantity': load('quantity', 0.0),
            'discount': load('discount', 0.0),
            'currency_id': currency,

            # The special_mode for the taxes computation:
            # - False for the normal behavior.
            # - total_included to force all taxes to be price included.
            # - total_excluded to force all taxes to be price excluded.
            'special_mode': kwargs.get('special_mode') or False,

            # A special typing of base line for some custom behavior:
            # - False for the normal behavior.
            # - early_payment if the base line represent an early payment in
            #   mixed mode.
            # - cash_rounding if the base line is a delta to round the
            #   business object for the cash rounding feature.
            # - non_deductible if the base line is used to compute non
            #   deductible amounts in bills.
            'special_type': kwargs.get('special_type') or False,

            # All computation are managing the foreign currency and the local
            # one. This is the rate to be applied when generating the tax
            # details (see '_add_tax_details_in_base_line').
            'rate': load('rate', 1.0),

            # Add a function allowing to filter out some taxes during the
            # evaluation. Those taxes can't be removed from the base_line
            # when dealing with group of taxes to maintain a correct link
            # between the child tax and its parent.
            'filter_tax_function': kwargs.get('filter_tax_function') or None,

            # ===== Accounting stuff =====

            # The sign of the business object regarding its accounting
            # balance.
            'sign': load('sign', 1.0),

            # If the document is a refund or not to know which repartition
            # lines must be used.
            'is_refund': load('is_refund', False),

            # Extra fields for tax lines generation:
            'partner_id': load('partner_id', None),
            'account_id': load('account_id', None),
            'analytic_distribution': load('analytic_distribution', None),
        }

        extra_tax_data = cls._import_base_line_extra_tax_data(
            base_line, load('extra_tax_data', {}) or {})
        base_line.update({
            # Allow to split the computation of taxes on subset of lines. For
            # example with a down payment of 300 on a sale order of 1000, the
            # last invoice will have an amount of 1000 - 300 = 700. However,
            # the taxes should be computed in 2 subsets of lines:
            # - the original lines for a total of 1000.0
            # - the previous down payment lines for a total of -300.0
            'computation_key': (kwargs.get('computation_key')
                                or extra_tax_data.get('computation_key')),

            # For all computation that are inferring a base amount in order
            # to reach a total you know in advance, you have to force some
            # base/tax amounts for the computation (E.g. down payment, combo
            # products, global discounts etc).
            'manual_total_excluded_currency': (
                kwargs.get('manual_total_excluded_currency')
                or extra_tax_data.get('manual_total_excluded_currency')),
            'manual_total_excluded': (
                kwargs.get('manual_total_excluded')
                or extra_tax_data.get('manual_total_excluded')),
            'manual_tax_amounts': (
                kwargs.get('manual_tax_amounts')
                or extra_tax_data.get('manual_tax_amounts')),
        })
        if 'price_unit' in extra_tax_data:
            base_line['price_unit'] = extra_tax_data['price_unit']

        # Propagate custom values.
        if record and isinstance(record, dict):
            for k, v in record.items():
                if k.startswith('_') and k not in base_line:
                    base_line[k] = v

        return base_line

    # -- detalles de impuestos en la base-line (odoo19c: :1737-1823) -------

    @classmethod
    def _add_tax_details_in_base_line(cls, base_line, company,
                                      rounding_method=None):
        """ Perform the taxes computation for the base line and add it to the
        base line under the 'tax_details' key.

        ≙ ``_add_tax_details_in_base_line`` (``odoo19c: :1737-1810``): los
        importes del motor en moneda extranjera (``*_currency``) y, divididos
        entre la tasa, en la local; con ``round_per_line`` los locales se
        redondean con la moneda de la compañía. Divergencia de pila: la
        fuente multiplica ``float``; aquí el motor y las líneas son
        ``Decimal``, así que precio, descuento y tasa entran por ``_d``.
        """
        rounding_method = (rounding_method
                           or company.tax_calculation_rounding_method)
        price_unit_after_discount = _d(base_line['price_unit']) * (
            1 - (_d(base_line['discount']) / 100))
        taxes_computation = base_line['tax_ids']._get_tax_details(
            price_unit=price_unit_after_discount,
            quantity=base_line['quantity'],
            precision_rounding=_d(base_line['currency_id'].rounding),
            rounding_method=rounding_method,
            product=base_line['product_id'],
            product_uom=base_line['product_uom_id'],
            special_mode=base_line['special_mode'],
            filter_tax_function=base_line['filter_tax_function'],
        )

        # Only python side for professional with reverse charge
        if base_line['special_type'] == 'non_deductible':
            taxes_data = taxes_computation['taxes_data']
            taxes_computation['taxes_data'] = []
            for tax_data in taxes_data:
                if not tax_data.get('is_reverse_charge'):
                    taxes_computation['taxes_data'].append(tax_data)
                else:
                    taxes_computation['total_included'] -= (
                        tax_data['tax_amount'])

        rate = _d(base_line['rate']) if base_line['rate'] else None
        tax_details = base_line['tax_details'] = {
            'raw_total_excluded_currency': taxes_computation['total_excluded'],
            'raw_total_excluded': (taxes_computation['total_excluded'] / rate
                                   if rate else Decimal('0')),
            'raw_total_included_currency': taxes_computation['total_included'],
            'raw_total_included': (taxes_computation['total_included'] / rate
                                   if rate else Decimal('0')),
            'taxes_data': [],
        }
        if rounding_method == 'round_per_line':
            tax_details['raw_total_excluded'] = company.currency.round(
                tax_details['raw_total_excluded'])
            tax_details['raw_total_included'] = company.currency.round(
                tax_details['raw_total_included'])
        for tax_data in taxes_computation['taxes_data']:
            tax_amount = (tax_data['tax_amount'] / rate if rate
                          else Decimal('0'))
            base_amount = (tax_data['base_amount'] / rate if rate
                           else Decimal('0'))
            if rounding_method == 'round_per_line':
                tax_amount = company.currency.round(tax_amount)
                base_amount = company.currency.round(base_amount)
            tax_details['taxes_data'].append({
                **tax_data,
                'raw_tax_amount_currency': tax_data['tax_amount'],
                'raw_tax_amount': tax_amount,
                'raw_base_amount_currency': tax_data['base_amount'],
                'raw_base_amount': base_amount,
            })

    @classmethod
    def _add_tax_details_in_base_lines(cls, base_lines, company):
        """ Shortcut to call '_add_tax_details_in_base_line' on multiple base
        lines at once. ≙ ``:1812-1823``.
        """
        for base_line in base_lines:
            cls._add_tax_details_in_base_line(base_line, company)

    # -- reparto de un delta de redondeo (odoo19c: :1824-1893) -------------

    @classmethod
    def _normalize_target_factors(cls, target_factors):
        """ Normalize the factors passed as parameter to have a distribution
        having a sum of 1.

        ≙ ``_normalize_target_factors`` (``odoo19c: :1824-1838``): devuelve
        pares ``<índice, factor normalizado>``, del factor mayor al menor; si
        todos valen cero, cada uno recibe la misma parte.
        """
        factors = [(i, abs(target_factor['factor']))
                   for i, target_factor in enumerate(target_factors)]
        factors.sort(key=lambda x: x[1], reverse=True)
        sum_of_factors = sum(x[1] for x in factors)
        return [(i, factor / sum_of_factors if sum_of_factors
                 else 1 / len(factors)) for i, factor in factors]

    @classmethod
    def _distribute_delta_amount_smoothly(cls, precision_digits, delta_amount,
                                          target_factors):
        """ Distribute 'delta_amount' across the factors passed as parameter.

        ≙ ``_distribute_delta_amount_smoothly`` (``odoo19c: :1841-1893``).
        Ejemplo de la fuente: *"if 'delta_amount' = 0.03 and precision_digits
        is 3 and target factors is a list of 3 factors [0.4, 0.3, 0.3] [...]
        The result of this method will be [0.012, 0.009, 0.009]."* Primero
        reparte por factor; los céntimos que sobran van, uno por factor, del
        mayor al menor.
        """
        if isinstance(delta_amount, Decimal):
            # Los importes del motor de este árbol son ``Decimal``: el paso
            # de precisión y el cero se calculan en ``Decimal`` (``HALF-UP``,
            # como el ``float_is_zero`` de la fuente); con ``float`` es la
            # fuente tal cual.
            precision_rounding = Decimal(1).scaleb(-precision_digits)
            amounts_to_distribute = [Decimal('0')] * len(target_factors)
            if not delta_amount.quantize(precision_rounding,
                                         rounding=ROUND_HALF_UP):
                return amounts_to_distribute
        else:
            precision_rounding = float(f"1e-{precision_digits}")
            amounts_to_distribute = [0.0] * len(target_factors)
            if float_is_zero(delta_amount, precision_digits=precision_digits):
                return amounts_to_distribute

        sign = -1 if delta_amount < 0.0 else 1
        nb_of_errors = round(abs(delta_amount / precision_rounding))
        remaining_errors = nb_of_errors

        # Distribute using the factor first.
        factors = cls._normalize_target_factors(target_factors)
        for i, factor in factors:
            if not remaining_errors:
                break

            nb_of_amount_to_distribute = min(
                round(factor * nb_of_errors),
                remaining_errors,
            )
            remaining_errors -= nb_of_amount_to_distribute
            amount_to_distribute = (
                sign * nb_of_amount_to_distribute * precision_rounding)
            amounts_to_distribute[i] += amount_to_distribute

        # Distribute the remaining cents across the factors.
        # There are sorted by the biggest first.
        # Since the factors are normalized, the residual number of cents
        # can't be higher than the number of factors.
        for i in range(remaining_errors):
            amounts_to_distribute[factors[i][0]] += sign * precision_rounding

        return amounts_to_distribute

    # -- agregación de detalles por clave (odoo19c: :2512-2712) ------------
    #
    # Las tres leen la estructura que ``_round_base_lines_tax_details`` deja
    # en cada ``base_line``. Son ``@api.model`` en la fuente: aquí métodos de
    # clase, porque ninguna lee el registro.

    @classmethod
    def _aggregate_base_line_tax_details(cls, base_line, grouping_function):
        """ Aggregate the tax details for a single line according a custom
        grouping function passed as parameter.

        ≙ ``_aggregate_base_line_tax_details`` (``odoo19c: :2512-2645``).
        Docstring de la fuente, verbatim en lo que gobierna: *"This method is
        mainly use for EDI to report some data per line. [...] In case the
        base_line has no tax, the grouping_function is called with an empty
        tax_data to get the grouping key for the line."* El mapeo devuelto
        lleva, por clave, ``base_amount``, ``tax_amount`` y
        ``total_excluded`` en sus formas redondeada, ``raw_`` y ``target_``,
        cada una con su variante ``_currency``, más ``grouping_key`` y
        ``taxes_data``.
        """
        values_per_grouping_key = {}
        tax_details = base_line['tax_details']
        taxes_data = tax_details['taxes_data']
        manual_tax_amounts = base_line['manual_tax_amounts']

        # If there are no taxes, we pass None to the grouping function.
        for tax_data in (taxes_data or [None]):
            current_manual_tax_amounts = (
                manual_tax_amounts and tax_data
                and manual_tax_amounts.get(str(tax_data['tax'].id)) or {}
            )

            grouping_key = grouping_function(base_line, tax_data)
            if isinstance(grouping_key, dict):
                grouping_key = frozendict(grouping_key)

            # Base amount.
            if grouping_key not in values_per_grouping_key:
                values = values_per_grouping_key[grouping_key] = {
                    'grouping_key': grouping_key,
                    'taxes_data': [],
                }
                for suffix in ('_currency', ''):
                    excluded_rounded_field = f'total_excluded{suffix}'
                    excluded_delta_field = f'delta_{excluded_rounded_field}'
                    excluded_raw_field = f'raw_{excluded_rounded_field}'
                    excluded_target_field = f'target_{excluded_rounded_field}'
                    excluded_manual_field = f'manual_{excluded_rounded_field}'
                    excluded_rounded_amount = (
                        tax_details[excluded_rounded_field]
                        + tax_details[excluded_delta_field]
                    )
                    excluded_raw_amount = tax_details[excluded_raw_field]
                    values[excluded_rounded_field] = excluded_rounded_amount
                    values[excluded_raw_field] = excluded_raw_amount
                    if base_line[excluded_manual_field] is not None:
                        excluded_target_amount = (
                            base_line[excluded_manual_field])
                    elif (not suffix and base_line[
                            'manual_total_excluded_currency'] is not None):
                        excluded_target_amount = excluded_rounded_amount
                    else:
                        excluded_target_amount = excluded_raw_amount
                    values[excluded_target_field] = excluded_target_amount

                    tax_base_rounded_field = f'base_amount{suffix}'
                    tax_base_raw_field = f'raw_{tax_base_rounded_field}'
                    tax_base_target_field = f'target_{tax_base_rounded_field}'
                    if tax_data:
                        values[tax_base_rounded_field] = (
                            tax_data[tax_base_rounded_field])
                        values[tax_base_raw_field] = (
                            tax_data[tax_base_raw_field])
                        if (tax_base_rounded_field
                                in current_manual_tax_amounts):
                            values[tax_base_target_field] = (
                                current_manual_tax_amounts[
                                    tax_base_rounded_field])
                        elif (not suffix and 'base_amount_currency'
                                in current_manual_tax_amounts):
                            values[tax_base_target_field] = (
                                tax_data[tax_base_rounded_field])
                        else:
                            values[tax_base_target_field] = (
                                tax_data[tax_base_raw_field])
                    else:
                        values[tax_base_rounded_field] = (
                            excluded_rounded_amount)
                        values[tax_base_raw_field] = excluded_raw_amount
                        values[tax_base_target_field] = excluded_target_amount

                    tax_rounded_field = f'tax_amount{suffix}'
                    tax_raw_field = f'raw_{tax_rounded_field}'
                    tax_target_field = f'target_{tax_rounded_field}'
                    # Cero neutro en tipo: el ``0.0`` de la fuente con los
                    # ``Decimal`` del motor de este árbol es ``TypeError``.
                    values[tax_rounded_field] = 0
                    values[tax_raw_field] = 0
                    values[tax_target_field] = 0

            # Tax amount.
            if tax_data:
                reverse_charge_sign = (
                    -1 if tax_data['is_reverse_charge'] else 1)
                values = values_per_grouping_key[grouping_key]
                for suffix in ('_currency', ''):
                    tax_rounded_field = f'tax_amount{suffix}'
                    tax_raw_field = f'raw_{tax_rounded_field}'
                    tax_target_field = f'target_{tax_rounded_field}'
                    values[tax_rounded_field] += tax_data[tax_rounded_field]
                    values[tax_raw_field] += tax_data[tax_raw_field]
                    if tax_rounded_field in current_manual_tax_amounts:
                        values[tax_target_field] += (
                            reverse_charge_sign
                            * current_manual_tax_amounts[tax_rounded_field])
                    elif (not suffix and 'tax_amount_currency'
                            in current_manual_tax_amounts):
                        values[tax_target_field] = tax_data[tax_rounded_field]
                    else:
                        values[tax_target_field] += tax_data[tax_raw_field]
                values['taxes_data'].append(tax_data)

        return values_per_grouping_key

    @classmethod
    def _aggregate_base_lines_tax_details(cls, base_lines, grouping_function):
        """ Shortcut to call '_aggregate_base_line_tax_details' on multiple
        base lines at once.

        ≙ ``_aggregate_base_lines_tax_details`` (``odoo19c: :2647-2662``):
        *"A list of tuple <base_line, results> that associates the result of
        '_aggregate_base_line_tax_details' for each base line
        independently."*
        """
        return [
            (base_line, cls._aggregate_base_line_tax_details(
                base_line, grouping_function))
            for base_line in base_lines
        ]

    @classmethod
    def _aggregate_base_lines_aggregated_values(
            cls, base_lines_aggregated_values):
        """ Aggregate the values returned by
        '_aggregate_base_lines_tax_details' for the whole document.

        ≙ ``_aggregate_base_lines_aggregated_values`` (``odoo19c:
        :2664-2712``): *"Most of the time, in EDI, you have to report
        unrounded amounts for each base line first and then, you need to
        report all rounded amounts for the whole business document."* Cada
        clave suma los dieciocho importes de sus líneas y lleva
        ``base_line_x_taxes_data``, la lista de pares
        ``<base_line, taxes_data>`` que la componen.
        """
        default_float_fields = set()
        for prefix in ('', 'raw_', 'target_'):
            for suffix in ('_currency', ''):
                for field in ('base_amount', 'tax_amount', 'total_excluded'):
                    default_float_fields.add(f'{prefix}{field}{suffix}')

        values_per_grouping_key = defaultdict(lambda: {
            # Cero neutro en tipo, por la misma razón que en la de una línea.
            **dict.fromkeys(default_float_fields, 0),
            'base_line_x_taxes_data': [],
        })
        for base_line, aggregated_values in base_lines_aggregated_values:
            for grouping_key, values in aggregated_values.items():
                agg_values = values_per_grouping_key[grouping_key]
                for field in default_float_fields:
                    agg_values[field] += values[field]
                agg_values['grouping_key'] = grouping_key
                agg_values['base_line_x_taxes_data'].append(
                    (base_line, values['taxes_data']))
        return values_per_grouping_key

    # -- redondeo contractual de los detalles (odoo19c: :1895-2293) --------

    @classmethod
    def _round_tax_details_tax_amounts(cls, base_lines, company,
                                       mode='mixed'):
        """ Dispatch the delta in term of tax amounts across the tax details
        when dealing with the 'round_globally' method.

        ≙ ``_round_tax_details_tax_amounts`` (``odoo19c: :1895-1992``). El
        ejemplo de la fuente, verbatim: *"Suppose 2 lines: quantity=12.12,
        price_unit=12.12, tax=23% [...] The tax of each line is computed as
        round(12.12 * 12.12 * 0.23) = 33.79. The expected tax amount of the
        whole document is round(12.12 * 12.12 * 0.23 * 2) = 67.57"*. Por
        clave de impuesto se reparte primero el delta del impuesto y después
        el de la base, según ``mode`` (``excluded``, ``included`` o
        ``mixed``). La moneda de la compañía es ``company.currency``.
        """
        def grouping_function(base_line, tax_data):
            if not tax_data:
                return None
            return {
                'tax': tax_data['tax'],
                'currency': base_line['currency_id'],
                'is_refund': base_line['is_refund'],
                'is_reverse_charge': tax_data['is_reverse_charge'],
                'price_include': tax_data['price_include'],
                'computation_key': base_line['computation_key'],
            }

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        for grouping_key, values in values_per_grouping_key.items():
            if not grouping_key:
                continue

            price_include = grouping_key['price_include']
            currency = grouping_key['currency']
            for delta_currency_indicator, delta_currency in (
                ('_currency', currency),
                ('', company.currency),
            ):
                # Tax amount.
                raw_total_tax_amount = values[
                    f'target_tax_amount{delta_currency_indicator}']
                rounded_raw_total_tax_amount = delta_currency.round(
                    raw_total_tax_amount)
                total_tax_amount = values[
                    f'tax_amount{delta_currency_indicator}']
                delta_total_tax_amount = (
                    rounded_raw_total_tax_amount - total_tax_amount)

                if not delta_currency.is_zero(delta_total_tax_amount):
                    target_factors = [
                        {
                            'factor': tax_data[
                                f'raw_tax_amount{delta_currency_indicator}'],
                            'tax_data': tax_data,
                        }
                        for _base_line, taxes_data in values[
                            'base_line_x_taxes_data']
                        for tax_data in taxes_data
                    ]
                    amounts_to_distribute = (
                        cls._distribute_delta_amount_smoothly(
                            precision_digits=delta_currency.decimal_places,
                            delta_amount=delta_total_tax_amount,
                            target_factors=target_factors,
                        ))
                    for target_factor, amount_to_distribute in zip(
                            target_factors, amounts_to_distribute):
                        tax_data = target_factor['tax_data']
                        tax_data[f'tax_amount{delta_currency_indicator}'] += (
                            amount_to_distribute)

                # Base amount.
                raw_total_base_amount = values[
                    f'target_base_amount{delta_currency_indicator}']
                if (mode == 'mixed' and price_include) or mode == 'included':
                    raw_total_amount = (
                        raw_total_base_amount + raw_total_tax_amount)
                    rounded_raw_total_amount = delta_currency.round(
                        raw_total_amount)
                    total_amount = (
                        values[f'base_amount{delta_currency_indicator}']
                        + total_tax_amount + delta_total_tax_amount)
                    delta_total_base_amount = (
                        rounded_raw_total_amount - total_amount)
                elif ((mode == 'mixed' and not price_include)
                        or mode == 'excluded'):
                    rounded_raw_total_base_amount = delta_currency.round(
                        raw_total_base_amount)
                    total_base_amount = values[
                        f'base_amount{delta_currency_indicator}']
                    delta_total_base_amount = (
                        rounded_raw_total_base_amount - total_base_amount)

                if not delta_currency.is_zero(delta_total_base_amount):
                    target_factors = [
                        {
                            'factor': tax_data[
                                f'raw_base_amount{delta_currency_indicator}'],
                            'tax_data': tax_data,
                        }
                        for _base_line, taxes_data in values[
                            'base_line_x_taxes_data']
                        for tax_data in taxes_data
                    ]
                    amounts_to_distribute = (
                        cls._distribute_delta_amount_smoothly(
                            precision_digits=delta_currency.decimal_places,
                            delta_amount=delta_total_base_amount,
                            target_factors=target_factors,
                        ))
                    for target_factor, amount_to_distribute in zip(
                            target_factors, amounts_to_distribute):
                        tax_data = target_factor['tax_data']
                        tax_data[
                            f'base_amount{delta_currency_indicator}'] += (
                            amount_to_distribute)

    @classmethod
    def _round_tax_details_base_lines(cls, base_lines, company,
                                      mode='mixed'):
        """ Additional global rounding depending on if the taxes are included
        or excluded in price.

        ≙ ``_round_tax_details_base_lines`` (``odoo19c: :1994-2103``):
        *"This method does not modify the rounding in `taxes_data`, rather
        it computes an adjustment for
        `tax_details['total_excluded{_currency}']` and stores it as
        `tax_details['delta_total_excluded{_currency}']`."* Con todos los
        impuestos incluidos en el precio se redondea el total con impuesto;
        si alguno con importe está excluido, el total sin impuesto.
        """
        def grouping_function(base_line, tax_data):
            return {
                'currency': base_line['currency_id'],
                'is_refund': base_line['is_refund'],
                'computation_key': base_line['computation_key'],
            }

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        for grouping_key, values in values_per_grouping_key.items():
            current_mode = mode
            if mode == 'mixed':
                current_mode = 'included'
                for base_line, taxes_data in values['base_line_x_taxes_data']:
                    if any(
                        not tax_data['price_include']
                        for tax_data in taxes_data
                        if (
                            not base_line['currency_id'].is_zero(
                                tax_data['tax_amount_currency'])
                            or not company.currency.is_zero(
                                tax_data['tax_amount'])
                        )
                    ):
                        current_mode = 'excluded'
                        break

            currency = grouping_key['currency']
            for delta_currency_indicator, delta_currency in (
                ('_currency', currency),
                ('', company.currency),
            ):
                if current_mode == 'excluded':
                    # Price-excluded rounding.
                    raw_total_excluded = values[
                        f'target_total_excluded{delta_currency_indicator}']
                    if not raw_total_excluded:
                        continue

                    rounded_raw_total_excluded = delta_currency.round(
                        raw_total_excluded)
                    total_excluded = values[
                        f'total_excluded{delta_currency_indicator}']
                    delta_total_excluded = (
                        rounded_raw_total_excluded - total_excluded)
                    target_factors = [
                        {
                            'factor': base_line['tax_details'][
                                f'raw_total_excluded'
                                f'{delta_currency_indicator}'],
                            'base_line': base_line,
                        }
                        for base_line, _taxes_data in values[
                            'base_line_x_taxes_data']
                    ]
                else:
                    # Price-included rounding.
                    raw_total_included = (
                        values[
                            f'target_total_excluded{delta_currency_indicator}']
                        + values[
                            f'target_tax_amount{delta_currency_indicator}']
                    )
                    if not raw_total_included:
                        continue

                    rounded_raw_total_included = delta_currency.round(
                        raw_total_included)
                    total_included = (
                        values[f'total_excluded{delta_currency_indicator}']
                        + values[f'tax_amount{delta_currency_indicator}']
                    )
                    delta_total_excluded = (
                        rounded_raw_total_included - total_included)
                    target_factors = [
                        {
                            'factor': base_line['tax_details'][
                                f'raw_total_included'
                                f'{delta_currency_indicator}'],
                            'base_line': base_line,
                        }
                        for base_line, _taxes_data in values[
                            'base_line_x_taxes_data']
                    ]

                amounts_to_distribute = cls._distribute_delta_amount_smoothly(
                    precision_digits=delta_currency.decimal_places,
                    delta_amount=delta_total_excluded,
                    target_factors=target_factors,
                )
                for target_factor, amount_to_distribute in zip(
                        target_factors, amounts_to_distribute):
                    base_line = target_factor['base_line']
                    base_line['tax_details'][
                        f'delta_total_excluded{delta_currency_indicator}'] += (
                        amount_to_distribute)

    @classmethod
    def _round_tax_details_tax_amounts_from_tax_lines(cls, base_lines,
                                                      company, tax_lines):
        """ If tax lines are provided, the totals will be aggregated according
        them. At this point, everything is rounded and won't change anymore.

        ≙ ``_round_tax_details_tax_amounts_from_tax_lines`` (``odoo19c:
        :2105-2182``): el impuesto de los apuntes existentes gobierna, por
        clave ``<impuesto, moneda, es reembolso>``, y la diferencia se
        reparte entre los ``taxes_data``. Divergencias de pila: el impuesto
        de la línea de reparto es ``tax_rep.tax`` (FK de Django), y signo e
        importes entran por ``_d`` porque los acumuladores son ``Decimal``.
        """
        if not tax_lines:
            return

        total_per_tax_line_key = defaultdict(lambda: {
            'currency': None,
            'tax_amount_currency': 0,
            'tax_amount': 0,
        })
        for tax_line in tax_lines:
            tax_rep = tax_line['tax_repartition_line_id']
            sign = _d(tax_line['sign'])
            tax = tax_rep.tax
            currency = tax_line['currency_id']
            tax_line_key = (tax.id, currency.id,
                            tax_rep.document_type == 'refund')
            total_per_tax_line_key[tax_line_key]['currency'] = currency
            total_per_tax_line_key[tax_line_key]['tax_amount_currency'] += (
                sign * _d(tax_line['amount_currency']))
            total_per_tax_line_key[tax_line_key]['tax_amount'] += (
                sign * _d(tax_line['balance']))

        def grouping_function(base_line, tax_data):
            if not tax_data:
                return None
            return {
                'tax': tax_data['tax'],
                'currency': base_line['currency_id'],
                'is_refund': base_line['is_refund'],
            }

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        for grouping_key, values in values_per_grouping_key.items():
            if not grouping_key:
                continue

            currency = grouping_key['currency']
            tax_line_key = (grouping_key['tax'].id, currency.id,
                            grouping_key['is_refund'])
            if tax_line_key not in total_per_tax_line_key:
                continue

            for delta_currency_indicator, delta_currency in (
                ('_currency', currency),
                ('', company.currency),
            ):
                current_total_tax_amount = values[
                    f'tax_amount{delta_currency_indicator}']
                if not current_total_tax_amount:
                    continue

                target_total_tax_amount = total_per_tax_line_key[
                    tax_line_key][f'tax_amount{delta_currency_indicator}']
                delta_total_tax_amount = (
                    target_total_tax_amount - current_total_tax_amount)

                target_factors = [
                    {
                        'factor': tax_data[
                            f'tax_amount{delta_currency_indicator}'],
                        'tax_data': tax_data,
                    }
                    for _base_line, taxes_data in values[
                        'base_line_x_taxes_data']
                    for tax_data in taxes_data
                ]
                amounts_to_distribute = cls._distribute_delta_amount_smoothly(
                    precision_digits=delta_currency.decimal_places,
                    delta_amount=delta_total_tax_amount,
                    target_factors=target_factors,
                )
                for target_factor, amount_to_distribute in zip(
                        target_factors, amounts_to_distribute):
                    tax_data = target_factor['tax_data']
                    tax_data[f'tax_amount{delta_currency_indicator}'] += (
                        amount_to_distribute)

    @classmethod
    def _round_base_lines_tax_details(cls, base_lines, company,
                                      tax_lines=None):
        """ Round the 'tax_details' added to base_lines with the
        '_add_accounting_data_to_base_line_tax_details'.

        ≙ ``_round_base_lines_tax_details`` (``odoo19c: :2184-2293``):
        *"This method copies all float prefixed with 'raw_' in the
        tax_details to the corresponding float without 'raw_'. [...] The
        rounding is made by aggregating the raw amounts per tax first. Then
        we round the total amount per tax, same for each tax amount in each
        base lines. Finally, we distribute the delta on each base lines."*
        El ejemplo de la fuente: dos líneas de 21.53 con un 21 % incluido
        dan una base de 35.59 (17.80 + 17.79) y un impuesto de 7.47
        (3.73 + 3.74). Divergencia de pila: los importes manuales y la tasa
        entran por ``_d`` antes de dividir, porque los detalles son
        ``Decimal``.
        """
        # Raw rounding.
        for base_line in base_lines:
            tax_details = base_line['tax_details']

            for suffix, currency in (('_currency', base_line['currency_id']),
                                     ('', company.currency)):
                total_excluded_field = f'total_excluded{suffix}'
                tax_details[total_excluded_field] = currency.round(
                    tax_details[f'raw_{total_excluded_field}'])

                for tax_data in tax_details['taxes_data']:
                    for prefix in ('base', 'tax'):
                        field = f'{prefix}_amount{suffix}'
                        tax_data[field] = currency.round(
                            tax_data[f'raw_{field}'])

        # Apply 'manual_tax_amounts'.
        for base_line in base_lines:
            manual_tax_amounts = base_line['manual_tax_amounts']
            rate = base_line['rate']
            tax_details = base_line['tax_details']

            for suffix, currency in (('_currency', base_line['currency_id']),
                                     ('', company.currency)):
                total_field = f'total_excluded{suffix}'
                manual_field = f'manual_{total_field}'
                if base_line[manual_field] is not None:
                    tax_details[total_field] = _d(base_line[manual_field])
                    if suffix == '_currency' and rate:
                        tax_details['total_excluded'] = company.currency.round(
                            tax_details[total_field] / _d(rate))

                for tax_data in tax_details['taxes_data']:
                    tax = tax_data['tax']
                    reverse_charge_sign = (
                        -1 if tax_data['is_reverse_charge'] else 1)
                    current_manual_tax_amounts = (
                        manual_tax_amounts
                        and manual_tax_amounts.get(str(tax.id)) or {})
                    for prefix, factor in (('base', 1),
                                           ('tax', reverse_charge_sign)):
                        field = f'{prefix}_amount{suffix}'
                        if field in current_manual_tax_amounts:
                            tax_data[field] = currency.round(
                                factor * _d(current_manual_tax_amounts[field]))
                            if suffix == '_currency' and rate:
                                tax_data[f'{prefix}_amount'] = (
                                    company.currency.round(
                                        tax_data[field] / _d(rate)))

        # Compute 'total_included' & add 'delta_total_excluded'.
        for base_line in base_lines:
            tax_details = base_line['tax_details']

            for suffix in ('_currency', ''):
                # Cero neutro en tipo, como en la agregación.
                tax_details[f'delta_total_excluded{suffix}'] = 0
                tax_details[f'total_included{suffix}'] = tax_details[
                    f'total_excluded{suffix}']

                for tax_data in tax_details['taxes_data']:
                    tax_details[f'total_included{suffix}'] += tax_data[
                        f'tax_amount{suffix}']

        cls._round_tax_details_tax_amounts(base_lines, company)
        cls._round_tax_details_base_lines(base_lines, company)
        cls._round_tax_details_tax_amounts_from_tax_lines(base_lines, company,
                                                          tax_lines)

    # -- importes brutos y redondeo de crudos (odoo19c: :4445-4949) --------

    @classmethod
    def _get_delta_amount_to_reach_target(
        cls,
        target_amount,
        target_currency,
        raw_current_amount,
        raw_current_amount_precision_digits,
    ):
        """ Get the minimum missing amount having
        'raw_current_amount_precision_digits' as precision to be added to
        'raw_current_amount' to give 'target_amount' after rounding using
        'target_currency'.

        ≙ ``_get_delta_amount_to_reach_target`` (``odoo19c: :4445-4486``):
        *"the delta returned by this method will be expressed with
        'raw_current_amount_precision_digits' such as
        target_currency.round(raw_current_amount + delta) == target_amount"*.
        Divergencia de pila: ``Decimal`` en vez de ``float``; el
        ``math.pow(10, -n)`` de la fuente es ``Decimal(1).scaleb(-n)``.
        """
        target_amount = _d(target_amount)
        raw_current_amount = _d(raw_current_amount)
        digits = raw_current_amount_precision_digits
        target_amount_sign = -1 if target_amount < 0 else 1
        raw_current_amount_rounding = Decimal(1).scaleb(-digits)
        half_rounding = _d(target_currency.rounding) / 2
        tolerance_bounds = (
            _round_to_digits(
                abs(target_amount) + half_rounding
                - raw_current_amount_rounding, digits),
            _round_to_digits(abs(target_amount) - half_rounding, digits),
        )

        signed_raw_current_amount = target_amount_sign * raw_current_amount
        if signed_raw_current_amount > tolerance_bounds[0]:
            delta_raw_amount = (
                tolerance_bounds[0] - signed_raw_current_amount)
        elif signed_raw_current_amount < tolerance_bounds[1]:
            delta_raw_amount = (
                tolerance_bounds[1] - signed_raw_current_amount)
        else:
            return Decimal('0')

        return target_amount_sign * delta_raw_amount

    @classmethod
    def _round_raw_total_excluded(
        cls,
        base_lines,
        company,
        precision_digits=6,
        apply_strict_tolerance=False,
        in_foreign_currency=True,
    ):
        """ Round 'raw_total_excluded[_currency]' according
        'precision_digits'.

        ≙ ``_round_raw_total_excluded`` (``odoo19c: :4488-4557``). Con
        ``apply_strict_tolerance`` *"the difference will be spread into the
        raw amounts"* hasta que la suma redondeada de los crudos iguale la
        suma de los ``total_excluded``.
        """
        if not base_lines:
            return

        suffix_currency = (base_lines[0]['currency_id']
                           if in_foreign_currency else company.currency)
        suffix = '_currency' if in_foreign_currency else ''
        raw_field = f'raw_total_excluded{suffix}'

        for base_line in base_lines:
            tax_details = base_line['tax_details']
            tax_details[raw_field] = _round_to_digits(
                tax_details[raw_field], precision_digits)

        # Tolerance.
        if not apply_strict_tolerance:
            return

        def grouping_function(base_line, tax_data):
            return True

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        expected_total_excluded = sum(
            values[f'total_excluded{suffix}']
            for values in values_per_grouping_key.values()
        )
        current_raw_total_excluded = sum(
            base_line['tax_details'][raw_field]
            for base_line in base_lines
        )

        delta_raw_amount = cls._get_delta_amount_to_reach_target(
            target_amount=expected_total_excluded,
            target_currency=suffix_currency,
            raw_current_amount=current_raw_total_excluded,
            raw_current_amount_precision_digits=precision_digits,
        )
        target_factors = [
            {
                'factor': base_line['tax_details'][raw_field],
                'base_line': base_line,
            }
            for base_line in base_lines
        ]
        amounts_to_distribute = cls._distribute_delta_amount_smoothly(
            precision_digits=precision_digits,
            delta_amount=delta_raw_amount,
            target_factors=target_factors,
        )
        for target_factor, amount_to_distribute in zip(
                target_factors, amounts_to_distribute):
            base_line = target_factor['base_line']
            base_line['tax_details'][raw_field] += amount_to_distribute

    @classmethod
    def _get_gross_total_without_tax(cls, base_line, company,
                                     in_foreign_currency=True,
                                     account_discount_base_lines=False,
                                     precision_digits=None):
        """ Infer the gross total without tax from the base line.

        ≙ ``_get_gross_total_without_tax`` (``odoo19c: :4560-4594``): el
        neto entre ``1 - descuento``; con descuento total, precio por
        cantidad (entre la tasa en moneda de la compañía).
        """
        suffix = '_currency' if in_foreign_currency else ''

        tax_details = base_line['tax_details']
        raw_total_excluded = tax_details[f'raw_total_excluded{suffix}']

        discount_factor = 1 - (_d(base_line['discount']) / _CIEN)
        price_by_quantity = (_d(base_line['price_unit'])
                             * _d(base_line['quantity']))
        if discount_factor:
            raw_gross_total_excluded = raw_total_excluded / discount_factor
        elif in_foreign_currency:
            raw_gross_total_excluded = price_by_quantity
        elif base_line['rate']:
            raw_gross_total_excluded = (
                price_by_quantity / _d(base_line['rate']))
        else:
            raw_gross_total_excluded = Decimal('0')
        if account_discount_base_lines:
            raw_gross_total_excluded -= sum(
                discount_base_line['tax_details'][
                    f'raw_total_excluded{suffix}']
                for discount_base_line in base_line.get(
                    'discount_base_lines', [])
            )

        if precision_digits is not None:
            raw_gross_total_excluded = _round_to_digits(
                raw_gross_total_excluded, precision_digits)
        return raw_gross_total_excluded

    @classmethod
    def _get_price_unit_without_tax(cls, base_line, company,
                                    raw_gross_total_excluded,
                                    in_foreign_currency=True,
                                    precision_digits=None):
        """ Infer the gross price unit without tax from the base line.

        ≙ ``_get_price_unit_without_tax`` (``odoo19c: :4597-4622``).
        """
        raw_gross_total_excluded = _d(raw_gross_total_excluded)
        if (
            (precision_digits and not _round_to_digits(
                raw_gross_total_excluded, precision_digits))
            or not raw_gross_total_excluded
        ):
            if in_foreign_currency:
                raw_gross_price_unit = _d(base_line['price_unit'])
            elif base_line['rate']:
                raw_gross_price_unit = (_d(base_line['price_unit'])
                                        / _d(base_line['rate']))
            else:
                raw_gross_price_unit = Decimal('0')
        elif not base_line['quantity']:
            raw_gross_price_unit = raw_gross_total_excluded
        else:
            raw_gross_price_unit = (raw_gross_total_excluded
                                    / _d(base_line['quantity']))

        if precision_digits is not None:
            raw_gross_price_unit = _round_to_digits(
                raw_gross_price_unit, precision_digits)
        return raw_gross_price_unit

    @classmethod
    def _get_discount_amount_without_tax(cls, base_line, company,
                                         raw_gross_total_excluded,
                                         in_foreign_currency=True,
                                         precision_digits=None):
        """ Infer the discount amount without tax from the base line.

        ≙ ``_get_discount_amount_without_tax`` (``odoo19c: :4625-4644``).
        """
        suffix = '_currency' if in_foreign_currency else ''
        raw_discount_amount = (
            _d(raw_gross_total_excluded)
            - base_line['tax_details'][f'raw_total_excluded{suffix}'])

        if precision_digits is not None:
            raw_discount_amount = _round_to_digits(
                raw_discount_amount, precision_digits)
        return raw_discount_amount

    @classmethod
    def _add_and_round_raw_gross_total_excluded_and_discount(
        cls,
        base_lines,
        company,
        precision_digits=6,
        apply_strict_tolerance=False,
        in_foreign_currency=True,
        account_discount_base_lines=False,
    ):
        """ Compute and add 'raw_gross_total_excluded[_currency]' /
        'raw_gross_price_unit[_currency]' / 'raw_discount_amount[_currency]'
        to the tax details according 'precision_digits' /
        'in_foreign_currency'.

        ≙ ``_add_and_round_raw_gross_total_excluded_and_discount``
        (``odoo19c: :4647-4768``).
        """
        if not base_lines:
            return

        suffix_currency = (base_lines[0]['currency_id']
                           if in_foreign_currency else company.currency)
        suffix = '_currency' if in_foreign_currency else ''
        raw_field = f'raw_total_excluded{suffix}'

        for base_line in base_lines:
            tax_details = base_line['tax_details']
            raw_total_excluded = tax_details[raw_field]

            global_discount_sum = 0
            if account_discount_base_lines:
                global_discount_sum = sum(
                    discount_base_line['tax_details'][raw_field]
                    for discount_base_line in base_line.get(
                        'discount_base_lines', [])
                )

            discount_factor = 1 - (_d(base_line['discount']) / _CIEN)
            price_by_quantity = (_d(base_line['price_unit'])
                                 * _d(base_line['quantity']))
            if discount_factor:
                raw_gross_total_excluded = (
                    (raw_total_excluded - global_discount_sum)
                    / discount_factor)
            elif suffix == '_currency':
                raw_gross_total_excluded = price_by_quantity
            elif base_line['rate']:
                raw_gross_total_excluded = (
                    price_by_quantity / _d(base_line['rate']))
            else:
                raw_gross_total_excluded = Decimal('0')
            tax_details[f'raw_gross_total_excluded{suffix}'] = (
                _round_to_digits(raw_gross_total_excluded, precision_digits))

            # Same as before but per unit.
            raw_gross_price_unit = cls._get_price_unit_without_tax(
                base_line=base_line,
                company=company,
                raw_gross_total_excluded=raw_gross_total_excluded,
                in_foreign_currency=in_foreign_currency,
                precision_digits=precision_digits,
            )
            tax_details[f'raw_gross_price_unit{suffix}'] = raw_gross_price_unit

            # Compute the amount of the discount due to the 'discount' value
            # set on 'base_line'.
            raw_discount_amount = cls._get_discount_amount_without_tax(
                base_line=base_line,
                company=company,
                raw_gross_total_excluded=raw_gross_total_excluded,
                in_foreign_currency=in_foreign_currency,
                precision_digits=precision_digits,
            )
            tax_details[f'raw_discount_amount{suffix}'] = raw_discount_amount

        # Tolerance.
        if not apply_strict_tolerance:
            return

        def grouping_function(base_line, tax_data):
            return True

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        expected_total_excluded = sum(
            values[f'total_excluded{suffix}']
            for values in values_per_grouping_key.values()
        )
        raw_total_discount_amount = sum(
            base_line['tax_details'][f'raw_discount_amount{suffix}']
            for values in values_per_grouping_key.values()
            for base_line, _taxes_data in values['base_line_x_taxes_data']
        )
        raw_total_gross_amount = sum(
            base_line['tax_details'][f'raw_gross_total_excluded{suffix}']
            for values in values_per_grouping_key.values()
            for base_line, _taxes_data in values['base_line_x_taxes_data']
        )
        total_discount_amount = suffix_currency.round(
            raw_total_discount_amount)
        expected_total_gross_amount = (
            expected_total_excluded + total_discount_amount)

        delta_raw_amount = cls._get_delta_amount_to_reach_target(
            target_amount=expected_total_gross_amount,
            target_currency=suffix_currency,
            raw_current_amount=raw_total_gross_amount,
            raw_current_amount_precision_digits=precision_digits,
        )
        target_factors = [
            {
                'factor': base_line['tax_details'][
                    f'raw_total_excluded{suffix}'],
                'base_line': base_line,
            }
            for values in values_per_grouping_key.values()
            for base_line, _taxes_data in values['base_line_x_taxes_data']
        ]
        amounts_to_distribute = cls._distribute_delta_amount_smoothly(
            precision_digits=precision_digits,
            delta_amount=delta_raw_amount,
            target_factors=target_factors,
        )
        for target_factor, amount_to_distribute in zip(
                target_factors, amounts_to_distribute):
            base_line = target_factor['base_line']
            base_line['tax_details'][
                f'raw_gross_total_excluded{suffix}'] += amount_to_distribute

    @classmethod
    def _round_raw_gross_total_excluded_and_discount(
        cls,
        base_lines,
        company,
        in_foreign_currency=True,
    ):
        """ ≙ ``_round_raw_gross_total_excluded_and_discount`` (``odoo19c:
        :4771-4846``): redondea el bruto y el descuento de cada línea y
        reparte, a un centavo por línea como mucho, lo que falta para que el
        bruto sume el documento sin impuesto más su descuento redondeado.
        """
        if not base_lines:
            return

        suffix_currency = (base_lines[0]['currency_id']
                           if in_foreign_currency else company.currency)
        suffix = '_currency' if in_foreign_currency else ''

        # Raw rounding.
        current_gross_total_excluded = 0
        current_discount_amount = 0
        current_raw_discount_amount = 0
        for base_line in base_lines:
            tax_details = base_line['tax_details']
            gross_total_excluded = suffix_currency.round(
                tax_details[f'raw_gross_total_excluded{suffix}'])
            tax_details[f'gross_total_excluded{suffix}'] = (
                gross_total_excluded)
            current_gross_total_excluded += gross_total_excluded

            raw_discount_amount = tax_details[f'raw_discount_amount{suffix}']
            discount_amount = suffix_currency.round(raw_discount_amount)
            tax_details[f'discount_amount{suffix}'] = discount_amount
            current_discount_amount += discount_amount
            current_raw_discount_amount += raw_discount_amount

        # Collect the 'total_excluded'.
        def grouping_function(base_line, tax_data):
            return True

        base_lines_aggregated_values = cls._aggregate_base_lines_tax_details(
            base_lines, grouping_function)
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        expected_total_excluded = sum(
            values[f'total_excluded{suffix}']
            for values in values_per_grouping_key.values()
        )

        # Fix rounding issues for 'gross_total_excluded'.
        # Note: 'expected_gross_total_excluded' contains also the
        # 'delta_total_excluded' to put all the difference due to the global
        # taxes rounding on it instead of putting it on 'discount_amount'
        # since the discount won't always be there.
        expected_gross_total_excluded = (
            expected_total_excluded
            + suffix_currency.round(current_raw_discount_amount))

        target_factors = [
            {
                # By default, we avoid to have more than one cent as a
                # difference per line.
                'factor': 1.0,
                'base_line': base_line,
            }
            for base_line in base_lines
        ]
        amounts_to_distribute = cls._distribute_delta_amount_smoothly(
            precision_digits=suffix_currency.decimal_places,
            delta_amount=(expected_gross_total_excluded
                          - current_gross_total_excluded),
            target_factors=target_factors,
        )
        for target_factor, amount_to_distribute in zip(
                target_factors, amounts_to_distribute):
            base_line = target_factor['base_line']
            base_line['tax_details'][
                f'gross_total_excluded{suffix}'] += amount_to_distribute

        # Fix rounding issues for 'discount_amount'.
        expected_discount_amount = (
            expected_gross_total_excluded - expected_total_excluded)
        amounts_to_distribute = cls._distribute_delta_amount_smoothly(
            precision_digits=suffix_currency.decimal_places,
            delta_amount=expected_discount_amount - current_discount_amount,
            target_factors=target_factors,
        )
        for target_factor, amount_to_distribute in zip(
                target_factors, amounts_to_distribute):
            base_line = target_factor['base_line']
            base_line['tax_details'][
                f'discount_amount{suffix}'] += amount_to_distribute

    @classmethod
    def _round_raw_tax_amounts(
        cls,
        base_lines_aggregated_values,
        company,
        precision_digits=6,
        apply_strict_tolerance=False,
        in_foreign_currency=True,
    ):
        """ Round 'raw_tax_amount[_currency]'/'raw_base_amount[_currency]'
        according 'precision_digits' / 'in_foreign_currency'.

        ≙ ``_round_raw_tax_amounts`` (``odoo19c: :4849-4949``). Con
        ``apply_strict_tolerance`` reparte la diferencia en los crudos y
        conserva la tasa entre cada base y su impuesto.
        """
        if not base_lines_aggregated_values:
            return

        suffix_currency = (base_lines_aggregated_values[0][0]['currency_id']
                           if in_foreign_currency else company.currency)
        suffix = '_currency' if in_foreign_currency else ''

        for _base_line, aggregated_values in base_lines_aggregated_values:
            for values in aggregated_values.values():
                values[f'raw_tax_amount{suffix}'] = _round_to_digits(
                    values[f'raw_tax_amount{suffix}'], precision_digits)
                values[f'raw_base_amount{suffix}'] = _round_to_digits(
                    values[f'raw_base_amount{suffix}'], precision_digits)

        # Tolerance.
        if not apply_strict_tolerance:
            return

        tax_field = f'tax_amount{suffix}'
        raw_tax_field = f'raw_{tax_field}'
        base_field = f'base_amount{suffix}'
        raw_base_field = f'raw_{base_field}'
        values_per_grouping_key = cls._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_values)
        for grouping_key, values in values_per_grouping_key.items():
            tax_rate = ((values[raw_tax_field] / values[raw_base_field])
                        if values[raw_base_field] else 0)

            target_factors = [
                {
                    'factor': aggregated_values[grouping_key][raw_tax_field],
                    'aggregated_values': aggregated_values[grouping_key],
                }
                for base_line, aggregated_values
                in base_lines_aggregated_values
                if grouping_key in aggregated_values
            ]

            # Tax amount.
            expected_tax_amount = values[tax_field]
            current_raw_tax_amount = values[raw_tax_field]
            delta_raw_amount = cls._get_delta_amount_to_reach_target(
                target_amount=expected_tax_amount,
                target_currency=suffix_currency,
                raw_current_amount=current_raw_tax_amount,
                raw_current_amount_precision_digits=precision_digits,
            )
            amounts_to_distribute = cls._distribute_delta_amount_smoothly(
                precision_digits=precision_digits,
                delta_amount=delta_raw_amount,
                target_factors=target_factors,
            )
            for target_factor, amount_to_distribute in zip(
                    target_factors, amounts_to_distribute):
                aggregated_values = target_factor['aggregated_values']
                aggregated_values[raw_tax_field] += amount_to_distribute
                values[raw_tax_field] += amount_to_distribute
                if amount_to_distribute and tax_rate:
                    new_raw_base_amount = (
                        aggregated_values[raw_tax_field] / tax_rate)
                    rounded_new_raw_base_amount = _round_to_digits(
                        new_raw_base_amount, precision_digits)
                    values[raw_base_field] += (
                        rounded_new_raw_base_amount
                        - aggregated_values[raw_base_field])
                    aggregated_values[raw_base_field] = (
                        rounded_new_raw_base_amount)

            # Base amount.
            if tax_rate:
                current_tax_raw_base_amount = (
                    (current_raw_tax_amount + delta_raw_amount) / tax_rate)
                delta_raw_amount = cls._get_delta_amount_to_reach_target(
                    target_amount=current_tax_raw_base_amount,
                    target_currency=suffix_currency,
                    raw_current_amount=values[raw_base_field],
                    raw_current_amount_precision_digits=precision_digits,
                )
                amounts_to_distribute = cls._distribute_delta_amount_smoothly(
                    precision_digits=precision_digits,
                    delta_amount=delta_raw_amount,
                    target_factors=target_factors,
                )
                for target_factor, amount_to_distribute in zip(
                        target_factors, amounts_to_distribute):
                    aggregated_values = target_factor['aggregated_values']
                    aggregated_values[raw_base_field] += amount_to_distribute
                    values[raw_base_field] += amount_to_distribute
