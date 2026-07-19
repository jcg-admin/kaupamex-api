"""Alias de tipos del ORM — fiel a ``odoo/orm/types.py`` (Odoo 19).

Módulo de *typing* puro (sin lógica de motor): expone los alias que el ORM de
Odoo usa en anotaciones. Se portan fieles, apuntando a nuestras piezas
(``NewId`` de ``orm/identifiers``, ``Model`` de ``orm/models`` sobre Django).
``DomainType`` admite tanto un ``Q`` de Django (nuestro dominio, ≙
``orm/domains.py``) como la lista de tuplas estilo Odoo, para que las
anotaciones de un addon portado sigan compilando.
"""
import typing
from collections.abc import Mapping

from django.db.models import Model as _DjangoModel
from django.db.models import Q as _Q

from orm.identifiers import IdType, NewId  # noqa: F401  (re-export)

# Un dominio: nuestro ``Q`` de Django (≙ orm/domains) o la lista estilo Odoo.
DomainType = _Q | list[str | tuple[str, str, typing.Any]]
# Contexto de ejecución (env.context) — mapping de solo lectura.
ContextType = Mapping[str, typing.Any]
# Valores para create()/write() — dict campo→valor.
ValuesType = dict[str, typing.Any]
# TypeVar acotado al modelo base (Django Model ≙ Odoo BaseModel).
ModelType = typing.TypeVar("ModelType", bound=_DjangoModel)

try:
    from typing import Self  # noqa: F401  (re-export; Python 3.11+)
except ImportError:  # pragma: no cover
    Self = typing.TypeVar("Self")  # type: ignore
