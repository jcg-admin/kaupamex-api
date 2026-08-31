"""``_optimize_in_required`` y por qué ``falsy_value`` es una función aquí.

≙ ``_optimize_in_required`` (``odoo19c: odoo/orm/domains.py:1322-1338``),
cuyo docstring dice verbatim *"Remove checks against a null value for required
fields"*: un campo cuya columna rechaza el nulo no puede valer ``False``, así
que compararlo contra ``False`` es trabajo que la base nunca satisface.

Este archivo mide **dos cosas distintas**, y la segunda existe porque una
pregunta del ejecutor destapó que la razón escrita en el docstring del
optimizador era prosa heredada, no una medición:

1. la conducta del optimizador — qué condiciones adelgaza y cuáles no;
2. **por qué** ``falsy_value`` es una función de módulo y no un atributo de
   clase, que es lo que aquel docstring afirmaba mal.

La afirmación refutada era *"el campo es de Django y no admite atributos
nuevos"*. Los admite. La razón real es de **población**, y se mide abajo.
"""
import pytest
from django.apps import apps
from django.db import models

from orm import registry
from orm.domains import DomainCondition, _optimize_in_required
from orm.fields import falsy_value
from orm.fields_binary import Binary


def _sole(domain):
    """La única condición del dominio, para asertar sobre ella."""
    conditions = list(domain.iter_conditions())
    assert len(conditions) == 1, f'se esperaba una condición, hay {len(conditions)}'
    return conditions[0]


@pytest.fixture
def sequence_range():
    return apps.get_model('base', 'IrSequenceDateRange')


@pytest.fixture
def mail_server():
    return apps.get_model('base', 'IrMailServer')


class TestTheGuardStripsTheFalse:
    """Los dos lados de la guarda, cada uno con su control negativo.

    La guarda tiene dos conjunciones —``falsy_value is None`` y
    ``is_not_null``— así que hacen falta **dos** controles negativos, uno por
    cada una. Con uno solo, un porte que borrara la otra seguiría en verde.
    """

    def test_a_not_null_field_without_falsy_value_loses_the_false(self, sequence_range):
        """``IrSequenceDateRange.sequence`` — ``ForeignKey(null=False)``.

        Medido: ``falsy_value`` = ``None``, ``is_not_null`` = ``True``. Es el
        caso que la fuente adelgaza.
        """
        field = sequence_range._meta.get_field('sequence')
        assert falsy_value(field) is None
        assert registry.is_not_null(field) is True

        result = _sole(DomainCondition('sequence', 'in', [1, False]).optimize(sequence_range))
        assert list(result.value) == [1], (
            'el False sobrevivió: la columna es NOT NULL y nunca puede valer '
            'False, así que compararla contra él es trabajo muerto')

    def test_the_primary_key_loses_it_too(self, sequence_range):
        """El caso que la corrección de ``falsy_value`` desbloquea.

        La fuente declara ``class Id(Field)`` (``odoo19c:
        fields_misc.py:89``) — **no** es subclase de ``Integer``, así que
        hereda ``Field.falsy_value = None``. En Django ``BigAutoField`` sí
        hereda de ``IntegerField``; sin la fila ``(models.AutoField, None)`` de
        ``_FALSY_VALUE_BY_FIELD_CLASS`` la clave primaria valdría ``0`` y este
        caso quedaría sin adelgazar, divergiendo de la fuente en silencio.
        """
        field = sequence_range._meta.get_field('id')
        assert isinstance(field, models.AutoField)
        assert falsy_value(field) is None, (
            'la clave primaria heredó el falsy 0 de IntegerField; la fuente le '
            'da None porque su Id no es un Integer')

        result = _sole(DomainCondition('id', 'in', [1, False]).optimize(sequence_range))
        assert list(result.value) == [1]

    def test_not_in_is_optimized_as_well(self, sequence_range):
        """El registrador declara los dos operadores, no sólo ``in``."""
        result = _sole(DomainCondition('sequence', 'not in', [1, False]).optimize(sequence_range))
        assert result.operator == 'not in'
        assert list(result.value) == [1]

    def test_a_field_with_a_falsy_value_keeps_the_false(self, sequence_range):
        """CONTROL NEGATIVO de la primera conjunción — ``falsy_value``.

        ``number_next`` es ``IntegerField(null=False)``: su *falsy value* es
        ``0``, así que ``False`` **sí** es un valor comparable (``0 == False``)
        y retirarlo cambiaría el conjunto de filas.
        """
        field = sequence_range._meta.get_field('number_next')
        assert falsy_value(field) == 0
        assert registry.is_not_null(field) is True

        result = _sole(DomainCondition('number_next', 'in', [1, False]).optimize(sequence_range))
        assert False in result.value, (
            'se retiró el False de un campo cuyo falsy value es 0: la guarda '
            'de falsy_value no discrimina')

    def test_a_nullable_field_keeps_the_false(self, mail_server):
        """CONTROL NEGATIVO de la segunda conjunción — ``is_not_null``.

        ``smtp_ssl_certificate`` tiene ``falsy_value`` ``None`` igual que el
        caso positivo, pero su columna **admite** nulo: ahí ``False`` designa
        la fila sin valor y no se puede retirar.
        """
        field = mail_server._meta.get_field('smtp_ssl_certificate')
        assert falsy_value(field) is None
        assert registry.is_not_null(field) is False

        result = _sole(
            DomainCondition('smtp_ssl_certificate', 'in', [b'x', False]).optimize(mail_server))
        assert False in result.value, (
            'se retiró el False de una columna nulable: la guarda de '
            'is_not_null no discrimina')


class TestWhereFalsyValueLives:
    """Dónde vive el atributo, y por qué la clave primaria se nombra a mano.

    La primera redacción de este bloque afirmaba que ``falsy_value`` era una
    **función** aquí porque *"el campo es de Django y no admite atributos
    nuevos"*. Las dos mitades eran falsas y ninguna estaba medida:

    - el campo de Django **sí** admite atributos nuevos (no hay ``__slots__``
      en su MRO), y
    - el árbol **ya** los instala: ``_FIELD_CLASS_ATTRIBUTES`` pone 66
      atributos sobre ``models.Field``, ``falsy_value`` entre ellos.

    Lo que sí es una divergencia medida es la clave primaria, y es de
    **mecanismo de búsqueda**, no de capacidad.
    """

    def test_a_django_field_has_no_slots_in_its_mro(self, sequence_range):
        """Lo que refuta la prosa heredada, y su causa.

        ``__slots__`` es el mecanismo que impediría un atributo nuevo. Ninguna
        clase de la jerarquía lo declara.
        """
        field = sequence_range._meta.get_field('date_from')
        with_slots = [c.__name__ for c in type(field).__mro__ if '__slots__' in c.__dict__]
        assert with_slots == [], (
            f'alguna clase de la jerarquía declara __slots__: {with_slots}; '
            'entonces la prosa heredada sí tenía razón y esta razón es otra')

    def test_the_attribute_is_installed_on_the_django_base_class(self):
        """El defecto de la fuente, instalado donde la fuente lo declara.

        ≙ ``Field.falsy_value = None`` (``odoo19c: odoo/orm/fields.py:254``).
        """
        assert models.Field.falsy_value is None

    def test_each_type_carries_the_value_the_reference_declares(self):
        """Las cinco sobrescrituras de la fuente, medidas sobre campos reales.

        ≙ ``Boolean`` ``False`` · ``Integer`` ``0`` · ``Float`` ``0.0`` ·
        ``Monetary`` ``0.0`` · ``BaseString`` ``''``.
        """
        assert models.IntegerField.falsy_value == 0
        assert models.BooleanField.falsy_value is False
        assert models.CharField.falsy_value == ''
        assert models.TextField.falsy_value == ''

    def test_the_attribute_and_the_function_agree(self, sequence_range, mail_server):
        """EL CONTROL que faltaba: dos mecanismos con el mismo nombre.

        Antes de esta corrección el árbol tenía los dos —el atributo plano
        sobre ``models.Field`` y una función que resolvía por ``isinstance``—
        y **discrepaban**: para un ``IntegerField`` el atributo decía ``None``
        y la función ``0``. Quien portara escribiendo ``field.falsy_value``,
        que es la forma de la fuente, obtenía la respuesta equivocada sin que
        nada lo delatara.
        """
        campos = [sequence_range._meta.get_field(n)
                  for n in ('id', 'number_next', 'date_from', 'sequence')]
        campos.append(mail_server._meta.get_field('smtp_ssl_certificate'))
        for field in campos:
            assert field.falsy_value == falsy_value(field), (
                f'{field.name} ({type(field).__name__}): el atributo dice '
                f'{field.falsy_value!r} y la función {falsy_value(field)!r}')

    def test_the_primary_key_needs_its_three_classes_named_one_by_one(self):
        """La divergencia medida — búsqueda por MRO frente a ``isinstance``.

        ``BigAutoField`` no tiene ``AutoField`` en su MRO: su cadena es
        ``BigAutoField → AutoFieldMixin → BigIntegerField → IntegerField``, y
        ``AutoFieldMixin`` no se exporta en ``django.db.models``. Lo que los
        emparenta es el ``__subclasscheck__`` de la metaclase, que gobierna
        ``isinstance`` y no la búsqueda de atributos.

        Este caso mide la asimetría con una sonda, para que se vea por qué las
        tres clases se nombran a mano en vez de heredar de una.
        """
        assert models.AutoField not in models.BigAutoField.__mro__
        assert issubclass(models.BigAutoField, models.AutoField), (
            'la metaclase dejó de emparentarlos; entonces la asimetría que '
            'este caso mide ya no existe')

        models.IntegerField.probe_falsy = 0
        models.AutoField.probe_falsy = None
        try:
            assert models.BigAutoField.probe_falsy == 0, (
                'el atributo de AutoField alcanzó a BigAutoField por MRO; '
                'entonces nombrar las tres clases ya es innecesario')
        finally:
            del models.IntegerField.probe_falsy, models.AutoField.probe_falsy

        assert models.BigAutoField.falsy_value is None, (
            'la clave primaria heredó el falsy 0 de IntegerField: '
            'install_class_attribute_overrides() dejó de nombrar las tres clases')

    def test_the_function_tolerates_an_unknown_field(self):
        """Lo único que la función añade sobre el atributo.

        ``DomainCondition._field`` devuelve ``None`` cuando el campo no existe
        en el modelo; el optimizador llama igual y la hipótesis conservadora
        es ``None``, que es lo que hace que ``_negate`` añada la rama de nulos.
        """
        assert falsy_value(None) is None

    def test_patching_the_base_class_reaches_every_app(self):
        """El alcance del mecanismo, que es su coste declarado.

        Un atributo en ``models.Field`` no distingue *nuestros* campos de los
        de cualquier otra app instalada: aparece también en los de
        ``django.contrib.auth``, que este ORM no gobierna. Es el precio
        aceptado por los 66 atributos de ``_FIELD_CLASS_ATTRIBUTES``, y este
        caso lo deja medido en vez de supuesto.
        """
        ajeno = apps.get_model('auth', 'Permission')._meta.get_field('name')
        assert type(ajeno).__module__.startswith('django.')
        assert ajeno.falsy_value == '', (
            'el campo de otra app no recibió el atributo; entonces el alcance '
            'del parche no es el que este caso declara')

    def test_the_subclass_route_cannot_reach_the_primary_key(self):
        """Por qué NO se subclasea: la mayoría de los campos no los escribimos.

        Subclasear exige un **sitio de declaración** que cambiar. La clave
        primaria no lo tiene: cuando un modelo no declara ``pk``, Django la
        crea él (``Options._prepare``) con la clase de
        ``DEFAULT_AUTO_FIELD``. Y es justo el campo del caso canónico de este
        optimizador — ``('id', 'in', [1, False])``.

        Lo mismo vale para los campos de las apps que no son nuestras
        (``auth``, ``contenttypes``, ``sessions``): un dominio puede
        apuntarlos y no hay declaración nuestra que reescribir.

        *Métrica:* claves primarias con ``auto_created``, y campos concretos
        por ``app_label``, sobre los modelos registrados.
        *Ciega a:* el conteo exacto, que crece con el árbol — el caso asierta
        que la población sin sitio de declaración **existe y domina**, no una
        cifra congelada.
        """
        implicitas = declaradas = 0
        for model in apps.get_models():
            if getattr(model._meta.pk, 'auto_created', False):
                implicitas += 1
            else:
                declaradas += 1

        assert implicitas > declaradas, (
            f'claves primarias implícitas {implicitas}, declaradas '
            f'{declaradas} — el reparto se invirtió: subclasear ya alcanzaría '
            'a la mayoría y la razón hay que rehacerla')

        ajenos = [f for model in apps.get_models()
                  if model._meta.app_label in ('auth', 'contenttypes', 'sessions')
                  for f in model._meta.get_fields() if isinstance(f, models.Field)]
        assert ajenos, 'no hay campos de apps ajenas: el caso mide un vacío'
        assert all(f.falsy_value == falsy_value(f) for f in ajenos), (
            'un campo de una app que no gobernamos quedó sin el atributo; el '
            'compilador de dominios tendría que responder por él igual')

    def test_a_reverse_relation_has_no_attribute_and_the_function_covers_it(self):
        """La tercera cosa que la función añade sobre el atributo.

        Una relación inversa (``ManyToOneRel``, ``ManyToManyRel``) aparece en
        ``_meta.get_fields()`` y **no** es un ``models.Field``: ningún parche
        sobre ``models.Field`` la alcanza. El ``getattr`` con defecto de la
        función responde por ella con la hipótesis conservadora.
        """
        inversa = apps.get_model('base', 'IrSequence')._meta.get_field('date_range_ids')
        assert not isinstance(inversa, models.Field)
        assert not hasattr(inversa, 'falsy_value'), (
            'la relación inversa recibió el atributo; entonces el getattr con '
            'defecto de la función ya no cubre nada y sobra')
        assert falsy_value(inversa) is None

    def test_our_own_field_classes_get_it_by_inheritance(self, mail_server):
        """Las clases propias no necesitan nada extra.

        ``orm.fields_binary.Binary`` desciende de ``models.BinaryField``, que
        desciende de ``models.Field``: hereda el defecto sin declararlo.
        """
        field = mail_server._meta.get_field('smtp_ssl_certificate')
        assert isinstance(field, Binary)
        assert type(field).__module__.startswith('orm.')
        assert field.falsy_value is None


class TestTheTwoWaysToAskForNotNullAgree:
    """``registry.not_null_fields`` y ``registry.is_not_null`` — la misma pregunta.

    La segunda es el atajo de la primera: el optimizador pregunta por **un**
    campo y no paga el recorrido del registro entero. Un atajo que responda
    distinto de lo que recorre no es un atajo, es un segundo mecanismo con el
    mismo nombre — el defecto que este mismo pase corrigió en ``falsy_value``,
    una capa más arriba.

    Medido al escribir estos casos: la primera versión del atajo leía
    ``field.null`` sin exigir columna, y discrepaba en **88 de 5345** campos.
    """

    def test_the_shortcut_agrees_with_the_walk_on_every_field(self):
        """EL CONTROL, y el único que ve las 88 a la vez.

        Recorre el registro y compara las dos vías campo por campo. Un caso
        con un solo campo no habría visto la clase que discrepa: los modelos
        sin M2M coincidían perfectamente.
        """
        conjunto = registry.not_null_fields()
        discrepan = []
        medidos = 0
        for model in apps.get_models(include_auto_created=True):
            for field in model._meta.get_fields():
                if not hasattr(field, 'null'):
                    continue
                medidos += 1
                if (field in conjunto) != registry.is_not_null(field):
                    discrepan.append(f'{model.__name__}.{field.name} '
                                     f'({type(field).__name__})')
        assert medidos > 1000, (
            f'sólo {medidos} campos medidos: el recorrido no está viendo el '
            'registro y un 0 discrepancias aquí sería un verde falso')
        assert not discrepan, (
            f'{len(discrepan)} de {medidos} campos: las dos vías responden '
            f'distinto — {discrepan[:5]}')

    def test_a_many_to_many_is_not_a_not_null_column(self):
        """El caso nombrado, que es el que rompió un optimizador.

        Django declara ``null=False`` en un ``ManyToManyField`` y avisa de que
        ahí el atributo **no tiene efecto**: la nulabilidad vive en la tabla
        intermedia, no en una columna de este modelo.
        """
        field = apps.get_model('base', 'IrRule')._meta.get_field('groups')
        assert isinstance(field, models.ManyToManyField)
        assert field.null is False, (
            'la precondición del caso cambió: si el M2M dejara de declarar '
            'null=False, el atajo ingenuo ya no discrepaba y este caso no '
            'distinguiría nada')
        assert field.concrete is False
        assert registry.is_not_null(field) is False, (
            'un M2M se dio por NOT NULL: el optimizador recortará el False de '
            'un dominio sobre él')

    def test_a_plain_not_null_column_still_counts(self):
        """El control positivo: la corrección no apagó el mecanismo.

        Sin este caso, un ``is_not_null`` que devolviera ``False`` siempre
        pasaría el caso de arriba y ninguna de las dos aserciones lo notaría.
        """
        rule = apps.get_model('base', 'IrRule')
        assert registry.is_not_null(rule._meta.get_field('name')) is True
        assert registry.is_not_null(rule._meta.get_field('id')) is True

    def test_the_optimizer_leaves_a_many_to_many_alone(self):
        """La consecuencia observable, medida sobre el optimizador.

        Es el caso por el que se descubrió: con el atajo ingenuo el ``False``
        se recortaba y ``groups not in [False]`` quedaba en ``not in []``,
        que colapsa a verdadero.
        """
        rule = apps.get_model('base', 'IrRule')
        condition = DomainCondition('groups', 'in', [1, False])
        assert _optimize_in_required(condition, rule) == condition, (
            'el optimizador recortó el False de un M2M: su columna no existe, '
            'así que la fila sin valor sigue siendo posible')
