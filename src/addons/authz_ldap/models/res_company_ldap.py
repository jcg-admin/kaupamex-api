"""``res.company.ldap`` — configuración LDAP por ResCompany.

Adaptación fiel de Odoo ``auth_ldap/models/res_company_ldap.py`` (LGPL-3).

La One2many ``ldaps`` que la referencia declara en ``res_company.py`` es aquí
el reverso de la FK ``company`` (``related_name='ldaps'``) — ver el mapa en
``models/__init__.py``.

Dependencia externa: ``python-ldap`` es opcional (extra ``ldap``; el propio
manifest de la referencia lo declara ``external_dependencies`` con fallback
apt). Verificado en este contenedor (2026-08-03): sin ``libldap2-dev``/
``libsasl2-dev`` la rueda no compila (``lber.h`` faltante), así que el import
va guardado con ``importlib`` — llamadas de función, no statements ``import``
(patrón sancionado de ``no-lazy-imports.md``). Sin el paquete,
``LDAP_AVAILABLE=False`` y toda operación LDAP levanta ``UserError``
explícito en vez de romper el arranque.
"""
import importlib.util
import logging

from django.conf import settings
from django.apps import apps as django_apps

import fields
import models
from exceptions import AccessDenied, UserError
from tools.mail import single_email_re
from tools.misc import str2bool

from addons.base.models import SystemParameter, TimeStampedModel

_logger = logging.getLogger(__name__)

LDAP_AVAILABLE = importlib.util.find_spec('ldap') is not None
if LDAP_AVAILABLE:
    ldap = importlib.import_module('ldap')
    ldap_filter = importlib.import_module('ldap.filter')
else:
    ldap = None
    ldap_filter = None

# ≙ ir.config_parameter 'auth_ldap.disable_chase_ref' de la referencia
# (res_company_ldap.py:109); renombrado al namespace del addon nuestro.
PARAM_DISABLE_CHASE_REF = 'authz_ldap.disable_chase_ref'

_NO_LDAP_MSG = (
    'python-ldap no está instalado. Instalar con `uv sync --extra ldap` '
    '(requiere libldap2-dev y libsasl2-dev del sistema).'
)


class LDAPWrapper:
    """≙ ``LDAPWrapper`` de la referencia (res_company_ldap.py:15-29) verbatim:
    expone sólo las 4 operaciones que el addon usa sobre la conexión."""

    def __init__(self, obj):
        self.__obj__ = obj

    def passwd_s(self, *args, **kwargs):
        self.__obj__.passwd_s(*args, **kwargs)

    def search_st(self, *args, **kwargs):
        return self.__obj__.search_st(*args, **kwargs)

    def simple_bind_s(self, *args, **kwargs):
        self.__obj__.simple_bind_s(*args, **kwargs)

    def unbind(self, *args, **kwargs):
        self.__obj__.unbind(*args, **kwargs)


class CompanyLdapManager(models.Manager):

    def get_ldap_dicts(self):
        """≙ ``_get_ldap_dicts`` (res_company_ldap.py:74-95): configuraciones
        en formato dict, ordenadas por ``sequence``."""
        return list(
            self.exclude(ldap_server='')
            .order_by('sequence')
            .values(
                'id', 'company_id', 'ldap_server', 'ldap_server_port',
                'ldap_binddn', 'ldap_password', 'ldap_filter', 'ldap_base',
                'user_id', 'create_user', 'ldap_tls',
            )
        )


class CompanyLdap(TimeStampedModel):
    """Campos fieles a ``res_company_ldap.py:38-72``. Los métodos de conexión
    y autenticación son de clase porque operan sobre el dict de configuración
    (igual que la referencia, donde ``self`` no lleva estado en ellos)."""

    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='ldaps',
        verbose_name='Compañía',
    )
    ldap_server = fields.Char(
        max_length=255, default='127.0.0.1',
        verbose_name='Servidor LDAP',
    )
    ldap_server_port = fields.Integer(
        default=389, verbose_name='Puerto LDAP',
    )
    ldap_binddn = fields.Char(
        max_length=255, blank=True, default='', verbose_name='binddn LDAP',
        help_text='Cuenta con la que se consulta el directorio. Vacío = '
                  'conexión anónima.',
    )
    ldap_password = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Contraseña LDAP',
        help_text='Contraseña de la cuenta que consulta el directorio.',
    )
    ldap_filter = fields.Char(
        max_length=1024, verbose_name='Filtro LDAP',
        help_text='Filtro de búsqueda de cuentas. Cada `%s` se reemplaza por '
                  'el login; debe producir exactamente 1 resultado. Ej.: '
                  '(&(objectCategory=person)(objectClass=user)'
                  '(sAMAccountName=%s))',
    )
    ldap_base = fields.Char(
        max_length=1024, verbose_name='Base LDAP',
        help_text='DN base de la búsqueda: se exploran todos sus '
                  'descendientes.',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Usuario plantilla',
        help_text='Usuario a copiar al crear usuarios nuevos.',
    )
    create_user = fields.Boolean(
        default=True, verbose_name='Crear usuario',
        help_text='Crear automáticamente la cuenta local para usuarios '
                  'nuevos que autentican vía LDAP.',
    )
    ldap_tls = fields.Boolean(
        default=False, verbose_name='Usar TLS',
        help_text='STARTTLS al conectar. Requiere servidor con STARTTLS; '
                  'sin él, toda autenticación fallará.',
    )

    objects = CompanyLdapManager()

    class Meta:
        db_table = 'res_company_ldap'
        ordering = ['sequence']
        verbose_name = 'Configuración LDAP'
        verbose_name_plural = 'Configuraciones LDAP'

    def __str__(self):
        # _rec_name = 'ldap_server' en la referencia
        return self.ldap_server

    # ------------------------------------------------------------------
    # Conexión y consulta — ≙ res_company_ldap.py:97-199
    # ------------------------------------------------------------------

    @classmethod
    def _connect(cls, conf):
        """≙ ``_connect`` (res_company_ldap.py:97-114)."""
        if not LDAP_AVAILABLE:
            raise UserError(_NO_LDAP_MSG)
        uri = 'ldap://%s:%d' % (conf['ldap_server'], conf['ldap_server_port'])
        connection = ldap.initialize(uri)
        chase_ref_disabled = SystemParameter.get_param(
            PARAM_DISABLE_CHASE_REF, 'True')
        if str2bool(chase_ref_disabled, default=True):
            connection.set_option(ldap.OPT_REFERRALS, ldap.OPT_OFF)
        if conf['ldap_tls']:
            connection.start_tls_s()
        return LDAPWrapper(connection)

    @classmethod
    def _get_entry(cls, conf, login):
        """≙ ``_get_entry`` (res_company_ldap.py:116-131)."""
        filter_tmpl = conf['ldap_filter']
        placeholders = filter_tmpl.count('%s')
        if not placeholders:
            _logger.warning(
                "LDAP filter %r contains no placeholder ('%%s').", filter_tmpl)
        formatted_filter = ldap_filter.filter_format(
            filter_tmpl, [login] * placeholders)
        results = cls._query(conf, formatted_filter)
        results = [entry for entry in results if entry[0]]
        dn, entry = False, False
        if len(results) == 1:
            dn, _attrs = entry = results[0]
        return dn, entry

    @classmethod
    def _authenticate(cls, conf, login, password):
        """≙ ``_authenticate`` (res_company_ldap.py:133-162).

        Rechaza password vacío explícitamente para impedir el
        'unauthenticated authentication' (bind anónimo con dn válido,
        RFC 4513 §6.3.1) — igual que la referencia.
        """
        if not password:
            return False
        dn, entry = cls._get_entry(conf, login)
        if not dn:
            return False
        try:
            conn = cls._connect(conf)
            conn.simple_bind_s(dn, password)
            conn.unbind()
        except ldap.INVALID_CREDENTIALS:
            return False
        except ldap.LDAPError as e:
            _logger.error('An LDAP exception occurred: %s', e)
            return False
        return entry

    @classmethod
    def _query(cls, conf, formatted_filter, retrieve_attributes=None):
        """≙ ``_query`` (res_company_ldap.py:164-199): bind simple (autenticado,
        anónimo o no-autenticado, RFC 4513 §5.1) + búsqueda subtree."""
        results = []
        try:
            conn = cls._connect(conf)
            ldap_password = conf['ldap_password'] or ''
            ldap_binddn = conf['ldap_binddn'] or ''
            conn.simple_bind_s(ldap_binddn, ldap_password)
            results = conn.search_st(
                conf['ldap_base'], ldap.SCOPE_SUBTREE, formatted_filter,
                retrieve_attributes, timeout=60)
            conn.unbind()
        except ldap.INVALID_CREDENTIALS:
            _logger.error('LDAP bind failed.')
        except ldap.LDAPError as e:
            _logger.error('An LDAP exception occurred: %s', e)
        return results

    # ------------------------------------------------------------------
    # Alta de usuarios federados — ≙ res_company_ldap.py:201-247
    # ------------------------------------------------------------------

    @classmethod
    def _map_ldap_attributes(cls, conf, login, ldap_entry):
        """≙ ``_map_ldap_attributes`` (res_company_ldap.py:201-218).

        Divergencia declarada: la referencia separa ``name`` (cn del
        directorio) de ``login``; nuestro ``ResUsers`` delega la identidad al
        partner y su ``login`` ES el email (base/models/res_users.py), así
        que el ``cn`` viaja como nombre del partner al crear el usuario.
        """
        data = {
            'name': ldap_entry[1]['cn'][0],
            'login': login,
            'company_id': conf['company_id'],
        }
        if isinstance(data['name'], bytes):
            data['name'] = data['name'].decode('utf-8')
        if single_email_re.match(login):
            data['email'] = login
        return data

    @classmethod
    def _get_or_create_user(cls, conf, login, ldap_entry):
        """≙ ``_get_or_create_user`` (res_company_ldap.py:220-247).

        Devuelve el id del usuario local activo con ese login, creándolo si
        no existe y ``create_user`` lo permite. La copia desde usuario
        plantilla de la referencia (``copy(default=values)``) no se porta:
        nuestro alta pasa por ``ResUsers.objects`` para que el partner se
        cree con la identidad correcta; el campo ``user`` (plantilla) queda
        reservado para cuando exista un caso que lo pida.
        """
        login = login.lower().strip()
        ResUsers = django_apps.get_model('base', 'ResUsers')
        existing = (
            ResUsers.objects.filter(login__iexact=login)
            .values_list('id', 'active').first()
        )
        if existing:
            if existing[1]:
                return existing[0]
        elif conf['create_user']:
            _logger.debug('Creating new user "%s" from LDAP', login)
            values = cls._map_ldap_attributes(conf, login, ldap_entry)
            user = ResUsers.objects.create_user(
                login=values['login'],
                name=values['name'],
                company_id=values.get('company_id'),
            )
            # Password local vacío: la credencial vive en el directorio.
            user.set_unusable_password()
            user.save(update_fields=['password'])
            return user.id

        raise AccessDenied(
            'No local user found for LDAP login and not configured to '
            'create one')

    # ------------------------------------------------------------------
    # Cambio de contraseña y prueba de conexión — ≙ :249-350
    # ------------------------------------------------------------------

    @classmethod
    def _change_password(cls, conf, login, old_passwd, new_passwd):
        """≙ ``_change_password`` (res_company_ldap.py:249-264)."""
        changed = False
        dn, _entry = cls._get_entry(conf, login)
        if not dn:
            return False
        try:
            conn = cls._connect(conf)
            conn.simple_bind_s(dn, old_passwd)
            conn.passwd_s(dn, old_passwd, new_passwd)
            changed = True
            conn.unbind()
        except ldap.INVALID_CREDENTIALS:
            # silent OK because una contraseña vieja incorrecta es un NO, no un
            # error: `changed` sigue en False y el llamador decide. Fiel a
            # `odoo19c: addons/auth_ldap/models/res_company_ldap.py:157-158`,
            # que hace `return False` en la misma rama. No se registra el
            # intento fallido a propósito — sería un canal de enumeración.
            pass
        except ldap.LDAPError as e:
            _logger.error('An LDAP exception occurred: %s', e)
        return changed

    def test_ldap_connection(self):
        """≙ ``test_ldap_connection`` (res_company_ldap.py:266-350).

        La referencia devuelve una ``ir.actions.client`` de notificación (su
        UI); aquí el contrato es un dict plano que la vista sella en la
        respuesta DRF — misma información, sin el sobre de acción de cliente.
        """
        conf = {
            'ldap_server': self.ldap_server,
            'ldap_server_port': self.ldap_server_port,
            'ldap_binddn': self.ldap_binddn,
            'ldap_password': self.ldap_password,
            'ldap_base': self.ldap_base,
            'ldap_tls': self.ldap_tls,
        }
        if not LDAP_AVAILABLE:
            return {'ok': False, 'codigo_error': 'LDAP_UNAVAILABLE',
                    'detail': _NO_LDAP_MSG}
        try:
            conn = self._connect(conf)
            conn.simple_bind_s(self.ldap_binddn or '', self.ldap_password or '')
            conn.unbind()
            return {'ok': True, 'detail': (
                'Conexión exitosa a %s:%d' % (
                    self.ldap_server, self.ldap_server_port))}
        except ldap.SERVER_DOWN:
            return {'ok': False, 'codigo_error': 'LDAP_SERVER_DOWN',
                    'detail': 'No se puede contactar %s:%d' % (
                        self.ldap_server, self.ldap_server_port)}
        except ldap.INVALID_CREDENTIALS:
            return {'ok': False, 'codigo_error': 'LDAP_INVALID_CREDENTIALS',
                    'detail': 'Credenciales inválidas para el bind DN %s' % (
                        self.ldap_binddn,)}
        except ldap.TIMEOUT:
            return {'ok': False, 'codigo_error': 'LDAP_TIMEOUT',
                    'detail': 'Tiempo de espera agotado contra %s:%d' % (
                        self.ldap_server, self.ldap_server_port)}
        except ldap.LDAPError as e:
            return {'ok': False, 'codigo_error': 'LDAP_ERROR',
                    'detail': 'Ocurrió un error: %s' % (e,)}
