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

- **La envoltura de base-lines** —``_prepare_base_line_for_taxes_computation``
  (``:1593``), ``_add_tax_details_in_base_line`` (``:1739``),
  ``_add_accounting_data_to_base_line_tax_details``—. No es cálculo: es el
  sobre que lleva el resultado a la contabilidad (cuenta destino por línea de
  reparto, etiquetas CABA, agrupación por ``account.tax.group``). El motor es
  el mismo a ambos lados, medido: ``_add_tax_details_in_base_line`` llama a
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
from decimal import Decimal

import fields
import models

#: Precisión por defecto del redondeo por línea, igual que la referencia
#: (``float_round(..., precision_rounding=0.01)``).
DEFAULT_ROUNDING = Decimal('0.01')

_CIEN = Decimal('100')


def _d(valor):
    """A ``Decimal`` sin pasar por ``float`` — la conversión que corrompe."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


class AccountTaxQuerySet(models.QuerySet):
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
        grupo_por_impuesto = {}
        for tax in sorted(self, key=clave):
            if tax.amount_type == 'group':
                hijos = sorted(tax.children.all(), key=clave)
                for hijo in hijos:
                    if hijo not in ordenados:
                        ordenados.append(hijo)
                    grupo_por_impuesto[hijo.pk] = tax
            elif tax not in ordenados:
                ordenados.append(tax)
        return ordenados, grupo_por_impuesto

    def _batch_for_taxes_computation(self, special_mode=False,
                                     filter_tax_function=None):
        """≙ ``_batch_for_taxes_computation`` (``odoo19c: :924``).

        Agrupa los impuestos **consecutivos** que se evalúan juntos. Recorre
        en orden inverso, igual que la referencia: el corte de lote depende de
        si el impuesto *siguiente* acepta ser afectado (``is_base_affected``),
        y eso sólo se sabe viniendo desde el final.
        """
        ordenados, grupo_por_impuesto = self._flatten_taxes_and_sort_them()
        if filter_tax_function:
            ordenados = [t for t in ordenados if filter_tax_function(t)]

        lote_por_impuesto = {}
        lote = []
        base_afectada = False
        for tax in reversed(ordenados):
            if lote:
                mismo_lote = (
                    tax.amount_type == lote[0].amount_type
                    and (special_mode
                         or tax.price_include == lote[0].price_include)
                    and tax.include_base_amount == lote[0].include_base_amount
                    and ((tax.include_base_amount and not base_afectada)
                         or not tax.include_base_amount)
                )
                if not mismo_lote:
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
            'group_per_tax': grupo_por_impuesto,
            'sorted_taxes': ordenados,
        }

    # -- propagación de base ------------------------------------------------

    @staticmethod
    def _propagate_extra_taxes_base(ordenados, tax, taxes_data,
                                    special_mode=False):
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

    # -- el motor -----------------------------------------------------------

    def _get_tax_details(self, price_unit, quantity=1,
                         precision_rounding=DEFAULT_ROUNDING,
                         rounding_method='round_per_line',
                         special_mode=False, filter_tax_function=None):
        """≙ ``_get_tax_details`` (``odoo19c: :1139``). Las tres pasadas.

        Devuelve ``{'total_excluded', 'total_included', 'taxes_data'}``, donde
        cada entrada de ``taxes_data`` trae su ``tax``, su ``base`` y su
        ``tax_amount``.
        """
        price_unit = _d(price_unit)
        quantity = _d(quantity)
        redondear = rounding_method == 'round_per_line'

        lotes = self._batch_for_taxes_computation(
            special_mode=special_mode, filter_tax_function=filter_tax_function)
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

        contexto = {'price_unit': price_unit, 'quantity': quantity}

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
                ordenados, tax, taxes_data, special_mode=special_mode)

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
            total_lote = sum(
                (taxes_data[otro.pk].get('tax_amount', Decimal('0'))
                 for otro in datos['batch']),
                Decimal('0'),
            )
            base = raw_base + datos['extra_base_for_base']
            if datos['price_include'] and special_mode in (False, 'total_included'):
                base -= total_lote
            datos['base'] = base
            datos['taxes'] = list(posteriores) if tax.include_base_amount else []
            if tax.is_base_affected:
                posteriores.append(tax)

        lista = [d for d in taxes_data.values() if 'tax_amount' in d]
        if lista:
            total_excluded = lista[0]['base']
            total_included = total_excluded + sum(
                (d['tax_amount'] for d in lista), Decimal('0'))
        else:
            total_excluded = total_included = raw_base

        return {
            'total_excluded': total_excluded,
            'total_included': total_included,
            'taxes_data': lista,
        }

    # -- la API pública -----------------------------------------------------

    def compute_all(self, price_unit, currency=None, quantity=1,
                    product=None, partner=None, is_refund=False,
                    handle_price_include=True, rounding_method='round_per_line'):
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
        precision = (currency.rounding if currency is not None
                     else DEFAULT_ROUNDING)
        detalle = self._get_tax_details(
            price_unit, quantity=quantity,
            precision_rounding=_d(precision),
            rounding_method=rounding_method,
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
                    'base': d['base'],
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
        'account.AccountTax', on_delete=models.CASCADE, related_name='+',
        help_text='Impuesto doméstico a reemplazar (Odoo src_tax_id).',
    )
    dest_tax = fields.Many2one(
        'account.AccountTax', on_delete=models.CASCADE, related_name='+',
        help_text='Impuesto de reemplazo — "this Replacement tax" en la '
                  'referencia (Odoo dest_tax_id).',
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

    name          = fields.Char(
        max_length=255, help_text='Nombre del impuesto (Odoo name, requerido).',
    )
    amount        = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0'),
        help_text='Monto/porcentaje del impuesto (Odoo amount).',
    )
    amount_type   = fields.Selection(
        max_length=12, choices=AMOUNT_TYPES, default='percent',
        help_text='Forma de cómputo (Odoo amount_type, requerido).',
    )
    type_tax_use  = fields.Selection(
        max_length=12, choices=TYPE_TAX_USE, default='sale',
        help_text='Uso del impuesto (Odoo type_tax_use, requerido).',
    )
    price_include = fields.Boolean(
        default=False,
        help_text='Precio con impuesto incluido (Odoo price_include). En la '
                  'referencia es un compute sobre price_include_override + '
                  'company_price_include; aquí es el booleano directo.',
    )
    sequence      = fields.Integer(
        default=1, db_index=True,
        help_text='Orden de aplicación de los impuestos de una línea (Odoo '
                  'sequence). NO es decorativo: el motor evalúa por este '
                  'orden y de él dependen los lotes.',
    )
    include_base_amount = fields.Boolean(
        default=False,
        help_text='Afecta la base de los impuestos posteriores (Odoo '
                  'include_base_amount).',
    )
    is_base_affected = fields.Boolean(
        default=True,
        help_text='Su base puede ser afectada por impuestos anteriores (Odoo '
                  'is_base_affected).',
    )
    children      = fields.Many2many(
        'account.AccountTax', blank=True, symmetrical=False,
        related_name='parent_taxes', db_table='account_tax_filiation_rel',
        help_text='Sub-impuestos cuando amount_type=group (Odoo '
                  'children_tax_ids). symmetrical=False: la relación es '
                  'dirigida, padre → hijos.',
    )
    active        = fields.Boolean(
        default=True, help_text='Impuesto activo (Odoo active).',
    )
    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='taxes',
        help_text='Empresa (Odoo company_id).',
    )
    tax_group     = fields.Many2one(
        'account.AccountTaxGroup', on_delete=models.PROTECT, null=True, blank=True,
        related_name='taxes',
        help_text='Grupo al que pertenece el impuesto (Odoo tax_group_id); '
                  'agrupa los subtotales del documento.',
    )
    original_tax_ids = fields.Many2many(
        'account.AccountTax', through='account.AccountTaxAlternative',
        through_fields=('dest_tax', 'src_tax'), related_name='+',
        blank=True, verbose_name='Reemplaza a',
        help_text='Impuestos que ESTE reemplaza al aplicar cualquiera de las '
                  'posiciones fiscales estipuladas (Odoo original_tax_ids, '
                  'string "Replaces"). Es la mitad de escritura del mecanismo '
                  'de sustitución: sin ella, '
                  'AccountFiscalPosition._compute_tax_map devuelve siempre '
                  '{} (H-API-322).',
    )
    replacing_tax_ids = fields.Many2many(
        'account.AccountTax', through='account.AccountTaxAlternative',
        through_fields=('src_tax', 'dest_tax'), related_name='+',
        editable=False, verbose_name='Reemplazado por',
        help_text='Reverso de original_tax_ids: impuestos que reemplazan a '
                  'ESTE (Odoo replacing_tax_ids, string "Replaced by", '
                  'readonly=True en la referencia — de ahí editable=False).',
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
            factor = (Decimal('1') / (Decimal('1') + total)
                      if total != Decimal('-1') else Decimal('0'))
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
            divisor = (Decimal('1') if total == Decimal('1')
                       else Decimal('1') - total)
            return raw_base * _d(self.amount) / _CIEN / divisor
        return None

    def compute_amount(self, base_amount):
        """Impuesto de UN ``base_amount`` — atajo de un solo impuesto.

        Delega en los mismos evaluadores que usa ``compute_all``, con el lote
        reducido a ``[self]``, así que el atajo y el motor **no pueden
        divergir**: si mañana cambia una fórmula, cambia en un solo sitio.
        Lo que el atajo sigue sin ver es lo que depende de haber más de un
        impuesto — lotes de dos porcentuales incluidos, ``include_base_amount``,
        propagación de base. Para una línea real, ``compute_all``.

        **``division`` cambió de semántica aquí (H-API-342).** Antes calculaba
        ``base - base/(1+amount/100)``, que es la extracción de un *porcentaje*
        incluido en precio, no lo que la referencia entiende por ``division``
        (``odoo19c: :88-95``: *"e.g 180 / (1 - 10%) = 200 (not price included);
        e.g 200 * (1 - 10%) = 180 (price included)"*). El resultado viejo
        coincidía con el nuevo sólo cuando ``amount`` era 0.

        **Y ahora honra ``price_include``**, que antes ignoraba: un 16 % marcado
        como incluido devuelve el impuesto *contenido* en el precio, no un 16 %
        añadido encima. Es la diferencia entre las dos ramas de la referencia
        (``:1110`` vs ``:1130``), y confundirlas era el defecto de fondo.
        """
        base = _d(base_amount)
        if self.amount_type == 'fixed':
            return _d(self.amount)
        contexto = {'price_unit': base, 'quantity': Decimal('1')}
        if self.price_include:
            monto = self._eval_tax_amount_price_included([self], base, contexto)
        else:
            monto = self._eval_tax_amount_price_excluded([self], base, contexto)
        return monto if monto is not None else Decimal('0')
