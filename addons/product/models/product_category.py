"""``product.category`` — el árbol de categorías de producto.

Adaptación de ``addons/product/models/product_category.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 69 líneas).

Un árbol, con las dos piezas que un árbol necesita
==================================================

La referencia declara ``_parent_store = True`` y un ``parent_path``, más un
``complete_name`` calculado y **almacenado** de forma recursiva. No son
redundantes: resuelven preguntas distintas.

- **``parent_path``** —la ruta materializada de ids— responde *"¿qué hay
  debajo de esta categoría?"* con un ``LIKE`` en vez de N consultas. Es lo que
  hace viable ``child_of``.
- **``complete_name``** —``Padre / Hijo / Nieto``— responde *"¿cómo se llama
  esto"* sin subir la cadena en cada lectura. Está **almacenado** justamente
  por eso, y por eso hay que **repropagarlo a los descendientes** cuando
  cambia el nombre de un padre: si no, media rama queda con el nombre viejo.

Los dos los mantiene el ORM, como en la fuente: ``parent_path`` por
``_parent_store`` en ``create``/``write`` de un ``BaseModel`` (y en ``save()``
para el camino de Django, como ``hr.department``), y ``complete_name`` como
cálculo almacenado y recursivo que el ORM recalcula también en los hijos.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-category-basemodel.md``.

``product_count`` cuenta la rama, no el nodo
============================================

El ``help`` de la referencia dice *"does not consider the children
categories"*, y su código hace **lo contrario**: recorre
``search([('id', 'child_of', categ.ids)])`` y suma. El texto de ayuda es el
que está mal, no el cálculo — se porta el cálculo, se corrige la ayuda, y se
deja anotado para que nadie lo "arregle" al revés más tarde.

Es un ``compute`` sin ``store``, declarado como en la fuente.

``name`` no lleva el índice ``trigram`` de la fuente: ``db_index`` es un
B-tree; el índice de trigramas espera a que el vocabulario lo exprese.
"""

import api
import fields
import models

from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.mail.models import MailThread
from exceptions import ValidationError
from orm.models import _parent_store_update
from tools.translate import _


class ProductCategory(models.BaseModel, MailThread, TimeStampedModel):
    """``product.category`` — una categoría dentro del árbol."""

    #: ≙ la cabecera de ``odoo19c: addons/product/models/
    #: product_category.py:9-15``, verbatim; el hilo lo da ``MailThread``.
    _name = 'product.category'
    _inherit = ['mail.thread']
    _description = "Product Category"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    #: ``Meta.ordering`` es su forma en Django; los dos conviven.
    _order = 'complete_name'

    name = fields.Char('Name', required=True, max_length=255, db_index=True)
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name', recursive=True,
        store=True, max_length=1024, blank=True, null=True, db_index=True)
    #: ≙ ``parent_id`` (``odoo19c: addons/product/models/
    #: product_category.py:21``) en forma C: el nombre de la fuente, con su
    #: columna explícita.
    parent_id = fields.Many2one(
        'self',
        db_column='parent_id',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='child_id',
        verbose_name='Categoría padre',
        help_text=(
            'Odoo parent_id. El related_name es child_id, que es como '
            'la referencia llama al One2many inverso.'
        ),
    )
    parent_path = fields.Char(
        max_length=1024,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Ruta del árbol',
        help_text=(
            'Ruta materializada de ids: responde "qué hay debajo" con '
            'un LIKE en vez de N consultas.'
        ),
    )
    product_count = fields.Integer(
        '# Products', compute='_compute_product_count', store=False,
        help="The number of products under this category (Does not consider"
             " the children categories)")
    product_properties_definition = fields.PropertiesDefinition(
        'Product Properties', null=True, blank=True)

    class Meta:
        db_table = 'product_category'
        ordering = ['complete_name']
        verbose_name = 'Categoría de producto'
        verbose_name_plural = 'Categorías de producto'

    def __str__(self):
        return self.complete_name or self.name or ''

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada en el camino de Django.

        ``objects.create`` y ``save()`` no pasan por ``create``/``write``
        del ORM, que son quienes mantienen el árbol de un ``BaseModel`` con
        ``_parent_store``. Mismo patrón que ``hr.department``: una fila que
        cambia de padre delega en :func:`orm.models._parent_store_update`.
        """
        stored = (type(self)._base_manager.filter(pk=self.pk)
                  .values_list('parent_id', 'parent_path').first()
                  if self.pk is not None else None)
        super().save(*args, **kwargs)
        if stored and stored[1] and stored[0] != self.parent_id_id:
            _parent_store_update(self)
        else:
            path = (f'{self.parent_id.parent_path}{self.pk}/'
                    if self.parent_id else f'{self.pk}/')
            if path != self.parent_path:
                self.parent_path = path
                super().save(update_fields=['parent_path'])

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        """≙ ``_compute_complete_name`` (``odoo19c:
        addons/product/models/product_category.py:28-34``)."""
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (
                    category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    def _compute_product_count(self):
        """≙ ``_compute_product_count`` (``:36-43``): cuenta toda la rama,
        aunque el ``help`` de la fuente diga lo contrario."""
        read_group_res = self.env['product.template']._read_group(
            [('categ_id', 'child_of', self.ids)], ['categ_id'], ['__count'])
        group_data = {categ.id: count for categ, count in read_group_res}
        for categ in self:
            product_count = 0
            for sub_categ_id in categ.search(
                    [('id', 'child_of', categ.ids)]).ids:
                product_count += group_data.get(sub_categ_id, 0)
            categ.product_count = product_count

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        """≙ ``_check_category_recursion`` (``:45-48``)."""
        if self._has_cycle():
            raise ValidationError(_('You cannot create recursive categories.'))

    @api.model
    def name_create(self, name):
        """≙ ``name_create`` (``:50-53``)."""
        category = self.create({'name': name})
        return category.id, category.display_name

    @api.depends_context('hierarchical_naming')
    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:55-60``)."""
        if self.env.context.get('hierarchical_naming', True):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``:62-68``): la copia lleva «(copy)»."""
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for category, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", category.name)
        return vals_list
