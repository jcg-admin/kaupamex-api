"""Metadata de release de la plataforma — fiel en forma a ``odoo/release.py``.

Se porta la **forma** (``version_info`` comparable estilo ``sys.version_info``,
niveles de release, mínimos de runtime), **no los valores**: copiar
``version_info = (19, 0, 0, FINAL, 0, '')`` y ``product_name = 'Odoo'`` verbatim
afirmaría que este árbol *es* Odoo 19, que es falso — es una adaptación
(DEC-KX-03). Los valores son los de Kaupamex.

``version`` se mantiene en sincronía con ``[project].version`` de
``pyproject.toml`` (hoy 0.1.0); ``pyproject`` es la fuente para el empaquetado y
éste lo es para el código que necesita la versión en runtime.
"""
RELEASE_LEVELS = [ALPHA, BETA, RELEASE_CANDIDATE, FINAL] = [
    'alpha', 'beta', 'candidate', 'final',
]
RELEASE_LEVELS_DISPLAY = {
    ALPHA: 'a',
    BETA: 'b',
    RELEASE_CANDIDATE: 'rc',
    FINAL: '',
}

# (MAJOR, MINOR, MICRO, RELEASE_LEVEL, SERIAL, SUFFIX) — comparable con
# operadores normales, igual que en la referencia:
#   (0,1,0,'beta',0) < (0,1,0,'candidate',1) < (0,1,0,'final',0)
version_info = (0, 1, 0, ALPHA, 0, '')
series = serie = major_version = '.'.join(str(s) for s in version_info[:2])
version = (
    series
    + RELEASE_LEVELS_DISPLAY[version_info[3]]
    + str(version_info[4] or '')
    + version_info[5]
)

product_name = 'Kaupamex'
description = 'Kaupamex — plataforma L0 de comercio multi-company'
long_desc = """Kaupamex es el operador L0 de una plataforma SaaS multi-empresa
que hospeda a empresas cliente (L1) para gestionar su ecommerce, ERP y CRM, con
cobro por modulo mas renta mensual. Las capacidades tecnicas incluyen un
monolito modular Django, un ORM extendido con el vocabulario de primitivos de la
referencia, aislamiento por empresa a nivel de fila y un contrato OpenAPI 3
generado desde el codigo.
"""
classifiers = """Development Status :: 3 - Alpha
License :: Other/Proprietary License

Programming Language :: Python
"""
url = 'https://github.com/jcg-admin/kaupamex'
author = 'Equipo Kaupamex'
author_email = 'dev@kaupamex.com'

# Licencia de ESTE árbol. No es la de los addons adaptados: cada addon declara
# en su ``__manifest__.py`` la licencia de la fuente de la que se adapta
# (DEC-KX-03 punto 1) — una licencia no se re-etiqueta.
license = 'Confidential'

# Nombre del servicio de Windows. La referencia lo deriva de la serie con ese
# mismo `replace` porque su MAJOR puede ser una cadena arbitraria ('saas~xx') y
# la tilde no es válida en el nombre de un servicio NT. Lo consume
# ``tools/osutil.is_running_as_nt_service`` en la rama de Windows.
nt_service_name = 'kaupamex-server-' + series.replace('~', '-')

# Mínimos de runtime. Coherentes con `requires-python` de pyproject
# (">=3.12,<3.15"). La BD canónica es PostgreSQL (ADR-028, supersede
# ADR-008/ADR-009 MariaDB).
MIN_PY_VERSION = (3, 12)
MAX_PY_VERSION = (3, 14)

# Entero, no tupla — la referencia lo multiplica por 10000 para compararlo con
# el `server_version` de libpq (``odoo19c: odoo/sql_db.py:699``), y una tupla no
# admite esa aritmética. El valor es el mínimo efectivo: el mayor entre el de la
# referencia (13, ``odoo19c: odoo/release.py:41``) y el de Django 6
# (``django/db/backends/postgresql/features.py:10``, que aborta la conexión).
MIN_PG_VERSION = 14
