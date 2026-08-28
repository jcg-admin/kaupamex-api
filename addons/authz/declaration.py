"""Contrato de declaración del catálogo L0 — cada addon declara lo suyo (#179).

**Qué resuelve (SOL-100).** Hasta ahora ``seed_authz`` era la **fuente** del
catálogo: un archivo con 25 códigos escritos a mano que nadie actualizaba al
agregar un addon. La consecuencia está medida (H-API-106): sólo 9 de 77
carpetas de ``src/addons/`` tenían un ``Module.code`` homónimo, y el código
``orders`` sobrevivió al addon retirado (``api@77bd1f0``) sosteniendo cuatro
aristas de dependencia hacia un nombre sin dueño.

Aquí ``seed_authz`` pasa de **fuente** a **recolector**: cada addon declara su
entrada de catálogo y sus capacidades en un módulo ``authz_catalog.py`` propio,
y el seed las recoge recorriendo ``INSTALLED_APPS``.

**Por qué declaración y no señales (DEC-01=B).** El análisis de referencia
(``analisis-mapeo-registro-permisos-pretix-vs-catalogo-db``) comparó el registro
por señales de pretix (``register_*_permission_groups``) contra un catálogo en
tabla, y cerró la decisión a favor del segundo: es *"greppeable, consultable por
SQL, auditable y versionado"*. Este contrato la respeta — el
``authz_catalog.py`` de cada addon es **dato declarativo**, no un receiver que
ensambla en runtime, y sigue siendo greppeable::

    grep -rn "ModuleSpec(" src/addons/*/authz_catalog.py

**Los dos archivos, y por qué son dos** (corregido 2026-08-01, H-API-113).

La primera versión de este módulo tenía aquí una sección titulada *"Por qué no
``__manifest__.py``"*, que lo descartaba por ser *"el manifiesto como archivo
que lee un instalador"*. Era falso, y el error fue de razonamiento: el manifest
de Odoo hace **dos trabajos** —declarar metadata y sostener el estado de
instalación— y se descartaron ambos midiendo sólo el segundo. La prueba está
en la referencia: ``ir.module.module.get_values_from_terp``
(odoo19c: odoo/addons/base/models/ir_module.py:752) es una función **pura** que
mapea el dict del manifest a columnas, sin instalador de por medio.

Así que el manifest sí se porta, y hoy conviven dos declaraciones con sujetos
distintos:

- ``<addon>/__manifest__.py`` — **el addon**. Dato literal, leído con
  ``ast.literal_eval`` igual que en la referencia. Lleva ``license``,
  ``category``, ``version``, ``application``, ``depends``. Es donde vive la
  licencia de la fuente adaptada, que DEC-KX-03 exige preservar y no
  re-etiquetar.
- ``<addon>/authz_catalog.py`` — **los módulos comerciales y sus capacidades**.
  No es lo mismo que el addon: medido, 18 de 25 códigos de módulo no coinciden
  con el nombre de su carpeta, y dos addons declaran dos módulos cada uno
  (``settings_app`` → ``banners`` + ``settings``; ``website`` → ``content`` +
  ``seo``) — algo que el modelo de Odoo no puede representar, porque allí un
  manifest es un módulo es una carpeta.

Son **dos ejes**: ``ir.module.module`` es catálogo técnico (qué está
instalado); ``authz.Module`` es catálogo comercial (qué contrata una company).
Que no coincidan **no** autoriza a colapsarlos — forzar ``code == carpeta``
rompería los 18 códigos de los que cuelgan las capacidades y las suscripciones
ya sembradas, y aun así no podría representar los dos addons con dos módulos:
ganaría parecido, no fidelidad.

Lo que sí exige es tener **los dos**, como la referencia (directiva del
ejecutor 2026-08-01). El técnico vive en ``base.IrModule`` y se puebla de los
manifiestos; el comercial es éste. Sin el técnico hay estado que el sistema no
registra en ninguna parte: medido, **4 carpetas de** ``src/addons/`` **no están
en** ``INSTALLED_APPS`` —``contact``, ``referral``, ``returns``, ``reviews``—
y hoy ese hecho sólo existe como conocimiento tribal.

Las capacidades tampoco tienen análogo en el manifest — en la referencia viven
en ``security/ir.model.access.csv`` y los grupos. Son extensión nuestra y se
declaran como tal.

**Por qué ``authz_catalog.py`` y no ``catalog.py``.** ``addons/authz/catalog.py``
ya existe con otro significado desde SOL-094 (consulta del catálogo sembrado:
``sensitive_codes``, ``unknown_capability_codes``). El prefijo evita la
colisión y dice a qué subsistema alimenta el archivo.

Uso desde un addon::

    # src/addons/<addon>/authz_catalog.py
    from addons.authz.declaration import CapabilitySpec, ModuleSpec

    MODULES = [
        ModuleSpec(code='catalogue', name='Catálogo',
                   is_application=True, category='Order Management'),
    ]
    CAPABILITIES = [
        CapabilitySpec(code='catalogue', name='Catálogo'),
    ]
"""
import ast
import importlib
import os
from textwrap import dedent

from django.apps import apps

# Nombre del módulo que cada addon puede definir para declarar su catálogo.
DECLARATION_MODULE = 'authz_catalog'


class DuplicateDeclaration(Exception):
    """Dos addons declaran el mismo ``code``.

    Es un error **ruidoso** a propósito: con la siembra central el último en
    escribir ganaba en silencio. Un código tiene exactamente un dueño.
    """


class ModuleSpec:
    """Declaración de un ``authz.Module`` por parte de su addon dueño.

    Los campos calcan el contrato ``__manifest__`` que ya modela
    ``authz.Module`` (``diseno-catalogo-l0-module-extendido``). ``tier`` **no**
    se declara aquí: el modelo de precios es #180 y todos quedan en el default
    ``free`` hasta esa decisión — declararlo ahora sería inventar precios.

    ``depends`` lista códigos de **otros módulos**, no de addons: es el grafo
    **funcional** que gobierna qué puede activarse para una company (SOL-085
    S3), distinto del grafo de imports que vigila
    ``scripts/check_addon_cycles.py``.
    """

    __slots__ = ('code', 'name', 'is_application', 'category', 'depends')

    def __init__(self, code, name, is_application=False, category='', depends=()):
        self.code = code
        self.name = name
        self.is_application = is_application
        self.category = category
        self.depends = tuple(depends)

    def __repr__(self):
        return f'ModuleSpec({self.code!r})'


class CapabilitySpec:
    """Declaración de una ``authz.Capability`` por parte de su addon dueño.

    Dos formas, según DEC-11:

    - **Sustantivo puro** (``catalogue``, ``payments``): capacidad CRUD; el
      nivel de acceso vive en ``RoleCapability.level``, no en el código.
    - **Acción nombrada** (``inventory.adjust``, ``platform.provision``): con
      punto; es membresía, sin nivel.

    ``module`` es el ``code`` del módulo al que pertenece. Si se omite se
    deriva: el prefijo antes del punto para las acciones nombradas, o el propio
    código para los sustantivos — que es la convención que ya seguía el seed
    central.
    """

    __slots__ = ('code', 'name', 'is_sensitive', 'module')

    def __init__(self, code, name, is_sensitive=False, module=None):
        self.code = code
        self.name = name
        self.is_sensitive = is_sensitive
        self.module = module or code.split('.', 1)[0]

    def __repr__(self):
        return f'CapabilitySpec({self.code!r})'


MANIFEST_FILE = '__manifest__.py'

# Las diez licencias que declara ``ir.module.module.license``
# (odoo19c: odoo/addons/base/models/ir_module.py:306-317), con su mismo
# default. Se porta la lista completa —no sólo las que hoy usamos— porque es
# el vocabulario del titular, no nuestro: recortarlo obligaría a re-etiquetar
# una fuente el día que aparezca, que es exactamente lo que DEC-KX-03 prohíbe.
MANIFEST_LICENSES = (
    'GPL-2', 'GPL-2 or any later version',
    'GPL-3', 'GPL-3 or any later version',
    'AGPL-3', 'LGPL-3',
    'Other OSI approved licence',
    'OEEL-1', 'OPL-1', 'Other proprietary',
)
DEFAULT_LICENSE = 'LGPL-3'

# Licencia de un addon escrito por nosotros, sin código copiado de una fuente
# externa. Coincide con la que declara ``pyproject.toml`` para el producto.
OWN_LICENSE = 'Confidential'

VALID_LICENSES = MANIFEST_LICENSES + (OWN_LICENSE,)


def values_from_manifest(manifest):
    """Mapea el dict de un ``__manifest__.py`` a los valores del catálogo.

    Es el análogo de ``ir.module.module.get_values_from_terp``
    (``odoo19c: odoo/addons/base/models/ir_module.py:752-768``) — una función
    **pura**, sin DB ni Django, para que el gate estático la use igual que el
    seed.

    Se portan los mismos defaults de la referencia, incluido
    ``license='LGPL-3'``: en Odoo un addon sin licencia declarada es LGPL-3, no
    "sin licencia".

    Cobertura, declarada: 14 de 14 claves de la fuente
    ===================================================

    La versión anterior devolvía **9** claves y su docstring decía *"se portan
    los mismos defaults de la referencia"* — cierto de las nueve presentes y
    silencioso sobre las **ocho** ausentes (``description``, ``author``,
    ``maintainer``, ``contributors``, ``website``, ``icon``, ``url``,
    ``to_buy``). Es la forma de :ref:`h-api-845`: una cobertura parcial
    declarada como completa. Ahora están las catorce.

    **Tres claves nuestras que la fuente no tiene**, y por qué:

    - ``category`` — la fuente la resuelve como FK (``category_id``) en
      ``_update_category``, no en esta función. Aquí es un desnormalizado
      provisional; su reestructuración a FK sigue pendiente.
    - ``installable`` y ``depends`` — el ``state`` y el grafo se derivan de
      ellas, y el seed las consume y descarta. En la fuente ese trabajo lo
      hacen ``_update_from_terp`` y ``_update_dependencies``, que pertenecen al
      instalador.

    **``author`` no cae a ``'Unknown'``.** La fuente lo hace porque su corpus
    tiene addons de terceros sin autor declarado. Aquí ``modules.module``
    ya rellena el autor del proyecto cuando el manifest no lo declara, así que
    escribir ``'Unknown'`` aquí guardaría un dato falso para un addon propio.
    Se cae a cadena vacía, que es lo que ``blank=True, default=''`` expresa.
    """
    return {
        'shortdesc':      manifest.get('name', ''),
        'summary':        manifest.get('summary', ''),
        'description':    dedent(manifest.get('description', '')),
        'category':       manifest.get('category', 'Uncategorized'),
        'version':        manifest.get('version', '1.0'),
        'license':        manifest.get('license', DEFAULT_LICENSE),
        'author':         manifest.get('author', ''),
        'maintainer':     manifest.get('maintainer', ''),
        'contributors':   ', '.join(manifest.get('contributors', ())),
        'website':        manifest.get('website', ''),
        'url':            manifest.get('url') or manifest.get('live_test_url', ''),
        'icon':           manifest.get('icon') or '',
        'to_buy':         False,
        'application':    manifest.get('application', False),
        'auto_install':   manifest.get('auto_install', False) is not False,
        'installable':    manifest.get('installable', True),
        'depends':        tuple(manifest.get('depends', ())),
    }


def read_manifest(addon_dir):
    """Lee y evalúa el ``__manifest__.py`` de un addon; ``None`` si no tiene.

    Se evalúa con ``ast.literal_eval`` —no ``exec``, no ``import``— porque el
    manifest **es dato**: un dict literal. Es la misma razón por la que Odoo lo
    parsea en vez de importarlo, y lo que permite leerlo sin Django arrancado.
    """
    path = os.path.join(addon_dir, MANIFEST_FILE)
    if not os.path.isfile(path):
        return None
    return ast.literal_eval(open(path, encoding='utf-8').read())


def _import_declaration(app_config):
    """Devuelve el módulo de catálogo del addon, o ``None`` si no declara.

    Busca en dos ubicaciones, en orden:

    1. ``<app>.security.authz_catalog`` — el layout fiel a odoo-tools, donde el
       catálogo (= la ACL ``security/ir.model.access.csv`` de la referencia)
       vive bajo ``security/``.
    2. ``<app>.authz_catalog`` — el layout plano histórico (raíz del addon).

    Retrocompatible: los addons planos siguen funcionando por la 2ª ruta; los
    reestructurados a ``security/`` por la 1ª. Se usa ``importlib.import_module``
    —una **llamada**, no un statement ``import``— porque el descubrimiento es
    dinámico (``.claude/rules/no-lazy-imports.md`` excepción #4; pasa el gate AST).
    """
    for dotted_path in (
        f'{app_config.name}.security.{DECLARATION_MODULE}',
        f'{app_config.name}.{DECLARATION_MODULE}',
    ):
        try:
            return importlib.import_module(dotted_path)
        except ModuleNotFoundError as exc:
            # Sólo se traga la ausencia del propio archivo de declaración (o su
            # paquete ``security``). Un ModuleNotFoundError lanzado DESDE
            # authz_catalog.py (un import roto adentro) se propaga: tragarlo
            # haría desaparecer al addon del catálogo en silencio, que es el
            # defecto que esta pieza viene a cerrar.
            if exc.name in (dotted_path, f'{app_config.name}.security'):
                continue
            raise
    return None


def discover():
    """Recorre ``INSTALLED_APPS`` y devuelve ``(modules, capabilities)``.

    Ambos son dicts ``code -> spec``. El orden de inserción es el de
    ``INSTALLED_APPS``, estable entre corridas.

    Levanta ``DuplicateDeclaration`` si dos addons declaran el mismo ``code``.
    """
    modules = {}
    capabilities = {}
    owners = {}
    for app_config in apps.get_app_configs():
        declared = _import_declaration(app_config)
        if declared is None:
            continue
        for spec in getattr(declared, 'MODULES', ()):
            if spec.code in modules:
                raise DuplicateDeclaration(
                    f'El módulo {spec.code!r} lo declaran {owners[spec.code]!r} '
                    f'y {app_config.name!r}. Un código tiene un solo dueño.'
                )
            modules[spec.code] = spec
            owners[spec.code] = app_config.name
        for spec in getattr(declared, 'CAPABILITIES', ()):
            if spec.code in capabilities:
                raise DuplicateDeclaration(
                    f'La capacidad {spec.code!r} la declaran '
                    f'{owners[spec.code]!r} y {app_config.name!r}.'
                )
            capabilities[spec.code] = spec
            owners[spec.code] = app_config.name
    return modules, capabilities


def orphan_capabilities(modules, capabilities):
    """Capacidades cuyo ``module`` no lo declara ningún addon.

    Es el ``assert_valid_permission`` de pretix aplicado al otro extremo del
    catálogo: allá se valida que un permiso **usado** exista; aquí, que una
    capacidad **declarada** cuelgue de un módulo real. Sin este check una
    capacidad huérfana rompe el seed con un ``KeyError`` opaco.
    """
    return sorted(
        spec.code for spec in capabilities.values() if spec.module not in modules
    )


def unknown_depends(modules):
    """Aristas ``depends`` que apuntan a un módulo no declarado.

    Este check es el que habría cazado el caso ``orders`` de H-API-106: el
    addon se retiró y cuatro aristas quedaron colgando de un código sin dueño
    sin que nada fallara.
    """
    dangling = []
    for spec in modules.values():
        for dep in spec.depends:
            if dep not in modules:
                dangling.append((spec.code, dep))
    return sorted(dangling)
