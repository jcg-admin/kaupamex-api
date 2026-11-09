"""``_inherits`` — delegación por Many2one nombrado.

Adaptación de Odoo ``odoo/orm/models.py`` (odoo-tools@622ddc2a, odoo19c:,
LGPL-3), donde ``_inherits = {'modelo.delegado': 'nombre_fk'}`` hace que el
delegante exponga los campos del delegado como propios: lectura, escritura y
creación en cascada.

Por qué existe este módulo
==========================

Django tiene un análogo —herencia multi-tabla (MTI)— pero **ata la delegación
a la jerarquía de clases**: hay que heredar del delegado, y la FK implícita
(``parent_ptr``) no se nombra ni se elige. ``_inherits`` es **composición**:
cualquier modelo delega en otro por un Many2one *nombrado*, sin subclasear, y
puede delegar en varios a la vez.

La diferencia no es teórica en este árbol: los ports que topan con
``_inherits`` la razonaron **uno por uno, cada quien a su manera**
(``product/models/product_product.py:12-20``,
``mail/models/mail_mail.py:23-26``), y el caso de ``res.users`` se resolvió
con una lista de propiedades escritas a mano — **3 de los 22 campos del
delegado**, con ``tz`` entre los 19 ausentes. Esa lista incompleta produjo
H-API-300: ``resource`` leyó ``user.tz`` y obtuvo ``AttributeError``.

El defecto no fue el olvido: fue que **una lista a mano no tiene forma de
estar completa**. Un mecanismo la deriva del delegado y no puede omitir un
campo.

Alcance de esta primera versión
=================================

Prototipo deliberadamente acotado (ver ``docs: …/reporte-orm-propio-vs-
mecanismos-sobre-django``):

1. **Lectura** — ``__getattr__`` delega al registro apuntado por la FK.
2. **Escritura** — ``__setattr__`` enruta al delegado y ``save()`` lo
   persiste antes que al delegante, en la misma transacción.
3. **Precedencia** — lo que el delegante define por su cuenta (campo,
   propiedad o método) **gana**. El mecanismo es aditivo: no pisa las
   propiedades ya escritas a mano, sólo cubre lo que faltaba.

La creación del delegado al crear el delegante **no vive aquí**: la hace
``BaseModel.create`` (``orm/models.py``), que crea el padre con
``parent_model.create`` o escribe el padre dado con ``parent.write`` como el
usuario del entorno, igual que ``odoo19c: odoo/orm/models.py:4692-4707``. Lo
verifica ``tests/unit/orm/test_contract_access_on_read_reference.py`` (los
cinco escenarios ``create …``). Los modelos que no derivan de ``BaseModel``
siguen resolviendo su alta a mano —p. ej. ``ResUsers._create_user``, tarea
#96—. **NO** se porta todavía la propagación de ``_inherits`` a través de
varios niveles.

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia declara ``_inherits`` dentro de
``odoo/orm/models.py``, no en un archivo propio. Aquí vive aparte porque el
mecanismo se construye sobre descriptores de Django en vez de sobre su
registro.

Eso lo hace legítimo como **mecanismo construido**
(``porte-completo-no-parcial.md``: *si el stack no trae el mecanismo, se
construye*) y a la vez lo deja **fuera de sitio**: ``src/orm`` es la raíz
espejada de ``odoo/orm``, y ``atributos-de-clase-de-modelo.md`` §2 manda listar
la raíz de la referencia antes de crear un archivo ahí.

``check_porte_completo`` **no puede verlo**: compara símbolos dentro de un par
de archivos, y un archivo que la referencia no tiene no entra en ninguna
comparación. Cinco archivos de ``src/orm`` están en esta situación —
``checks``, ``fields_nonstored``, ``inherits``, ``method_chain``, ``routers``—
y hasta este pase sólo ``checks`` lo declaraba.

El veredicto por archivo —quedarse aquí con la divergencia declarada, o mudarse
a una raíz propia como ``src/core``— es la tarea **#121**.
"""

from django.apps import apps
from django.db import transaction

from orm.environments import CURRENT_USER_SU, is_su
from orm.fields_relational import bypass_search_access
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry


def _delegable_field_names(delegate_model, delegant_cls):
    """Campos del delegado que el delegante NO define por su cuenta.

    ≙ la regla de ``_add_inherited_fields`` (``odoo19c: odoo/orm/
    model_classes.py:480-508``): todo campo del padre que el hijo no
    redefine responde en el hijo, sea columna o no. La lista sale del mismo
    mapa que publica ``_fields`` (:func:`orm.utils.model_field_registry`),
    así que incluye los relacionados, los calculados, los x2many y los
    campos que el padre a su vez hereda; hasta este pase sólo se delegaban
    los concretos, y leer por el hijo un relacionado del padre levantaba
    ``AttributeError``.

    La precedencia del delegante es lo que hace al mecanismo aditivo: lo que
    el delegante declara como campo, propiedad o atributo de clase gana, y
    también el ``attname`` de sus propios campos, que Django asigna en la
    instancia al construirla (``company_id`` de una FK propia no se manda al
    padre).

    *Métrica:* nombres del mapa de campos del delegado, menos los que el
    delegante declara.
    *Ciega a:* atributos que el delegante resuelva por su cuenta en un
    ``__getattr__`` propio — no aparecen en ``vars()`` ni en ``_meta``. Si un
    modelo combina ambos mecanismos, el orden lo decide Python, no esta
    función.
    """
    own = set()
    for field in delegant_cls._meta.get_fields():
        own.add(field.name)
        own.add(getattr(field, 'attname', None) or field.name)
    for klass in delegant_cls.__mro__:
        own |= set(vars(klass))
    return tuple(
        name
        for name in model_field_registry(delegate_model)
        if name not in own
        and not name.startswith('_')
        and name not in ('id', 'pk')
    )


def _check_delegate_access(delegate, operation='read'):
    """Las reglas del padre antes de leer o escribir un campo heredado.

    La copia que publica ``_add_inherited_fields`` lleva
    ``related_sudo=False`` (``odoo19c: odoo/orm/model_classes.py:497``), así
    que allá su ``related`` lee el padre como el usuario y ``fetch`` exige
    ``check_access('read')`` (``models.py:3775-3818``). Aquí la fila del padre
    llega entera por la FK y sus campos no pasan por ``fetch``: la
    comprobación se hace en la puerta. Un recordset de ``BaseModel`` la
    resuelve él; una fila de Django, el ``AccessQuerySet`` de su manager.
    En modo superusuario no se comprueba nada, como allá.

    La escritura es la misma regla con ``'write'``: el inverso del
    ``related`` escribe el padre como el usuario, así que sin permiso de
    escritura sobre el modelo padre el campo heredado no se escribe,
    aunque el hijo sí se pueda escribir.
    """
    if is_su() or delegate.pk is None:
        return
    if hasattr(delegate, 'check_access'):
        delegate.check_access(operation)
        return
    rows = type(delegate)._default_manager.filter(pk=delegate.pk)
    if hasattr(rows, 'check_access'):
        rows.check_access(operation)


class DelegatedFieldNames:
    """``_inherits_fields``: el mapa ``nombre → FK`` de la delegación,
    resuelto tarde.

    Cada nombre delegado apunta a la FK del padre que lo responde. Con varios
    padres se recorren en el orden en que se registraron —el de ``_inherits``,
    que es el que :func:`ensure_inherits` sigue—, y un padre posterior pisa a
    uno anterior en el mismo nombre: *"the inherited field will correspond to
    the last one (in the inherits list order)"* (``odoo19c: odoo/orm/
    models.py:422-425``), la misma regla que ``_add_inherited_fields``
    aplica al mapa de campos (``model_classes.py:486-490``).

    La lista de cada padre sale de su mapa de campos, y ese mapa memoriza sus
    campos sin columna la primera vez que se consulta
    (:func:`orm.fields_nonstored.non_stored_fields`). ``apply_inherits``
    corre dentro de ``ready()`` de cada app, antes de que las siguientes
    contribuyan sus campos al padre: consultarlo ahí congelaba el mapa sin
    ellos, y un campo sin columna añadido después —``city_id`` de
    ``base_address_extended`` en ``res.partner``— quedaba fuera del reparto
    entre columna y descriptor y el ``UPDATE`` lo rechazaba.

    Por eso el mapa se calcula en la primera lectura con el registro de apps
    ya listo, y se memoriza por clase. Antes de eso no hay instancias que
    delegar, y responde vacío sin tocar el mapa del padre.
    """

    def __init__(self):
        self.parents = {}
        self.resolved = {}

    def add_parent(self, delegate_model, fk_name):
        """Registra un padre; reinstalar el mismo no cambia su orden."""
        if self.parents.get(fk_name) is not delegate_model:
            self.parents[fk_name] = delegate_model
            self.resolved.clear()

    def __get__(self, instance, owner):
        names = self.resolved.get(owner)
        if names is not None:
            return names
        if not apps.ready:
            return {}
        names = {}
        for fk_name, delegate_model in self.parents.items():
            for name in _delegable_field_names(delegate_model, owner):
                names[name] = fk_name
        self.resolved[owner] = names
        return names


def apply_inherits(delegant_cls, delegate_model, fk_name):
    """Instala la delegación ``_inherits`` de ``delegant_cls`` al delegado.

    Equivale a una entrada ``'<delegado>': '<fk_name>'`` del ``_inherits`` de
    la referencia; se llama una vez por padre. **Idempotente:** los cuatro
    ganchos —``_inherits_fields``, ``__getattr__``, ``__setattr__`` y
    ``save``— se instalan sólo la primera vez por clase; las llamadas
    siguientes registran el padre en el mapa y marcan su FK. Antes cada
    llamada los sustituía con el cierre de su propio padre, así que con dos
    padres el segundo anulaba al primero y cada ``ensure_inherits`` envolvía
    ``save`` una vez más.

    **El mecanismo CONSUME ``_inherits``; no lo escribe** (tarea #385). Hasta
    hoy esta función lo sobreescribía con la etiqueta de Django —
    ``{'base.ResPartner': 'partner'}`` — pisando el ``{'res.partner': …}`` que
    la clase declara verbatim de la fuente. Con eso, el atributo de clase que
    ``atributos-de-clase-de-modelo.md`` manda portar dejaba de existir en
    cuanto
    ``ready()`` corría: quien lo leyera vería la traducción, no el contrato.
    El estado interno vive en ``_inherits_fields``, que es de este mecanismo.
    """
    # La delegación implica saltar el permiso del comodelo — ≙ ``odoo19c:
    # odoo/orm/fields_relational.py:257-259``, con su comentario de una línea:
    # *"self.delegate implies self.bypass_search_access"*.
    #
    # Tiene que ser así, y no es una comodidad: un campo delegado expone los
    # campos del delegado **como propios**. Aplicarle por debajo el permiso del
    # comodelo dejaría al registro delegante viendo la mitad de sí mismo, según
    # qué reglas de fila pesen sobre el modelo del que hereda.
    fk_field = delegant_cls._meta.get_field(fk_name)
    bypass_search_access(fk_field)

    # ``delegate`` es el atributo que la fuente declara en el propio campo
    # (``odoo19c: odoo/orm/fields_relational.py:248,257``) y **no** un estado
    # interno de este mecanismo: lo lee ``Many2one.convert_to_cache`` para
    # decidir si el id del padre de un registro nuevo también es nuevo. Hasta
    # ahora la delegación se marcaba sólo por su consecuencia —el salto de
    # permiso— y el atributo no tenía dónde leerse.
    fk_field.delegate = True

    descriptor = delegant_cls.__dict__.get('_inherits_fields')
    if isinstance(descriptor, DelegatedFieldNames):
        descriptor.add_parent(delegate_model, fk_name)
        return delegant_cls._inherits_fields
    descriptor = DelegatedFieldNames()
    descriptor.add_parent(delegate_model, fk_name)
    delegant_cls._inherits_fields = descriptor

    def __getattr__(self, name):
        # Sólo se invoca cuando la búsqueda normal falló: los campos y
        # propiedades propias del delegante nunca llegan aquí.
        fk = type(self)._inherits_fields.get(name)
        if fk is not None:
            delegate = getattr(self, fk, None)
            if delegate is not None:
                if not self.__dict__.get(CURRENT_USER_SU):
                    _check_delegate_access(delegate, 'read')
                return getattr(delegate, name)
            return None
        # Un nombre que no se delega vuelve a la búsqueda normal, que relanza
        # el error ORIGINAL: Python llama a ``__getattr__`` también cuando un
        # descriptor levanta ``AttributeError``, y el de una FK vacía levanta
        # ``RelatedObjectDoesNotExist``, que es subclase. Sustituirlo por un
        # ``AttributeError`` genérico escondía ese tipo a quien lo espera.
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        fk = (None if name.startswith('_')
              else type(self)._inherits_fields.get(name))
        if fk is not None:
            delegate = self.__dict__.get(fk) or getattr(self, fk, None)
            if delegate is not None:
                if not self.__dict__.get(CURRENT_USER_SU):
                    _check_delegate_access(delegate, 'write')
                setattr(delegate, name, value)
                self.__dict__.setdefault('_inherits_dirty', set()).add(fk)
                return
        object.__setattr__(self, name, value)

    original_save = delegant_cls.save

    def save(self, *args, **kwargs):
        """Persiste los padres tocados ANTES que el delegante.

        El orden importa: el delegante guarda una FK a cada padre, así que un
        padre sin ``pk`` rompería la integridad. Todos en la misma
        transacción — un padre guardado con un delegante que falla es
        justamente la inconsistencia que la referencia evita.
        """
        dirty = self.__dict__.pop('_inherits_dirty', None)
        if not dirty:
            return original_save(self, *args, **kwargs)
        with transaction.atomic():
            for fk in type(self)._inherits_fields_order(dirty):
                delegate = getattr(self, fk, None)
                if delegate is not None:
                    delegate.save()
            return original_save(self, *args, **kwargs)

    def _inherits_fields_order(cls, dirty):
        """Las FK tocadas, en el orden de registro de sus padres."""
        return [fk for fk in cls.__dict__['_inherits_fields'].parents
                if fk in dirty]

    delegant_cls.__getattr__ = __getattr__
    delegant_cls.__setattr__ = __setattr__
    delegant_cls.save = save
    delegant_cls._inherits_fields_order = classmethod(_inherits_fields_order)
    return delegant_cls._inherits_fields


def ensure_inherits():
    """
    Cablea la delegación de **todo** modelo registrado que declare
    ``_inherits``.

    Hermana de ``ensure_rec_names`` / ``ensure_access_managers`` /
    ``ensure_display_names`` / ``ensure_base_urls`` de
    :mod:`orm.model_classes`, y por la misma razón: el atributo de clase se
    declara en el modelo, pero el mecanismo que lo consume vive fuera y hay
    que invocarlo una vez que el registro está poblado.

    **Por qué deja de ser una lista escrita a mano.** Hasta hoy cada app
    cableaba su propio declarante —``base`` el suyo, ``website`` el suyo— y el
    tercero del árbol quedó fuera: ``ir.cron`` declaraba ``_inherits`` y nunca
    se cableó, así que su FK no llevaba ``delegate`` y la delegación no
    existía. Lo destapó :func:`~orm.model_classes._check_inherits` al portarse,
    que es exactamente para lo que la fuente lo tiene.

    Es el mismo defecto que el docstring de este módulo ya describe para otro
    eje: *"una lista a mano no tiene forma de estar completa"*.

    Idempotente: :func:`apply_inherits` reinstala sin duplicar, así que las
    apps pueden llamarla cada una en su ``ready()``. Un declarante cuyo
    comodelo aún no esté registrado se salta — lo cablea la app que lo cargue
    después.

    Devuelve los nombres de los modelos cableados, para que el llamador pueda
    medir en vez de suponer.
    """
    cableados = []
    for model_cls in list(MODELS_BY_NAME.values()):
        declared = model_cls.__dict__.get('_inherits')
        if not declared:
            continue
        for comodel_name, fk_name in declared.items():
            comodel = MODELS_BY_NAME.get(comodel_name)
            if comodel is None:
                continue
            apply_inherits(model_cls, comodel, fk_name)
            cableados.append(model_cls._name)
    return cableados
