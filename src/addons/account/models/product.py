"""Lo que ``account`` le cuelga al producto — ≙ ``_inherit`` (T-B2a, Bloque 3).

Adaptación de ``addons/account/models/product.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``). Es la superficie que ningún inventario
de ``_name`` ve: ``account`` no declara ``product.template`` ni
``product.category``, pero les añade los campos sin los cuales una línea de
venta no sabe **qué impuesto aplicar** ni **a qué cuenta imputar**.

Sin esto, el impuesto de una factura llega cableado desde fuera en vez de
resolverse desde el producto. Ése es el circuito que este archivo cierra.

Quién escribe la extensión — y dónde aterriza su columna
========================================================

La escribe ``account``, no ``product``: el producto existe en el catálogo
aunque nadie lleve contabilidad. Medido en la referencia
(``odoo-tools@622ddc2a``): el ``__manifest__`` de ``product`` declara
``depends = ['base', 'mail', 'uom']`` — **no** ``account``; el de ``account``
sí declara ``product``. La dirección de la dependencia es la que fija quién
puede nombrar a quién.

El mecanismo es el mismo que ya usa ``website_sale`` para publicar un producto
(``website_sale/models/product_template.py``): ``add_to_class`` desde el
``ready()`` del addon que extiende. Y arrastra la misma **divergencia de
plataforma**, ya declarada allí: el autodetector atribuye la migración al
``app_label`` del **modelo**, así que las columnas se crean desde
``product/migrations/`` aunque las contribuya ``account``. En la referencia,
desinstalar ``account`` retira las columnas; aquí no hay tal desinstalación.

Lo que **sí** se preserva es lo que importa: ``product/models/*.py`` no
menciona la contabilidad, y quien decide que un producto tenga cuenta de
ingreso es este archivo.

``company_dependent`` → FK simple
==================================

Los cuatro campos de cuenta son ``company_dependent=True`` en la referencia —
el mecanismo de *Property fields*, un valor distinto por empresa sobre la
misma fila. Este ORM no lo tiene, así que se portan como FK simples: mismo
criterio ya fijado en ``account_cash_rounding.py:12`` y en
``analytic_plan.py:53``. Se declara aquí para que nadie lea la FK como si
fuera per-empresa.

``ondelete='restrict'`` de la referencia → ``on_delete=PROTECT``: borrar una
cuenta usada por un producto debe fallar, no dejar el producto sin cuenta.

Los 6 campos del bloque que **no** se portan, y por qué
=======================================================

De los 13 campos que el mapa de T-B1 cuenta para este bloque, se portan **7**.
Los otros 6 son ``compute`` no almacenados y cada uno está bloqueado por algo
concreto — ninguno es un olvido:

=================================  ==========  ==========================================
Campo                              Modelo      Qué lo bloquea
=================================  ==========  ==========================================
``tax_string``                     template    ``AccountTax`` no tiene ``compute_all``
``tax_string``                     product     ídem (delega en el de la plantilla)
``fiscal_country_codes``           template    ``ResCompany.account_fiscal_country_id``
``fiscal_country_codes``           currency    ídem
``display_rounding_warning``       currency    ``_origin`` (pseudo-registro de onchange)
=================================  ==========  ==========================================

- **``tax_string``** (×2) construye *"(= 121,00 € Incl. Taxes)"* llamando a
  ``taxes_id.compute_all(price, product=…, partner=…)``
  (``odoo19c: product.py:112-128``). Nuestro ``AccountTax`` declara
  ``compute_amount`` y **no** ``compute_all`` — medido:
  ``grep -n "def " account_tax.py`` da ``__str__`` y ``compute_amount``, nada
  más. Portar el formateador sobre un motor que no existe daría siempre la
  cadena vacía que la referencia usa como *placeholder*. **Sucesor: tarea
  #141.**
- **``fiscal_country_codes``** (×2) mapea
  ``account_fiscal_country_id.code`` sobre las empresas permitidas. Ese campo
  es del Bloque 1 (los 72 de ``res.company``), medido ausente:
  ``grep -n "account_fiscal_country" res_company.py`` → 0 hits. **Ya cubierto
  por la tarea #137**, que mapea ese bloque.
- **``display_rounding_warning``** compara ``record._origin.rounding`` con
  ``record.rounding``: es el aviso que la vista de formulario de Odoo muestra
  **mientras se edita**, comparando el valor en pantalla con el de la base.
  ``_origin`` es el pseudo-registro de ``onchange``; aquí no hay análogo
  porque no hay onchange de servidor. **DESCONOCIDO declarado**, con su
  condición de cierre: se decide si alguna vez existe un canal equivalente
  (validación en el serializer con el valor previo), no antes.

El ``default`` de los dos M2M tampoco se porta
===============================================

La referencia da a ``taxes_id`` el default
``env.companies.account_sale_tax_id or …root_id.sudo().account_sale_tax_id``
(``odoo19c: product.py:44``). Depende del mismo Bloque 1 ausente, así que un
producto nuevo nace **sin impuestos por defecto** en vez de con los de la
empresa. Es una divergencia de comportamiento real y se declara: la cierra
#137, no este archivo.

Los métodos sí se portan — con su tercer escalón cortado
=========================================================

``_get_product_accounts`` resuelve la cuenta en **tres escalones**: producto →
categoría (subiendo el árbol) → empresa. Los dos primeros se portan enteros;
el tercero —``(self.company_id or self.env.company).income_account_id``— cae
en el mismo hueco del Bloque 1. Queda como ``None`` con el hueco anotado en el
propio método, no silenciado.
"""
import fields
from django.db import models as dj_models

from addons.product.models import ProductCategory, ProductProduct, ProductTemplate


def _property_account(help_text):
    """FK a ``account.account`` con la semántica de la referencia.

    ``company_dependent`` allá, FK simple aquí (ver el docstring del módulo);
    ``ondelete='restrict'`` → ``PROTECT``.
    """
    return fields.Many2one(
        'account.AccountAccount',
        null=True, blank=True, on_delete=dj_models.PROTECT,
        related_name='+',
        help_text=help_text,
    )


def _get_category_account(self, field_name):
    """≙ ``_get_category_account`` (``odoo19c: product.py:80-92``).

    Sube el árbol de categorías y devuelve la primera cuenta definida. No es
    "la cuenta de mi categoría": es la de la primera categoría **ascendiente**
    que la tenga, que es lo que permite configurar una vez arriba y heredar
    hacia abajo.
    """
    categ = self.categ
    while categ is not None:
        cuenta = getattr(categ, field_name, None)
        if cuenta is not None:
            return cuenta
        categ = categ.parent
    return None


def _get_product_accounts(self):
    """≙ ``_get_product_accounts`` (``odoo19c: product.py:67-78``).

    Tres escalones en la referencia: producto → categoría → empresa. Aquí los
    dos primeros; el tercero (``ResCompany.income_account_id`` /
    ``expense_account_id``) pertenece al Bloque 1 y **no existe todavía**, así
    que un producto sin cuenta propia ni categoría con cuenta devuelve
    ``None`` en vez de la de la empresa. Lo cierra la tarea #137.
    """
    return {
        'income': (
            self.property_account_income
            or _get_category_account(self, 'property_account_income_categ')
        ),
        'expense': (
            self.property_account_expense
            or _get_category_account(self, 'property_account_expense_categ')
        ),
    }


def get_product_accounts(self, fiscal_pos=None):
    """≙ ``get_product_accounts`` (``odoo19c: product.py:94-98``).

    La posición fiscal **remapea** la cuenta resuelta: es el punto donde un
    cliente de otro régimen imputa a una cuenta distinta sin tocar el
    producto. Sin posición fiscal, devuelve la resolución cruda.
    """
    cuentas = _get_product_accounts(self)
    if fiscal_pos is None:
        return cuentas
    return {clave: fiscal_pos.map_account(cuenta)
            for clave, cuenta in cuentas.items()}


def _get_variant_product_accounts(self):
    """≙ ``ProductProduct._get_product_accounts`` (``odoo19c: product.py:219``).

    La variante delega en su plantilla: la cuenta contable es del producto,
    no de la combinación de atributos.
    """
    return _get_product_accounts(self.product_tmpl)


def _add_if_absent(model, nombre, campo):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en tests
    que recargan el registro de apps (mismo criterio que
    ``WebsitePublishedMixin.apply_to``).
    """
    if not any(f.name == nombre for f in model._meta.get_fields()):
        model.add_to_class(nombre, campo)


def apply_account_extensions():
    """Cuelga del producto lo que la contabilidad necesita — ≙ ``_inherit``.

    Se invoca desde ``AccountConfig.ready()``: en tiempo de import el registro
    de modelos aún no está poblado.
    """
    # --- product.category (2 campos) ---------------------------------------
    _add_if_absent(
        ProductCategory, 'property_account_income_categ',
        _property_account(
            'Cuenta de ingreso de la categoría, usada al validar una factura '
            'de cliente cuando el producto no declara la suya (Odoo '
            'property_account_income_categ_id).'),
    )
    _add_if_absent(
        ProductCategory, 'property_account_expense_categ',
        _property_account(
            'Cuenta de gasto de la categoría, usada al validar una factura de '
            'proveedor cuando el producto no declara la suya (Odoo '
            'property_account_expense_categ_id).'),
    )

    # --- product.template (5 de 7 campos; ver docstring) -------------------
    _add_if_absent(
        ProductTemplate, 'taxes',
        fields.Many2many(
            'account.AccountTax', blank=True,
            related_name='product_templates_sale',
            db_table='product_taxes_rel',
            help_text='Impuestos por defecto al VENDER el producto (Odoo '
                      'taxes_id; type_tax_use=sale). Sin default: el de la '
                      'referencia lee ResCompany.account_sale_tax_id, campo '
                      'del Bloque 1 aún ausente (tarea #137).'),
    )
    _add_if_absent(
        ProductTemplate, 'supplier_taxes',
        fields.Many2many(
            'account.AccountTax', blank=True,
            related_name='product_templates_purchase',
            db_table='product_supplier_taxes_rel',
            help_text='Impuestos por defecto al COMPRAR el producto (Odoo '
                      'supplier_taxes_id; type_tax_use=purchase). Sin default '
                      'por la misma razón que taxes.'),
    )
    _add_if_absent(
        ProductTemplate, 'property_account_income',
        _property_account(
            'Cuenta de ingreso del producto. Vacía = se usa la de la '
            'categoría (Odoo property_account_income_id).'),
    )
    _add_if_absent(
        ProductTemplate, 'property_account_expense',
        _property_account(
            'Cuenta de gasto del producto. Vacía = se usa la de la categoría '
            '(Odoo property_account_expense_id).'),
    )
    _add_if_absent(
        ProductTemplate, 'account_tags',
        fields.Many2many(
            'account.AccountAccountTag', blank=True,
            related_name='product_templates',
            db_table='product_template_account_tag_rel',
            help_text='Etiquetas a poner en los apuntes de base e impuesto '
                      'generados por este producto (Odoo account_tag_ids; '
                      'applicability=products).'),
    )

    # --- métodos (no son campos: se cuelgan directo) ------------------------
    for modelo, metodos in (
        (ProductTemplate, {
            '_get_product_accounts': _get_product_accounts,
            '_get_category_account': _get_category_account,
            'get_product_accounts': get_product_accounts,
        }),
        (ProductProduct, {
            '_get_product_accounts': _get_variant_product_accounts,
        }),
    ):
        for nombre, funcion in metodos.items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, funcion)
