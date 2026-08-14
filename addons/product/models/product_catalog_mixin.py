r"""``product.catalog.mixin`` — el contrato del selector de productos.

Adaptación de ``addons/product/models/product_catalog_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 151 líneas). Lo hereda todo modelo que
tenga **líneas de producto** y quiera ofrecer el selector de catálogo: el
pedido de venta, la orden de compra, la lista de materiales. Su trabajo es
armar, para una pantalla de productos, **cuánto hay ya en el documento** y
**qué mostrar de lo que todavía no está**.

Clase Python, no modelo abstracto de Django
===========================================

La referencia lo declara ``models.AbstractModel``, pero **no tiene ni un
campo**: son nueve métodos y ninguna columna. Aquí eso es una clase Python a
secas, igual que ``BusListenerMixin`` (``bus/models/bus_listener_mixin.py:61``),
y **no** un ``Meta: abstract = True`` como ``AvatarMixin``
(``base/models/avatar_mixin.py:53-65``), que sí aporta campos.

La discriminación no es de estilo: un abstracto de Django arrastra ``Meta``,
gestores y registro de campos para no declarar ninguno, y complica el orden de
resolución cuando el modelo concreto ya hereda de ``TimeStampedModel``. La
regla que queda es simple — **mixin con campos → abstracto; mixin sólo de
comportamiento → clase**.

Las claves camelCase son el contrato, no un descuido
====================================================

``productId``, ``productType``, ``uomDisplayName``, ``readOnly`` — el
diccionario que estos métodos devuelven **viaja al cliente**, y sus claves son
las que el widget lee. Se conservan verbatim. Traducirlas a ``snake_case``
"por consistencia con el resto del Python" rompería al consumidor sin que nada
lo avise aquí: el diccionario seguiría construyéndose igual de bien.

Es el mismo criterio que ya rige para ``codigo_error`` en la capa DRF — la
clave que cruza la frontera se decide una vez y no se retoca desde dentro.

Dos precedencias, las dos direccionales
=======================================

``_get_product_catalog_order_line_info`` mezcla tres fuentes y el resultado
depende del orden en que las aplica:

1. **Las líneas que ya existen ganan sobre todo lo demás.** El bucle de
   productos nuevos hace ``if product_id in order_line_info: continue`` — un
   producto ya presente en el documento no se pisa con su ficha de catálogo,
   porque su cantidad y su precio son los negociados, no los de lista.
2. **Dentro de un producto nuevo, su ficha gana sobre los valores por
   defecto**: ``{**default_data, **data}``. Invertir ese desempaquetado
   pondría ``quantity: 0`` encima del dato real y el catálogo mostraría todo a
   cero.

Y una tercera, más fácil de perder: ``uomDisplayName`` **sólo** cae a la
unidad del producto si la línea no trajo la suya. Una línea puede estar
expresada en otra unidad, y ése es justamente el caso que el respaldo
incondicional borraría.

Los tres ganchos que hay que sobreescribir — y su trampa
========================================================

``_get_product_catalog_record_lines`` devuelve ``{}``,
``_update_order_line_info`` devuelve ``0`` y ``_is_readonly`` devuelve
``False``. Los tres dicen *"Must be overrided by each model using this
mixin"* y **ninguno lanza**. Se porta tal cual —el neutro es la conducta de la
fuente— pero conviene saber lo que implica: un modelo que herede el mixin y
olvide el primero no da error, da un **catálogo vacío**; y si olvida el
segundo, todo producto añadido queda a precio **cero**. El fallo no aparece
donde está la causa.

Qué NO se porta, con su medición
================================

- **``action_add_from_catalog`` y ``_get_action_add_from_catalog_extra_context``**:
  construyen un ``ir.actions.act_window`` que abre dos vistas XML por
  referencia externa. Lo que falta **no** es la acción: ``IrActionsActWindow``
  está portada (``base/models/ir_actions.py:218``, tabla ``ir_act_window``).
  Faltan **las dos vistas** —
  ``grep -rn "product_view_kanban_catalog\|product_view_search_catalog" src/``
  excluyendo este archivo → **0** — y con ellas el widget de cliente que las
  renderiza. Devolver el diccionario sin los ``id`` que resuelve
  ``self.env.ref`` daría una acción que apunta a nada. El equivalente aquí es
  la ruta DRF que la interfaz llame, que consume los métodos de abajo
  directamente.
- **``self.env.user.has_group('uom.group_uom')``** del contexto extra: decide
  si la pantalla muestra la columna de unidad. La autorización aquí es por
  capacidad (DEC-11), no por grupo, y además es una decisión de presentación.
- **``@api.readonly``**: marca la acción como no-mutante para el enrutado de
  lecturas de Odoo. No tiene análogo; en DRF lo expresa el verbo HTTP.
"""
import models

from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import TYPE_COMBO

#: Los valores neutros de ``_default_order_line_values``, verbatim. Un producto
#: que aún no está en el documento entra con cantidad cero.
DEFAULT_QUANTITY = 0


class ProductCatalogMixin:
    """``product.catalog.mixin`` — lo hereda quien tiene líneas de producto.

    El modelo que lo use debe tener el conjunto de líneas y, en el modelo de
    esas líneas, un ``_get_product_catalog_lines_data``. Es la suposición que
    el docstring de la referencia declara y que este mixin no puede verificar.
    """

    def _is_readonly(self):
        """¿El documento admite cambios? Gancho — sobreescribir.

        Devuelve ``False`` (editable) por defecto, como la fuente. Un pedido
        confirmado o una orden cerrada devolverían ``True``.
        """
        return False

    def _default_order_line_values(self, child_field=False):
        """Lo que se muestra de un producto que **no** está en el documento.

        La fuente escribe ``self._is_readonly() if self else False`` para
        cubrir el conjunto vacío de su ORM. Aquí ``self`` es siempre un
        registro, así que la guarda desaparece — no es una simplificación de
        criterio, es que la condición no puede darse.
        """
        return {
            'quantity': DEFAULT_QUANTITY,
            'readOnly': self._is_readonly(),
        }

    def _get_product_catalog_domain(self):
        """Qué productos entran en el catálogo de **este** documento.

        Dos condiciones, verbatim de la fuente:

        - la compañía del producto está vacía (compartido) **o** es la del
          documento o una de sus ascendientes. El ``parent_of`` de la
          referencia se resuelve con ``ResCompany.parent_ids``, que sale de
          leer la ruta materializada y no de recorrer la cadena;
        - el producto **no** es un combo. Un combo agrupa otros productos: no
          es un artículo que se añada a una línea.

        Quien herede el mixin y necesite ocultar más puede componer con este
        ``Q``; la fuente lo dice en su docstring y aquí es lo mismo.
        """
        company = getattr(self, 'company', None)
        if company is None:
            company_scope = models.Q(company__isnull=True)
        else:
            company_scope = (
                models.Q(company__isnull=True)
                | models.Q(company__in=company.parent_ids)
            )
        return company_scope & ~models.Q(type=TYPE_COMBO)

    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        """Las líneas del documento agrupadas por producto. Gancho.

        Devuelve ``{}`` como la fuente. **Sobreescribir**: sin él el catálogo
        no sabe qué hay ya en el documento y lo muestra todo como nuevo, sin
        un solo error que lo delate.

        El diccionario va **indexado por el producto**, no por su id — así lo
        consume la mezcla de abajo. Aquí eso trae una condición que la fuente
        no tiene: una instancia de Django sin ``pk`` **no es hashable** y
        rompe al usarse de clave. En la práctica no se da (un producto de
        catálogo está guardado), pero quien sobreescriba no debe construir la
        clave con un producto sin persistir.
        """
        return {}

    def _get_product_catalog_order_data(self, products, **kwargs):
        """La ficha de catálogo de productos que **aún no** están.

        Las claves son las que lee el cliente. ``code`` es el código con que
        el interlocutor conoce el producto: en la referencia sale de
        ``product.code``, que depende del ``partner_id`` del contexto. Aquí ese
        contexto no existe, así que el interlocutor llega por ``kwargs`` y se
        pasa a ``code_for`` — la misma dependencia, escrita donde se ve.
        """
        partner = kwargs.get('partner')
        return {
            product.pk: {
                'productType': product.type,
                'uomDisplayName': str(product.uom) if product.uom else '',
                'code': product.code_for(partner) or '',
            }
            for product in products
        }

    def _get_product_catalog_order_line_info(
        self, product_ids, child_field=False, **kwargs,
    ):
        """Lo que la pantalla muestra por producto: lo que hay y lo que falta.

        Las tres precedencias del docstring del módulo se aplican aquí, en
        este orden: primero las líneas existentes, luego el respaldo de
        ``uomDisplayName``, y al final los productos nuevos, que **no** pisan
        a los que ya estaban.
        """
        order_line_info = {}

        record_lines = self._get_product_catalog_record_lines(
            product_ids, child_field=child_field, **kwargs)
        for product, lines in record_lines.items():
            info = {
                **lines._get_product_catalog_lines_data(
                    parent_record=self, **kwargs),
                'productType': product.type,
                'code': product.code_for(kwargs.get('partner')) or '',
            }
            # Sólo si la línea no trajo la suya: puede estar en otra unidad.
            if not info.get('uomDisplayName'):
                info['uomDisplayName'] = str(product.uom) if product.uom else ''
            order_line_info[product.pk] = info

        default_data = self._default_order_line_values(child_field)
        products = self._catalog_products(product_ids)
        product_data = self._get_product_catalog_order_data(products, **kwargs)

        for product_id, data in product_data.items():
            if product_id in order_line_info:
                continue        # lo negociado gana sobre la ficha de catálogo
            order_line_info[product_id] = {**default_data, **data}

        return order_line_info

    @staticmethod
    def _catalog_products(product_ids):
        """Las variantes por id — el ``browse`` de la fuente.

        Aparte para que quien herede pueda acotar el conjunto (por compañía,
        por archivado) sin reescribir la mezcla de arriba, que es donde están
        las precedencias que importan.
        """
        return ProductProduct.objects.filter(pk__in=product_ids)

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """Fija la cantidad de un producto, creando la línea si no existe.
        Gancho.

        Devuelve el precio unitario resultante. El neutro de la fuente es
        ``0``: **sobreescribir**, o todo lo que se añada desde el catálogo
        entra a precio cero sin avisar.
        """
        return 0
