"""Campos dispersos — ≙ ``addons/base_sparse_field`` de la referencia.

Un campo **disperso** (*sparse*) es casi siempre nulo. En vez de gastar una
columna por cada uno, su valor vive dentro de un único campo **serializado**
que los agrupa a todos en un mapa JSON. La referencia lo declara así
(``odoo19c: base_sparse_field/models/models.py:79-87``)::

    data     = fields.Serialized()
    boolean  = fields.Boolean(sparse='data')
    integer  = fields.Integer(sparse='data')
    partner  = fields.Many2one('res.partner', sparse='data')

El motivo que da su manifiesto es el límite de PostgreSQL al número de
columnas de una tabla; el efecto secundario —y el que más se usa— es poder
añadir atributos a un modelo sin migración.

Qué hace la referencia, y qué se hizo aquí
===========================================

La referencia **parchea su propia clase base** ``fields.Field`` con un
decorador ``monkey_patch`` (``models/fields.py:9-16``): añade el atributo
``sparse``, y engancha ``_get_attrs`` para que un campo con ``sparse=``
quede ``store=False`` + ``copy=False`` + ``compute=_compute_sparse`` +
``inverse=_inverse_sparse``.

Aquí **no se parchea**, y la razón es medida, no una costumbre: en este
puerto ``fields.Char`` **es** ``django.db.models.CharField``
(``orm/fields_textual.py``), así que la clase base equivalente es
``models.Field`` — del framework, no nuestra. Parchearla alcanzaría al
admin, a las migraciones y a DRF, que no son consumidores de este
mecanismo. La diferencia no es "no se puede": es que el radio de la misma
técnica no es el mismo.

Medido antes de decidir::

    models.CharField(max_length=10, sparse='data')
    -> TypeError: Field.__init__() got an unexpected keyword argument 'sparse'

Lo que sí conserva la conducta: un campo disperso es, por definición de la
referencia, un campo **sin columna** (``store=False``) cuyo valor se calcula
al leerlo y se escribe al asignarlo. Eso es exactamente el descriptor que
este puerto ya construyó en ``orm/fields_nonstored.py``; ``Sparse`` es ese
mismo mecanismo con el respaldo puesto en el campo serializado hermano en
vez de en ``instance.__dict__``.

Cómo se declara aquí
=====================

::

    from orm import fields

    class SparseFieldsTest(models.Model):
        data    = fields.Serialized()
        boolean = fields.Sparse('data')
        integer = fields.Sparse('data', coerce=int)
        partner = fields.Sparse('data', relational_model='base.ResPartner')

El tipo viaja en ``coerce``/``relational_model`` en vez de en el nombre de
la clase, porque el valor ya llega tipado desde el JSON: un ``bool`` de la
referencia sale ``bool`` de ``jsonb`` sin conversión. ``coerce`` está para
los casos en que el JSON no distingue —``int`` frente a ``float``— y para
``Decimal``, que JSON no tiene.

Qué NO es
==========

- **No es un campo de Django.** No aparece en ``_meta.get_fields()``, no
  genera migración y no se puede filtrar con ``.filter(campo=…)``. Para
  consultar por él se consulta el JSON hermano
  (``.filter(data__boolean=True)``), que en PostgreSQL es indexable con GIN.
- **No es un ``JSONField`` con azúcar.** ``Serialized`` sí lo es; ``Sparse``
  es el descriptor que da a una clave del mapa la apariencia de un campo.

Diferencia de almacenamiento respecto de la referencia
=======================================================

La referencia declara ``column_type = ('text', 'text')`` y serializa a mano
con ``json.dumps``/``json.loads`` (``models/fields.py:88-101``), porque su
capa soporta varios motores. Este proyecto es PostgreSQL-only (ADR-028), así
que ``Serialized`` es un ``JSONField`` sobre ``jsonb`` nativo: el mapa se
guarda estructurado, no como texto. Los tres métodos de conversión de la
referencia —``convert_to_column_insert``, ``convert_to_cache``,
``convert_to_record``— quedan cubiertos por el propio ``JSONField``, que ya
entrega un ``dict`` al leer y acepta un ``dict`` al escribir.
"""
import copy

from django.db import models

__all__ = ['Serialized', 'Sparse']


class Serialized(models.JSONField):
    """Almacén de los campos dispersos de un modelo — ≙ ``fields.Serialized``.

    Un ``JSONField`` cuyo default es un mapa vacío, para que un registro
    recién creado tenga siempre dónde escribir sin comprobar ``None`` en cada
    asignación. La referencia obtiene lo mismo con
    ``convert_to_record: json.loads(value or "{}")``.

    ``prefetch = False`` de la referencia no tiene equivalente: aquí no hay
    prefetch por campo, la fila trae sus columnas completas.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', dict)
        kwargs.setdefault('blank', True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Omite del migration los defaults que este campo fija por sí mismo."""
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get('default') is dict:
            del kwargs['default']
        if kwargs.get('blank') is True:
            del kwargs['blank']
        return name, path, args, kwargs


class Sparse:
    """Un campo cuyo valor vive dentro del ``Serialized`` que se le nombra.

    Sigue el protocolo ``contribute_to_class`` de Django por la misma razón
    que ``NonStored``: el atributo llega al modelo por dos caminos —el cuerpo
    de la clase, que recorre ``ModelBase``, y ``add_to_class``, que usan las
    extensiones ``_inherit`` de este puerto— y sólo el segundo dejaría el
    descriptor sin saber su propio nombre.
    """

    def __init__(self, sparse, *, default=None, coerce=None,
                 relational_model=None, help_text=''):
        if not sparse:
            raise ValueError('Sparse requiere el nombre del campo serializado')
        self.sparse = sparse
        self.default = default
        self.coerce = coerce
        self.relational_model = relational_model
        self.help_text = help_text
        self.name = None

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase cuando el dueño no es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class``.

        No se registra nada en ``_meta``: ése es el punto — el campo no tiene
        columna, igual que el ``store=False`` que la referencia le impone en
        ``_get_attrs``.
        """
        self.name = name
        setattr(cls, name, self)

    # -- protocolo de descriptor -------------------------------------------

    def __get__(self, instance, owner=None):
        """≙ ``_compute_sparse``: lee el mapa y saca la clave de este campo."""
        if instance is None:
            return self
        values = self._container(instance)
        if self.name not in values:
            return self.default
        value = values[self.name]
        if value is not None and self.relational_model is not None:
            return self._resolve_relational(instance, value)
        if value is not None and self.coerce is not None:
            return self.coerce(value)
        return value

    def __set__(self, instance, value):
        """≙ ``_inverse_sparse``: escribe la clave, o la retira si es falsy.

        La referencia distingue los dos casos explícitamente: si el valor es
        verdadero y difiere del guardado lo asigna; si es falso y la clave
        existe, la **retira** del mapa en vez de guardar el falso. Se conserva
        esa asimetría — es lo que mantiene el mapa disperso de verdad.
        """
        values = self._container(instance)
        stored = self._to_stored(value)
        if stored:
            if values.get(self.name) != stored:
                values[self.name] = stored
                self._write_container(instance, values)
        elif self.name in values:
            values.pop(self.name)
            self._write_container(instance, values)

    def __delete__(self, instance):
        values = self._container(instance)
        if self.name in values:
            values.pop(self.name)
            self._write_container(instance, values)

    # -- acceso al campo serializado hermano -------------------------------

    def _container(self, instance):
        """El mapa del campo serializado, siempre un ``dict`` manipulable.

        Se devuelve una **copia**: mutar el ``dict`` que Django tiene en la
        instancia haría que el propio Django no viera el cambio como sucio, y
        la escritura se perdería en `save(update_fields=…)`. La referencia no
        tiene el problema porque su asignación pasa por el ORM.
        """
        raw = getattr(instance, self.sparse, None)
        if not isinstance(raw, dict):
            return {}
        return copy.copy(raw)

    def _write_container(self, instance, values):
        setattr(instance, self.sparse, values)

    def _to_stored(self, value):
        """Reduce el valor a lo que se guarda en el mapa.

        ≙ ``convert_to_read(..., use_display_name=False)`` de la referencia,
        que para un relacional guarda el id, no el registro.
        """
        if value is None:
            return None
        if self.relational_model is not None:
            return getattr(value, 'pk', value)
        return value

    def _resolve_relational(self, instance, value):
        """≙ el ``record[self.name].exists()`` del compute de la referencia.

        Un id guardado puede apuntar a una fila ya borrada; la referencia lo
        resuelve filtrando por ``exists()``. Aquí devuelve ``None`` en ese
        caso, que es la misma promesa: nunca se entrega un registro muerto.
        """
        model = instance._meta.apps.get_model(self.relational_model)
        return model.objects.filter(pk=value).first()
