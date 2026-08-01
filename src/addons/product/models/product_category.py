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

Aquí los dos se mantienen en ``save()``, mismo patrón que ``uom_uom.py`` ya
usa para su ``factor`` y su ``parent_path`` — y por la misma razón: Django no
recalcula en cadena.

``product_count`` cuenta la rama, no el nodo
============================================

El ``help`` de la referencia dice *"does not consider the children
categories"*, y su código hace **lo contrario**: recorre
``search([('id', 'child_of', categ.ids)])`` y suma. El texto de ayuda es el
que está mal, no el cálculo — se porta el cálculo, se corrige la ayuda, y se
deja anotado para que nadie lo "arregle" al revés más tarde.

Es un ``compute`` sin ``store`` → propiedad derivada aquí.

Qué NO se porta, con su medición
================================

- **``_inherit = ['mail.thread']``**: la categoría es un hilo de mensajería en
  la referencia (seguidores, registro de cambios). Aquí ``addons/mail`` existe
  con otro diseño —``MailThread``, ``MailFollowers``, ``MailMessage``— y
  colgar la categoría de él es una decisión de producto, no de portación.
- **``name_create`` / ``copy_data``**: crear desde un desplegable escribiendo
  un nombre, y duplicar añadiendo *"(copia)"*. Son azúcar del cliente web de
  Odoo; el equivalente aquí es el serializer DRF.
- **``product_properties_definition``** (``PropertiesDefinition``): el esquema
  de propiedades libres que heredan los productos de la categoría. Se porta
  el campo —es ``JSONField`` en este árbol— pero **no** la maquinaria que lo
  aplica a los productos, que vive en ``product_template.py``.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.timestamped_mixin import TimeStampedModel

#: Separador de los tramos del nombre completo, verbatim de la fuente.
COMPLETE_NAME_SEPARATOR = ' / '


class ProductCategory(TimeStampedModel):
    """``product.category`` — una categoría dentro del árbol."""

    name = fields.Char(max_length=255, db_index=True, verbose_name='Nombre')
    complete_name = fields.Char(
        max_length=1024, blank=True, default='', db_index=True,
        verbose_name='Nombre completo',
        help_text='Ruta legible "Padre / Hijo". Almacenado y repropagado a '
                  'los descendientes al renombrar un padre.',
    )
    parent = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True, db_index=True,
        related_name='child_id', verbose_name='Categoría padre',
        help_text='Odoo parent_id. El related_name es child_id, que es como '
                  'la referencia llama al One2many inverso.',
    )
    parent_path = fields.Char(
        max_length=1024, blank=True, default='', db_index=True,
        verbose_name='Ruta del árbol',
        help_text='Ruta materializada de ids: responde "qué hay debajo" con '
                  'un LIKE en vez de N consultas.',
    )
    product_properties_definition = fields.Json(
        default=list, blank=True, verbose_name='Propiedades del producto',
        help_text='Esquema de propiedades libres que heredan los productos de '
                  'esta categoría. La maquinaria que lo aplica vive en '
                  'product_template.',
    )

    class Meta:
        db_table = 'product_category'
        ordering = ['complete_name']
        verbose_name = 'Categoría de producto'
        verbose_name_plural = 'Categorías de producto'

    def __str__(self):
        return self.complete_name or self.name

    def clean(self):
        """``_check_category_recursion`` — no se admiten categorías cíclicas."""
        super().clean()
        seen = set()
        node = self.parent
        while node is not None:
            if node.pk == self.pk or node.pk in seen:
                raise ValidationError('No se pueden crear categorías recursivas.')
            seen.add(node.pk)
            node = node.parent

    def build_complete_name(self):
        """``_compute_complete_name`` — ``Padre / Hijo``, o el nombre a secas."""
        if self.parent is not None:
            parent_name = self.parent.complete_name or self.parent.name
            return f'{parent_name}{COMPLETE_NAME_SEPARATOR}{self.name}'
        return self.name

    def save(self, *args, **kwargs):
        """Mantiene ``complete_name`` y ``parent_path``, y repropaga a los hijos.

        Los dos son ``store=True`` en la referencia y su ORM los recalcula en
        cadena. Django no, así que la repropagación es explícita: sin ella,
        renombrar un padre deja media rama con el nombre viejo y el árbol
        mintiendo en cada lectura.
        """
        self.complete_name = self.build_complete_name()
        super().save(*args, **kwargs)

        parent_path = (
            f'{self.parent.parent_path}{self.pk}/'
            if self.parent is not None else f'{self.pk}/'
        )
        if self.parent_path != parent_path:
            self.parent_path = parent_path
            super().save(update_fields=['parent_path'])

        for child in self.child_id.all():
            child.save()

    @property
    def product_count(self):
        """``_compute_product_count`` — productos de **toda la rama**.

        La ayuda de la referencia dice que no cuenta las hijas; su código sí
        las cuenta (``child_of``). Se porta el código — ver el docstring del
        módulo.

        Devuelve 0 mientras ``product.template`` no esté portado; se conecta
        con él, sin tocar este archivo.
        """
        template_model = getattr(type(self), '_product_template_model', None)
        if template_model is None:
            return 0
        branch = type(self).objects.filter(
            parent_path__startswith=self.parent_path)
        return template_model.objects.filter(categ__in=branch).count()
