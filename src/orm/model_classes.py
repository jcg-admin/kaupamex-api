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
``add_to_registry(...)``               registro automático de ``ModelBase`` en ``apps``
``setup_model_classes(env)``           import de ``models/`` + ``apps.populate()``
herencia por ``_inherit`` (misma       herencia Python normal (abstract base /
tabla, fusión de clases)               multi-table) o **FK RELATED** entre apps
                                       (DEC-SALE-01: donde Odoo usa ``_inherit``
                                       cross-app, aquí va una FK relacionada)
``add_field`` / ``pop_field``          declaración de campos en la clase +
                                       ``contribute_to_class`` de ``ModelBase``
``is_model_class`` / ``is_model_def``  ``issubclass(x, models.Model)`` /
                                       ``not x._meta.abstract``
=====================================  ==================================================

Diferencia semántica clave (ya decidida, DEC-SALE-01): Odoo fusiona clases del
mismo ``_name`` en UNA tabla; nosotros **no** reimplementamos esa fusión — la
herencia intra-app es herencia Python y la extensión cross-app es una **FK
RELATED**. Por eso no hay ``add_to_registry`` que replicar: ``ModelBase`` hace
el registro, y las migraciones materializan el schema.
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
