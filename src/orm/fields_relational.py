"""Campos relacionales — fiel a ``odoo/orm/fields_relational.py`` (Odoo 19).

``Many2one`` = ``ForeignKey``; ``Many2many`` = ``ManyToManyField``; ``One2many``
es el reverso de un FK en Django (``related_name``), sin clase propia.

``store=False`` — el Many2one sin columna
==========================================

La referencia declara relaciones **calculadas y no almacenadas**::

    properties_base_definition_id = fields.Many2one(
        "properties.base.definition",
        compute="_compute_properties_base_definition_id",
        search="_search_properties_base_definition_id",
    )

(``odoo19c: odoo/addons/base/models/properties_base_definition_mixin.py:21-25``)
— un ``compute`` sin ``store`` **no tiene columna**: el valor se resuelve al
leerlo. Django no lo tiene: todo ``ForeignKey`` es una columna.

Por eso ``Many2one`` deja de ser un alias pelado y pasa a ser un
**despachador**, el mismo patrón que ya tienen ``Char``
(``orm/fields_textual.py``) y ``Float`` (``orm/fields_numeric.py``): con
``store`` por defecto devuelve el ``ForeignKey`` de siempre y con
``store=False`` devuelve un :class:`~orm.fields_nonstored.NonStored`. El sitio
de declaración queda **idéntico al de la fuente**, que es el punto — la
alternativa era colgar una ``property`` fuera de la clase y repartir en el
cableado lo que la referencia declara en el cuerpo.

``join`` — el salto de un camino relacional
===========================================

``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466``) añade a una
consulta el LEFT JOIN que sigue este campo y devuelve el par
``(comodelo, alias)``. Lo consume ``BaseModel._traverse_related_sql``, que
recorre un campo delegado salto a salto.

Se adjunta a ``models.ForeignKey`` —la clase que ``Many2one`` devuelve— por la
misma razón de forma que ``orm/fields.py`` declara para ``to_sql``: la clase es
de Django y no es nuestra para declararla. Medido antes de adjuntar: ``join``
da ``False`` en ``hasattr(models.ForeignKey, 'join')``.

``Many2many`` no lleva **esas dos** ramas: ``grep -rn "Many2many(" ``
sobre ``odoo19c:`` no arroja ninguna declarada ``store=False`` con ``compute``
sin almacenar en la familia ``base``, así que dárselo sería construir para un
caso que no existe. Tampoco lleva ``company_dependent``: ``many2many`` no está
en la lista cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``) — un ``jsonb`` guarda un valor por
empresa, no una tabla intermedia.

.. note:: **Corregido.** Esta línea decía *"``Many2many`` **no** lleva el
   despachador"*, y hoy sí lo lleva: es una función, no el alias pelado
   ``Many2many = models.ManyToManyField``. Lo que sigue siendo cierto es la
   razón que el párrafo daba — ninguna de esas **dos** ramas aplica—; lo que
   cambió es que apareció una tercera palabra clave que sí, ``check_company``,
   medida en **19** declaraciones de la referencia dentro de los addons que
   este árbol ya tiene.

``company_dependent`` — el destino que cambia con la empresa (tarea #129)
=========================================================================

``Many2one`` sí lo lleva, y es el tipo que más lo usa en la referencia: **35**
de las 54 declaraciones de producto. Ver la rama en :func:`Many2one`.
"""
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from orm.fields_company_dependent import CompanyDependent
from orm.fields_nonstored import (
    _UNSET,
    NonStored,
    annotate_related,
    projection_or_none,
)
from tools.sql import SQL

__all__ = ['Many2one', 'One2many', 'Many2many', 'bypass_search_access']

class One2many:
    """El conjunto de registros del comodelo cuyo inverso apunta a este — ≙ ``:843``.

    La fuente lo define en una linea: *"the recordset of all the records in
    ``comodel_name`` such that the field ``inverse_name`` is equal to the
    current record"*. Django tiene ese conjunto —es el reverso de la FK, el
    ``related_name`` del hijo— pero **no tiene donde declararlo en el padre**,
    y ese es exactamente el hueco que esta clase cierra.

    Hasta ``api@596cd2b`` este nombre valia ``None`` y estaba en el ``__all__``
    publico: ``fields.One2many(...)`` daba ``TypeError: 'NoneType' object is
    not callable``. La razon escrita —*"es el reverso de un FK en Django, sin
    clase propia"*— describia el **mecanismo de lectura**, que es correcto, y
    callaba el **sitio de declaracion**, que no lo es::

        # la fuente, en el padre                    (odoo19c: res_partner.py)
        child_ids = fields.One2many('res.partner.category', 'parent_id')

        # Django, en el hijo                        (otro archivo, otra clase)
        parent = models.ForeignKey(..., related_name='child_ids')

    Al portar un modelo padre sus ``One2many`` desaparecian de su cuerpo. Es
    el defecto de forma de :ref:`h-api-350` y del ``store=False``
    (:ref:`h-api-361`): todos los simbolos presentes, la forma cambiada — y el
    conteo, que es lo unico que el gate mide, no lo ve.

    **No reimplementa la lectura: la reusa.** El valor sale del manager que
    Django ya construyo, asi que ``.add()``, ``.create()`` y el resto del
    protocolo del reverso siguen siendo los suyos. Lo que esta clase aporta es
    el sitio de declaracion, ``copy=False`` y el rechazo por nombre.

    Poblacion que lo consume: **730** declaraciones en ``odoo19c``, **37** solo
    en ``base``. No hay que esperar al consumidor real — ya existe y esta
    contado.

    **No persiste.** Sigue el protocolo de ``contribute_to_class`` sin
    registrarse en ``_meta``, igual que :class:`~orm.fields_nonstored.NonStored`:
    la columna es la FK del hijo, que ya existe. Un ``One2many`` en ``_meta``
    generaria migracion para una columna que nadie tiene.

    Cobertura del porte — 13 simbolos en la fuente
    ==============================================

    ``porte-completo-no-parcial.md`` exige declarar **cuantos, cuales y por
    que** cuando un porte no cierra todos los simbolos. Medido por AST contra
    ``odoo19c: odoo/orm/fields_relational.py:843``:

    ======================================= ===================================
    Simbolo de la fuente                    Desenlace
    ======================================= ===================================
    ``__init__``                            **portado**, con los cuatro
                                            parametros que su docstring
                                            documenta
    ``__get__``                             **portado** — reusa el manager del
                                            reverso de Django
    ``_additional_domain``                  **portado**; su rama polimorfica es
                                            DESCONOCIDO con condicion de
                                            cierre, tarea **#240**
    ``get_comodel_domain``                  **portado** en su composicion; el
                                            tipo de retorno esta bloqueado y
                                            medido, tarea **#241**
    ``_description_relation_field``         **portado** (aqui es ``property``,
                                            alli ``property(attrgetter(...))``)
    ``setup_nonrelated`` · ``update_db``    conducta **portada** en
                                            ``_inverse_field``, con el mensaje
                                            verbatim — pero **perezosa** donde
                                            la fuente es eager. El eje eager es
                                            la tarea **#242**
    ``write_real`` · ``write_new``          su rama ``CLEAR``/``SET`` esta
                                            **portada** en ``__set__``, con la
                                            decision de ``ondelete``. Los otros
                                            cinco comandos no pasan por el
                                            campo: ``Command`` aqui es
                                            ejecutivo (:ref:`h-api-589`, tarea
                                            **#345**)
    ``read``                                **divergencia de mecanismo** — la
                                            fuente llena su cache por lote; aqui
                                            la lectura es el manager del
                                            reverso, y el lote lo da
                                            ``prefetch_related``
    ``setup_inverses``                      **divergencia de mecanismo** — el
                                            mapa existe y lo mantiene Django en
                                            ``remote_field``; la fuente tiene
                                            que construirlo porque su ORM no lo
                                            guarda. Aqui lo deriva
                                            ``registry._TriggerRegistry``.
                                            Cerrado con la capa B de #273
                                            (:ref:`h-api-1032`); era
                                            DESCONOCIDO por *"este arbol no
                                            tiene cache de campos"*, y esa
                                            causa la retiro la capa A
    ``_condition_to_sql_relational``        **trabajo**, no divergencia: el lado
    ``_get_query_for_condition_value``      SQL del campo. Tarea **#243**
    ``_internal_description_domain_raw``    **trabajo**, detras de #241 porque
                                            necesita el tipo ``Domain``
    ======================================= ===================================

    Siete simbolos son propios y no tienen contraparte por nombre:
    ``__set_name__`` y ``contribute_to_class`` son el protocolo de nombre de
    Django; ``_inverse_field``, ``_deletes_the_leftover`` y ``__set__`` son el
    cuerpo de lo que la fuente resuelve dentro de ``setup_nonrelated`` y
    ``write_real``; ``__repr__`` es el que la fuente hereda de ``Field``.
    """

    #: ≙ ``type = 'one2many'`` (``odoo19c: :866``).
    type = 'one2many'

    def __new__(cls, *args, related=None, **kwargs):
        """Despacha la proyección sin dejar de ser una clase.

        ``One2many`` no puede ser una función —``domains`` la usa en un
        ``isinstance``— así que la bifurcación va aquí, con el mismo mecanismo
        que ``Html``: cuando ``__new__`` devuelve una instancia que **no** es
        de ``cls``, Python no llama a ``__init__``.

        **Este era el peor de los nueve.** El ``**_ignored`` de abajo tragaba
        ``related=`` y devolvía un campo sin la ruta puesta: la declaración se
        escribía igual que la de la fuente
        (``fields.One2many(related='employee_id.subordinate_ids')``), pasaba
        sin error, y no hacía nada. Es literalmente el defecto que el
        comentario de ``domain``/``context`` de este mismo constructor ya
        describe —*«un parámetro tragado es peor que uno ausente»*— cometido
        por segunda vez en la misma firma.

        Sin ``store`` no hay comodelo ni inverso que declarar: el extremo de
        la cadena es el manager del reverso, y navegarlo no necesita ninguno
        de los dos. Es lo que la referencia declara, sin ellos.
        """
        projection, _attributes = projection_or_none(related, kwargs)
        if projection is not None:
            return projection
        instance = super().__new__(cls)
        instance.related = related
        return instance

    def __init__(self, comodel_name=None, inverse_name=None, *, copy=False,
                 string=None, domain=None, context=None,
                 bypass_search_access=False, related=None, **_ignored):
        #: ``__new__`` ya lo dejó puesto; se acepta con nombre para que **no**
        #: caiga en ``**_ignored``, que es como se tragaba antes.
        self.related = related
        self.comodel_name = comodel_name
        self.inverse_name = inverse_name
        #: Los tres que la fuente documenta en su docstring (``:852-860``) y
        #: que este porte tragaba en ``**_ignored``. Un parametro tragado es
        #: peor que uno ausente: la llamada se escribe igual que la de la
        #: fuente, pasa sin error, y no hace nada.
        self.domain = domain
        self.context = context or {}
        #: *"whether access rights are bypassed on the comodel (default:
        #: ``False``)"* — ``:859-860``. El default abierto seria un hueco de
        #: permiso; lo consume ``domains._optimize_any_with_rights``.
        self.bypass_search_access = bool(bypass_search_access)
        #: ≙ ``copy: bool = False`` con su comentario verbatim: *"o2m are not
        #: copied by default"* (``:867``). Lo mira ``BaseModel.copy`` para
        #: decidir si arrastra los hijos; el default contrario duplicaria un
        #: arbol entero al copiar su raiz.
        self.copy = bool(copy)
        self.string = string
        self.name = None

    @property
    def _description_relation_field(self):
        """La columna del hijo por la que cuelga el conjunto — ≙ ``:901``::

            _description_relation_field = property(attrgetter('inverse_name'))

        Es lo que el cliente lee en la descripcion del campo para saber por
        donde esta enlazado.
        """
        return self.inverse_name

    def _additional_domain(self, env=None):
        """El predicado extra del inverso polimorfico — ≙ ``:913-919``.

        La fuente devuelve ``Domain(inverse_field.model_field, '=',
        self.model_name)`` cuando el inverso es un ``many2one_reference``: un
        FK polimorfico guarda modelo e id en dos columnas, y sin acotar el
        modelo el conjunto traeria las filas de todos los demas.

        **DESCONOCIDO declarado, con su condicion de cierre.** Aqui
        ``Many2oneReference`` es el ``GenericForeignKey`` de ``contenttypes``
        (``orm/fields_reference.py:14``), que **no** expone ``model_field``: su
        par de columnas se llama ``ct_field``/``fk_field`` y ningun addon
        portado declara todavia un inverso polimorfico. La rama se cierra
        cuando exista el primero que medir — tarea **#240**. Hasta entonces
        devuelve el predicado vacio, que es lo que la fuente devuelve para los
        otros dos tipos de inverso (``Domain.TRUE``).
        """
        return []

    def get_comodel_domain(self, model=None):
        """El dominio declarado, mas el del inverso — ≙ ``:918-919``.

        La fuente compone ``super().get_comodel_domain(model) &
        self._additional_domain(model.env)`` y devuelve un ``Domain``.

        **El tipo de retorno esta BLOQUEADO, y el bloqueo esta medido dos
        veces.** ``from orm.domains import Domain`` en la cabecera de este
        archivo no arranca, por dos causas independientes que se apilan:

        1. **Ciclo.** ``orm/domains.py:102`` importa ``orm.fields``, y
           ``orm/fields.py:77`` importa este archivo de vuelta. Medido en las
           dos direcciones, que es lo que ``no-lazy-imports.md`` excepcion #3
           exige antes de aceptar nada que no sea un refactor::

               ImportError: cannot import name 'Many2many' from partially
               initialized module 'orm.fields_relational'

        2. **Registro de apps.** Aun rompiendo el ciclo por orden, ``fields.py``
           arrastra ``fields_reference`` -> ``contenttypes`` -> ``ContentType``,
           y este archivo se carga desde ``inherits.py`` **durante**
           ``apps.populate``::

               django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.

        La referencia no tiene ninguno de los dos: su ``odoo/orm/domains.py``
        importa ``.identifiers`` y ``.utils``, y **no** el modulo de campos
        (medido sobre sus 19 imports). La arista de vuelta la pone nuestro
        ``orm/fields.py`` al cargar el papel de fachada que la referencia
        declara en ``odoo/fields.py``.

        **No se resuelve aqui, y no por conveniencia:** retirar
        ``orm/fields.py:77`` tiene dos consumidores medidos —``__all__``, del
        que ``ir_model.FIELD_TYPES`` se deriva (``ir_model.py:213,239``), y
        ``tests/unit/orm/test_fields_facade.py:61``, que ejercita
        ``from orm.fields import *``— asi que cambia el vocabulario de
        ``IrModelFields.ttype``. Separar definidor de fachada es el alcance
        declarado de la tarea **#211**; el cambio de tipo de retorno de este
        metodo es la tarea **#241**, que la sucede.

        Lo que SI esta portado es la **composicion**, que es el contenido del
        metodo: el dominio declarado en el campo mas el del inverso.
        """
        declarado = list(self.domain) if self.domain else []
        return declarado + list(self._additional_domain())

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class`` — sin tocar ``_meta``."""
        self.name = name
        self.model_name = cls._meta.label
        setattr(cls, name, self)

    # -- protocolo de descriptor -------------------------------------------

    def _inverse_field(self):
        """El ``Many2one`` del comodelo que este campo invierte.

        Rechaza el inverso inexistente **por nombre**, con el mensaje de
        ``setup_nonrelated`` (``odoo19c: :889``)::

            raise ValueError(f"{self.inverse_name!r} declared in {self!r} "
                             f"does not exist on {comodel._name!r}.")

        Un ``FieldDoesNotExist`` pelado de Django no dice cual de los dos
        nombres esta mal: si el del comodelo o el del inverso.
        """
        comodel = apps.get_model(self.comodel_name)
        try:
            return comodel, comodel._meta.get_field(self.inverse_name)
        except FieldDoesNotExist:
            raise ValueError(
                f'{self.inverse_name!r} declared in {self!r} does not exist '
                f'on {self.comodel_name!r}.') from None

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        comodel, inverse = self._inverse_field()
        accessor = inverse.remote_field.get_accessor_name()
        if accessor is not None and hasattr(instance, accessor):
            # El manager del reverso: trae ademas la escritura (``add``,
            # ``create`` con el padre ya puesto), que un ``filter`` no da.
            return getattr(instance, accessor)
        # El inverso apunta a otro modelo, o su reverso esta suprimido con
        # ``related_name='+'``. Queda la definicion literal de la fuente.
        return comodel._default_manager.filter(**{self.inverse_name: instance})

    def _deletes_the_leftover(self, inverse):
        """Que hacer con el hijo que se queda fuera — ≙ ``write_real:975-979``.

        La fuente lo decide por el ``ondelete`` del inverso, no por la
        nulabilidad de la columna::

            if getattr(comodel._fields[inverse], 'ondelete', False) == 'cascade':
                to_delete.extend(lines._ids)
            else:
                lines[inverse] = False

        Django decide por otra cosa: su ``RelatedManager.set()`` existe **si la
        FK admite nulo**, y entonces anula. Sobre una FK ``null=True`` con
        ``on_delete=CASCADE`` las dos politicas discrepan, y el porte impone la
        de la fuente.
        """
        return getattr(inverse.remote_field, 'on_delete', None) is models.CASCADE

    def __set__(self, instance, value):
        """Asignar el conjunto — ≙ el tramo ``CLEAR``/``SET`` de ``write_real``.

        La fuente los trata juntos (``command[0] in (Command.CLEAR,
        Command.SET)``, ``:1027``): el conjunto queda **exactamente** en las
        lineas dadas, y las que sobran pasan por ``unlink``. ``CLEAR`` es el
        mismo camino con la lista vacia.

        Los otros cinco comandos —``CREATE``, ``UPDATE``, ``DELETE``,
        ``UNLINK``, ``LINK``— no pasan por aqui: en este arbol ``Command`` es
        **ejecutivo** (escribe al llamarlo) en vez de ser un valor diferido que
        el ORM interpreta. Esa divergencia es de la clase entera y esta
        registrada en :ref:`h-api-589` (tarea **#345**), no de este metodo.
        """
        comodel, inverse = self._inverse_field()
        nuevos = list(value or ())
        vivos = [obj.pk for obj in nuevos if obj.pk is not None]
        sobrantes = (comodel._default_manager
                     .filter(**{self.inverse_name: instance})
                     .exclude(pk__in=vivos))
        if self._deletes_the_leftover(inverse):
            sobrantes.delete()
        else:
            sobrantes.update(**{inverse.attname: None})
        for obj in nuevos:
            setattr(obj, self.inverse_name, instance)
            obj.save(update_fields=[inverse.attname])

    def __repr__(self):
        return (f'One2many({self.comodel_name!r}, {self.inverse_name!r})')



#: El permiso del comodelo no se aplica al atravesar este campo — ≙
#: ``_Relational.bypass_search_access`` (``odoo19c:
#: odoo/orm/fields_relational.py:39``), con su comentario verbatim: *"whether
#: access rights are bypassed on the comodel"*.
#:
#: Lo consume ``domains._optimize_any_with_rights``: un ``any`` sobre un campo
#: que lo declara se reescribe a ``any!``, la forma que salta el permiso, y de
#: ahí cuelga el resto de la cadena — ``_optimize_m2o_bypass_comodel_id_lookup``
#: sólo actúa sobre los que llevan ``!``.
#:
#: **Se declara sobre las clases de campo de Django y no se consulta con un
#: ``getattr`` de respaldo.** Es la misma decisión que la fuente toma al
#: ponerlo en ``_Relational`` y no en ``Field``: un campo escalar **no** lo
#: tiene, y preguntárselo tiene que ser un error y no un ``False`` silencioso.
#: Un respaldo haría indistinguible *"este campo no lo concede"* de *"a este
#: campo la pregunta no le aplica"*.
#:
#: Va sobre la clase porque **759** declaraciones del árbol lo necesitarían:
#: 690 pasan por la fábrica ``fields.Many2one`` y 69 son ``models.ForeignKey``
#: directas (medido con ``grep -rhoP`` sobre ``src/`` y ``addons/``). Marcarlo
#: sólo en la fábrica dejaría a esas 69 sin el atributo, que es justo el
#: agujero que el párrafo anterior prohíbe. Es un atributo **nuevo**: no
#: sobreescribe nada de Django, así que no puede alterar su comportamiento.
models.ForeignKey.bypass_search_access = False
models.ManyToManyField.bypass_search_access = False


def bypass_search_access(field, flag=True):
    """Declara que el permiso del comodelo no aplica al atravesar ``field``.

    La fuente lo recibe como palabra clave del constructor; aquí se cuelga del
    campo ya construido por la misma razón de forma que ``check_company``: la
    clase del campo es de Django y su constructor no conoce la palabra.

    Es público —sin guion bajo— porque lo llama ``orm.inherits``, que está
    fuera de este módulo: la delegación lo implica (``:257-259`` de la fuente,
    con su comentario *"self.delegate implies self.bypass_search_access"*).
    """
    field.bypass_search_access = bool(flag)
    return field


def _mark_check_company(field, check_company):
    """Marca el campo para que ``BaseModel._check_company`` lo mire.

    ≙ ``_Relational.check_company`` (``odoo19c:
    odoo/orm/fields_relational.py:40``), que allá es un atributo de clase con
    ``False`` por defecto y aquí es un atributo de instancia por la misma
    razón de forma que ``join``: la clase del campo es de Django y no es
    nuestra para declararla.

    El valor **no** llega al constructor de Django — ``ForeignKey`` no lo
    conoce y reventaría—; se cuelga del campo ya construido, que es donde
    ``_check_company`` lo lee al recorrer ``_meta.get_fields()``.
    """
    field.check_company = bool(check_company)
    return field


def Many2many(*args, check_company=False, store=_UNSET, related=None,
              **kwargs):
    """``fields.Many2many`` — el ``ManyToManyField`` de Django, marcable.

    Era un alias pelado (``Many2many = models.ManyToManyField``) y pasa a ser
    despachador por un solo motivo medido: **19** declaraciones de la
    referencia en los addons que este árbol ya tiene la marcan
    ``check_company=True`` (contra 282 ``Many2one`` y 5 ``One2many``), y el
    alias no tenía dónde recibir la palabra clave.

    No lleva ``store=False`` ni ``company_dependent`` — ver el bloque del
    docstring del módulo, que mide por qué ninguno de los dos aplica aquí.
    """
    #: ``:452-458`` — igual que en ``Many2one``: la referencia declara
    #: ``fields.Many2many(related="lead_id.tag_ids", readonly=True)`` sin
    #: comodelo, porque el extremo de la cadena lo determina.
    if store is not _UNSET:
        kwargs['store'] = store
    #: ``compute=`` en un M2M — #313. El bloque de la fuente se aplica igual
    #: que en cualquier otro tipo; lo que cambia es el VOLCADO, no la
    #: declaración: ``orm.models._flush_m2m`` entrega el valor calculado al
    #: manager relacional en vez de asignarlo, porque Django prohíbe el
    #: ``setattr`` sobre el lado directo de un muchos-a-muchos.
    #:
    #: La bandera viaja hasta el bloque de ``precompute``: un M2M no se puede
    #: adelantar al ``INSERT`` —su tabla intermedia necesita el ``pk``—, así
    #: que ahí se apaga con aviso. Va por el enrutador y no por una segunda
    #: llamada a ``apply_source_defaults`` porque la primera **vacía**
    #: ``kwargs``: llamarla dos veces devolvía un vocabulario vacío, y el
    #: campo salía sin ``compute`` anotado.
    projection, related_attrs = projection_or_none(related, kwargs,
                                                   many_to_many=True)
    if projection is not None:
        return _mark_check_company(projection, check_company)
    field = _mark_check_company(models.ManyToManyField(*args, **kwargs),
                                check_company)
    return annotate_related(field, related, related_attrs)


def _comodel_label(to):
    """La etiqueta ``app.Modelo`` del destino de una FK, venga como venga.

    ``registry.many2one_company_dependents`` indexa por ``_meta.label``, así
    que el comodelo hay que guardarlo con esa forma. Django admite el destino
    como cadena (``'base.ResPartner'``), como clase, o como
    ``'self'``; los tres se normalizan aquí para que el catálogo no tenga que
    saber cuál se usó en la declaración.

    ``'self'`` se conserva verbatim: en el momento de construir el campo la
    clase todavía no existe, y quien lo resuelve es la carga del modelo.
    """
    if to is None or isinstance(to, str):
        return to
    return to._meta.label


def Many2one(*args, store=_UNSET, company_dependent=False,
             check_company=False, related=None, **kwargs):
    """``fields.Many2one`` — ≙ el de la referencia: con columna, sin ella o por empresa.

    ``store=True`` (el defecto, y el de todos los usos previos del árbol)
    devuelve un ``models.ForeignKey`` con la firma de Django, exactamente como
    antes: el alias sigue siendo transparente para quien no nombra ``store``.

    ``store=False`` devuelve un campo **no persistido** cuyo valor sale de
    ``default`` al leerlo. No genera migración ni aparece en ``_meta``, que es
    lo que la referencia promete con un ``compute`` sin ``store``. El primer
    argumento posicional —el modelo apuntado— se acepta y se descarta, igual
    que ``NonStored`` descarta el resto de la firma de Django.

    ``company_dependent=True`` — el destino depende de la empresa
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tercera rama, con la firma de la fuente::

        property_account_payable_id = fields.Many2one(
            'account.account', company_dependent=True)

    Es **el tipo más usado** de la referencia con esa palabra clave: 35 de las
    54 declaraciones de producto (``odoo19c``, medido por AST). Devuelve un
    :class:`~orm.fields_company_dependent.CompanyDependent` de
    ``base_type='many2one'``, cuya columna guarda ``{empresa: id}``.

    **Deja de haber FK real, y eso es del mecanismo, no de la adaptación.**
    Allá pasa igual: el valor vive dentro del ``jsonb``, así que el catálogo de
    claves foráneas de PostgreSQL no ve la referencia y nadie la protege con
    ``ON DELETE``. Por eso la fuente lleva un índice propio —
    ``Registry.many2one_company_dependents``, portado en
    ``orm/registry.py``— y por eso el comodelo se guarda en el campo: es lo
    único que queda para responder *"¿quién apunta a este modelo?"*.

    Los argumentos que sólo tienen sentido en una FK real —``on_delete``,
    ``related_name``— se descartan aquí: sin FK no hay nada que cascadear ni
    accesor inverso que nombrar. Descartarlos en silencio sería el defecto que
    ``porte-completo-no-parcial.md`` prohíbe, así que quedan declarados.
    """
    #: ``:452-458`` — con ``related=`` y sin columna, el comodelo sobra: el
    #: extremo de la cadena lo determina, y así lo declara la referencia
    #: (``fields.Many2one(related='product_id.categ_id')``, sin comodelo).
    #: El centinela distingue «no declaró store» de «lo declaró True», que un
    #: default literal no puede.
    if store is not _UNSET:
        kwargs['store'] = store
    projection, related_attrs = projection_or_none(related, kwargs,
                                                  company_dependent)
    if projection is not None:
        return projection
    store = related_attrs['store']

    if company_dependent:
        to = args[0] if args else kwargs.pop('to', None)
        resto = args[1:]                       # el ``on_delete`` posicional
        if to is None:
            raise ValueError(
                'un Many2one dependiente de empresa necesita su modelo '
                'destino: es lo único que queda para indexarlo, porque el '
                'jsonb no deja FK que el catálogo pueda seguir.')
        for solo_fk in ('on_delete', 'related_name', 'limit_choices_to',
                        'to_field', 'db_constraint'):
            kwargs.pop(solo_fk, None)
        if resto:
            # ``Many2one('x', models.CASCADE)`` — el segundo posicional es el
            # ``on_delete`` de Django, que aquí tampoco tiene destinatario.
            resto = ()
        return _mark_check_company(
            CompanyDependent(*resto, base_type='many2one',
                             comodel=_comodel_label(to), **kwargs),
            check_company)
    if store:
        field = _mark_check_company(models.ForeignKey(*args, **kwargs),
                                    check_company)
    else:
        field = _mark_check_company(NonStored(*args, **kwargs), check_company)
    return annotate_related(field, related, related_attrs)


def _many2one_join(self, model, alias, query):
    """``join`` — añade el LEFT JOIN de este Many2one y devuelve (modelo, alias).

    ≙ ``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466-478``).
    Es lo que ``BaseModel._traverse_related_sql`` invoca en cada salto de un
    camino relacional: sin él, un campo delegado no se puede resolver a SQL.

    La condición ON se compone con ``model._field_to_sql(alias, self.name,
    query)`` —el mismo punto de entrada que la fuente usa— para que la columna
    del lado izquierdo salga del mismo sitio que cualquier otra, con su
    comprobación de acceso incluida.

    Divergencias de nombre, las dos mecánicas: el comodelo se obtiene de
    ``self.related_model`` en vez de ``model.env[self.comodel_name]`` —Django
    ya lo tiene resuelto en el campo—, y su tabla de ``_meta.db_table`` en vez
    de ``_table``.
    """
    comodel = self.related_model
    coalias = query.make_alias(alias, self.name)
    query.add_join('LEFT JOIN', coalias, comodel._meta.db_table, SQL(
        "%s = %s",
        model._field_to_sql(alias, self.name, query),
        SQL.identifier(coalias, 'id'),
    ))
    return (comodel, coalias)


models.ForeignKey.join = _many2one_join

