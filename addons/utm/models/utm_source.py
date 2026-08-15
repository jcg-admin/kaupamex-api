"""``utm.source`` y ``utm.source.mixin`` — el origen del enlace y su nombre.

Adaptación fiel de Odoo ``utm/models/utm_source.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Los 7 símbolos de la fuente están portados: 3 de
``UtmSource`` y 4 de ``UtmSourceMixin``.

``utm.source.mixin`` es el mecanismo menos evidente del addon, y conviene
nombrarlo: un modelo que lo herede (un envío de correo, una publicación en
red social) **no tiene nombre propio** — su ``name`` es el de su
``utm.source``, y ese nombre se **genera a partir del contenido** del propio
registro (el campo que declara su ``_rec_name``). Así el informe de marketing
distingue dos envíos sin que nadie los bautice a mano.

Divergencias declaradas (las mismas que ``utm_medium.py``, más una):

- ``create`` → ``save()``; ``@api.ondelete`` → método conservado + ``delete()``.
- ``copy_data`` de la fuente construye los valores de la copia y deja que el
  ORM cree; aquí se conserva con esa misma forma —devuelve la lista de
  valores— porque quien copia es quien decide con qué crearlos. Django no
  tiene ``copy()`` de recordset que lo invoque solo.
- ``write`` de ``UtmSourceMixin`` levanta ``ValueError`` en la fuente cuando
  se actualizan varios registros con el mismo nombre. Aquí ``save()`` opera
  sobre **un** registro por construcción, así que esa rama no puede darse; la
  guarda se conserva sobre el ``update()`` del queryset, que es donde este
  stack sí puede escribir muchos de una vez.
"""
from django.utils import timezone

import fields
import models
from addons.base.models import IrModelData, TimeStampedModel
from exceptions import ValidationError
from tools.translate import _

from .utm_mixin import UtmMixin


class UtmSource(TimeStampedModel):
    """``utm.source`` — origen del enlace (``odoo19c: utm_source.py:7-48``)."""

    _name = 'utm.source'
    _description = 'UTM Source'

    # ≙ ``name`` (requerido).
    name = fields.Char(
        max_length=255, verbose_name='Nombre de la fuente',
        help_text='Nombre de la fuente del enlace.',
    )

    class Meta:
        db_table = 'utm_source'
        verbose_name = 'Fuente UTM'
        verbose_name_plural = 'Fuentes UTM'
        constraints = [
            # ≙ ``_unique_name = models.Constraint('UNIQUE(name)', 'The name
            # must be unique')`` (``odoo19c: :13-16``).
            models.UniqueConstraint(
                fields=['name'], name='utm_source_unique_name',
                violation_error_message='The name must be unique',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # -- borrado -------------------------------------------------------------

    def _unlink_except_referral(self):
        """≙ ``_unlink_except_referral`` (``odoo19c: :18-23``).

        La fuente «Referral» la citan otros módulos por identificador externo.
        """
        utm_source_referral = IrModelData.ref(
            'utm.utm_source_referral', raise_if_not_found=False)
        if utm_source_referral is not None and utm_source_referral.pk == self.pk:
            raise ValidationError(
                _("You cannot delete the 'Referral' UTM source record."))

    def delete(self, *args, **kwargs):
        """El punto donde este stack ejecuta la guarda de ``@api.ondelete``."""
        self._unlink_except_referral()
        return super().delete(*args, **kwargs)

    # -- persistencia --------------------------------------------------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (``odoo19c: :25-30``) — numera el nombre al insertar."""
        if self._state.adding:
            self.name = UtmMixin._get_unique_names(self._name, [self.name])[0]
        return super().save(*args, **kwargs)

    # -- generación del nombre a partir del contenido -------------------------

    @classmethod
    def _generate_name(cls, record, content):
        """≙ ``_generate_name`` (``odoo19c: :32-48``).

        El nombre de la fuente es el contenido recortado más la descripción
        del modelo y la fecha de creación del registro — así dos envíos con el
        mismo asunto no colisionan por accidente.

        La fuente lee la descripción de ``ir.model``; aquí se toma
        ``_description`` de la clase, que es el mismo dato en su hogar de este
        árbol (``atributos-de-clase-de-modelo.md``), sin depender de que
        ``ir.model`` esté sembrado.
        """
        if not content:
            return None

        content = content.replace('\n', ' ')
        if len(content) >= 24:
            content = f'{content[:20]}...'

        # ``created_at`` es el ``create_date`` de la fuente
        # (``TimeStampedModel``); ``timezone.now()`` su ``fields.Datetime.today()``.
        create_date = getattr(record, 'created_at', None) or timezone.now()
        model_description = getattr(type(record), '_description', type(record).__name__)
        return str(_(
            '%(content)s (%(model_description)s created on %(create_date)s)',
            content=content,
            model_description=model_description,
            create_date=create_date.date().isoformat(),
        ))


class UtmSourceMixin(models.Model):
    """``utm.source.mixin`` — el nombre del registro sale de su contenido.

    ≙ ``odoo19c: utm_source.py:51-113``. Quien lo hereda declara su
    ``_rec_name``: el campo cuyo contenido bautiza la fuente.
    """

    _name = 'utm.source.mixin'
    _description = 'UTM Source Mixin'

    # ≙ ``source_id`` (requerido, ``ondelete=restrict``, ``copy=False``).
    source_id = fields.Many2one(
        'utm.UtmSource', on_delete=models.PROTECT, related_name='+',
        verbose_name='Fuente',
        help_text='Fuente UTM asociada a este registro.',
    )

    class Meta:
        abstract = True

    @property
    def name(self):
        """``name`` — ≙ el campo ``related='source_id.name'`` de la fuente.

        Allá es un campo *related* con ``readonly=False``: se lee y se escribe
        a través de la relación, sin columna propia. Aquí es una ``property``
        con su ``setter``, que es la forma que este stack da a un related no
        almacenado (``H-API-611``: el origen se declara).
        """
        return self.source_id.name if self.source_id_id else None

    @name.setter
    def name(self, value):
        if self.source_id_id:
            self.source_id.name = value

    @classmethod
    def default_get(cls, field_names, values=None):
        """≙ ``default_get`` (``odoo19c: :61-64``) — ``name`` fuera de los defaults.

        La fuente lo excluye para que un ``default_name`` del contexto no se
        cuele como nombre del registro: el nombre lo genera ``create`` a
        partir del contenido.
        """
        return dict(values or {}) if 'name' not in field_names else {
            key: value for key, value in dict(values or {}).items() if key != 'name'
        }

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:66-89``) + ``write`` (``:91-104``).

        Al **crear** sin fuente asignada, se crea la ``utm.source`` con el
        nombre que ``_generate_name`` deriva del contenido. Al **actualizar**
        el contenido, el nombre se regenera y se vuelve a numerar excluyendo
        la propia fuente — que es para lo que la fuente usa
        ``utm_check_skip_record_ids``.
        """
        rec_name = getattr(type(self), '_rec_name', 'name')
        content = getattr(self, rec_name, None)

        if self._state.adding and not self.source_id_id:
            source_name = UtmSource._generate_name(self, content)
            self.source_id = UtmSource.objects.create(name=source_name)
        elif self.source_id_id and content:
            new_name = UtmSource._generate_name(self, content)
            if new_name:
                self.source_id.name = UtmMixin._get_unique_names(
                    'utm.source', [new_name],
                    skip_record_ids=[self.source_id_id])[0]
                self.source_id.save(update_fields=['name'])

        return super().save(*args, **kwargs)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``:106-113``) — al duplicar, el contador avanza.

        Devuelve los valores de la copia con su nombre ya numerado; quien
        copia decide con qué crearlos. Sin esto la copia chocaría con la
        restricción ``UNIQUE(name)`` de ``utm.source``.
        """
        default = default or {}
        default_name = default.get('name')
        vals = dict(default)
        vals['name'] = UtmMixin._get_unique_names(
            'utm.source', [default_name or self.name])[0]
        return [vals]
