"""Decoradores del ORM — fiel a ``odoo/orm/decorators.py`` (Odoo 19).

En Odoo 19 los decoradores ``@api.depends``/``@api.constrains``/``@api.model``…
se **definen** en ``odoo/orm/decorators.py`` y ``odoo/api/__init__.py`` los
re-exporta. Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``),
esta es la **definición**; ``src/api/__init__.py`` (≙ ``odoo/api/__init__.py``)
la re-exporta como el namespace ``api``.

Django no tiene el motor de dependencias del ORM de Odoo: el cómputo se ejecuta
en ``save()`` y la validación en ``clean()``. Estos decoradores **no cambian el
comportamiento** (devuelven la función tal cual) y anotan el metadato ``_odoo_*``
con los campos declarados; permiten conservar el decorador sobre el método
portado para expresar la intención Odoo — el ``save()``/``clean()`` del modelo
es quien realmente los llama.
"""

__all__ = [
    'attrsetter', 'depends', 'constrains', 'onchange', 'model',
    'model_create_multi', 'returns', 'autovacuum',
]


def attrsetter(attr, value):
    """Devuelve una función que fija ``attr`` en su argumento y lo devuelve.

    ≙ ``attrsetter`` (``odoo19c: odoo/orm/decorators.py:73-79``). Docstring de
    la fuente, verbatim: *"Return a function that sets ``attr`` on its argument
    and returns it"*.

    Devolver el argumento es lo que la hace componible: dos ``attrsetter``
    apilados sobre el mismo método dejan las dos marcas, porque el de dentro
    entrega al de fuera lo mismo que recibió.
    """
    def setter(method):
        setattr(method, attr, value)
        return method

    return setter


def depends(*fields):
    def deco(func):
        func._depends = fields
        return func
    return deco


def constrains(*fields):
    def deco(func):
        func._constrains = fields
        return func
    return deco


def onchange(*fields):
    def deco(func):
        func._onchange = fields
        return func
    return deco


def _mark(method, attr):
    """Deja ``attr`` en la función, atravesando ``classmethod``/``staticmethod``.

    Un objeto ``classmethod`` no admite atributos arbitrarios, pero su
    ``__func__`` sí — y ``getattr`` sobre el método ligado delega en él, así que
    el marcador se lee igual desde la clase. Hace falta porque en este árbol un
    método de nivel de modelo se escribe ``@api.model`` sobre un ``classmethod``
    (``addons/product/models/product_template.py:400``), forma que la referencia
    no tiene.

    El cuerpo es :func:`attrsetter` con el valor fijo en ``True``; lo único
    propio es **sobre qué** lo aplica. Escribir el ``setattr`` aquí otra vez
    sería la segunda fuente de verdad que ``calibration-verified-numbers.md``
    prohíbe, y divergiría el día que la fuente cambie el suyo.
    """
    attrsetter(attr, True)(getattr(method, '__func__', method))
    return method


def model(method):
    """≙ ``odoo19c: odoo/orm/decorators.py:313`` — ``method._api_model = True``.

    Marca el método como de **nivel de modelo**: opera sobre el modelo, no sobre
    registros concretos. El dispatcher ``/json/2`` lo lee para rechazar con 422
    una llamada que además traiga ``ids``.

    Era ``return func`` —un no-op con el nombre de la referencia— hasta
    :ref:`h-api-639`.
    """
    return _mark(method, '_api_model')


def model_create_multi(method):
    """≙ ``odoo19c: odoo/orm/decorators.py:371`` — ``create._api_model = True``.

    La referencia marca el ``create`` multi con el **mismo** atributo que
    ``model``: crear no parte de registros existentes.
    """
    return _mark(method, '_api_model')


def returns(*args, **kwargs):
    def deco(func):
        return func
    return deco


def autovacuum(method):
    """Marca un método para que lo llame el barrido de ``ir.autovacuum``.

    Fiel a ``odoo/orm/decorators.py:299-310`` (``odoo19c:``), incluida la
    aserción de que el nombre sea privado: allá el mensaje es *"autovacuum
    methods must be private"*. Sirve para tareas de recolección que no ameritan
    un cron propio.

    El valor de retorno puede ser la tupla ``(hechos, restantes)``; si
    ``restantes`` es verdadero, el colector vuelve a encolar el método.
    """
    assert method.__name__.startswith('_'), (
        '%s: los métodos de autovacuum deben ser privados' % method.__name__
    )
    method._autovacuum = True
    return method


def private(method):
    """Marca un método público como **no invocable remotamente**.

    ≙ ``odoo19c: odoo/orm/decorators.py:private``. Su docstring lo encuadra: si
    un método de negocio no debe llamarse por RPC, lo natural es prefijarlo con
    ``_``; este decorador existe para los que **ya son públicos** y pasan a no
    serlo, y para los métodos del propio ORM.

    Lo consulta ``service.model.get_public_method`` recorriendo el MRO: un
    ancestro puede volver privado un nombre que la subclase redefine.
    """
    method._api_private = True
    return method


def readonly(method):
    """Declara que el método puede correr con un cursor de sólo lectura.

    ≙ ``odoo19c: odoo/orm/decorators.py:readonly``. Lo consulta el selector de
    cursor del despacho genérico (``_web_json_2_rpc_readonly`` en la
    referencia), que recorre el MRO buscando el primer ``_readonly`` declarado.
    """
    method._readonly = True
    return method
