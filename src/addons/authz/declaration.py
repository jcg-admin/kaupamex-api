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

**Por qué no ``__manifest__.py``.** El diseño
(``diseno-catalogo-l0-module-extendido``) fija la frontera: se calca el
*contrato de metadata* de Odoo, no su sistema de módulos (``addons_path``, el
manifiesto como archivo que lee un instalador). Kaupamex es Django-nativo — el
catálogo vive en DB y su declaración es Python importable.

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
import importlib

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


def _import_declaration(app_config):
    """Devuelve ``<app>.authz_catalog`` del addon, o ``None`` si no declara.

    Se usa ``importlib.import_module`` —una **llamada**, no un statement
    ``import``— porque el descubrimiento es dinámico por definición: el conjunto
    de addons se conoce en runtime. Es el patrón sancionado en
    ``.claude/rules/no-lazy-imports.md`` (excepción #4) y pasa el gate AST.
    """
    dotted_path = f'{app_config.name}.{DECLARATION_MODULE}'
    try:
        return importlib.import_module(dotted_path)
    except ModuleNotFoundError as exc:
        # Sólo se traga la ausencia del propio archivo de declaración. Un
        # ModuleNotFoundError lanzado DESDE authz_catalog.py (un import roto
        # adentro) se propaga: tragarlo haría desaparecer al addon del catálogo
        # en silencio, que es el defecto que esta pieza viene a cerrar.
        if exc.name == dotted_path:
            return None
        raise


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
