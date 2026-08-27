"""El equivalente de ``super()`` para el idioma de extensión por ``setattr``.

Un addon que extiende un modelo ajeno lo hace aquí colgando funciones de
módulo sobre la clase desde su ``AppConfig.ready()`` — es como este árbol
materializa el ``_inherit`` de la referencia. Ese idioma **no tiene
``super()``**: dos addons que extienden el mismo método del mismo modelo se
pisan, y el que gana depende del orden de ``INSTALLED_APPS``.

En la referencia el problema no existe porque ``_inherit`` construye una MRO
real y cada override llama a ``super()``. Medido en
``odoo19c: account_qr_code_{sepa,emv}/models/res_bank.py``: **5 llamadas a
``super()`` en cada archivo**, y los dos addons extienden los mismos cinco
métodos de ``res.partner.bank``, despachando por ``qr_method``.

El episodio que lo destapó (:ref:`h-api-364`): ambos satélites se portaron en
paralelo, cada uno instaló sus métodos con la guarda ``if not hasattr(...)``
—correcta para **campos**, que no deben duplicar columna; catastrófica para
**overrides**, cuyo propósito es precisamente añadirse a lo que ya hay— y
``account_qr_code_emv`` ganó por ir antes en ``INSTALLED_APPS``. Los cinco
métodos de ``account_qr_code_sepa`` no se instalaron nunca. No lo vio ningún
gate estático: lo vieron sus 14 tests, al correr el sistema cableado.

Uso::

    from orm.method_chain import chain_method, extend_list

    chain_method(ResPartnerBank, '_get_qr_vals', _get_qr_vals)
    chain_method(ResPartnerBank, '_get_available_qr_methods',
                 _get_available_qr_methods, combine=extend_list)

Dos semánticas, porque la referencia usa las dos:

- **Relevo** (default) — el override atiende lo suyo y devuelve ``None`` para
  lo ajeno; entonces se delega en la implementación previa. Es la forma de
  ``if qr_method == 'sct_qr': ... ; return super()._get_qr_vals(...)``. La
  previa se invoca **de forma perezosa**: sólo si la nueva devolvió ``None``.
- **Combinación** (``combine=``) — el resultado de ambas se funde. Es la forma
  de ``rslt = super()._get_available_qr_methods(); rslt.append(...)``. Aquí sí
  se invocan las dos, porque ésa es la semántica.

Descriptores: el tipo del método base fija la forma de ``func``
=================================================================

El método previo puede estar declarado como ``@classmethod`` o
``@staticmethod``, no sólo como método de instancia. Los tres se encadenan, y
**``func`` recibe lo mismo que recibe el método base**:

======================  ==========================  ==========================
Base declarado como     Firma de ``func``           Cómo queda instalado
======================  ==========================  ==========================
método de instancia     ``def f(self, ...)``        función simple
``@classmethod``        ``def f(cls, ...)``         ``classmethod(chained)``
``@staticmethod``       ``def f(...)``              ``staticmethod(chained)``
======================  ==========================  ==========================

Por qué hace falta decirlo (:ref:`h-api-381`): ``getattr(cls, name)`` sobre un
``@classmethod`` devuelve un método **ya ligado** a ``cls``, así que reinvocarlo
como ``previous(self, ...)`` pasa la instancia como argumento posicional extra
—``TypeError``— y ``setattr(cls, name, chained)`` instala una función plana,
destruyendo el descriptor: ``Cls.metodo(x)`` pasaría ``x`` como ``self``. Por
eso la implementación previa se resuelve **cruda** recorriendo el ``__mro__``
(``cls.__dict__``), nunca con ``getattr``, y se reinstala envuelta en el mismo
descriptor que tenía.
"""
import functools
import types

#: Marcas que ``_already_in_chain`` recorre. Viven en la función envoltorio,
#: no en el descriptor: un ``classmethod`` no acepta atributos propios.
_ORIGIN = '_chain_origin'
_PREVIOUS = '_chain_previous'


def _previous_of(cls, name):
    """La implementación previa **sin ligar**, y su tipo de descriptor.

    Devuelve ``(function, wrapper)`` donde ``wrapper`` es ``classmethod``,
    ``staticmethod`` o ``None`` (método de instancia). ``(None, None)`` cuando
    no hay nada que encadenar.

    Recorre el ``__mro__`` en vez de usar ``getattr`` porque ``getattr`` ya
    aplica el protocolo de descriptor: sobre un ``@classmethod`` devuelve un
    método ligado a ``cls``, que es exactamente la información que aquí hay que
    conservar sin consumir.

    :raises TypeError: si el atributo existe pero no es un método —una
        ``property``, el descriptor de un campo—. Encadenar ahí no tiene
        semántica definida, y **instalar encima destruiría el descriptor en
        silencio**: medido, una ``property`` sustituida por una función plana
        hace que ``obj.value`` devuelva el método en vez de su valor. Este
        mecanismo existe para no pisar nada en silencio (:ref:`h-api-364`), así
        que aquí falla ruidoso.
    """
    for klass in getattr(cls, '__mro__', (cls,)):
        if name not in klass.__dict__:
            continue
        raw = klass.__dict__[name]
        if isinstance(raw, classmethod):
            return raw.__func__, classmethod
        if isinstance(raw, staticmethod):
            return raw.__func__, staticmethod
        if isinstance(raw, types.FunctionType):
            return raw, None
        raise TypeError(
            f'{cls.__name__}.{name} es {type(raw).__name__}, no un método: '
            f'chain_method no sabe encadenarlo y no lo va a sobreescribir.')
    return None, None


def _already_in_chain(current, func):
    """¿``func`` ya está instalada en la cadena que cuelga de ``current``?

    ``ready()`` puede correr más de una vez en el mismo proceso (recarga del
    autoreloader) y los tests llaman a ``apply_*_extensions()`` explícitamente.
    Sin este recorrido, cada llamada envolvería otra vez y un hook acumulativo
    devolvería duplicados — medido: ``_get_available_qr_methods`` daba **7**
    entradas en vez de 2 tras varias aplicaciones.
    """
    while current is not None:
        if current is func or getattr(current, '_chain_origin', None) is func:
            return True
        current = getattr(current, '_chain_previous', None)
    return False


def chain_method(cls, name, func, combine=None):
    """Instala ``func`` como ``cls.name`` preservando la implementación previa.

    Si no había previa, instala ``func`` tal cual. Si la había, instala un
    envoltorio que encadena — el equivalente del ``super()`` que este idioma
    no tiene. **Idempotente**: reinstalar la misma ``func`` es un no-op.

    El descriptor del método previo se preserva: si era ``@classmethod`` o
    ``@staticmethod``, la cadena se reinstala envuelta igual. Ver la tabla del
    docstring del módulo para la firma que debe tener ``func`` en cada caso.

    :param combine: ``f(nuevo, anterior) -> resultado``. Sin él, se aplica el
        relevo por ``None``.
    """
    new_wrapper = None
    if isinstance(func, (classmethod, staticmethod)):
        new_wrapper = type(func)
        func = func.__func__

    # ``previous is None`` cubre dos casos que se tratan igual: no había nada,
    # o lo que hay no es un método (``property``, descriptor de campo) y por
    # tanto no es el caso de uso de esta herramienta.
    previous, wrapper = _previous_of(cls, name)
    if _already_in_chain(previous, func):
        return
    if previous is None:
        setattr(cls, name, new_wrapper(func) if new_wrapper else func)
        return

    if wrapper is staticmethod:
        @functools.wraps(func)
        def chained(*args, **kwargs):
            result = func(*args, **kwargs)
            if combine is not None:
                return combine(result, previous(*args, **kwargs))
            return result if result is not None else previous(*args, **kwargs)
    else:
        # ``first`` es ``self`` en un método de instancia y ``cls`` en un
        # ``@classmethod``: el mismo cuerpo sirve para los dos porque
        # ``previous`` está SIN ligar y lo recibe explícito.
        @functools.wraps(func)
        def chained(first, *args, **kwargs):
            result = func(first, *args, **kwargs)
            if combine is not None:
                return combine(result, previous(first, *args, **kwargs))
            return (result if result is not None
                    else previous(first, *args, **kwargs))

    # Después de ``wraps``: copia ``func.__dict__`` y borraría estas marcas.
    setattr(chained, _ORIGIN, func)
    setattr(chained, _PREVIOUS, previous)
    setattr(cls, name, wrapper(chained) if wrapper else chained)


def extend_list(new, previous):
    """``combine`` para hooks que acumulan — ≙ ``super()[...] + [propio]``.

    El orden replica al de la referencia: primero lo que ya había, después lo
    que aporta el addon que se instala.
    """
    return list(previous or []) + list(new or [])


def keep_previous(new, previous):
    """``combine`` de relevo INVERSO — ≙ ``r = super()(); if r is not None: return r``.

    El relevo por defecto de :func:`chain_method` da la precedencia al addon
    que se instala **después**: corre ``func`` primero y sólo cae en la previa
    si devolvió ``None``. La referencia hace lo contrario en toda una familia
    de métodos: consulta ``super()`` **primero** y sólo aporta lo suyo si el
    eslabón interno no respondió::

        # odoo19c: auth_totp_mail/models/res_users.py:116-125
        def _mfa_type(self):
            r = super()._mfa_type()
            if r is not None:
                return r
            ...                       # sólo si el interno calló

    Con ese idioma la precedencia la gana el addon **más interno** —el que se
    instaló antes— y el orden lo fija la cadena de ``depends``. Ejemplo medido:
    ``auth_totp`` declara ``'totp'`` y ``auth_totp_mail`` declara ``'totp_mail'``;
    un usuario con la app configurada **y** la política activa obtiene ``'totp'``,
    porque ``auth_totp_mail`` depende de ``auth_totp`` y por tanto va después.

    Sin este ``combine`` la cadena devolvería ``'totp_mail'`` — misma población,
    precedencia invertida, y ningún gate lo vería: los dos valores son válidos.

    **Divergencia declarada:** un ``combine`` invoca las dos implementaciones,
    así que el cuerpo del eslabón externo corre aunque el interno ya haya
    respondido — en la referencia el ``if r is not None: return r`` lo salta.
    Es equivalente mientras los cuerpos sean consultas puras, que es el caso de
    esta familia. Un eslabón con efectos secundarios NO puede usar este
    ``combine``: necesita el relevo perezoso, y entonces su precedencia es la
    contraria.
    """
    return previous if previous is not None else new


def merge_dict(new, previous):
    """``combine`` para el override que ENRIQUECE un diccionario.

    ≙ el idioma ``res = super()._format_settings(...); res['x'] = ...; return
    res`` (``odoo19c: addons/web/models/res_users_settings.py:9-14``): el
    eslabón externo no reemplaza el formato, le añade su clave.

    El relevo por defecto no sirve para esta familia y el modo de fallo es
    silencioso: un diccionario vacío **no es ``None``**, así que
    :func:`chain_method` lo da por respuesta buena y nunca invoca la previa.
    Medido en ``res.users.settings``: el eslabón de ``web`` arrancaba en
    ``{}`` y el formato perdía ``id`` y ``user`` — el porte de base entregaba
    los cinco métodos y su resultado no llegaba a ningún llamador.

    Las claves de ``new`` ganan sobre las de ``previous``, que es el orden del
    idioma que replica: el override escribe **después** de leer a ``super()``.
    """
    return {**(previous or {}), **(new or {})}
