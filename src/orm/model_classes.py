"""Construcción de clases de modelo — fiel a ``odoo/orm/model_classes.py`` (Odoo 19).

En Odoo este módulo es la maquinaria que, al cargar los addons, **fusiona** las
definiciones de un mismo ``_name`` (herencia por ``_inherit``) en una sola clase
registrada, resuelve los campos, y las inserta en el ``Registry``
(``add_to_registry``, ``setup_model_classes``, ``add_field``, ``pop_field``). Es
el corazón del sistema de herencia de Odoo.

Mapeo a Django — **Django ya tiene su propia maquinaria de construcción de
clases**: la metaclase ``ModelBase`` procesa cada ``class X(models.Model)`` al
importarla (resuelve campos, ``Meta``, herencia) y la registra en ``apps``. Por
eso este archivo es un stub delgado documentado:

=====================================  ==================================================
Odoo ``model_classes``                 Equivalente Django
=====================================  ==================================================
metaclase que arma la clase            ``django.db.models.base.ModelBase``
``add_to_registry(...)`` (``:152``)    registro automático de ``ModelBase`` en ``apps``
``setup_model_classes(env)`` (``:301``)  import de ``models/`` + ``apps.populate()``
``_inherit`` = *extensión* (fusiona    intra-app: herencia Python (abstract base /
definiciones del mismo ``_name``,      multi-table); cross-app: **FK RELATED**
o del padre, en una clase por MRO)     (DEC-SALE-01) — no hay fusión por ``_name``
``_inherits`` = *delegación* (Many2one  ``OneToOneField``/FK + delegación por
delegate required, ondelete cascade;   ``property`` (o multi-table inheritance) —
``_check_inherits`` ``:465``)          composición, no fusión de clase
``add_field`` / ``pop_field``          declaración de campos en la clase +
                                       ``contribute_to_class`` de ``ModelBase``
``is_model_class`` / ``is_model_def``  ``issubclass(x, models.Model)`` /
                                       ``not x._meta.abstract``
=====================================  ==================================================

Validación del bloque de comentarios de Odoo (``model_classes.py:32-138``,
PROVEN verbatim en la fuente 19) y su mapeo — los comentarios son **correctos** y
describen el mecanismo real (el código bajo ellos, ``:152+``, lo implementa). Tres
conceptos y por qué en Django divergen:

1. **"model definitions" vs "model classes".** En Odoo la *definición* es la
   clase estática del código del módulo; la *model class* del ``Registry`` se
   construye **dinámicamente al armar el registro**, heredando (en orden inverso,
   para respetar el override) de TODAS las definiciones del mismo ``_name`` — su
   MRO se calcula ahí. En Django **no existe esa dualidad**: ``ModelBase``
   construye la clase **una vez, al importar** (estática), y esa misma clase es la
   del registro (``apps``). No hay "definición" separada de "clase de registro".

2. **Fusión por ``_name`` (A1+A2+A3 → una clase ``a``).** Es la mayor divergencia:
   Django es *una clase = un modelo = una tabla*; no se declara el mismo modelo
   varias veces en módulos distintos para fusionarlo. Por DEC-SALE-01, la
   *extensión* (``_inherit``) se resuelve como herencia Python intra-app y como
   **FK RELATED** cross-app; la *delegación* (``_inherits``, que en Odoo exige un
   Many2one delegate) es composición nativa (``OneToOneField``/FK + delegación).

3. **Model classes por registro (por-DB) + "fields shared across registries".**
   En Odoo el registro es **por base de datos** y la optimización es compartir el
   objeto ``field`` entre registros cuando se puede (por eso los magic fields van
   en las clases-definición, ``:136-138``). En Django las clases son
   **process-global** (una sola vez por proceso), así que esa optimización es
   **irrelevante**: no hay reconstrucción de clase por conexión — el multi-DB es
   un asunto de *router* (``orm/routers.py``), no de rebuild de clases.

Por eso este archivo es un stub delgado documentado: ``ModelBase`` hace el
registro y las migraciones materializan el schema; no hay ``add_to_registry`` ni
MRO-fusion que replicar.
"""
from django.db.models import Model
from django.db.models.base import ModelBase

__all__ = ['ModelBase', 'is_model_class', 'is_model_definition']


def is_model_class(cls) -> bool:
    """``True`` si ``cls`` es una clase de modelo (subclase de ``models.Model``).
    Equivale a ``odoo.orm.model_classes.is_model_class`` — sobre ``ModelBase``."""
    return isinstance(cls, ModelBase) and issubclass(cls, Model)


def is_model_definition(cls) -> bool:
    """``True`` si ``cls`` es una definición concreta (no abstracta). Equivale a
    ``odoo.orm.model_classes.is_model_definition`` — sobre ``Model._meta``."""
    return is_model_class(cls) and not cls._meta.abstract
