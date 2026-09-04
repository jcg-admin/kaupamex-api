r"""``account_edi_proxy_client.user`` — el usuario de un formato EDI sobre el
proxy (Odoo ``account_edi_proxy_client``).

Adaptación de ``odoo19c: account_edi_proxy_client/models/
account_edi_proxy_user.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a
43eb31de``, LGPL-3, 235 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Veinte símbolos (9 campos + 1 excepción + 11 métodos) — todos con
contraparte real, salvo el detalle explícito abajo
======================================================================================

.. list-table::
   :header-rows: 1
   :widths: 32 15 53

   * - Símbolo
     - Estado
     - Nota
   * - ``AccountEdiProxyError`` (excepción)
     - portada
     - clase Python plana, sin cambios
   * - ``active`` / ``id_client`` / ``company_id`` / ``edi_identification`` /
       ``private_key_id`` / ``refresh_token`` / ``is_token_out_of_sync`` /
       ``token_sync_version`` / ``proxy_type`` / ``edi_mode``
     - portados
     - 10 campos (la referencia dice 9 en el cuerpo pero declara 10 — medido
       contra el archivo real); ``company`` → ``base.ResCompany``,
       ``related_name='account_edi_proxy_client_ids'`` (así ``res.company``
       gana el O2M inverso sin tocar su archivo, ver ``res_company.py``)
   * - ``_unique_id_client`` / ``_unique_active_company_proxy``
     - portados
     - ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``); la
       segunda es un ``UniqueConstraint`` **parcial** (``condition=Q(active
       =True)``), traducción directa del ``UniqueIndex`` con ``WHERE`` de
       la referencia
   * - ``_get_proxy_urls``
     - portado
     - terminal — ``{}``, para sobreescribir por un ``l10n_*_edi`` concreto
   * - ``_get_server_url``
     - portado
     - —
   * - ``_get_proxy_users``
     - portado
     - ``.filter()`` en vez de ``.filtered(lambda...)``
   * - ``_get_proxy_identification``
     - portado
     - terminal — ``None``
   * - ``_make_request``
     - portado
     - ``requests.post`` real; ``env.cr.commit()`` de la rama
       ``refresh_token_expired`` → ``transaction.atomic()`` no aplica aquí
       (no hay bloque abierto que cerrar) — se documenta como no-op
       explícito, ver el método
   * - ``_get_iap_params``
     - portado
     - ``company.env['ir.config_parameter']`` → ``SystemParameter``
       (``addons.base.models.ir_config_parameter``)
   * - ``_register_proxy_user``
     - portado
     - —
   * - ``_renew_token``
     - portado
     - ``self.lock_for_update()``/``LockError`` → ``lock_for_update()`` de
       ``account_edi/models/account_edi_document.py`` (mismo helper,
       reutilizado — construido una vez, no duplicado)
   * - ``_decrypt_data``
     - portado
     - ``self.env['certificate.key']._account_edi_fernet_decrypt`` →
       ``CertificateKey._account_edi_fernet_decrypt`` (``key.py``, este
       addon)

``sudo()`` — divergencia uniforme del módulo
==================================================

Cada ``.sudo()`` de la referencia (``self.sudo().active = False``,
``self.sudo().refresh_token = ...``, ``private_key_sudo``) → acceso/
escritura directos, mismo criterio que ``account_edi`` completo: sin ACL de
campo que saltarse en este puerto.
"""
import base64
import logging
import uuid
from typing import Literal

import requests

import fields
import models
from addons.account_edi.models.account_edi_document import lock_for_update
from addons.account_edi_proxy_client.models.account_edi_proxy_auth import KaupaMexEdiProxyAuth
from addons.base.models.ir_config_parameter import SystemParameter
from addons.certificate.models.key import CertificateKey
from exceptions import LockError, UserError
from tools.translate import _

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class AccountEdiProxyError(Exception):
    """≙ ``AccountEdiProxyError`` (``odoo19c: :18-22``)."""

    def __init__(self, code, message=None):
        self.code = code
        self.message = message
        super().__init__(message or code)


class AccountEdiProxyUser(models.Model):
    """≙ ``account_edi_proxy_client.user`` (``odoo19c: :25-31``).

    Un usuario de un formato EDI concreto (ej. PEPPOL) frente al proxy de
    Odoo S.A., identificado de forma única por ``(company, proxy_type,
    edi_mode)`` mientras esté activo.
    """

    _name = 'account_edi_proxy_client.user'
    _description = 'Account EDI proxy user'

    EDI_MODES = [
        ('prod', 'Producción'),
        ('test', 'Prueba'),
        ('demo', 'Demo'),
    ]

    active = fields.Boolean(default=True, help_text='Odoo active.')
    id_client = fields.Char(
        max_length=255,
        help_text='Identificador asignado por el proxy (Odoo id_client, requerido).',
    )
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, db_index=True,
        related_name='account_edi_proxy_client_ids',
        help_text='Empresa (Odoo company_id, requerido). related_name da a '
                  'res.company el O2M inverso sin tocar su archivo.',
        db_column='company_id',
    )
    edi_identification = fields.Char(
        max_length=255,
        help_text='Identificador único del usuario (típicamente el RFC/VAT), '
                  'requerido.',
    )
    private_key_id = fields.Many2one(
        'certificate.CertificateKey', on_delete=models.PROTECT,
        related_name='edi_proxy_users',
        help_text='Llave para cifrar los datos del usuario (Odoo '
                  'private_key_id, requerido; domain público=False en la '
                  'referencia, no reforzado a nivel de campo aquí).',
        db_column='private_key_id',
    )
    refresh_token = fields.Char(max_length=255, blank=True, default='')
    is_token_out_of_sync = fields.Boolean(
        default=False,
        help_text='El token quedó desincronizado con el proxy y necesita '
                  'renovarse (Odoo is_token_out_of_sync).',
    )
    token_sync_version = fields.Integer(default=0)
    proxy_type = fields.Selection(
        max_length=32, choices=[], blank=True, default='',
        help_text='Tipo de proxy — vacío hasta que un l10n_*_edi concreto '
                  'declare valores (Odoo proxy_type, requerido allá).',
    )
    edi_mode = fields.Selection(max_length=4, choices=EDI_MODES, blank=True, default='')

    class Meta:
        db_table = 'account_edi_proxy_client_user'
        verbose_name = 'Usuario del proxy EDI'
        verbose_name_plural = 'Usuarios del proxy EDI'
        constraints = [
            # ≙ ``_unique_id_client`` (``odoo19c: :63-64``).
            models.UniqueConstraint(fields=['id_client'], name='uniq_edi_proxy_id_client'),
            # ≙ ``_unique_active_company_proxy`` (``odoo19c: :65-68``) —
            # UniqueIndex parcial: sólo entre filas activas.
            models.UniqueConstraint(
                fields=['company_id', 'proxy_type', 'edi_mode'],
                condition=models.Q(active=True),
                name='uniq_edi_proxy_active_company',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.proxy_type}:{self.edi_identification}'

    def _get_proxy_urls(self):
        """≙ ``_get_proxy_urls`` (``odoo19c: :70-72``, terminal —
        sobreescribir)."""
        return {}

    def _get_server_url(self, proxy_type=None, edi_mode=None):
        """≙ ``_get_server_url`` (``odoo19c: :74-79``)."""
        proxy_type = proxy_type or self.proxy_type
        edi_mode = edi_mode or self.edi_mode
        proxy_urls = self._get_proxy_urls()
        return proxy_urls[proxy_type][edi_mode]

    @classmethod
    def _get_proxy_users(cls, company, proxy_type):
        """≙ ``_get_proxy_users`` (``odoo19c: :81-84``)."""
        return company.account_edi_proxy_client_ids.filter(proxy_type=proxy_type)

    @classmethod
    def _get_proxy_identification(cls, company, proxy_type):
        """≙ ``_get_proxy_identification`` (``odoo19c: :86-91``, terminal —
        sobreescribir)."""
        return None

    def _make_request(self, url, params=None, *, auth_type: Literal['hmac', 'asymmetric'] = 'hmac'):
        """≙ ``_make_request`` (``odoo19c: :93-137``).

        El ``self.env.cr.commit()`` de la rama ``refresh_token_expired`` no
        tiene contraparte: no hay bloque ``transaction.atomic()`` abierto
        que cerrar aquí (cada llamada corre en autocommit salvo que el
        llamador abra su propia transacción) — se omite, documentado, no
        silencioso.
        """
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': params or {},
            'id': uuid.uuid4().hex,
        }

        if self.edi_mode == 'demo':
            raise AccountEdiProxyError('block_demo_mode', "Can't access the proxy in demo mode")

        try:
            res = requests.post(
                url, json=payload, timeout=DEFAULT_TIMEOUT,
                headers={'content-type': 'application/json'},
                auth=KaupaMexEdiProxyAuth(user=self, auth_type=auth_type))
            res.raise_for_status()
            response = res.json()
        except (ValueError, requests.exceptions.ConnectionError,
                requests.exceptions.MissingSchema, requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as error:
            _logger.warning('Connection error <%s>: %s', url, error)
            raise AccountEdiProxyError(
                'connection_error',
                _('The url that this service requested returned an error. '
                  'The url it tried to contact was %s') % url) from error

        if 'error' in response:
            if response['error']['code'] == 404:
                message = _(
                    'The url that this service tried to contact does not '
                    'exist. The url was “%s”') % url
            else:
                error_message = (response['error'].get('data', {}).get('message')
                                  or response['error']['message'])
                message = _(
                    'The url that this service requested returned an error. '
                    'The url it tried to contact was %(url)s. %(error_message)s'
                ) % {'url': url, 'error_message': error_message}
            raise AccountEdiProxyError('connection_error', message)

        proxy_error = response['result'].pop('proxy_error', None)
        if proxy_error:
            error_code = proxy_error['code']
            if error_code == 'refresh_token_expired':
                self._renew_token()
                return self._make_request(url, params, auth_type='hmac')
            if error_code == 'no_such_user':
                self.active = False
                self.save(update_fields=['active'])
            if error_code == 'invalid_signature':
                raise AccountEdiProxyError(
                    error_code,
                    _("Failed to connect to Odoo Access Point server. This "
                      "might be due to another connection to Odoo Access "
                      "Point server. It can occur if you have duplicated "
                      "your database. \n\n"
                      "If you are not sure how to fix this, please contact "
                      "our support."))
            raise AccountEdiProxyError(error_code, proxy_error.get('message') or None)

        return response['result']

    def _get_iap_params(self, company, proxy_type, private_key):
        """≙ ``_get_iap_params`` (``odoo19c: :139-147``). ``company.env[
        'ir.config_parameter']`` → ``SystemParameter`` directo (sin ``env``
        en este ORM)."""
        edi_identification = self._get_proxy_identification(company, proxy_type)
        return {
            'dbuuid': SystemParameter.get_param('database.uuid'),
            'company_id': company.pk,
            'edi_identification': edi_identification,
            'public_key': private_key._get_public_key_bytes(encoding='pem').decode(),
            'proxy_type': proxy_type,
        }

    def _register_proxy_user(self, company, proxy_type, edi_mode):
        """≙ ``_register_proxy_user`` (``odoo19c: :149-179``)."""
        private_key = CertificateKey._generate_rsa_private_key(
            company, name=f'{proxy_type}_{edi_mode}_{company.pk}.key')
        edi_identification = self._get_proxy_identification(company, proxy_type)
        if edi_mode == 'demo':
            response = {'id_client': f'demo{company.pk}{proxy_type}', 'refresh_token': 'demo'}
        else:
            try:
                server_url = self._get_server_url(proxy_type, edi_mode)
                response = self._make_request(
                    f'{server_url}/iap/account_edi/2/create_user',
                    params=self._get_iap_params(company, proxy_type, private_key))
            except AccountEdiProxyError as error:
                raise UserError(error.message) from error
            if 'error' in response:
                if response['error'] == 'A user already exists with this identification.':
                    raise UserError(_(
                        'A user already exists with theses credentials on '
                        'our server. Please check your information.'))
                raise UserError(response['error'])

        return AccountEdiProxyUser.objects.create(
            id_client=response['id_client'],
            company_id=company,
            proxy_type=proxy_type,
            edi_mode=edi_mode,
            edi_identification=edi_identification,
            private_key_id=private_key,
            refresh_token=response['refresh_token'],
        )

    def _renew_token(self):
        """≙ ``_renew_token`` (``odoo19c: :191-206``)."""
        try:
            lock_for_update(AccountEdiProxyUser.objects.filter(pk=self.pk))
        except LockError:
            return
        response = self._make_request(self._get_server_url() + '/iap/account_edi/1/renew_token')
        if 'error' in response:
            _logger.error(response['error'])
        self.refresh_token = response['refresh_token']
        self.save(update_fields=['refresh_token'])

    def _decrypt_data(self, data, symmetric_key):
        """≙ ``_decrypt_data`` (``odoo19c: :208-215``)."""
        decrypted_key = self.private_key_id._decrypt(base64.b64decode(symmetric_key))
        return CertificateKey._account_edi_fernet_decrypt(
            decrypted_key, base64.b64decode(data))


def apply_account_edi_proxy_client_extensions():
    """No aplica — ``AccountEdiProxyUser`` es un modelo NUEVO (``_name``, no
    ``_inherit``). Se define por uniformidad con
    ``AccountEdiProxyClientConfig.ready()``."""
    return None
