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
"""
import functools


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

    :param combine: ``f(nuevo, anterior) -> resultado``. Sin él, se aplica el
        relevo por ``None``.
    """
    previous = getattr(cls, name, None)
    if _already_in_chain(previous, func):
        return
    if previous is None:
        setattr(cls, name, func)
        return

    @functools.wraps(func)
    def chained(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        if combine is not None:
            return combine(result, previous(self, *args, **kwargs))
        return result if result is not None else previous(self, *args, **kwargs)

    # Después de ``wraps``: copia ``func.__dict__`` y borraría estas marcas.
    chained._chain_origin = func
    chained._chain_previous = previous
    setattr(cls, name, chained)


def extend_list(new, previous):
    """``combine`` para hooks que acumulan — ≙ ``super()[...] + [propio]``.

    El orden replica al de la referencia: primero lo que ya había, después lo
    que aporta el addon que se instala.
    """
    return list(previous or []) + list(new or [])
