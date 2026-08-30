"""Objetos de tabla del ORM — porte de ``odoo/orm/table_objects.py`` (19.0).

Un **objeto de tabla** es un objeto SQL declarado en el cuerpo del modelo:
una restricción o un índice. La fuente los declara así::

    class ResPartner(models.Model):
        _name_uniq = models.Constraint('unique (name)', "El nombre es único")
        _active_idx = models.Index('(active) WHERE active IS TRUE')

El nombre del objeto **sale del atributo que lo aloja**, sin su guion bajo
inicial, y el identificador que llega a la base es ``{tabla}_{nombre}``.

Qué trae Django y qué no
========================

Django **sí** trae el motor de esquema: ``Meta.constraints`` y ``Meta.indexes``
se materializan con ``makemigrations``. Por eso ``apply_to_database`` diverge de
mecanismo — emite por el editor de esquema en vez de componer el DDL a mano
como ``sql.add_constraint``/``sql.add_index`` en la fuente.

Django **no** trae tres cosas, y son las que este archivo construye:

1. **El nombrado por atributo de clase.** ``__set_name__`` toma el nombre del
   atributo, exige su guion bajo inicial y rechaza el nombre mangleado. Medido
   en ``scripts/workbench/table-object-naming-20260830T201048``: el protocolo
   **sí** se dispara en el cuerpo de un modelo de Django.
2. **El nombre completo acotado.** ``{tabla}_{nombre}`` por ``make_identifier``,
   que recorta a los 63 caracteres de PostgreSQL con un ``crc32`` detrás.
3. **El mensaje de violación invocable.** ``get_error_message`` admite un
   invocable que recibe ``(env, diagnostics)`` y compone el texto con el
   diagnóstico real de la excepción. El ``violation_error_message`` de Django es
   una cadena fija.

Lo que este archivo reemplaza
=============================

Hasta ``api@668bdadf`` este módulo eran **tres alias** a los constructos
nativos —``Constraint = CheckConstraint``, ``UniqueIndex = UniqueConstraint``—
con firmas **incompatibles**: el nativo recibe su condición por palabra clave y
la fuente la pasa posicional, así que ``Constraint('unique (name)', 'msg')``
lanzaba ``TypeError``. Ningún test lo medía y ningún archivo lo importaba.

Divergencia declarada y medida
==============================

La fuente distingue en ``__set_name__`` la **clase de definición** de la de
registro con ``getattr(owner, 'pool', None) is None``. Aquí no hay clases de
registro —no existe el ``Registry`` de la fuente— y además ``_meta`` **aún no
existe** cuando corre el protocolo (medido en la misma sonda), así que el
registro va a ``_table_object_definitions``, una lista de clase, igual que allá.

El puente ``to_django`` es propio: convierte el objeto de tabla al constructo
nativo para que ``Meta.constraints``/``Meta.indexes`` lo materialicen. Es el
hogar que ``atributos-de-clase-de-modelo.md`` ya había fijado, ahora
construido en vez de aliasado.
"""
from django.db import connection
from django.db.models import BaseConstraint
from django.db.models import CheckConstraint  # noqa: F401  (re-exportado)
from django.db.models import Index as DjangoIndex
from django.db.models import UniqueConstraint  # noqa: F401  (re-exportado)

from tools.sql import make_identifier


class RawConstraint(BaseConstraint):
    """Una restricción declarada por SQL crudo — construida, no traída.

    Django expresa una restricción por **condición de consulta**:
    ``CheckConstraint`` exige un ``Q`` o una expresión booleana, y rechaza
    cualquier otra cosa con ``TypeError``. La fuente entrega SQL crudo, y su
    universo es más ancho que el ``CHECK``: sus ejemplos incluyen
    ``FOREIGN KEY (abc) REFERENCES some_table(id)`` y ``UNIQUE (user_id)``,
    que no son condiciones.

    Por eso el puente no puede ser un alias. Esta clase emite el fragmento con
    la plantilla del propio editor de esquema —``sql_constraint``, que es
    ``CONSTRAINT %(name)s %(constraint)s``— así que el DDL sale por el motor de
    Django y no compuesto a mano.
    """

    def __init__(self, definition, *, name, violation_error_message=None):
        self.definition = definition
        super().__init__(
            name=name, violation_error_message=violation_error_message)

    def constraint_sql(self, model, schema_editor):
        """El fragmento en línea, para el ``CREATE TABLE``."""
        return schema_editor.sql_constraint % {
            'name': schema_editor.quote_name(self.name),
            'constraint': self.definition,
        }

    def create_sql(self, model, schema_editor):
        return (
            f'ALTER TABLE {schema_editor.quote_name(model._meta.db_table)} '
            f'ADD CONSTRAINT {schema_editor.quote_name(self.name)} '
            f'{self.definition}'
        )

    def remove_sql(self, model, schema_editor):
        return schema_editor.sql_delete_constraint % {
            'table': schema_editor.quote_name(model._meta.db_table),
            'name': schema_editor.quote_name(self.name),
        }

    def validate(self, model, instance, exclude=None, using=None):
        """La base la valida; aquí no hay predicado que evaluar en Python.

        Es la misma postura de la fuente, que delega la violación al motor y
        sólo compone su mensaje al recibir el diagnóstico.
        """
        return None

    def deconstruct(self):
        path = f'{self.__class__.__module__}.{self.__class__.__qualname__}'
        return path, (self.definition,), {'name': self.name}

    def __eq__(self, other):
        if isinstance(other, RawConstraint):
            return (self.name == other.name
                    and self.definition == other.definition)
        return super().__eq__(other)

    def __hash__(self):
        return hash((self.__class__, self.name, self.definition))


class RawIndex(DjangoIndex):
    """Un índice declarado por SQL crudo — construido, no traído.

    ``models.Index`` compone su cuerpo desde nombres de campo o expresiones
    resueltas. La fuente entrega la cláusula entera —``(group_id, active)
    WHERE active IS TRUE``, ``USING btree (group_id, user_id)``—, así que el
    índice se emite tal cual, y su unicidad la declara ``unique``.
    """

    def __init__(self, definition, *, name, unique=False):
        self.definition = definition
        self.unique = unique
        # ``Index.__init__`` exige campos o expresiones; aquí el cuerpo es la
        # cláusula cruda, así que se fijan los atributos que su API expone.
        self.fields = []
        self.name = name
        self.db_tablespace = None
        self.opclasses = ()
        self.condition = None
        self.include = ()
        self.expressions = ()
        self.fields_orders = []

    def create_sql(self, model, schema_editor, using='', **kwargs):
        keyword = 'UNIQUE INDEX' if self.unique else 'INDEX'
        return (
            f'CREATE {keyword} {schema_editor.quote_name(self.name)} '
            f'ON {schema_editor.quote_name(model._meta.db_table)} '
            f'{self.definition}'
        )

    def remove_sql(self, model, schema_editor, **kwargs):
        return schema_editor.sql_delete_index % {
            'table': schema_editor.quote_name(model._meta.db_table),
            'name': schema_editor.quote_name(self.name),
        }

    def deconstruct(self):
        path = f'{self.__class__.__module__}.{self.__class__.__qualname__}'
        return path, (self.definition,), {'name': self.name, 'unique': self.unique}

    def __repr__(self):
        return f'<{self.__class__.__name__}: name={self.name!r}>'


class TableObject:
    """≙ ``TableObject`` (``odoo19c: odoo/orm/table_objects.py:26-76``).

    Docstring de la fuente, verbatim: *"Declares a SQL object related to the
    model. The identifier of the SQL object will be ``{model._table}_{name}``"*.
    """

    name: str
    message = ''
    _module: str = ''

    def __init__(self):
        """Objeto SQL abstracto."""
        # Para no confundirlos: ``name`` es único dentro del modelo,
        # ``full_name`` lo es dentro de la base.
        self.name = ''

    def __set_name__(self, owner, name):
        """Toma el nombre del atributo de clase que aloja al objeto.

        La fuente exige el guion bajo inicial por dos razones que declara
        verbatim: *"you should not need to access them from any model"* y
        *"this avoid having them in the middle of the fields when listing
        members"*.
        """
        assert name.startswith('_'), (
            "El nombre de un objeto SQL en un modelo empieza con guion bajo")
        assert not name.startswith(f'_{owner.__name__}__'), (
            "El nombre de un objeto SQL no puede venir mangleado")
        self.name = name[1:]
        # La fuente discrimina aquí la clase de definición de la de registro
        # con ``getattr(owner, 'pool', None) is None``. Aquí no hay clases de
        # registro, y ``_meta`` aún no existe en este instante — medido.
        if '_table_object_definitions' not in owner.__dict__:
            owner._table_object_definitions = []
        owner._table_object_definitions.append(self)

    def get_definition(self, registry) -> str:
        """La definición SQL del objeto. La declara cada subclase."""
        raise NotImplementedError

    def full_name(self, model) -> str:
        """≙ ``full_name`` (``odoo19c: :55-58``) — ``{tabla}_{nombre}``."""
        assert self.name, (
            f"El objeto de tabla no está nombrado ({self.get_definition(None)})")
        return make_identifier(f'{_table_of(model)}_{self.name}')

    def get_error_message(self, model, diagnostics=None) -> str:
        """≙ ``get_error_message`` (``odoo19c: :60-69``).

        Docstring de la fuente, verbatim: *"Build an error message for the
        object/constraint"*.

        :param model: el modelo sobre el que se declara la restricción.
        :param diagnostics: el diagnóstico de la excepción, si lo hay.
        :returns: el error ya traducido, para el usuario.
        """
        message = self.message
        if callable(message):
            return message(model.env, diagnostics)
        return message

    def apply_to_database(self, model):
        """Materializa el objeto en el esquema. La declara cada subclase."""
        raise NotImplementedError

    def to_django(self, model):
        """El puente al constructo nativo — propio, no de la fuente.

        Django es el motor de esquema aquí, así que el objeto de tabla se
        entrega convertido para que ``Meta.constraints``/``Meta.indexes`` lo
        materialicen con ``makemigrations``.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        return f"({self.name!r}={self.get_definition(None)!r}, {self.message!r})"


def _table_of(model) -> str:
    """El nombre de tabla del modelo, por cualquiera de sus dos vocabularios.

    La fuente lee ``model._table``; aquí el canónico es ``_meta.db_table``, y
    ``_table`` convive con él por el porte de los atributos de clase.
    """
    table = getattr(model, '_table', None)
    if table:
        return table
    return model._meta.db_table


class Constraint(TableObject):
    """≙ ``Constraint`` (``odoo19c: :79-122``).

    Docstring de la fuente, verbatim: *"SQL table constraint. The definition of
    the constraint is used to ``ADD CONSTRAINT`` on the table"*.
    """

    def __init__(self, definition: str, message='') -> None:
        """Restricción de tabla en SQL.

        Docstring de la fuente, verbatim: *"The definition is the SQL that will
        be used to add the constraint. If the constraint is violated, we will
        show the message to the user or an empty string to get a default
        message"*.

        Ejemplos de definición que la fuente cita:

        - ``CHECK (x > 0)``
        - ``FOREIGN KEY (abc) REFERENCES some_table(id)``
        - ``UNIQUE (user_id)``
        """
        super().__init__()
        self._definition = definition
        if message:
            self.message = message

    def get_definition(self, registry):
        return self._definition

    def apply_to_database(self, model):
        """Materializa la restricción por el editor de esquema de Django.

        **Divergencia de mecanismo declarada.** La fuente compone el DDL con
        ``sql.constraint_definition``/``sql.add_constraint`` y lo aplaza con
        ``pool.post_constraint``. Aquí el editor de esquema de Django hace las
        dos cosas: sabe si la restricción ya existe y emite el ``ALTER TABLE``.
        """
        with connection.schema_editor() as editor:
            editor.add_constraint(type(model), self.to_django(model))

    def to_django(self, model):
        """El constructo nativo: una ``RawConstraint`` con su nombre completo."""
        return RawConstraint(
            self._definition,
            name=self.full_name(model),
            violation_error_message=self.message if isinstance(
                self.message, str) and self.message else None,
        )


class Index(TableObject):
    """≙ ``Index`` (``odoo19c: :125-182``).

    Docstring de la fuente, verbatim: *"Index on the table.
    ``CREATE INDEX ... ON model_table <your definition>``"*.
    """

    unique: bool = False

    def __init__(self, definition):
        """Índice en SQL.

        Docstring de la fuente, verbatim: *"The name of the SQL object will be
        ``{model._table}_{key}``. The definition is the SQL that will be used to
        create the constraint"*.

        Ejemplos de definición que la fuente cita:

        - ``(group_id, active) WHERE active IS TRUE``
        - ``USING btree (group_id, user_id)``

        La definición puede ser un invocable que recibe el registro: hay
        índices cuya forma depende de qué módulos estén instalados.
        """
        super().__init__()
        self._index_definition = definition

    def get_definition(self, registry):
        if callable(self._index_definition):
            definition = self._index_definition(registry)
        else:
            definition = self._index_definition
        if not definition:
            return ''
        return f"{'UNIQUE ' if self.unique else ''}INDEX {definition}"

    def apply_to_database(self, model):
        """Materializa el índice por el editor de esquema de Django.

        **Divergencia de mecanismo declarada**, misma que en ``Constraint``.
        Un índice con definición vacía no se crea — la fuente lo dice verbatim:
        *"Don't create index with an empty definition"*.
        """
        if not self.get_definition(None):
            return
        with connection.schema_editor() as editor:
            editor.add_index(type(model), self.to_django(model))

    def to_django(self, model):
        """El constructo nativo: un ``RawIndex`` con su nombre completo."""
        return RawIndex(
            self._raw_definition(),
            name=self.full_name(model),
            unique=self.unique,
        )

    def _raw_definition(self) -> str:
        """La definición sin la palabra clave ``INDEX`` que la envuelve."""
        if callable(self._index_definition):
            return self._index_definition(None) or ''
        return self._index_definition or ''


class UniqueIndex(Index):
    """≙ ``UniqueIndex`` (``odoo19c: :185-205``).

    Docstring de la fuente, verbatim: *"Unique index on the table.
    ``CREATE UNIQUE INDEX ... ON model_table <your definition>``"*.
    """

    unique = True

    def __init__(self, definition, message=''):
        """Índice único en SQL.

        Docstring de la fuente, verbatim: *"You can also specify a message to be
        used when constraint is violated"*.
        """
        super().__init__(definition)
        if message:
            self.message = message

    # ``to_django`` se hereda de ``Index``: un índice único sigue siendo un
    # ``CREATE UNIQUE INDEX``, que es lo que la fuente emite. Su ``unique``
    # de clase decide la palabra clave.


__all__ = [
    'BaseConstraint',
    'CheckConstraint',
    'Constraint',
    'Index',
    'RawConstraint',
    'RawIndex',
    'TableObject',
    'UniqueConstraint',
    'UniqueIndex',
]
