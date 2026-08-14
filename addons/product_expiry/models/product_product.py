r"""``product.template`` / ``product.product`` — configuración de caducidad.

Adaptación de Odoo ``product_expiry/models/product_product.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 8 de la referencia
================================================

``odoo19c: addons/product_expiry/models/product_product.py`` (59 líneas):
2 clases, 8 símbolos.

===========================================  ==========================================
Símbolo de la referencia (línea)             Dónde queda en este puerto
===========================================  ==========================================
``ProductProduct._compute_quantities_dict``  **bloqueado** — ver "Lo que no cierra"
``ProductProduct.free_qty`` (help, 51-54)    **bloqueado** — el campo no existe aquí
``ProductProduct.virtual_available`` (55-58) **bloqueado** — el campo no existe aquí
``ProductTemplate.use_expiration_date`` (20) campo homónimo (``add_to_class``)
``ProductTemplate.expiration_time`` (24)     campo homónimo (``add_to_class``)
``ProductTemplate.use_time`` (28)            campo homónimo (``add_to_class``)
``ProductTemplate.removal_time`` (31)        campo homónimo (``add_to_class``)
``ProductTemplate.alert_time`` (34)          campo homónimo (``add_to_class``)
``ProductTemplate.write`` (37-40)            receptor ``pre_save`` ``_clear_expiry_when_untracked``
===========================================  ==========================================

Los cinco campos van sobre **``product.template``**, igual que la referencia;
``product.product`` los expone por delegación al template — que es como este
puerto materializa el ``_inherits`` de la referencia
(``api: addons/product/models/product_product.py``, donde ``categ``, ``uom`` y
``type`` ya se resuelven así).

``write`` → receptor ``pre_save``
-----------------------------------

La referencia intercepta la escritura para apagar ``use_expiration_date`` en
cuanto el producto deja de llevar trazabilidad::

    def write(self, vals):
        if 'tracking' in vals and vals['tracking'] == 'none':
            vals['use_expiration_date'] = False
        return super().write(vals)

Este ORM no reabre el método de un modelo ajeno; el equivalente construido es
un receptor ``pre_save`` sobre ``ProductTemplate``, que corre en el mismo punto
(antes de persistir) y aplica la misma regla. No es una divergencia de
semántica: es el mismo invariante en el gancho que este stack sí ofrece.

Lo que este archivo no cierra
===============================

``ProductProduct._compute_quantities_dict`` y las dos redefiniciones de
ayuda (``free_qty``, ``virtual_available``) **no se portan**, y la razón es
medible, no de conveniencia: los tres símbolos no existen en el puerto de
``product``/``stock``.

.. code-block:: text

   grep -rn "_compute_quantities_dict\|virtual_available" addons/ src/ --include=*.py
   → 0

Sin el diccionario de cantidades no hay dónde inyectar el contexto
``with_expiration``, que es todo lo que hace el override. Sucesor registrado:
tarea **#274** (``stock``: 17 archivos ausentes) — el bloqueo se levanta
cuando ``stock`` porte ``product.py``, que es quien declara esos tres
símbolos en la referencia (``odoo19c: stock/models/product.py``).
"""
import fields
from django.db.models.signals import pre_save
from django.dispatch import receiver

from addons.product.models import ProductProduct, ProductTemplate


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``account``/``account_fleet``/``l10n_mx``: el idioma de
    extensión por ``add_to_class`` no tiene MRO, así que dos addons que
    cuelguen el mismo campo duplicarían la columna.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


# -- delegación template → variante (≙ el `_inherits` de la referencia) --


def use_expiration_date(self):
    """≙ ``product.product.use_expiration_date`` — delegado al template."""
    return self.product_tmpl.use_expiration_date


def expiration_time(self):
    """≙ ``product.product.expiration_time`` — delegado al template."""
    return self.product_tmpl.expiration_time


def use_time(self):
    """≙ ``product.product.use_time`` — delegado al template."""
    return self.product_tmpl.use_time


def removal_time(self):
    """≙ ``product.product.removal_time`` — delegado al template."""
    return self.product_tmpl.removal_time


def alert_time(self):
    """≙ ``product.product.alert_time`` — delegado al template."""
    return self.product_tmpl.alert_time


@receiver(pre_save, sender=ProductTemplate,
          dispatch_uid='product_expiry.clear_expiry_when_untracked')
def _clear_expiry_when_untracked(sender, instance, **kwargs):
    """≙ ``ProductTemplate.write`` (``odoo19c: product_product.py:37-40``).

    Un producto sin trazabilidad no puede llevar fechas de caducidad: sin lote
    no hay portador de la fecha. La referencia lo fuerza en ``write``; aquí, en
    el ``pre_save`` del mismo modelo.

    ``tracking`` lo declara ``stock`` sobre ``product.template``
    (``odoo19c: stock/models/product.py:842``) y este puerto **sí** lo tiene
    (``api: addons/stock/models/product.py``, portado en el mismo pase). El
    ``getattr`` con default protege el caso en que ``stock`` no esté instalado:
    sin trazabilidad declarada no hay nada que apagar.
    """
    if getattr(instance, 'tracking', 'none') == 'none':
        instance.use_expiration_date = False


def apply_product_expiry_extensions():
    """Cuelga los 5 campos sobre ``product.template`` y su delegación.

    La llama ``ProductExpiryConfig.ready()``; los tests la invocan
    explícitamente (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(ProductTemplate, 'use_expiration_date', fields.Boolean(
        default=False,
        help_text='Gestiona fechas de caducidad (Odoo use_expiration_date).',
    ))
    _add_if_absent(ProductTemplate, 'expiration_time', fields.Integer(
        default=0,
        help_text='Días tras la recepción hasta la caducidad del lote '
                  '(Odoo expiration_time).',
    ))
    _add_if_absent(ProductTemplate, 'use_time', fields.Integer(
        default=0,
        help_text='Días antes de la caducidad en que el producto empieza a '
                  'deteriorarse — consumo preferente (Odoo use_time).',
    ))
    _add_if_absent(ProductTemplate, 'removal_time', fields.Integer(
        default=0,
        help_text='Días antes de la caducidad para retirar del stock '
                  '(Odoo removal_time).',
    ))
    _add_if_absent(ProductTemplate, 'alert_time', fields.Integer(
        default=0,
        help_text='Días antes de la caducidad para levantar una alerta '
                  '(Odoo alert_time).',
    ))

    for nombre, funcion in (
        ('use_expiration_date', use_expiration_date),
        ('expiration_time', expiration_time),
        ('use_time', use_time),
        ('removal_time', removal_time),
        ('alert_time', alert_time),
    ):
        if not hasattr(ProductProduct, nombre):
            setattr(ProductProduct, nombre, property(funcion))
