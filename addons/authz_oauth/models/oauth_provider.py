"""``auth.oauth.provider`` — configuración de un proveedor OAuth2.

Adaptación fiel de Odoo ``auth_oauth/models/auth_oauth.py`` (LGPL-3, 22 loc):
mismos campos y mismo orden ``sequence, name``. ``css_class`` y ``body`` son
presentación del botón de login — aquí los consume el SPA vía el endpoint
público de proveedores, así que se conservan tal cual.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class OauthProvider(TimeStampedModel):
    """Class defining the configuration values of an OAuth2 provider."""

    name = fields.Char(
        max_length=255, verbose_name='Nombre del proveedor',
        help_text='Nombre de la entidad OAuth2: Google, etc.',
    )
    client_id = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Client ID',
        help_text='Nuestro identificador ante el proveedor.',
    )
    auth_endpoint = fields.Char(
        max_length=1024, verbose_name='URL de autorización',
        help_text='URL del proveedor para autenticar usuarios.',
    )
    scope = fields.Char(
        max_length=255, blank=True, default='openid profile email',
        verbose_name='Scope',
        help_text='Datos del usuario a los que se pide acceso.',
    )
    validation_endpoint = fields.Char(
        max_length=1024, verbose_name='URL de UserInfo',
        help_text='URL del proveedor para obtener la información del '
                  'usuario.',
    )
    data_endpoint = fields.Char(
        max_length=1024, blank=True, default='',
        verbose_name='URL de datos',
    )
    enabled = fields.Boolean(default=False, verbose_name='Permitido')
    css_class = fields.Char(
        max_length=255, blank=True,
        default='fa fa-fw fa-sign-in text-primary',
        verbose_name='Clase CSS',
    )
    body = fields.Char(
        max_length=255, verbose_name='Etiqueta del botón de login',
        help_text='Texto del enlace en el diálogo de login.',
    )
    sequence = fields.Integer(default=10, verbose_name='Secuencia')

    class Meta:
        db_table = 'auth_oauth_provider'
        ordering = ['sequence', 'name']
        verbose_name = 'Proveedor OAuth2'
        verbose_name_plural = 'Proveedores OAuth2'

    def __str__(self):
        return self.name
