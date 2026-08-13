"""``product.combo`` — una *elección* dentro de un producto combo.

Adaptación de ``addons/product/models/product_combo.py``
(``odoo-tools@622ddc2aa5``, ``odoo19c:``, 79 líneas).

Qué es un combo, y por qué hay dos modelos
==========================================

El nombre engaña si se lee rápido. Un **producto** de tipo ``combo``
(``product.template.type == 'combo'``) es el menú; un ``product.combo`` es
**una elección dentro de ese menú** —el ``string`` de la referencia lo dice:
*"Combo Choices"*—; y un ``product.combo.item`` es **una opción concreta**
dentro de la elección.

Con un menú de hamburguesería: el producto combo es "Menú del día"; sus dos
``product.combo`` son "Bebida" y "Postre"; los ``product.combo.item`` de
"Bebida" son refresco, agua, cerveza. Por eso la relación producto→elección es
**muchos a muchos**: la elección "Bebida" se reutiliza en varios menús.

``base_price`` es el **mínimo**, y ahí está todo el diseño
==========================================================

No es la suma ni el promedio: es ``min()`` sobre el precio de los items. El
``help`` de la referencia explica para qué, y conviene leerlo entero porque es
la razón de que el campo exista:

    *"El precio mínimo entre los productos de este combo. Se usa para prorratear
    el precio de este combo respecto a los otros combos de un producto combo.
    Esta heurística asegura que, elija lo que elija el usuario, siempre costará
    lo mismo."*

Es decir: el menú tiene un precio único, y cada elección se lleva una fracción
proporcional a su ``base_price``. Tomar la suma o el promedio rompería esa
invariante — el precio final del menú cambiaría según cuántas opciones tenga
cada elección, que es exactamente lo que la heurística evita.

Qué NO se porta, con su medición
================================

- **La conversión entre monedas de ``_compute_base_price``.** La referencia
  convierte el precio de cada item a la moneda del combo antes de comparar,
  con ``item.currency_id._convert(from_amount, to_currency, company, date)``.
  Ese método **no está portado**: ``ResCurrency``
  (``base/models/res_currency.py:14-70``) declara ``name``, ``symbol``,
  ``rounding``, ``decimal_places``, ``position``, ``active`` y
  ``currency_unit_label``, y sus únicos métodos son ``__str__`` y ``save``.

  Consecuencia declarada: ``base_price`` es exacto **mientras los items
  compartan moneda**, que es el caso normal —los items son productos de la
  misma compañía—. Con monedas mezcladas el mínimo se toma sobre importes no
  comparables. Se porta el ``min`` porque **el algoritmo es el mínimo**; la
  conversión llega sola cuando ``ResCurrency`` gane su ``_convert``, sin tocar
  este archivo.
- **``_get_main_company()`` como respaldo de la moneda.** La referencia cae a
  la moneda de la compañía principal cuando el combo no tiene compañía. Ese
  helper tampoco existe aquí, así que sin compañía la moneda es ``None`` — y
  se dice, en vez de inventar un respaldo que no está en la fuente.
- **``copy=False`` en ``sequence``.** Es semántica de *duplicar registro* del
  ORM de Odoo; Django no tiene una operación de copia que lo respete. Se anota
  porque describe intención —al duplicar una elección, su orden no se hereda—
  y quien implemente la duplicación en un serializer debe respetarlo.
- **``_read_group`` de ``_compute_combo_item_count``.** Es una optimización
  para contar los items de N combos en **una** consulta agrupada. Aquí el
  conteo es una propiedad por registro; la optimización equivalente es
  ``annotate(Count(...))`` en el queryset de la vista, que es su sitio.

Las tres invariantes, y por qué una no puede vivir en ``clean()``
=================================================================

La referencia declara tres ``@api.constrains``. Dos se portan a ``clean()``
sin fricción —son sobre campos propios—. La tercera **no puede**:

``_check_combo_item_ids_not_empty`` exige que la elección tenga al menos un
item. En Odoo el ``One2many`` se escribe en la misma transacción que el padre,
así que la comprobación tiene datos que mirar. En Django el padre se persiste
**antes** que sus hijos: un ``clean()`` que exija items haría **imposible
crear** una elección, porque en el instante de validar todavía no puede tener
ninguno.

Se porta como ``check_has_items()``, un método explícito que el llamador
invoca **después** de adjuntar los items. La invariante es la misma; lo que
cambia es quién dispara la comprobación, y cambia por una diferencia real de
los dos ORM, no por comodidad.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_template import ProductTemplate


class ProductCombo(TimeStampedModel):
    """``product.combo`` — una elección dentro de un producto combo."""

    name = fields.Char(max_length=255, verbose_name='Nombre de la elección')
    sequence = fields.Integer(
        default=10, verbose_name='Secuencia',
        help_text='Orden de la elección dentro del menú. En la referencia es '
                  'copy=False: al duplicar, el orden NO se hereda.',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='combo_ids', verbose_name='Compañía',
        help_text='Vacío = la elección sirve a todas las compañías.')
    product_tmpls = fields.Many2many(
        ProductTemplate, blank=True, related_name='combo_ids',
        verbose_name='Productos combo que la usan',
        help_text='Odoo declara este M2M en product.template como combo_ids; '
                  'aquí se declara del lado del combo con ese related_name, '
                  'así template.combo_ids es el mismo nombre de la fuente. La '
                  'referencia no nombra el lado inverso.',
    )

    class Meta:
        db_table = 'product_combo'
        ordering = ['sequence', 'id']
        verbose_name = 'Elección de combo'
        verbose_name_plural = 'Elecciones de combo'

    def __str__(self):
        return self.name

    # === DERIVADOS ========================================================

    @property
    def combo_item_count(self):
        """``_compute_combo_item_count`` — cuántas opciones ofrece.

        Devuelve 0 mientras ``product.combo.item`` no esté portado; llega solo
        por el ``related_name`` de aquel archivo, sin tocar éste.
        """
        items = getattr(self, 'combo_item_ids', None)
        return items.count() if items is not None else 0

    @property
    def currency(self):
        """``_compute_currency_id`` — la moneda de la compañía de la elección.

        Sin compañía devuelve ``None``: el respaldo a la compañía principal de
        la referencia necesita ``_get_main_company()``, que no está portado
        (ver el docstring del módulo).
        """
        return getattr(self.company, 'currency', None)

    @property
    def base_price(self):
        """``_compute_base_price`` — el **mínimo** precio entre sus opciones.

        Mínimo, no suma ni promedio: es lo que permite prorratear el precio del
        menú entre sus elecciones de forma que la elección del usuario no
        cambie el total. Ver el docstring del módulo.

        Sin items devuelve 0, como la fuente. La conversión de moneda que la
        referencia aplica antes de comparar **no** se porta; el resultado es
        exacto mientras los items compartan moneda.
        """
        items = getattr(self, 'combo_item_ids', None)
        if items is None:
            return 0
        prices = [item.lst_price for item in items.all()]
        return min(prices) if prices else 0

    # === INVARIANTES ======================================================

    def clean(self):
        """Las dos invariantes que sí caben en la validación del registro.

        - **Sin productos duplicados** (``_check_combo_item_ids_no_duplicates``):
          ofrecer dos veces el mismo refresco en la misma elección no es una
          opción, es un error de captura.
        - **Coherencia de compañía** (``_check_company_id``): la elección, los
          productos de sus opciones y los menús que la usan tienen que ser de
          la misma compañía. La referencia lo expresa con ``check_company``;
          Django no tiene ese atributo, así que la comprobación es explícita.

        La tercera —que tenga al menos un item— vive en ``check_has_items``;
        el docstring del módulo explica por qué no puede estar aquí.
        """
        super().clean()
        items = getattr(self, 'combo_item_ids', None)
        if items is None or self.pk is None:
            return
        product_ids = [item.product_id for item in items.all()]
        if len(set(product_ids)) < len(product_ids):
            raise ValidationError(
                'Una elección de combo no puede ofrecer el mismo producto '
                'dos veces.')
        if self.company_id and any(
            getattr(item, 'company_id', None)
            and item.company_id != self.company_id for item in items.all()
        ):
            raise ValidationError(
                'Las opciones y la elección son de compañías distintas.')

    def check_has_items(self):
        """``_check_combo_item_ids_not_empty`` — al menos una opción.

        **Se invoca después de adjuntar los items**, no desde ``clean()``:
        Django persiste el padre antes que sus hijos, así que un ``clean()``
        que exigiera items impediría crear la elección. Ver el docstring del
        módulo.
        """
        items = getattr(self, 'combo_item_ids', None)
        if items is None or not items.exists():
            raise ValidationError(
                'Una elección de combo debe ofrecer al menos un producto.')
