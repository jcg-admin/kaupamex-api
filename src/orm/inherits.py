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
"""
from django.db import transaction


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
