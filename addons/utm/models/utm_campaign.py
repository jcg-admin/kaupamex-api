"""``utm.campaign`` — la campaña de marketing.

Adaptación fiel de Odoo ``utm/models/utm_campaign.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Los 3 símbolos de la fuente están portados.

La campaña tiene **dos nombres**, y no es redundancia: ``title`` es el que lee
una persona (traducible, se puede repetir), ``name`` es el identificador que
viaja en la URL como ``utm_campaign`` (único, no traducible, con contador
``[N]`` si hace falta). ``_compute_name`` deriva el segundo del primero.

Divergencias declaradas:

- ``create`` (``@api.model_create_multi``) y el ``compute`` almacenado
  ``_compute_name`` se funden en **``save()``**, el único punto de
  persistencia de Django — el mismo idioma que ``utm_medium.py`` y
  ``utm_source.py``. La fuente separa las dos ramas porque su ORM las
  distingue; aquí ambas escriben en el mismo sitio y el orden se conserva:
  primero el respaldo ``title`` ← ``name``, después la numeración.
- ``group_expand='_group_expand_stage_ids'`` es un atributo del campo que
  consume el kanban del cliente web de Odoo. El método **se porta** —es
  Python puro y su respuesta es útil a cualquier cliente— pero no cuelga de
  un atributo de campo que este stack no tiene: se invoca explícitamente.
- ``precompute=True`` / ``readonly=False`` / ``store=True`` de ``name`` son
  la forma en que la fuente declara *"calculado, pero editable y en columna"*.
  Aquí una columna normal escrita en ``save()`` es exactamente eso.
"""
import fields
import models
from addons.base.models import TimeStampedModel
from orm.environments import get_current_uid

from .utm_mixin import UtmMixin
from .utm_stage import UtmStage


class UtmCampaign(TimeStampedModel):
    """``utm.campaign`` — campaña (``odoo19c: utm_campaign.py:7-61``)."""

    _name = 'utm.campaign'
    _description = 'UTM Campaign'
    _rec_name = 'title'

    # ≙ ``active``.
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Permite archivar la campaña sin borrarla.',
    )
    # ≙ ``name`` (``compute`` con ``store``, ``readonly=False``,
    # ``translate=False`` en la fuente).
    name = fields.Char(
        max_length=255, verbose_name='Identificador de campaña',
        help_text='Identificador único que viaja en la URL como utm_campaign. '
                  'Se deriva del nombre legible.',
    )
    # ≙ ``title`` (traducible en la fuente).
    title = fields.Char(
        max_length=255, verbose_name='Nombre de campaña',
        help_text='Nombre legible de la campaña.',
    )
    # ≙ ``user_id`` (requerido, con el usuario actual por defecto). Nullable en
    # columna porque el default se resuelve en ``save()``; ver el docstring.
    user_id = fields.Many2one(
        'base.ResUsers', null=True, on_delete=models.PROTECT,
        related_name='utm_campaign_ids', verbose_name='Responsable',
        help_text='Persona responsable de la campaña.',
    )
    # ≙ ``stage_id`` (requerido, ``ondelete=restrict``, ``copy=False``,
    # ``group_expand=_group_expand_stage_ids``).
    stage_id = fields.Many2one(
        'utm.UtmStage', on_delete=models.PROTECT, related_name='campaign_ids',
        verbose_name='Etapa',
        help_text='Etapa en la que se encuentra la campaña.',
    )
    # ≙ ``tag_ids`` (M2M sobre la tabla ``utm_tag_rel``).
    tag_ids = fields.Many2many(
        'utm.UtmTag', db_table='utm_tag_rel', related_name='campaign_ids',
        blank=True, verbose_name='Etiquetas',
        help_text='Etiquetas con las que se clasifica la campaña.',
    )
    # ≙ ``is_auto_campaign``.
    is_auto_campaign = fields.Boolean(
        default=False, verbose_name='Campaña generada automáticamente',
        help_text='Permite filtrar las campañas relevantes de las generadas '
                  'automáticamente.',
    )
    # ≙ ``color``.
    color = fields.Integer(
        default=0, verbose_name='Índice de color',
        help_text='Color con el que se presenta la campaña.',
    )

    class Meta:
        db_table = 'utm_campaign'
        verbose_name = 'Campaña UTM'
        verbose_name_plural = 'Campañas UTM'
        constraints = [
            # ≙ ``_unique_name = models.Constraint('UNIQUE(name)', 'The name
            # must be unique')`` (``odoo19c: :31-34``).
            models.UniqueConstraint(
                fields=['name'], name='utm_campaign_unique_name',
                violation_error_message='The name must be unique',
            ),
        ]

    def __str__(self) -> str:
        # ≙ ``_rec_name = 'title'`` (``odoo19c: :10``).
        return self.title or self.name or ''

    # -- el identificador derivado del título ---------------------------------

    def _compute_name(self):
        """≙ ``_compute_name`` (``odoo19c: :36-42``) — ``name`` sale de ``title``.

        Excluye el propio registro de la búsqueda de colisiones: sin eso, cada
        actualización incrementaría el contador aunque el título no cambie —
        que es para lo que la fuente pasa ``utm_check_skip_record_ids``.
        """
        skip = [self.pk] if self.pk else []
        self.name = UtmMixin._get_unique_names(
            self._name, [self.title], skip_record_ids=skip)[0]
        return self.name

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:44-53``) + el ``compute`` almacenado de ``name``.

        El orden es el de la fuente: primero el respaldo ``title`` ← ``name``
        (una campaña creada sólo con identificador toma ése como título),
        después la numeración del identificador.
        """
        if self._state.adding:
            if not self.title and self.name:
                self.title = self.name
            if self.user_id_id is None:
                # ≙ ``default=lambda self: self.env.uid`` (``odoo19c: :19``).
                self.user_id_id = get_current_uid()
            if self.stage_id_id is None:
                # ≙ ``default=lambda self: self.env['utm.stage'].search([], limit=1)``
                # (``odoo19c: :22``) — la primera etapa por ``_order``.
                self.stage_id = UtmStage.objects.first()
            self.name = UtmMixin._get_unique_names(
                self._name, [self.name or self.title])[0]
        return super().save(*args, **kwargs)

    # -- kanban ---------------------------------------------------------------

    @classmethod
    def _group_expand_stage_ids(cls, stages=None, domain=None):
        """≙ ``_group_expand_stage_ids`` (``odoo19c: :55-61``).

        Devuelve **todas** las etapas, para que el kanban muestre también las
        que no tienen ninguna campaña. Los dos parámetros se conservan aunque
        no se usen: es la firma que la fuente declara, y quien la invoque
        desde un cliente la reconocerá.
        """
        return UtmStage.objects.all().order_by(*UtmStage._meta.ordering)
