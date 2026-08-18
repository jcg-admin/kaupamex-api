"""``utm.medium`` — el medio de entrega (correo, web, red social…).

Adaptación fiel de Odoo ``utm/models/utm_medium.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Los 4 símbolos de la fuente están portados.

Divergencias declaradas:

- ``create`` (``@api.model_create_multi``) → **``save()``**, el único punto de
  persistencia de Django. Es el idioma ya fijado del árbol (ver
  ``analytic/models/analytic_mixin.py``: *"antes ``create``/``write``
  overrides con ``vals`` dict — aquí unificado en ``save()``"*). La fuente
  numera un **lote** de nombres de una vez; aquí se numera uno por guardado,
  que es la misma semántica para el caso de uno y la única que ``save()``
  puede dar. ``bulk_create`` se salta ``save()`` y por tanto el contador — no
  se usa para estos modelos.
- ``_unlink_except_utm_medium_record`` (``@api.ondelete``) → se **conserva el
  método con su nombre y su guion bajo**, y lo invoca ``delete()``, que es el
  punto equivalente del stack. Mejora sobre el precedente de
  ``account_account_tag`` (que fundió la guarda dentro de ``delete()`` y
  perdió el nombre del símbolo).
- ``SELF_REQUIRED_UTM_MEDIUMS_REF`` sigue siendo una ``@property``, como en la
  fuente, y su contenido vive además como constante de módulo: la ``property``
  no es legible desde la clase, y ``_fetch_or_create_utm_medium`` —que aquí es
  ``classmethod``, porque allá se invoca sobre el modelo y no sobre un
  registro— la necesita.
"""
import re

import fields
import models
from addons.base.models import IrModelData, TimeStampedModel
from exceptions import UserError
from tools.translate import _

from .utm_mixin import UtmMixin

#: Los medios que otros módulos dan por existentes: su identificador externo y
#: el nombre con el que se crean. Borrarlos rompe a quien los cita.
#: ≙ el dict que devuelve ``SELF_REQUIRED_UTM_MEDIUMS_REF``
#: (``odoo19c: utm_medium.py:31-40``).
SELF_REQUIRED_UTM_MEDIUMS_REF = {
    'utm.utm_medium_email': 'Email',
    'utm.utm_medium_direct': 'Direct',
    'utm.utm_medium_website': 'Website',
    'utm.utm_medium_twitter': 'X',
    'utm.utm_medium_facebook': 'Facebook',
    'utm.utm_medium_linkedin': 'LinkedIn',
}


class UtmMedium(TimeStampedModel):
    """``utm.medium`` — medio de entrega (``odoo19c: utm_medium.py:11-67``)."""

    _name = 'utm.medium'
    _description = 'UTM Medium'
    _order = 'name'

    # ≙ ``name`` (requerido; ``translate=False`` en la fuente — el medio es
    # un identificador, no una etiqueta).
    name = fields.Char(
        max_length=255, verbose_name='Nombre del medio',
        help_text='Nombre del medio de entrega.',
    )
    # ≙ ``active``.
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Permite archivar el medio sin borrarlo.',
    )

    class Meta:
        db_table = 'utm_medium'
        # ≙ ``_order = 'name'`` (``odoo19c: :14``).
        ordering = ['name']
        verbose_name = 'Medio UTM'
        verbose_name_plural = 'Medios UTM'
        constraints = [
            # ≙ ``_unique_name = models.Constraint('UNIQUE(name)', 'The name
            # must be unique')`` (``odoo19c: :19-22``).
            models.UniqueConstraint(
                fields=['name'], name='utm_medium_unique_name',
                violation_error_message='The name must be unique',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # -- persistencia --------------------------------------------------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (``odoo19c: :24-29``) — numera el nombre al insertar.

        Sólo al **crear**: la fuente numera en ``create`` y no en ``write``, y
        renumerar en cada actualización incrementaría el contador sin motivo
        (es justo lo que ``utm_check_skip_record_ids`` existe para evitar).
        """
        if self._state.adding:
            self.name = UtmMixin._get_unique_names(self._name, [self.name])[0]
        return super().save(*args, **kwargs)

    @property
    def SELF_REQUIRED_UTM_MEDIUMS_REF(self):
        """≙ ``SELF_REQUIRED_UTM_MEDIUMS_REF`` (``odoo19c: :31-40``)."""
        return dict(SELF_REQUIRED_UTM_MEDIUMS_REF)

    # -- borrado -------------------------------------------------------------

    def _unlink_except_utm_medium_record(self):
        """≙ ``_unlink_except_utm_medium_record`` (``odoo19c: :42-51``).

        Un medio que otro módulo cita por identificador externo no se borra:
        hacerlo dejaría a ese módulo sin resolver su referencia.
        """
        for medium in SELF_REQUIRED_UTM_MEDIUMS_REF:
            utm_medium = IrModelData.ref(medium, raise_if_not_found=False)
            if utm_medium is not None and utm_medium.pk == self.pk:
                raise UserError(str(_(
                    "Oops, you can't delete the Medium '%s'.\n"
                    "Doing so would be like tearing down a load-bearing wall "
                    "— not the best idea.",
                    self.name,
                )))

    def delete(self, *args, **kwargs):
        """El punto donde este stack ejecuta la guarda de ``@api.ondelete``."""
        self._unlink_except_utm_medium_record()
        return super().delete(*args, **kwargs)

    # -- búsqueda o creación por identificador externo ------------------------

    @classmethod
    def _fetch_or_create_utm_medium(cls, name, module='utm'):
        """≙ ``_fetch_or_create_utm_medium`` (``odoo19c: :53-67``).

        Resuelve el medio por su identificador externo; si no existe, lo crea
        **y le graba el identificador**, para que la siguiente llamada lo
        encuentre. Los espacios y los puntos del nombre pasan a guion bajo,
        igual que en la fuente.

        ``classmethod`` y no método de instancia: allá se invoca sobre el
        modelo (``self.env['utm.medium']._fetch_or_create_utm_medium(...)``),
        que aquí es la clase. ``sudo()`` no tiene análogo — el control de
        acceso de este árbol es por capacidad en la vista, no por recordset.
        """
        name_normalized = re.sub(r"[\s|.]", "_", name.lower())
        xmlid = f'{module}.utm_medium_{name_normalized}'
        utm_medium = IrModelData.ref(xmlid, raise_if_not_found=False)
        if utm_medium is not None:
            return utm_medium

        utm_medium = cls.objects.create(
            name=SELF_REQUIRED_UTM_MEDIUMS_REF.get(xmlid, name),
        )
        # ``set_xmlid`` es el escritor canónico del árbol: graba la etiqueta
        # de Django (``_meta.label``) que ``ref`` sabe resolver. Escribir la
        # fila a mano con el nombre Odoo del modelo la deja irresoluble.
        IrModelData.set_xmlid(utm_medium, xmlid)
        return utm_medium
