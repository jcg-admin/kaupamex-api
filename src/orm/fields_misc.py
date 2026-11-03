"""Campos misceláneos — fiel a ``odoo/orm/fields_misc.py`` (Odoo 19).

``Boolean``, ``Json`` (Odoo ``Id`` es el pk implícito: en Django lo provee
``AutoField``/``BigAutoField`` automático, no se declara).

``Boolean`` es un **despachador** de ``company_dependent`` (tarea #129), no un
alias pelado: el tipo está en ``COMPANY_DEPENDENT_FIELDS`` y tiene cuatro
consumidores en la referencia — ``account/models/partner.py:573-574``
(``ignore_abnormal_invoice_date`` / ``_amount``),
``purchase/models/res_partner.py:41`` (``receipt_reminder_email``) y
``sale_purchase/models/product_template.py:11`` (``service_to_purchase``).

``Json`` **no** lo lleva: ``json`` no está en la lista cerrada de tipos de la
fuente (``odoo19c: odoo/orm/fields.py:42-44``), y además un campo por empresa
YA es un ``jsonb`` — anidarlo no tendría dónde poner el mapa de empresas.
"""

import json
from copy import deepcopy
from functools import partial

from django.db import models

from orm.fields_company_dependent import make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)
from tools.json import json_default

__all__ = ['Boolean', 'Json']

Boolean = make_dispatcher('Boolean', 'boolean', models.BooleanField)


def Json(*args, store=_UNSET, related=None, **kwargs):
    """``fields.Json`` — el ``JSONField`` de Django, con y sin columna.

    Era un alias pelado (``Json = models.JSONField``) y pasa a ser despachador
    por un solo motivo medido: la referencia declara ``fields.Json(related=…)``
    y el alias no tenía dónde recibir la clave — el conteo lo publica
    ``python3 scripts/census_related_fields.py``.

    **No usa** :func:`~orm.fields_company_dependent.make_dispatcher`, que es
    el camino de los otros: su fábrica valida el tipo base contra los diez que
    la referencia declara ``company_dependent``, y ``json`` no está entre
    ellos. Forzarlo ahí habría exigido ensanchar esa lista para un caso que la
    fuente no tiene, que es construir de más.

    Nadie hace ``isinstance(campo, fields.Json)`` en este árbol —medido—, así
    que ser función no rompe ninguna identidad de tipo. Si algún día hiciera
    falta, la salida es un ``__new__`` como el de ``Html``.
    """
    if store is not _UNSET:
        kwargs['store'] = store
    # TASK-API-0420: la fuente copia el JSON al entregarlo al registro
    # (Json.convert_to_record). Django evalúa un default invocable por
    # instancia; partial conserva el literal y es serializable en migraciones.
    default = kwargs.get('default')
    if default is not None and not callable(default):
        kwargs['default'] = partial(deepcopy, default)
    #: La columna ``jsonb`` de la fuente admite ``NULL`` (``Json`` no declara
    #: ``required``), y ``convert_to_cache`` guarda ahí todo valor falso.
    #: Sin ``null=`` Django la crearía ``NOT NULL``.
    if 'null' not in kwargs:
        kwargs['null'] = True
        kwargs.setdefault('blank', True)
    related_attrs = apply_source_defaults(related, kwargs)
    #: El tipo se construye SIEMPRE, con columna o sin ella: ``store`` es un
    #: atributo del campo, no una clase distinta
    #: (``odoo19c: odoo/orm/fields.py:455``). La forma sin columna la resuelve
    #: la costura —``contribute_to_class`` con ``private_only``— no el
    #: enrutado de esta fachada.
    field = models.JSONField(*args, **kwargs)
    return annotate_related(field, related, related_attrs)


def _boolean_convert_to_column(
    self, value, record, values=None, validate=True
):
    """
    ``Boolean.convert_to_column`` — ≙ ``odoo19c:
    odoo/orm/fields_misc.py:28-29``.

    ``bool(value)`` y no la rama de la base: es el ÚNICO tipo para el que
    ``False`` es un valor y no la ausencia de valor. Sin esta sobrecarga, la
    base lo traduciría a ``NULL`` y una columna booleana perdería la mitad de
    su dominio.
    """
    return bool(value)


models.BooleanField.convert_to_column = _boolean_convert_to_column


def _json_convert_to_column(self, value, record, values=None, validate=True):
    """``Json.convert_to_column`` — ≙ ``:76-81``.

    **Divergencia de mecanismo declarada:** la fuente envuelve el valor en el
    adaptador ``PsycopgJson`` porque su cursor recibe el parámetro crudo. Aquí
    ese envoltorio lo pone el stack — ``JSONField.get_prep_value`` de Django
    serializa con el codificador del campo—, así que el cuerpo entrega el valor
    ya normalizado y deja el adaptado a quien lo trae hecho. Lo que sí se porta
    es la forma: validar primero y descartar el ``None`` después.
    """
    if validate:
        value = self.convert_to_cache(value, record)
    if value is None:
        return None
    return value


models.JSONField.convert_to_column = _json_convert_to_column


def _json_convert_to_cache(self, value, record, validate=True):
    """``Json.convert_to_cache`` — ≙ ``odoo19c: odoo/orm/fields_misc.py:70-73``.

    La caché guarda la forma JSON del valor: la ida y vuelta por ``json``
    convierte una tupla en lista y separa el valor de cualquier referencia que
    conserve quien lo asignó.

    Todo valor falso se guarda como ``None``, como en la fuente, en una
    columna que admite ``NULL`` —la de todo ``fields.Json``, que lo es por
    defecto—. **Divergencia declarada, acotada:** en una columna ``NOT NULL``
    (un ``models.JSONField`` con el vocabulario de Django, o un ``Json`` con
    ``null=False``) el falso se conserva, porque ``NULL`` fallaría al volcar.

    Serializa con ``tools.json.json_default``, como la fuente: un instante
    sale como ``Datetime.to_string``, una fecha como ``Date.to_string`` y un
    ``Domain`` como su lista.
    """
    if not value:
        return None if self.null else value
    return json.loads(json.dumps(value, ensure_ascii=False,
                                 default=json_default))


def _json_convert_to_record(self, value, record):
    """``Json.convert_to_record`` — ≙ ``:66-68``: el registro recibe una copia.

    La fuente documenta que ``Json`` no admite mutar el valor leído; la copia
    profunda es lo que hace cierta esa frase, porque modificar lo devuelto no
    toca la caché ni la fila.
    """
    return False if value is None else deepcopy(value)


models.JSONField.convert_to_cache = _json_convert_to_cache
models.JSONField.convert_to_record = _json_convert_to_record


_DJANGO_JSON_PRE_SAVE = models.JSONField.pre_save


def _json_pre_save(self, model_instance, add):
    """Lo que se vuelca es el valor del almacén de la fila, no el del registro.

    ``Field.pre_save`` de Django lee el atributo, y para un ``Json`` el
    atributo es ``convert_to_record``: un ``NULL`` llega al registro como
    ``False`` (``odoo19c: odoo/orm/fields_misc.py:66-68``). Volcar esa lectura
    escribiría el JSON ``false`` donde la fuente deja ``NULL``. Sin valor en
    el almacén se vuelve al camino de Django.
    """
    if self.attname in model_instance.__dict__:
        return model_instance.__dict__[self.attname]
    return _DJANGO_JSON_PRE_SAVE(self, model_instance, add)


models.JSONField.pre_save = _json_pre_save


def _id_convert_to_column(self, value, record, values=None, validate=True):
    """``Id.convert_to_column`` — ≙ ``:119-120``.

    ``return value``, sin traducir nada. El identificador no tiene vocabulario
    de ausencia: o hay fila o no la hay. Hace falta declararlo porque
    ``AutoField`` hereda de ``IntegerField``, y sin esta sobrecarga el
    ``int(value or 0)`` de aquél convertiría el ``None`` de una fila en vuelo
    en un ``0`` — un identificador que no existe.
    """
    return value


models.AutoField.convert_to_column = _id_convert_to_column
models.BigAutoField.convert_to_column = _id_convert_to_column
models.SmallAutoField.convert_to_column = _id_convert_to_column
