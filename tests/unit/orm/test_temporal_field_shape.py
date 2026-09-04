"""Tests — por qué ``fields_temporal`` no declara clases como la fuente.

Pregunta del ejecutor: *"si en la fuente los declara como métodos de clase,
¿por qué nosotros no los declaramos igual?"*.

El **análisis ya existía** — vive en el docstring de
``src/orm/fields_temporal.py``, con sus dos mecanismos y una razón de datos —
pero **no tenía ningún control**. Estos casos lo cierran: cada uno mide una de
las afirmaciones que sostienen la decisión, de modo que si una deja de ser
cierta caiga aquí y no se descubra al reescribir el módulo.

Las tres afirmaciones, y por qué cada una carga peso:

1. **``DateTimeField`` es subclase de ``DateField``** — de ahí que todo lo que
   ``Datetime`` redefine se adjunte a las **dos**: dejar una sola heredaría el
   valor de fecha.
2. **La ruta de deconstrucción es la de Django** — es la razón *de datos* para
   no subclasificar: el autodetector de migraciones compara esa ruta, así que
   una subclase nuestra emitiría un ``AlterField`` por cada campo de fecha del
   árbol.
3. **El despachador es una función** — por eso los constructores se cuelgan en
   vez de decorarse con ``@staticmethod``: una función no admite decoradores de
   clase.

Y la contraparte que la pregunta abre: **en DRF sí se declararía con clases**,
porque los campos de DRF son nuestros para subclasificar. Los dos últimos casos
lo miden y fijan la frontera entre las dos capas.
"""
import re
import types
from datetime import date, datetime
from pathlib import Path

from django.db import models
from rest_framework import fields as drf_fields
from rest_framework import serializers

from orm import fields_temporal
from orm.fields_temporal import Date, Datetime


class TestWhyTheDjangoFieldIsNotSubclassed:
    """Las tres afirmaciones del docstring, medidas."""

    def test_datetimefield_is_a_subclass_of_datefield(self):
        """Afirmación 1 — la que obliga a adjuntar a las dos clases.

        Qué lo haría fallar: que Django rompiera esa herencia. Entonces
        adjuntar sólo a ``DateTimeField`` dejaría a ``DateField`` sin los
        métodos del protocolo, y el módulo tendría que dejar de hacerlo dos
        veces.
        """
        assert issubclass(models.DateTimeField, models.DateField)

    def test_the_deconstruction_path_is_the_one_of_django(self):
        """Afirmación 2 — la razón de datos, no de estilo.

        ``deconstruct()`` es lo que el autodetector escribe en la migración.
        Mientras la ruta sea la de Django, adjuntar métodos **no** genera
        migración; una subclase nuestra cambiaría la ruta y cada campo de fecha
        del árbol pediría un ``AlterField`` sin cambio de columna.
        """
        for field in (models.DateField(), models.DateTimeField()):
            _name, path, _args, _kwargs = field.deconstruct()
            assert path.startswith('django.db.models.'), path

    def test_the_protocol_methods_are_attached(self):
        """El mecanismo 1 del docstring, verificado sobre la clase de Django.

        No es un ``hasattr`` de adorno: estos nombres son los de la fuente, y
        que respondan sobre ``models.DateField`` es lo que sustituye a la
        herencia ``BaseDate`` → ``Field`` que allá los provee.
        """
        for name in ('expression_getter', 'property_to_sql',
                       'convert_to_column', 'convert_to_cache',
                       'convert_to_export', 'convert_to_display_name'):
            assert hasattr(models.DateField, name), name
            assert hasattr(models.DateTimeField, name), name

    def test_the_dispatcher_is_a_function_and_so_it_is_attached(self):
        """Afirmación 3 — la razón por la que no hay ``@staticmethod``.

        ``Date`` y ``Datetime`` son despachadores de ``company_dependent``, y un
        despachador es una función. Los constructores de la fuente
        (``Date.today``, ``Datetime.now``, ``Datetime.context_timestamp``) se le
        **cuelgan** como atributos para que la forma de llamada quede literal.
        """
        assert isinstance(Date, types.FunctionType)
        assert isinstance(Datetime, types.FunctionType)
        for name in ('today', 'to_date', 'from_string'):
            assert callable(getattr(Date, name)), name
        for name in ('now', 'today', 'context_timestamp', 'to_datetime'):
            assert callable(getattr(Datetime, name)), name

    def test_the_call_shape_is_the_one_of_the_source(self):
        """El criterio que las tres afirmaciones sirven: que el uso no cambie.

        La divergencia es de **declaración**, no de superficie. Este caso lo
        mide sobre el comportamiento, que es lo único que el consumidor ve.
        """
        assert isinstance(Date.today(), date)
        assert isinstance(Datetime.now(), datetime)
        converted = Datetime.context_timestamp(None, datetime(2026, 1, 2, 3, 4))
        assert converted.tzinfo is not None
        assert Date.to_date('2026-01-02') == date(2026, 1, 2)


class TestInDrfTheAnswerWouldBeTheOpposite:
    """La frontera entre las dos capas — y por qué la pregunta cambia de signo.

    Un campo del ORM convierte **contra la columna**; uno de DRF convierte
    **contra el contrato HTTP**. Son capas distintas y la restricción también:
    el campo de Django no es nuestro para subclasificar, el de DRF sí, y por eso
    ahí la forma de la fuente —clases con métodos— sería la correcta.
    """

    def test_the_drf_field_is_a_class_meant_for_subclassing(self):
        """Declara métodos de instancia sobreescribibles, no funciones sueltas.

        ``to_internal_value`` / ``to_representation`` son el par que un campo a
        medida redefine. Que existan en ``vars()`` de la clase —y no heredados—
        es lo que dice que el punto de extensión es la subclase.
        """
        own_members = set(vars(drf_fields.DateTimeField))
        assert {'to_internal_value', 'to_representation'} <= own_members
        assert issubclass(serializers.DateTimeField, drf_fields.Field)

    def test_a_drf_field_subclass_touches_no_migration(self):
        """La razón de datos del ORM no aplica en la capa de DRF.

        Un campo de serializer no se deconstruye ni entra en el estado de
        migraciones: vive en la petición. Por eso ahí la subclase es gratis y
        aquí no — misma pregunta, respuesta opuesta, y la diferencia es
        medible, no de gusto.
        """
        class UtcDateTimeField(serializers.DateTimeField):
            """Campo de prueba: fija la salida a UTC con sufijo ``Z``."""

            def to_representation(self, value):
                return super().to_representation(value).replace('+00:00', 'Z')

        assert not hasattr(UtcDateTimeField, 'deconstruct')
        assert issubclass(UtcDateTimeField, serializers.DateTimeField)

    def test_the_tree_declares_no_custom_drf_field_yet(self):
        """Cifra de estado, con su denominador declarado.

        Medido con ``grep -rn "^class \\w*(serializers\\.\\w*Field)"`` sobre
        ``src/`` y ``addons/``: **0**. No es un defecto — ningún endpoint lo ha
        necesitado — pero deja escrito que la capa está libre, de modo que el
        primero que la use no crea estar inventando un mecanismo.

        *Métrica:* subclases directas de un campo de ``serializers`` declaradas
        a nivel de módulo.
        *Ciega a:* una subclase declarada dentro de una función o de otra clase,
        y a un campo a medida que herede de ``serializers.Field`` con otro
        nombre de base. La cifra es un piso.
        """
        pattern = re.compile(r'^class \w+\(serializers\.\w*Field\)', re.M)
        found = [
            str(path) for root in ('src', 'addons')
            for path in Path(root).rglob('*.py')
            if pattern.search(path.read_text(errors='ignore'))
        ]
        assert found == [], found


class TestTheModuleDeclaresItsOwnShape:
    """El docstring es la fuente de esta decisión; que siga diciéndolo importa.

    Sin este caso, alguien podría reescribir el módulo con clases y dejar el
    docstring describiendo un mecanismo que ya no está — el defecto que
    ``porte-completo-no-parcial.md`` llama declarar la referencia en vez de
    nuestra diferencia.
    """

    def test_the_docstring_declares_both_mechanisms(self):
        # El docstring va envuelto a 79 columnas, así que las frases cruzan
        # saltos de línea: se normaliza el espacio antes de buscar. Un
        # ``in`` sobre el texto crudo falla por el envoltorio y no por el
        # contenido — medido al escribir este caso.
        doc = ' '.join(fields_temporal.__doc__.split())
        assert 'FORMA DEL PORTE' in doc
        assert 'autodetector de migraciones de Django compara la' in doc
        assert 'despachador' in doc
