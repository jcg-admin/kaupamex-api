"""Registro único de opciones de configuración — patrón ``conf[]`` de Odoo.

Adaptación del ``configmanager`` de la referencia
(``odoo/tools/config.py``, ver ``docs: analisis-flujo-arranque-odoo-conf.rst``)
a las restricciones de Django. Dos diferencias deliberadas frente al modelo
original, ambas por la forma en que Django carga sus settings:

1. **Sin capa de CLI.** ``configmanager`` antepone flags de línea de
   comandos a las variables de entorno porque ``odoo-bin`` es un proceso de
   larga vida que se relanza con distintos argumentos. Los settings de
   Django se importan **una sola vez** por proceso (WSGI/Gunicorn, pytest,
   ``manage.py``); no hay un `argv` de arranque que reinterpretar en cada
   request. La capa de CLI de la referencia no tiene equivalente útil aquí.
2. **Sin ``ChainMap`` en vivo.** ``config['x']`` de Odoo resuelve en
   *runtime*, en cada acceso. Un `settings.X` de Django resuelve **una vez**,
   al importar el módulo — por eso este registro no expone un objeto
   ``config`` que el resto del código consulte: expone ``get(nombre)``,
   llamado una única vez por cada settings/*.py al construir sus constantes.

   Verificado contra el propio Django instalado (``.venv/lib/python3.12/
   site-packages/django/conf/__init__.py``, Django 6.0.5), no de memoria
   (``react-verification-gate.md`` §1-bis): ``LazySettings._setup()``
   (línea 62) hace ``self._wrapped = Settings(settings_module)`` una única
   vez, la primera vez que algo lee ``django.conf.settings``; ``Settings.
   __init__`` (línea 162) hace un único ``importlib.import_module(self.
   SETTINGS_MODULE)``; y ``LazySettings.__getattr__`` (línea 87) cachea
   cada valor resuelto en ``self.__dict__[name] = val`` — lecturas
   posteriores de ``settings.X`` golpean el caché de instancia, no vuelven a
   importar ni a re-evaluar el módulo. No hay lookup por-request: el
   ``ChainMap`` de la referencia sería trabajo sin efecto aquí.

Lo que sí se porta, íntegro, es la idea que motivó el análisis: **una tabla
única que declara cada opción, su variable de entorno y si es secreta**
(SOL-087: una opción sin ``default`` falla ruidoso si falta, en vez de
esconder un valor mágico), en vez de 35 llamadas ``config('X', default=Y,
cast=Z)`` dispersas en cuatro archivos sin registro central (H-CFG-01,
H-CFG-02). El fallback sigue siendo la capa de archivo — en Odoo un
``.conf`` INI; en Django, el propio módulo ``settings/*.py`` por entorno,
que ya cumple ese rol (development.py/testing.py/production.py sobre
base.py son la jerarquía de archivos de configuración de Django).
"""
from decouple import config as _decouple_config, Csv, Undefined


class Option:
    """Una entrada del registro — equivalente a un ``OdooOption``.

    ``default=Undefined`` (el valor por defecto de esta clase) es la marca
    de opción **secreta/requerida** (SOL-087): ``decouple.config()`` sin
    ``default=`` lanza ``UndefinedValueError`` si la variable de entorno no
    está presente, fallando ruidoso en vez de arrancar con un valor mágico.
    Un ``default`` explícito — literal o ``callable`` — es una opción
    **opcional**.
    """

    def __init__(self, env_name, *, default=Undefined, cast=None, help=''):
        self.env_name = env_name
        self.default = default
        self.cast = cast
        self.help = help

    @property
    def required(self):
        return self.default is Undefined

    def resolve(self):
        """Resuelve el valor: variable de entorno, con fallback al default.

        Un ``default`` ``callable`` se invoca sólo si la variable de
        entorno está ausente — reproduce a ``MFA_ENCRYPTION_KEY`` (cae a
        ``SECRET_KEY`` ya resuelto) y ``DJANGO_ADMIN_ENABLED`` (cae a
        ``DEBUG`` ya resuelto), que en el código disperso previo eran
        defaults de Python evaluados en el sitio, no de ``decouple``.
        """
        kwargs = {}
        if self.cast is not None:
            kwargs['cast'] = self.cast
        if self.default is Undefined:
            return _decouple_config(self.env_name, **kwargs)
        default = self.default() if callable(self.default) else self.default
        return _decouple_config(self.env_name, default=default, **kwargs)


# ─── Registro ────────────────────────────────────────────────────────────
# Un `Option` por variable de entorno reconocida. El orden sigue el de
# aparición original en base.py/testing.py/production.py (H-CFG-02) para
# que el diff de la migración sea trazable línea a línea.
OPTIONS = {
    # --- Django core ---------------------------------------------------
    'SECRET_KEY': Option('SECRET_KEY', help='Django secret key (SOL-087: requerida, sin default)'),
    'MFA_ENCRYPTION_KEY': Option(
        'MFA_ENCRYPTION_KEY',
        default=lambda: OPTIONS['SECRET_KEY'].resolve(),
        help='Clave Fernet para 2FA/TOTP en reposo; cae a SECRET_KEY si no se declara aparte',
    ),
    'DEBUG': Option('DEBUG', default=False, cast=bool),
    'DJANGO_ADMIN_ENABLED': Option(
        'DJANGO_ADMIN_ENABLED',
        default=lambda: OPTIONS['DEBUG'].resolve(),
        cast=bool,
        help='Monta /admin/ de Django (H-11); cae a DEBUG si no se declara aparte',
    ),
    'ALLOWED_HOSTS': Option('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv()),

    # --- Base de datos — producción/desarrollo (DATABASES['default']) --
    'DB_SSL_MODE': Option('DB_SSL_MODE', default='', help='Toggle opcional; vacío = verify-full contra CAs públicas (certifi)'),
    'DB_SOCKET': Option('DB_SOCKET', default='', help='Directorio del socket Unix; el socket ES el HOST en libpq (H-API-305)'),
    'DB_NAME': Option('DB_NAME', help='SOL-087: requerida'),
    'DB_USER': Option('DB_USER', help='SOL-087: requerida'),
    'DB_PASSWORD': Option('DB_PASSWORD', help='SOL-087: requerida'),
    'DB_HOST': Option('DB_HOST', help='SOL-087: requerida (ignorada si DB_SOCKET está presente)'),
    'DB_PORT': Option('DB_PORT', help='SOL-087: requerida'),

    # --- Multi-DB DB-per-company (SOL-091) ------------------------------
    'MULTIDB_COMPANY_DATABASES': Option('MULTIDB_COMPANY_DATABASES', default='', cast=Csv()),

    # --- Bootstrap del L1 de ejemplo (DEC-3 tenants-sin-clases-en-codigo)
    'BOOTSTRAP_COMPANY_CODE': Option('BOOTSTRAP_COMPANY_CODE', default=''),
    'BOOTSTRAP_COMPANY_NAME': Option('BOOTSTRAP_COMPANY_NAME', default=''),

    # --- CORS ------------------------------------------------------------
    'CORS_ALLOWED_ORIGINS': Option('CORS_ALLOWED_ORIGINS', default='', cast=Csv()),

    # --- Base de datos — QA (testing.py, DATABASES['default']) ----------
    'DB_QA_SSL_MODE': Option('DB_QA_SSL_MODE', default=''),
    'DB_QA_SOCKET': Option('DB_QA_SOCKET', default=''),
    'DB_QA_NAME': Option('DB_QA_NAME', help='SOL-087: requerida'),
    'DB_QA_USER': Option('DB_QA_USER', help='SOL-087: requerida'),
    'DB_QA_PASSWORD': Option('DB_QA_PASSWORD', help='SOL-087: requerida'),
    'DB_QA_HOST': Option('DB_QA_HOST', help='SOL-087: requerida (ignorada si DB_QA_SOCKET está presente)'),
    'DB_QA_PORT': Option('DB_QA_PORT', help='SOL-087: requerida'),

    # --- Producción (production.py) --------------------------------------
    'UI_DIST': Option('UI_DIST', default='', help='Ruta al build del SPA; vacío desactiva serve_spa'),
    'EMAIL_BACKEND': Option('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend'),
    'EMAIL_HOST': Option('EMAIL_HOST', default=''),
    'EMAIL_PORT': Option('EMAIL_PORT', default=587, cast=int),
    'EMAIL_USE_TLS': Option('EMAIL_USE_TLS', default=True, cast=bool),
    'EMAIL_HOST_USER': Option('EMAIL_HOST_USER', default=''),
    'EMAIL_HOST_PASSWORD': Option('EMAIL_HOST_PASSWORD', default=''),
    'FRONTEND_URL': Option('FRONTEND_URL', default='https://kaupamex.com'),
    'MEDIA_ROOT': Option('MEDIA_ROOT', default='/opt/kaupamex/media'),
}

# ALLOWED_HOSTS de producción usa un default distinto al de base.py — el
# dominio público de la plataforma en vez de sólo loopback (production.py:79).
# Se declara como una segunda entrada con el mismo env_name: decouple no
# distingue "quién pregunta", así que dos ``Option`` con env_names iguales y
# defaults distintos modelan correctamente que el default depende del
# archivo de settings que pregunta — igual que Odoo, donde un ``.conf`` de
# producción documenta valores que el ``.conf`` de dev no necesita.
OPTIONS_PRODUCTION_OVERRIDES = {
    'ALLOWED_HOSTS': Option(
        'ALLOWED_HOSTS',
        default='kaupamex.com,www.kaupamex.com,localhost,127.0.0.1',
        cast=Csv(),
    ),
}


def get(name, *, overrides=None):
    """Resuelve una opción registrada por su nombre.

    ``overrides`` es el diccionario a consultar antes que ``OPTIONS`` — lo
    usa ``production.py`` para su ``ALLOWED_HOSTS`` con default distinto.
    """
    if overrides and name in overrides:
        return overrides[name].resolve()
    return OPTIONS[name].resolve()


def required_options():
    """Nombres de las opciones sin default — el equivalente a SOL-087."""
    return sorted(name for name, opt in OPTIONS.items() if opt.required)
