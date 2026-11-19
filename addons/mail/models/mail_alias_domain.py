"""MailAliasDomain — dominio de correo por empresa (app ``addons.mail``).

Portación **fiel** de Odoo ``mail.alias.domain``
(``odoo19c: addons/mail/models/mail_alias_domain.py``, ``odoo-tools@622ddc2a``;
addon ``mail`` declara ``license: LGPL-3`` → copia + adaptación con
atribución, DEC-KX-03).

Modela los dominios de correo usados para recibir mensajes por los alias
*catchall* y *bounce*, y para redirigir respuestas vía ``mail.alias``. En Odoo
esto **reemplazó** al parámetro de configuración ``mail.alias.domain`` que se
usaba hasta v16: el dominio dejó de ser un ajuste global y pasó a ser un
registro por empresa. Esa es la razón de que exista el modelo — no es un
catálogo decorativo.

Correspondencia Odoo -> Django (adaptación sin azúcar sintáctica):

- ``_name='mail.alias.domain'`` / ``_description='Email Domain'`` -> modelo
  ``MailAliasDomain`` con ``db_table='mail_alias_domain'``.
- ``_order='sequence ASC, id ASC'`` -> ``Meta.ordering=['sequence', 'id']``.
- ``company_ids = One2many('res.company', 'alias_domain_id')`` -> en Django la
  inversa la provee el ``related_name`` del FK, que vive en ``res_company.py``
  y **no** en este archivo — igual que en la referencia, donde el ``One2many``
  sólo declara la vuelta de un ``Many2one`` ajeno. Ese FK
  (``ResCompany.alias_domain``) **todavía no existe** en nuestro árbol: ver la
  divergencia declarada abajo.
- ``bounce_email`` / ``catchall_email`` / ``default_from_email`` son
  ``compute=`` **sin** ``store`` -> ``@property``. No llevan columna en ninguno
  de los dos lados: son la concatenación de dos campos que sí existen.
- ``_bounce_email_uniques`` / ``_catchall_email_uniques``
  (``UNIQUE(bounce_alias, name)`` / ``UNIQUE(catchall_alias, name)``) ->
  dos ``UniqueConstraint``.
- ``_check_name`` (``@api.constrains``) -> ``clean()``: el nombre debe casar
  ``DOT_ATOM_TEXT``. Odoo **no** lo sanea dinámicamente aquí a propósito
  ("would be confusing"): levanta para que el usuario corrija. Se preserva.
- ``_sanitize_configuration`` (``@api.model``) -> ``classmethod``; se invoca
  desde ``save()``, que cubre los dos puntos donde Odoo lo llama (``create``
  línea 147 y ``write`` línea 170).
- ``_find_aliases`` (``@api.model``) -> ``classmethod``. Es el consumidor real
  de ``SystemParameter`` (``ir.config_parameter`` ya portado en
  ``addons.base``): lee ``mail.catchall.domain.allowed``.

``res.company.alias_domain_id`` —la inversa de ``company_ids``— lo declara
``addons/mail/models/res_company.py`` (columna en ``base/0121``), y
``_check_default_from_not_used_by_users`` (``:175-184``) corre tras cada
``save()``, como tras ``create``/``write`` en la fuente, contra los servidores
personales de ``addons/mail/models/ir_mail_server.py``. El arranque de
``create`` (``:152-163``) —el primer dominio se asigna a toda empresa y a todo
alias sin dominio— lo hace ``_assign_first_domain`` en la misma transacción.

**Divergencias declaradas** respecto a la referencia:

"""

from django.core.exceptions import ValidationError
from django.db import models, transaction

import fields

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_mail_server import IrMailServer
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.mail.models.mail_alias import DOT_ATOM_TEXT, MailAlias
from exceptions import UserError
from orm.environments import env, sudo
from tools.translate import _


class MailAliasDomain(TimeStampedModel):
    """
    Dominio de correo usado por los alias catchall / bounce de una empresa.
    """

    name = fields.Char(
        max_length=255,
        help_text=(
            "Odoo ``name``: dominio de correo, p. ej. 'example.com' en "
            "'kaupamex@example.com'."
        ),
    )
    sequence = fields.Integer(
        default=10, help_text="Odoo ``sequence``: orden de presentación."
    )

    bounce_alias = fields.Char(
        max_length=255,
        default='bounce',
        help_text=(
            "Odoo ``bounce_alias``: parte local del correo usado como "
            "Return-Path cuando un mensaje rebota, p. ej. 'bounce' en "
            "'bounce@example.com'."
        ),
    )
    catchall_alias = fields.Char(
        max_length=255,
        default='catchall',
        help_text=(
            "Odoo ``catchall_alias``: parte local del correo usado como "
            "Reply-To para capturar respuestas, p. ej. 'catchall' en "
            "'catchall@example.com'."
        ),
    )
    default_from = fields.Char(
        max_length=255,
        null=True,
        blank=True,
        default='notifications',
        help_text=(
            "Odoo ``default_from``: remitente por defecto cuando no casa "
            "ningún filtro del servidor saliente. Admite parte local "
            "('notifications') o correo completo "
            "('notifications@example.com') para sobreescribir todo el "
            "correo saliente."
        ),
    )

    class Meta:
        db_table = 'mail_alias_domain'
        ordering = ['sequence', 'id']
        verbose_name = 'Email Domain'
        verbose_name_plural = 'Email Domains'
        constraints = [
            models.UniqueConstraint(
                fields=['bounce_alias', 'name'],
                name='mail_alias_domain_bounce_email_unique',
            ),
            models.UniqueConstraint(
                fields=['catchall_alias', 'name'],
                name='mail_alias_domain_catchall_email_unique',
            ),
        ]

    def __str__(self):
        return self.name

    # -- Campos derivados (Odoo compute sin store) --------------------------

    @property
    def bounce_email(self):
        """Odoo ``_compute_bounce_email`` (líneas 53-57)."""
        if not self.bounce_alias:
            return ''
        return f'{self.bounce_alias}@{self.name}'

    @property
    def catchall_email(self):
        """Odoo ``_compute_catchall_email`` (líneas 59-63)."""
        if not self.catchall_alias:
            return ''
        return f'{self.catchall_alias}@{self.name}'

    @property
    def default_from_email(self):
        """Odoo ``_compute_default_from_email`` (líneas 65-75).

        ``default_from`` puede ser un correo completo, no sólo una parte
        izquierda como bounce o catchall: sólo se le añade el dominio si hace
        falta.
        """
        if not self.default_from:
            return ''
        if '@' in self.default_from:
            return self.default_from
        return f'{self.default_from}@{self.name}'

    # -- Validación (Odoo @api.constrains) ----------------------------------

    def clean(self):
        """
        Odoo ``_check_name`` (líneas 128-141) +
        ``_check_bounce_catchall_uniqueness``.

        El nombre debe casar ``DOT_ATOM_TEXT``. Odoo **no** lo sanea aquí a
        propósito (cambiar el valor dinámicamente confundiría al usuario):
        levanta para que se corrija.
        """
        super().clean()
        if not self.name:
            raise ValidationError(
                'No se puede asignar un nombre de dominio vacío.'
            )
        if not DOT_ATOM_TEXT.match(self.name):
            raise ValidationError(
                'No se puede usar nada distinto de caracteres latinos sin '
                'acentos en el nombre de dominio %s.'
                % self.name
            )
        self._check_bounce_catchall_uniqueness()

    def _check_bounce_catchall_uniqueness(self):
        """Odoo ``_check_bounce_catchall_uniqueness`` (líneas 77-126).

        Dos comprobaciones distintas, ambas de la referencia:

        1. Otro dominio **con el mismo nombre** no puede repetir el bounce o
           el catchall (los ``UniqueConstraint`` lo garantizan en la DB; esto
           lo reporta como error de validación legible antes de llegar ahí).
        2. Ningún ``MailAlias`` existente puede estar ya ocupando esa
           dirección de bounce/catchall — si lo estuviera, el correo entrante
           se rutearía al alias en vez de a la pasarela.
        """
        propios = [e for e in (self.bounce_email, self.catchall_email) if e]
        if not propios:
            return

        gemelos = type(self).objects.filter(name=self.name).exclude(pk=self.pk)
        for gemelo in gemelos:
            if self.bounce_alias and gemelo.bounce_alias == self.bounce_alias:
                raise ValidationError(
                    'El alias de rebote %s ya se usa en otro dominio con el '
                    'mismo nombre.'
                    % self.bounce_email
                )
            if (
                self.catchall_alias
                and gemelo.catchall_alias == self.catchall_alias
            ):
                raise ValidationError(
                    'El alias catchall %s ya se usa en otro dominio con el '
                    'mismo nombre.'
                    % self.catchall_email
                )

        # Odoo busca por parte izquierda para acotar y luego filtra por la
        # derecha (líneas 100-109). Aquí se filtra por la dirección completa,
        # que ``MailAlias`` almacena en ``alias_full_name`` — mismo resultado,
        # una consulta menos.
        existente = (
            MailAlias.objects.filter(alias_full_name__in=propios)
            .exclude(alias_domain__isnull=True)
            .first()
        )
        if existente is not None:
            raise ValidationError(
                "El bounce/catchall '%s' ya está en uso. Elige otro alias o "
                "cámbialo en el modelo enlazado."
                % existente.display_name
            )

    # -- Saneo de la configuración (Odoo _sanitize_configuration) -----------

    @classmethod
    def sanitize_configuration(cls, config_values):
        """Odoo ``_sanitize_configuration`` (líneas 186-199).

        Sanea ``name`` / ``bounce_alias`` / ``catchall_alias`` /
        ``default_from`` con el sanitizador de ``mail.alias``. El último va con
        ``is_email=True`` porque admite un correo completo.
        """
        sanear = MailAlias.sanitize_alias_name
        if config_values.get('name'):
            config_values['name'] = sanear(config_values['name'])
        if config_values.get('bounce_alias'):
            config_values['bounce_alias'] = sanear(
                config_values['bounce_alias']
            )
        if config_values.get('catchall_alias'):
            config_values['catchall_alias'] = sanear(
                config_values['catchall_alias']
            )
        if config_values.get('default_from'):
            config_values['default_from'] = sanear(
                config_values['default_from'], is_email=True
            )
        return config_values

    def save(self, *args, **kwargs):
        """
        Sanea antes de guardar (Odoo lo hace en ``create`` y en ``write``).
        """
        saneado = self.sanitize_configuration(
            {
                'name': self.name,
                'bounce_alias': self.bounce_alias,
                'catchall_alias': self.catchall_alias,
                'default_from': self.default_from,
            }
        )
        self.name = saneado['name'] or self.name
        self.bounce_alias = saneado['bounce_alias'] or self.bounce_alias
        self.catchall_alias = saneado['catchall_alias'] or self.catchall_alias
        self.default_from = saneado['default_from'] or self.default_from
        # ≙ ``create``/``write`` (``:150``, ``:172``): la comprobación corre
        # tras escribir y, si falla, la transacción deshace la escritura
        adding = self._state.adding
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            self._check_default_from_not_used_by_users()
            if adding:
                self._assign_first_domain()
        return result

    def _assign_first_domain(self):
        """≙ el arranque de ``create`` (``:152-163``): el primer dominio se
        asigna a toda empresa —archivada o no— y a todo alias sin dominio."""
        cls = type(self)
        if cls.objects.count() != 1:
            return
        company_model = self._meta.get_field('company_ids').related_model
        with sudo():
            company_model.objects.filter(alias_domain_id__isnull=True).update(
                alias_domain_id=self.pk)
            # uno a uno: ``save`` recalcula ``alias_full_name``, el
            # ``compute`` almacenado de la fuente
            for alias in MailAlias.objects.filter(alias_domain__isnull=True):
                alias.alias_domain = self
                alias.save()

    def _check_default_from_not_used_by_users(self):
        """≙ ``_check_default_from_not_used_by_users`` (``:175-184``): el
        remitente por defecto no puede ser el de un servidor personal."""
        match_from_filter = IrMailServer._match_from_filter
        with sudo():
            personal_mail_servers = env()['ir.mail_server'].search(
                [('owner_user_id', '!=', False)])
            if any(
                match_from_filter(self.default_from_email, server.from_filter)
                for server in personal_mail_servers
            ):
                raise UserError(_(
                    "A personal mail server is using that address, you can "
                    "not use it."))

    # -- Búsqueda de alias por lista de correos (Odoo _find_aliases) --------

    @classmethod
    def find_aliases(cls, email_list):
        """Odoo ``_find_aliases`` (líneas 201-252).

        Dada una lista de correos ya normalizados, devuelve los que
        corresponden a un alias del sistema — sea de dominio (bounce, catchall,
        default_from) o un ``mail.alias`` concreto.

        :param email_list: correos normalizados; normalizar y descartar los
            inválidos es trabajo de quien llama (fiel a la referencia).
        """
        filtrados = [e for e in email_list if e and '@' in e]
        if not filtrados:
            return filtrados

        dominios = list(cls.objects.all())
        alias_de_dominio = set()
        for d in dominios:
            alias_de_dominio.update(
                x
                for x in (
                    d.bounce_email,
                    d.catchall_email,
                    d.default_from_email,
                )
                if x
            )

        # Dominios permitidos como catchall, de SystemParameter
        # (Odoo: ir.config_parameter 'mail.catchall.domain.allowed').
        permitidos_raw = (
            SystemParameter.get_param('mail.catchall.domain.allowed') or ''
        )
        permitidos = set(filter(None, permitidos_raw.split(',')))
        if permitidos:
            permitidos.update(d.name for d in dominios)
            partes_locales = [
                e.partition('@')[0]
                for e in filtrados
                if e.partition('@')[2] in permitidos
            ]
        else:
            partes_locales = [e.partition('@')[0] for e in filtrados if e]

        candidatos = MailAlias.objects.filter(
            models.Q(alias_full_name__in=filtrados)
            | models.Q(
                alias_name__in=partes_locales, alias_incoming_local=True
            )
        )
        # Los alias globales casan por nombre completo.
        alias_de_dominio.update(
            a.alias_full_name
            for a in candidatos
            if not a.alias_incoming_local and a.alias_full_name
        )
        # Los locales casan por parte izquierda + validación del dominio.
        locales = {a.alias_name for a in candidatos if a.alias_incoming_local}

        res = []
        for email in filtrados:
            if email in alias_de_dominio:
                res.append(email)
                continue
            parte_local, _, dominio = email.partition('@')
            if parte_local in locales and (
                not permitidos or dominio in permitidos
            ):
                res.append(email)
        return res
