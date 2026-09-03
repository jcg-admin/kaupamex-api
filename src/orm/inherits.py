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

**NO** se porta todavía: la creación automática del delegado al crear el
delegante (Odoo la hace en ``create()``; aquí cada modelo ya resuelve su alta
—p. ej. ``ResUsers._create_user``—, y unificarlo es un cambio de contrato que
merece su propia decisión), ni la propagación de ``_inherits`` a través de
varios niveles.

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia declara ``_inherits`` dentro de ``odoo/orm/models.py``, no en un archivo propio. Aquí vive aparte porque el mecanismo se construye sobre descriptores de Django en vez de sobre su registro.

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
from django.db import transaction

from orm.fields_relational import bypass_search_access
from orm.registry import MODELS_BY_NAME


def _delegable_field_names(delegate_model, delegant_cls):
    """Campos del delegado que el delegante NO define por su cuenta.

    La precedencia del delegante es lo que hace al mecanismo aditivo: si
    ``ResUsers`` ya expone ``email`` como propiedad con su propio fallback
    (``self.partner.email or self.login``), esa propiedad gana y el mecanismo
    ni la ve.

    *Métrica:* nombres de campo concretos del delegado, menos los nombres que
    el delegante declara como campo, propiedad o atributo de clase.
    *Ciega a:* atributos que el delegante resuelva por su cuenta en un
    ``__getattr__`` propio — no aparecen en ``vars()`` ni en ``_meta``. Si un
    modelo combina ambos mecanismos, el orden lo decide Python, no esta
    función.
    """
    own = {f.name for f in delegant_cls._meta.get_fields()}
    for klass in delegant_cls.__mro__:
        own |= set(vars(klass))
    return tuple(
        f.name for f in delegate_model._meta.get_fields()
        if getattr(f, 'concrete', False)
        and f.name not in own
        and not f.name.startswith('_')
        and f.name != 'id'
    )


def apply_inherits(delegant_cls, delegate_model, fk_name):
    """Instala la delegación ``_inherits`` de ``delegant_cls`` al delegado.

    Equivale a ``_inherits = {'<delegado>': '<fk_name>'}`` de la referencia.
    Idempotente: reinstalarla no duplica nada.

    **El mecanismo CONSUME ``_inherits``; no lo escribe** (tarea #385). Hasta
    hoy esta función lo sobreescribía con la etiqueta de Django —
    ``{'base.ResPartner': 'partner'}`` — pisando el ``{'res.partner': …}`` que
    la clase declara verbatim de la fuente. Con eso, el atributo de clase que
    ``atributos-de-clase-de-modelo.md`` manda portar dejaba de existir en cuanto
    ``ready()`` corría: quien lo leyera vería la traducción, no el contrato.
    El estado interno vive en ``_inherits_fields``, que es de este mecanismo.
    """
    delegated = _delegable_field_names(delegate_model, delegant_cls)
    delegant_cls._inherits_fields = delegated

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

    def __getattr__(self, name):
        # Sólo se invoca cuando la búsqueda normal falló: los campos y
        # propiedades propias del delegante nunca llegan aquí.
        if name in delegated:
            delegate = getattr(self, fk_name, None)
            if delegate is not None:
                return getattr(delegate, name)
            return None
        raise AttributeError(
            f'{type(self).__name__!r} no tiene {name!r} ni lo delega en '
            f'{delegate_model.__name__!r}'
        )

    def __setattr__(self, name, value):
        if name in delegated and not name.startswith('_'):
            delegate = self.__dict__.get(fk_name) or getattr(self, fk_name, None)
            if delegate is not None:
                setattr(delegate, name, value)
                self.__dict__.setdefault('_inherits_dirty', set()).add(fk_name)
                return
        object.__setattr__(self, name, value)

    original_save = delegant_cls.save

    def save(self, *args, **kwargs):
        """Persiste el delegado ANTES que el delegante.

        El orden importa: el delegante guarda una FK al delegado, así que un
        delegado sin ``pk`` rompería la integridad. Ambos en la misma
        transacción — un delegado guardado con un delegante que falla es
        justamente la inconsistencia que la referencia evita.
        """
        dirty = self.__dict__.pop('_inherits_dirty', None)
        if not dirty:
            return original_save(self, *args, **kwargs)
        with transaction.atomic():
            delegate = getattr(self, fk_name, None)
            if delegate is not None:
                delegate.save()
            return original_save(self, *args, **kwargs)

    delegant_cls.__getattr__ = __getattr__
    delegant_cls.__setattr__ = __setattr__
    delegant_cls.save = save
    return delegated


def ensure_inherits():
    """Cablea la delegación de **todo** modelo registrado que declare ``_inherits``.

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
