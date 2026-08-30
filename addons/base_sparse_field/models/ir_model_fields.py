"""Lo que ``base_sparse_field`` le cuelga a ``ir.model.fields`` (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/base_sparse_field/models/models.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). Es la **otra mitad** del addon: el
archivo hermano ``fields.py`` porta el campo (``Serialized``/``Sparse``); éste
porta el registro, para que un campo disperso **aparezca en el catálogo** con
su campo serializado nombrado.

Los siete símbolos de la referencia, con su veredicto
=====================================================

``porte-completo-no-parcial.md`` exige que cada símbolo se porte o declare por
qué no. Los siete de ``models.py``:

=================================== ==============================================
Símbolo de la referencia            Veredicto
=================================== ==============================================
``IrModelFields.ttype`` (+serialized) portado — ``add_serialized_ttype()``
``IrModelFields.serialization_field_id`` portado — ``add_to_class`` desde ``ready()``
``IrModelFields.write`` (guarda)      portado — encadenado sobre ``save``
``IrModelFields._reflect_fields``     portado — encadenado sobre ``_reflect_fields``
``Sparse_FieldsTest``                 portado — ``models/sparse_fields_test.py``
``Base._valid_field_parameter``       divergencia de mecanismo (abajo)
``IrModelFields._instanciate_attrs``  divergencia de mecanismo (abajo)
=================================== ==============================================

``_valid_field_parameter`` — no hay parámetro que validar
----------------------------------------------------------

La referencia declara un campo disperso como ``fields.Integer(sparse='data')``
y ``_valid_field_parameter`` existe para que su ORM **acepte** ese ``kwarg``
sin avisar. Aquí no hay tal ``kwarg``: ``api@0a9a0fb`` midió que la clase base
de este puerto es ``django.db.models.Field``, del framework, y que rechaza el
argumento::

    models.CharField(max_length=10, sparse='data')
    -> TypeError: Field.__init__() got an unexpected keyword argument 'sparse'

Por eso ``Sparse`` es un descriptor propio (``fields.Sparse('data')``) y no un
``kwarg``. Un validador de parámetros que nadie puede pasar no tiene conducta
que replicar. La divergencia está medida y declarada en ``fields.py``.

``_instanciate_attrs`` — la maquinaria de campos manuales no está portada
-------------------------------------------------------------------------

Ese método traduce **una fila de la base** en los atributos con que la
referencia instancia un campo en caliente: lee ``serialization_field_id`` y
devuelve ``attrs['sparse'] = <nombre>``. Pertenece a ``_add_manual_models`` /
``_instanciate``, que ``base/models/ir_model.py`` ya declaró NO portadas con
su medición: *"Django construye su registro al importar y lo congela
(``apps.populate``); no hay equivalente"*.

Consecuencia declarada, y es la que da forma a este archivo: aquí
``serialization_field_id`` es **registro**, no insumo. Nada lo lee para
reconstruir un campo — se escribe para que el catálogo diga la verdad sobre
qué campo disperso vive en qué serializado. Es el mismo criterio con que ese
archivo porta ``IrModelConstraint`` e ``IrModelRelation``: *"se portan como
registro —que es lo que aporta trazabilidad— sin el ejecutor de DDL"*.

Por qué la corrección de ``ttype`` va en ``ttype_for`` y no en la reflexión
===========================================================================

En la referencia un campo serializado **se sabe** ``serialized``: es el
``type`` de su clase. Aquí ``Serialized`` es un ``JSONField``, así que el
instrumento de la reflexión lo confunde con cualquier otro JSON. Medido antes
de decidir::

    Serialized().get_internal_type()        -> 'JSONField'
    IrModelFields.ttype_for(Serialized())   -> 'json'

Corregirlo dentro de ``_reflect_fields`` no bastaría: ``_reflect_fields`` es
quien escribe la fila, y su ``update_or_create`` volvería a poner ``json``
cada vez que corriera. La corrección va donde nace el valor —``ttype_for``—
encadenada con el relevo por ``None`` de ``orm/method_chain.py``: si el campo
es ``Serialized`` responde ``serialized``, y si no, deja pasar al mapa de
siempre. Así el orden de las dos pasadas deja de importar.
"""
import fields
import models
from exceptions import UserError

from addons.base.models.ir_model import STATE_BASE, IrModelFields
from addons.base_sparse_field.models.fields import Serialized, Sparse
from orm.method_chain import chain_method

#: Clave de tipo que la referencia añade al vocabulario de ``ttype``
#: (``odoo19c: base_sparse_field/models/models.py:19-21``).
SERIALIZED_TTYPE = 'serialized'


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que
    ya existe rompe con ``FieldError``. Mismo ayudante que
    ``l10n_mx/models/res_bank.py`` y ``account/models/res_company.py``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def add_serialized_ttype():
    """≙ ``ttype = fields.Selection(selection_add=[('serialized', …)])``.

    ``FIELD_TYPES`` se **deriva** de ``orm.fields.__all__``
    (``base/models/ir_model.py``), y ``Serialized`` no está ahí: vive en este
    addon, y el núcleo no lo importa a propósito (:ref:`h-api-556`). Así que
    el hueco que la referencia rellena con ``selection_add`` es un hueco real
    aquí también — medido: ``FIELD_TYPES`` trae **20** claves y ninguna es
    ``serialized``.

    Se extiende el ``choices`` del campo vivo, que es donde Django valida.
    ``ondelete={'serialized': 'cascade'}`` de la referencia no tiene
    equivalente: es su política para las filas que quedan al DESinstalar el
    módulo que aportó el valor, y aquí la instalación es ``INSTALLED_APPS``
    —no hay desinstalación que dispare esa limpieza—.
    """
    ttype = IrModelFields._meta.get_field('ttype')
    if any(key == SERIALIZED_TTYPE for key, _label in ttype.choices):
        return
    ttype.choices = list(ttype.choices) + [(SERIALIZED_TTYPE, SERIALIZED_TTYPE)]


def add_serialization_field():
    """≙ ``serialization_field_id = fields.Many2one('ir.model.fields', …)``.

    El ``domain`` de la referencia —``[('ttype','=','serialized'),
    ('model_id','=',model_id)]``— no es un ``kwarg`` de Django; se porta como
    ``limit_choices_to``, que es el constructor que cumple el mismo papel
    (acotar el conjunto elegible). La mitad ``model_id`` de ese dominio **no**
    cabe ahí: ``limit_choices_to`` no puede referirse a otro campo de la misma
    fila. Esa mitad la hace cumplir ``check_sparse_write`` abajo, que sí ve la
    fila entera.
    """
    _add_if_absent(IrModelFields, 'serialization_field_id', fields.Many2one(
        'base.IrModelFields', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sparse_field_ids', verbose_name='Campo de serialización',
        limit_choices_to={'ttype': SERIALIZED_TTYPE},
        help_text='Si está puesto, el campo se guarda dentro de la estructura '
                  'dispersa del campo de serialización en vez de tener columna '
                  'propia. No se puede cambiar después de crearlo.',
        db_column='serialization_field_id',
    ))


def check_sparse_write(self, *args, **kwargs):
    """≙ ``write`` de la referencia: ni renombrar el campo ni mudar su almacén.

    La referencia lo declara como limitación explícita en su comentario:
    *"renaming a sparse field or changing the storing system is currently not
    allowed"*. Se conserva entera, incluida la asimetría — cambiar el almacén
    está prohibido **siempre**; renombrar, sólo si el campo es disperso.

    Encadenado sobre ``save`` con el relevo por ``None``: devuelve ``None``,
    así que tras validar corre el ``save`` real. El estado anterior se lee de
    la base porque en Django la instancia ya trae los valores nuevos — la
    referencia no tiene ese problema, su ``write`` recibe ``vals`` aparte.
    """
    if self.pk:
        previous = type(self).objects.filter(pk=self.pk).values(
            'name', 'serialization_field_id').first()
        if previous is not None:
            if previous['serialization_field_id'] != self.serialization_field_id_id:
                raise UserError(
                    f'No se permite cambiar el sistema de almacenamiento del '
                    f'campo "{previous["name"]}".')
            if previous['serialization_field_id'] and previous['name'] != self.name:
                raise UserError(
                    f'No se permite renombrar el campo disperso '
                    f'"{previous["name"]}".')
    return None


def sparse_ttype_for(field):
    """≙ que ``Serialized.type`` sea ``'serialized'`` en la referencia.

    Encadenado sobre ``ttype_for`` con el relevo por ``None``: reclama sólo el
    campo serializado y deja pasar todo lo demás al mapa de
    ``DJANGO_TYPE_TO_TTYPE``. Ver el encabezado del módulo para por qué la
    corrección va aquí y no en la reflexión.
    """
    if isinstance(field, Serialized):
        return SERIALIZED_TTYPE
    return None


def sparse_descriptors_of(model):
    """Los descriptores ``Sparse`` declarados en el modelo, con su nombre.

    Recorre el ``__mro__`` porque un ``Sparse`` heredado es tan campo del
    modelo como uno propio, y ``contribute_to_class`` lo deja como atributo de
    clase —no en ``_meta``, que es justo el punto: no tiene columna—.

    *Métrica:* atributos de clase que son instancias de ``Sparse``.
    *Ciega a:* un campo disperso declarado de otra forma (una ``property`` que
    lea el mapa a mano). Esa forma no existe hoy en el árbol y no se inventa
    aquí un detector para ella.
    """
    encontrados = {}
    for klass in reversed(model.__mro__):
        for name, attr in vars(klass).items():
            if isinstance(attr, Sparse):
                encontrados[name] = attr
    return encontrados


def reflect_sparse_fields(cls, model_row):
    """≙ ``_reflect_fields``: pone ``serialization_field_id`` en los dispersos.

    La referencia hace esta pasada **después** de la de su ``super()`` con un
    motivo escrito: *"it is done here to ensure that the serialized field is
    reflected already"*. Aquí el orden no se puede imponer —el encadenado corre
    el nuevo primero—, así que la dependencia se resuelve en vez de ordenarse:
    la fila del campo serializado se obtiene con ``get_or_create``, y la pasada
    de ``base`` la completa después con su ``update_or_create``. Las dos son
    idempotentes sobre la misma clave ``(model, name)``, y ninguna toca el
    campo de la otra.

    Un ``Sparse`` **no aparece** en ``model._meta.get_fields()`` —no tiene
    columna—, así que ``base`` nunca crea su fila: crearla es parte de este
    porte, no un extra.

    El ``ttype`` de la fila dispersa sale de lo que el descriptor declara
    (``relational_model`` → ``many2one``; ``coerce`` conocido → su clave) y cae
    a ``char`` cuando no declara ninguno — el **mismo** respaldo que usa
    ``ttype_for`` en ``base``, no uno inventado aquí. La referencia no lo
    necesita porque allí el tipo viaja en la clase del campo.

    :raises UserError: si un ``Sparse`` nombra un serializado que no existe —
        ≙ *"Serialization field %s not found for sparse field %s!"*.
    """
    model = model_row.django_model
    if model is None:
        return 0, 0
    dispersos = sparse_descriptors_of(model)
    if not dispersos:
        return 0, 0

    serializados = {
        campo.name: campo for campo in model._meta.get_fields()
        if isinstance(campo, Serialized)
    }
    creados = actualizados = 0
    for name, descriptor in dispersos.items():
        contenedor = serializados.get(descriptor.sparse)
        if contenedor is None:
            raise UserError(
                f'No se encontró el campo de serialización '
                f'"{descriptor.sparse}" del campo disperso "{name}".')
        fila_contenedor, _creada = cls.objects.get_or_create(
            model=model_row.model, name=contenedor.name,
            defaults={
                'model_id': model_row,
                'ttype': SERIALIZED_TTYPE,
                'state': STATE_BASE,
            },
        )
        _fila, fue_creada = cls.objects.update_or_create(
            model=model_row.model, name=name,
            defaults={
                'model_id': model_row,
                'ttype': _ttype_of_sparse(descriptor),
                'field_description': name,
                'help': descriptor.help_text or '',
                'store': False,
                'state': STATE_BASE,
                'serialization_field_id': fila_contenedor,
            },
        )
        creados += fue_creada
        actualizados += not fue_creada
    return creados, actualizados


#: Lo que un ``Sparse`` alcanza a declarar de su tipo. Corto a propósito: el
#: descriptor guarda un conversor, no una clave de tipo, así que este mapa
#: cubre los conversores que el propio ``fields.py`` documenta como el motivo
#: de existir de ``coerce`` (``int`` frente a ``float``, y ``Decimal``).
_COERCE_TO_TTYPE = {
    int: 'integer',
    float: 'float',
    bool: 'boolean',
    str: 'char',
}


def _ttype_of_sparse(descriptor):
    """Clave de tipo de un campo disperso, o ``char`` si no declara ninguna."""
    if descriptor.relational_model is not None:
        return 'many2one'
    return _COERCE_TO_TTYPE.get(descriptor.coerce, 'char')


def sum_counters(nuevo, anterior):
    """Suma los ``(creados, actualizados)`` de las dos pasadas de reflexión."""
    return (nuevo[0] + anterior[0], nuevo[1] + anterior[1])


def apply_base_sparse_field_extensions():
    """Cuelga las cuatro piezas sobre ``ir.model.fields``.

    Se llama desde ``BaseSparseFieldConfig.ready()``, no al importar: en tiempo
    de import el registro de modelos aún no está poblado y ``add_to_class``
    fallaría con ``AppRegistryNotReady``.
    """
    add_serialized_ttype()
    add_serialization_field()
    chain_method(IrModelFields, 'ttype_for', staticmethod(sparse_ttype_for))
    chain_method(IrModelFields, 'save', check_sparse_write)
    chain_method(IrModelFields, '_reflect_fields',
                 classmethod(reflect_sparse_fields), combine=sum_counters)
