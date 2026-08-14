"""``stock.package.history`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_package_history.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Qué es, y por qué no basta con mirar el paquete: cuando un paquete se mueve,
su ``parent_package_id`` y su ubicación **cambian en su sitio**. Preguntarle
al paquete dónde estuvo no tiene respuesta — sólo sabe dónde está. Este modelo
es la fotografía: guarda los **nombres** de origen y destino además de sus FK,
para que la traza sobreviva a que el contenedor se renombre o se borre.

Porte símbolo por símbolo — 15 de 15
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_package_history.py``
(42 líneas): 13 campos y 2 métodos.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``company_id`` (10)                              ``company``
``location_id`` (11)                             ``location``
``location_dest_id`` (12)                        ``location_dest``
``move_line_ids`` (13)                           reverso ``move_line_ids``
``package_id`` (14)                              ``package``
``package_name`` (15)                            ``package_name``
``package_type_id`` (16)                         property ``package_type``
``parent_orig_id`` (17)                          ``parent_orig``
``parent_orig_name`` (18)                        ``parent_orig_name``
``parent_dest_id`` (19)                          ``parent_dest``
``parent_dest_name`` (20)                        ``parent_dest_name``
``outermost_dest_id`` (21)                       ``outermost_dest``
``picking_ids`` (22)                             ``picking_ids`` (M2M)
``_get_complete_dest_name_except_outermost`` (24-32) mismo nombre sin guion bajo
``action_show_package`` (34-42)                  ``action_show_package``
===============================================  ======================================

Divergencia declarada
=======================

**``action_show_package`` devuelve el paquete, no una acción de ventana.** La
referencia retorna ``{'type': 'ir.actions.act_window', 'res_model':
'stock.package', 'res_id': …}`` para que su cliente web abra el formulario.
Sin capa de vistas, aquí devuelve el registro; el consumidor —la API REST—
decide cómo presentarlo. Registrado en la tarea **#279**.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class StockPackageHistory(TimeStampedModel):
    """``stock.package.history`` — la fotografía de un movimiento de paquete."""

    company           = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='package_histories',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    location          = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='package_history_origins',
        help_text='Ubicación de origen (Odoo location_id).',
    )
    location_dest     = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='package_history_destinations',
        help_text='Ubicación de destino (Odoo location_dest_id).',
    )
    package           = fields.Many2one(
        'stock.StockPackage', on_delete=models.CASCADE,
        related_name='history_ids',
        help_text='Paquete movido (Odoo package_id, requerido).',
    )
    package_name      = fields.Char(
        max_length=512,
        help_text='Nombre completo del paquete al momento del movimiento '
                  '(Odoo package_name, requerido).',
    )
    parent_orig       = fields.Many2one(
        'stock.StockPackage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='history_as_origin_container', db_index=True,
        help_text='Contenedor de origen (Odoo parent_orig_id).',
    )
    parent_orig_name  = fields.Char(
        max_length=512, blank=True, default='',
        help_text='Nombre del contenedor de origen (Odoo parent_orig_name).',
    )
    parent_dest       = fields.Many2one(
        'stock.StockPackage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='history_as_dest_container', db_index=True,
        help_text='Contenedor de destino (Odoo parent_dest_id).',
    )
    parent_dest_name  = fields.Char(
        max_length=512, blank=True, default='',
        help_text='Nombre del contenedor de destino (Odoo parent_dest_name).',
    )
    outermost_dest    = fields.Many2one(
        'stock.StockPackage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='history_as_outermost_container',
        help_text='Contenedor destino más externo (Odoo outermost_dest_id).',
    )
    picking_ids       = fields.Many2many(
        'stock.StockPicking', blank=True, related_name='package_history_ids',
        help_text='Transferencias implicadas (Odoo picking_ids).',
    )

    class Meta:
        db_table = 'stock_package_history'
        ordering = ['-id']
        verbose_name = 'Historial de paquete'
        verbose_name_plural = 'Historiales de paquete'

    def __str__(self) -> str:
        return f'{self.package_name}: {self.location} → {self.location_dest}'

    @property
    def package_type(self):
        """≙ ``package_type_id`` (``related='package_id.package_type_id'``, ``:16``)."""
        return self.package.package_type if self.package is not None else None

    def get_complete_dest_name_except_outermost(self):
        """≙ ``_get_complete_dest_name_except_outermost`` (``odoo19c: :24-32``).

        El nombre jerárquico del destino **sin** el contenedor más externo.
        Sirve para mostrar la posición relativa dentro del envío: repetir el
        nombre del contenedor exterior en cada línea es ruido.

        Tres casos, los tres de la referencia: sin contenedor destino, cadena
        vacía; si el contenedor destino **es** el más externo, el nombre del
        propio paquete; en otro caso, el nombre completo menos su primer tramo.
        """
        if self.parent_dest is None:
            return ''
        if self.parent_dest_id == self.outermost_dest_id:
            return self.package.name if self.package is not None else ''
        return ' > '.join(self.package_name.split(' > ')[1:])

    def action_show_package(self):
        """≙ ``action_show_package`` (``odoo19c: :34-42``).

        Devuelve el paquete de esta entrada — ver la divergencia del módulo.
        """
        return self.package
