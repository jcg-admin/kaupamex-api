"""Mixins del sitio — adaptación de ``odoo19c: website/models/mixins.py``.

Sólo se porta el que la vitrina necesita hoy: **el estado de publicación**.
En la referencia vive en ``website``, no en ``product``, y ese reparto es
deliberado: un producto existe en el ERP aunque no esté en la tienda. Quien
dueña "esto se ve en el sitio" es el sitio.

Medido en las dos poblaciones que llevan el mixin
(``odoo-tools@622ddc2a``):

===========  ===========================================
Árbol        ``is_published``
===========  ===========================================
``odoo19c``  ``website/models/mixins.py:207``
``odoo18c``  el mismo ``_name``, consumido por
             ``website_sale/models/product_template.py``
===========  ===========================================

Qué **no** se porta y por qué
-----------------------------

La referencia declara cinco campos en el mixin; aquí sólo dos tienen sentido:

- ``is_published`` — **sí**: es el estado real.
- ``website_published`` — **sí**, como propiedad de sólo lectura. Allá es un
  ``related`` editable sobre ``is_published``; aquí no hay ``related``, así
  que se expone como alias legible y se escribe siempre sobre el campo real.
  Un alias escribible sin mecanismo que lo respalde sería dos fuentes de
  verdad para un booleano.
- ``can_publish`` / ``website_url`` / ``website_absolute_url`` — **no**: los
  tres son ``compute`` que dependen de piezas que este proyecto no tiene
  (el motor de permisos de publicación por grupo, y el enrutador QWeb que
  construye la URL del documento). Portar el campo sin su motor daría un
  valor siempre falso o siempre ``'#'`` — que es lo que la referencia pone
  como *placeholder*, no como respuesta.
"""
from django.db import models


class WebsitePublishedMixin(models.Model):
    """≙ ``website.published.mixin`` (``odoo19c: website/models/mixins.py:201``).

    Abstracto: no crea tabla propia. Lo heredan los modelos que se muestran
    en la tienda (hoy ``ProductTemplate``).
    """

    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Publicado',
        help_text='Visible en la tienda. Por defecto NO — igual que '
                  '_default_is_published de la referencia: dar de alta un '
                  'producto no es publicarlo.',
    )

    class Meta:
        abstract = True

    @property
    def website_published(self):
        """≙ ``website_published`` / ``_compute_website_published``
        (``:280``, ``:287-293``) — alias de lectura de ``is_published``.

        La referencia lo declara ``related=…, readonly=False``; aquí es sólo
        lectura (ver el docstring del módulo).
        """
        return self.is_published

    def website_publish_button(self):
        """≙ ``website_publish_button`` (``:230``): alterna y devuelve el valor.

        Se conserva el nombre de la referencia porque el verbo es el mismo —
        el botón de publicar/despublicar de la ficha.
        """
        self.is_published = not self.is_published
        self.save(update_fields=['is_published'])
        return self.is_published

    @classmethod
    def apply_to(cls, model):
        """Aplica la publicación a un modelo **ya definido** — ≙ ``_inherit``.

        Éste es el camino que un addon de sitio usa para publicar un modelo
        que **no le pertenece**, sin tocar su código. Es el análogo directo de
        lo que hace la referencia::

            # odoo19c: website_sale/models/product_template.py:34-42
            class ProductTemplate(models.Model):
                _name = 'product.template'
                _inherit = [… 'website.published.multi.mixin' …]

        Se llama desde el ``ready()`` del addon que declara la dependencia
        (``website_sale``), nunca desde el modelo destino: así ``product``
        queda **cerrado a modificación y abierto a extensión**, y no adquiere
        una razón de cambio que es del escaparate.

        Idempotente: si el campo ya está, no hace nada — ``ready()`` puede
        ejecutarse más de una vez en tests que recargan el registro de apps.
        """
        if not model._meta.get_fields():  # pragma: no cover - defensivo
            raise RuntimeError(
                f'{model.__name__} no está poblado todavía; apply_to debe '
                f'llamarse desde AppConfig.ready(), no en tiempo de import.')

        existing = {f.name for f in model._meta.get_fields()}
        if 'is_published' not in existing:
            field = cls._meta.get_field('is_published').clone()
            model.add_to_class('is_published', field)

        # Los métodos no son campos: se cuelgan directo. No se sobrescriben si
        # el modelo destino ya define los suyos.
        for name in ('website_published', 'website_publish_button'):
            if not hasattr(model, name):
                setattr(model, name, getattr(cls, name))
