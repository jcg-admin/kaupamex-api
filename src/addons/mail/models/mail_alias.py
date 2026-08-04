"""MailAlias — mapeo de una dirección de correo a un modelo (app ``addons.mail``).

Portación **fiel** de Odoo ``mail.alias``
(``odoo19c: addons/mail/models/mail_alias.py``, ``odoo-tools@622ddc2a``;
addon ``mail`` declara ``license: LGPL-3`` → copia + adaptación con
atribución, DEC-KX-03).

Un alias asocia una dirección entrante con un modelo: cuando la pasarela de
correo recibe un mensaje cuyo destinatario casa con el alias, o bien lo adjunta
a la discusión existente (si es respuesta) o crea un registro nuevo del modelo
apuntado.

Correspondencia Odoo -> Django (adaptación sin azúcar sintáctica):

- ``_name='mail.alias'`` / ``_description='Email Aliases'`` -> modelo
  ``MailAlias`` con ``db_table='mail_alias'`` (tabla fiel al nombre de Odoo).
- ``_order='alias_model_id, alias_name'`` -> ``Meta.ordering``.
- ``_rec_name='alias_name'`` -> ``__str__`` devuelve ``display_name``, que es
  lo que Odoo muestra (incluye el dominio cuando existe).
- ``alias_full_name`` es ``compute=..., store=True`` en Odoo: campo **derivado
  y almacenado**. Aquí se recalcula en ``save()`` (línea 42 de la referencia).
  No es duplicación: Odoo lo almacena para poder **buscar** por él
  (``_find_aliases`` filtra ``alias_full_name in ...``).
- ``alias_domain`` es ``related='alias_domain_id.name'`` -> ``@property``
  (lectura delegada, sin columna — es el mismo criterio de delegación que
  ``ir_cron``/``mail_mail``: FK real + propiedad).
- ``alias_model_id`` / ``alias_parent_model_id`` -> FK a ``IrModel`` (el
  registro reflejado ya portado en ``addons.base``).
- ``ondelete='restrict'`` -> ``on_delete=models.PROTECT``;
  ``ondelete='cascade'`` -> ``models.CASCADE``.
- ``_name_domain_unique = UniqueIndex('(alias_name, COALESCE(alias_domain_id, 0))')``
  -> ``UniqueConstraint`` sobre el par. Odoo usa ``COALESCE`` porque en SQL
  ``NULL != NULL``: sin él, dos aliases con el mismo nombre y **sin** dominio
  no colisionarían. MariaDB tiene la misma semántica, así que se replica con
  ``Coalesce`` en el constraint.
- ``dot_atom_text`` (rfc5322 §3.2.3) y ``_sanitize_alias_name`` se portan
  verbatim — son el contrato que ``MailAliasDomain`` invoca para sanear sus
  propios ``bounce_alias`` / ``catchall_alias`` / ``default_from``.

**Fuera de este archivo:** la pasarela de correo entrante de Odoo
(``_alias_bounced_content``, ``_check_alias_domain_id_mc`` y el ruteo de
mensajes por modelo) no se porta aquí — depende del ORM de Odoo (``self.env``
dinámico por nombre de modelo) y de ``mail.thread``. Lo que se porta es el
**registro** del alias: su identidad, su saneo y su unicidad.
"""
import re
import unicodedata

from django.db import models
from django.db.models.functions import Coalesce

import fields
from addons.base.models.timestamped_mixin import TimeStampedModel

# rfc5322 sección 3.2.3 — verbatim de la referencia (líneas 15-16).
ATEXT = r"[a-zA-Z0-9!#$%&'*+\-/=?^_`{|}~]"
DOT_ATOM_TEXT = re.compile(r"^%s+(\.%s+)*$" % (ATEXT, ATEXT))


def remove_accents(input_str):
    """Quita los diacríticos de ``input_str``.

    Odoo lo importa de ``odoo.tools``; aquí se porta como función del módulo
    (misma implementación: descomposición NFKD y descarte de los combinantes).
    """
    if not input_str:
        return input_str
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return ''.join(c for c in nkfd_form if not unicodedata.combining(c))


def sanitize_alias_name(name, is_email=False):
    """Limpia y sanea el nombre de un alias (Odoo ``_sanitize_alias_name``).

    En algunos casos el alias debe ser un correo completo en vez de sólo la
    parte izquierda (al sanear ``default_from``, por ejemplo). En ese caso se
    extrae la parte derecha y se vuelve a poner tras sanear la izquierda.

    :param str name: nombre a sanear.
    :param bool is_email: si conservar la parte derecha; si no, sólo se
        conserva la izquierda.
    :returns: el nombre saneado, o ``False`` si no queda nada.

    Es función de módulo (no método) porque Odoo la declara ``@api.model`` —
    no usa el recordset. ``MailAliasDomain`` la invoca directamente.
    """
    sanitized_name = name.strip() if name else ''
    if is_email:
        right_part = sanitized_name.lower().partition('@')[2]
    else:
        right_part = False
    if sanitized_name:
        sanitized_name = remove_accents(sanitized_name).lower().split('@')[0]
        # no puede empezar ni terminar en punto
        sanitized_name = re.sub(r'^\.+|\.+$|\.+(?=\.)', '', sanitized_name)
        # subconjunto de caracteres permitidos
        sanitized_name = re.sub(r"[^\w!#$%&'*+\-/=?^_`{|}~.]+", '-', sanitized_name)
        sanitized_name = sanitized_name.encode('ascii', errors='replace').decode()
    if not sanitized_name.strip():
        return False
    return f'{sanitized_name}@{right_part}' if is_email and right_part else sanitized_name


class MailAlias(TimeStampedModel):
    """Mapeo de una dirección de correo a un modelo del registro reflejado."""

    # -- Definición del correo ---------------------------------------------
    alias_name = fields.Char(
        max_length=255, null=True, blank=True,
        help_text="Odoo ``alias_name``: nombre del alias, p. ej. 'jobs' para "
                  "recibir correo en <jobs@example.com>.")
    alias_full_name = fields.Char(
        max_length=512, null=True, blank=True, db_index=True,
        help_text="Odoo ``alias_full_name`` (compute+store): dirección "
                  "completa. Almacenado para poder buscar por él.")
    alias_domain = fields.Many2one(
        'mail.MailAliasDomain', on_delete=models.PROTECT,
        null=True, blank=True, related_name='aliases',
        help_text="Odoo ``alias_domain_id``: dominio del alias "
                  "(``ondelete='restrict'``).")

    # Columna generada que materializa el ``COALESCE(alias_domain_id, 0)`` del
    # índice de la referencia. No es un campo del modelo Odoo: es el soporte
    # físico que MariaDB necesita para poder indexar esa expresión — no admite
    # índices funcionales, sólo índices sobre columnas generadas STORED.
    # Sin ella, Django OMITE el constraint EN SILENCIO y la unicidad no existe
    # (H-API-281). Se declara ``editable=False``: la calcula la base.
    alias_domain_key = models.GeneratedField(
        expression=Coalesce('alias_domain_id', models.Value(0)),
        output_field=models.BigIntegerField(),
        db_persist=True,
    )

    # -- Destino: crear / actualizar ---------------------------------------
    alias_model = fields.Many2one(
        'base.IrModel', on_delete=models.CASCADE, related_name='aliases',
        help_text="Odoo ``alias_model_id``: modelo al que corresponde el "
                  "alias. Todo correo entrante que no responda a un registro "
                  "existente crea un registro nuevo de este modelo.")
    alias_defaults = fields.Text(
        default='{}',
        help_text="Odoo ``alias_defaults``: diccionario Python evaluado para "
                  "proveer valores por defecto al crear registros.")
    alias_force_thread_id = fields.Integer(
        null=True, blank=True,
        help_text="Odoo ``alias_force_thread_id``: ID opcional de un hilo al "
                  "que se adjuntan todos los mensajes entrantes aunque no lo "
                  "respondan. Si se fija, deshabilita la creación de "
                  "registros nuevos.")

    # -- Propietario --------------------------------------------------------
    alias_parent_model = fields.Many2one(
        'base.IrModel', on_delete=models.CASCADE,
        null=True, blank=True, related_name='child_aliases',
        help_text="Odoo ``alias_parent_model_id``: modelo que sostiene el "
                  "alias, no necesariamente el mismo que ``alias_model`` "
                  "(ejemplo: project sostiene el alias que crea task).")
    alias_parent_thread_id = fields.Integer(
        null=True, blank=True,
        help_text="Odoo ``alias_parent_thread_id``: ID del registro padre "
                  "que sostiene el alias.")

    # -- Configuración de entrada (pasarela) --------------------------------
    CONTACT_EVERYONE = 'everyone'
    CONTACT_PARTNERS = 'partners'
    CONTACT_FOLLOWERS = 'followers'
    CONTACT_CHOICES = [
        (CONTACT_EVERYONE, 'Everyone'),
        (CONTACT_PARTNERS, 'Authenticated Partners'),
        (CONTACT_FOLLOWERS, 'Followers only'),
    ]
    alias_contact = fields.Char(
        max_length=16, choices=CONTACT_CHOICES, default=CONTACT_EVERYONE,
        help_text="Odoo ``alias_contact``: política para publicar en el "
                  "documento vía la pasarela. everyone: cualquiera; "
                  "partners: sólo partners autenticados; followers: sólo "
                  "seguidores del documento.")
    alias_incoming_local = fields.Boolean(
        default=False,
        help_text="Odoo ``alias_incoming_local``: detección de entrada "
                  "basada en la parte local.")
    alias_bounced_content = fields.Text(
        null=True, blank=True,
        help_text="Odoo ``alias_bounced_content``: si se fija, este "
                  "contenido se envía a usuarios no autorizados en lugar del "
                  "mensaje por defecto.")

    STATUS_NOT_TESTED = 'not_tested'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_CHOICES = [
        (STATUS_NOT_TESTED, 'Not Tested'),
        (STATUS_VALID, 'Valid'),
        (STATUS_INVALID, 'Invalid'),
    ]
    alias_status = fields.Char(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_NOT_TESTED,
        help_text="Odoo ``alias_status`` (compute+store): estado evaluado "
                  "sobre el último mensaje recibido.")

    class Meta:
        db_table = 'mail_alias'
        ordering = ['alias_model_id', 'alias_name']
        verbose_name = 'Email Alias'
        verbose_name_plural = 'Email Aliases'
        constraints = [
            # Odoo: UniqueIndex('(alias_name, COALESCE(alias_domain_id, 0))').
            # El COALESCE es deliberado: sin él dos aliases homónimos SIN
            # dominio no colisionarían (NULL != NULL en SQL).
            #
            # Va sobre ``fields=`` y no sobre la expresión: MariaDB declara
            # ``supports_expression_indexes = False``, y ante eso Django NO
            # falla — omite el constraint sin decir nada. La expresión vive en
            # la columna generada ``alias_domain_key``, que sí se puede indexar
            # (``supports_stored_generated_columns = True``). Ver H-API-281.
            models.UniqueConstraint(
                fields=['alias_name', 'alias_domain_key'],
                name='mail_alias_name_domain_unique',
            ),
        ]

    def __str__(self):
        return self.display_name

    # -- Campos derivados (Odoo compute) ------------------------------------

    @property
    def alias_domain_name(self):
        """Odoo ``alias_domain`` (``related='alias_domain_id.name'``).

        Delegación por propiedad, no columna — mismo criterio que ``ir_cron``
        y ``mail_mail``. El nombre lleva sufijo ``_name`` porque en Django el
        campo FK ya ocupa el identificador ``alias_domain``.
        """
        return self.alias_domain.name if self.alias_domain_id else None

    @property
    def display_name(self):
        """Odoo ``_compute_display_name`` (líneas 229-240 de la referencia).

        Devuelve ``jobs@mail.example.com``, o ``jobs`` si no hay dominio, o
        "Inactive Alias" si no hay ni nombre.
        """
        if self.alias_name and self.alias_domain_id:
            return f'{self.alias_name}@{self.alias_domain.name}'
        if self.alias_name:
            return self.alias_name
        return 'Inactive Alias'

    def _compute_alias_full_name(self):
        """Odoo ``_compute_alias_full_name`` (líneas de ``mail_alias.py``).

        A diferencia de ``display_name``, no tiene el texto de UI "Inactive
        Alias": devuelve ``None`` cuando no hay nombre, porque es un campo
        almacenado sobre el que se busca.
        """
        if self.alias_domain_id and self.alias_name:
            return f'{self.alias_name}@{self.alias_domain.name}'
        if self.alias_name:
            return self.alias_name
        return None

    def save(self, *args, **kwargs):
        """Sanea el nombre y recalcula ``alias_full_name`` antes de guardar.

        Odoo lo hace con ``@api.depends`` + ``store=True``; Django no tiene
        campos calculados almacenados, así que el recálculo va aquí — el
        efecto observable es el mismo: la columna queda siempre consistente
        con ``alias_name`` + ``alias_domain``.
        """
        if self.alias_name:
            self.alias_name = sanitize_alias_name(self.alias_name) or None
        self.alias_full_name = self._compute_alias_full_name()
        return super().save(*args, **kwargs)
