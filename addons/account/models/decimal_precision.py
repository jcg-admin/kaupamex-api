r"""``decimal.precision`` extendido por ``account`` — la pila de recursión del
descuento.

Adaptación de ``addons/account/models/decimal_precision.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
====================================

La referencia sobreescribe un único método, ``precision_get``. Se porta
entero, con el mecanismo que lo activa construido (ver abajo) — no es
divergencia, es la excepción sancionada por ``porte-completo-no-parcial.md``:
*"si el stack no trae el mecanismo, se construye"*.

Qué hace la referencia
========================

Dentro de un tramo marcado ``account_disable_recursion_stack
.ignore_discount_precision`` en ``self.env.cr.cache`` (la caché por-cursor de
la referencia — vive mientras dura la transacción SQL en curso), dos usos
concretos devuelven una precisión FIJA en vez de la que declare la fila de
``decimal.precision``: 13 dígitos para ``'Discount'``, 10 para
``'Product Unit'``. Fuera de ese tramo, cae al comportamiento normal
(``super().precision_get(application)``).

El propósito: evitar que un cálculo de descuento recursivo (una línea que
recalcula su propio descuento a partir de un total ya redondeado) pierda
dígitos de precisión intermedios por el redondeo declarado del uso.

Construcción — ``threading.local()`` en vez de caché por-cursor
===================================================================

Django no tiene una caché por-cursor equivalente a ``env.cr.cache``. Lo más
cercano —y lo que ya usa este árbol para estado que vive "durante esta
operación, en este hilo de ejecución" (``orm/environments.py``: ``uid``,
empresas activas)— es ``threading.local()``: misma familia de mecanismo,
alcance por hilo en vez de por transacción SQL, sin persistencia entre
peticiones.

Se implementa aquí como un contador (no un booleano) porque un cálculo
recursivo puede entrar al tramo más de una vez; un booleano simple lo
desactivaría al salir de la llamada interior mientras la exterior sigue
activa.

Divergencia declarada — el override del classmethod
=======================================================

La referencia usa herencia Python normal (``super()`` dentro del método
sobreescrito de la subclase Odoo). Este ORM no tiene subclases de modelo por
addon: ``DecimalPrecision.precision_get`` es un **único** classmethod que
``base`` declara y que **seis** sitios de ``stock`` llaman directamente
(``DecimalPrecision.precision_get('Product Unit')`` — medido:
``grep -rn "DecimalPrecision.precision_get" addons/`` → 6 hits, todos en
``stock/models/stock_move.py`` y ``stock_scrap.py``). Reemplazarlo en el sitio
—guardando la función original para invocarla como el ``super()`` de la
referencia— es lo único que preserva esos 6 call-sites sin tocarlos: siguen
llamando al mismo símbolo, que ahora consulta la pila antes de delegar.
"""
import threading

from addons.base.models.decimal_precision import DecimalPrecision

#: Estado por-hilo — el análogo de ``env.cr.cache`` que este ORM no tiene.
_local = threading.local()


class ignore_discount_precision:
    """Context manager — ≙ marcar ``account_disable_recursion_stack
    .ignore_discount_precision`` en la caché por-cursor de la referencia
    (``odoo19c: decimal_precision.py:10``).

    Contador reentrante, no booleano: un cálculo recursivo puede entrar al
    tramo más de una vez, y el interior no debe apagar el flag del exterior
    al salir.
    """

    def __enter__(self):
        _local.depth = getattr(_local, 'depth', 0) + 1
        return self

    def __exit__(self, exc_type, exc, tb):
        _local.depth -= 1
        return False


def ignore_discount_precision_active():
    """¿El hilo actual está dentro de un tramo ``ignore_discount_precision``?"""
    return getattr(_local, 'depth', 0) > 0


#: El classmethod original de ``base``, capturado ANTES de reemplazarlo — es
#: el ``super().precision_get(application)`` de la referencia.
_original_precision_get = DecimalPrecision.precision_get.__func__


def precision_get(cls, application):
    """≙ ``precision_get`` de ``account`` (``odoo19c: decimal_precision.py:8-15``).

    Dentro de :class:`ignore_discount_precision`, fija 13 dígitos para
    ``'Discount'`` y 10 para ``'Product Unit'``. Fuera del tramo, o para
    cualquier otro uso, delega al classmethod original de ``base``.
    """
    if ignore_discount_precision_active():
        if application == 'Discount':
            return 13
        if application == 'Product Unit':
            return 10
    return _original_precision_get(cls, application)


def apply_account_extensions():
    """≙ ``_inherit = 'decimal.precision'`` de ``account``.

    Se llama desde ``AccountConfig.ready()``. Reemplaza el classmethod en el
    sitio — no hay ``add_to_class`` que aplicar, así que la idempotencia se
    guarda con un marcador explícito en vez del ``hasattr`` que usan las
    extensiones que sólo añaden campos/métodos nuevos (aquí el símbolo YA
    existe; lo que hay que evitar es parchearlo dos veces).
    """
    if getattr(DecimalPrecision, '_account_precision_get_patched', False):
        return
    DecimalPrecision.precision_get = classmethod(precision_get)
    DecimalPrecision._account_precision_get_patched = True
