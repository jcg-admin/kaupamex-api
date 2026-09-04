"""``ir.config_parameter`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/ir_config_parameter.py``
(LGPL-3, 31 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Cobertura: 3 de 3 símbolos — **3 portados**
============================================

.. list-table::
   :header-rows: 1
   :widths: 26 14 60

   * - Símbolo
     - Estado
     - Nota
   * - ``write`` (``:12``)
     - portado
     - como receptor de ``post_save`` (ver "El mecanismo" abajo)
   * - ``create`` (``:20``)
     - portado
     - el mismo receptor: Django funde crear y escribir en ``save``
   * - ``unlink`` (``:27``)
     - portado
     - como receptor de ``post_delete``

El mecanismo: una señal, no un override
=======================================

Los tres símbolos de la fuente son **enganches del ciclo de vida** de un
modelo ajeno, y este árbol ya tiene su forma para eso: una señal de Django
conectada desde ``ready()``. Es la misma resolución que ``account`` usa para
``load_chart_for_new_company`` y ``check_audit_trail_on_save``, y la que el
registro de divergencias cita para ``TotpSecret``.

No se encadenan con ``chain_method`` a propósito: su semántica de relevo
delega en la implementación previa **sólo si la nueva devuelve ``None``**, y
un enganche de ``save`` tiene que correr siempre, después del guardado. La
señal expresa exactamente ese "después", que es lo que ``super().write(vals)``
seguido del cuerpo significa en la fuente.

Y ``create`` no necesita receptor propio: Django funde crear y escribir en
``save``, así que el mismo ``post_save`` cubre los dos casos que la fuente
tiene que escribir por separado.

DIVERGENCIA DE MECANISMO declarada — la mitad de ``_setup_models__``
====================================================================

La fuente hace dos cosas al tocar ``crm.pls_fields``::

    self.env.flush_all()
    self.env.registry._setup_models__(self.env.cr, ['crm.lead'])

Aquí **la primera no aplica y la segunda no tiene receptor**:

- ``flush_all`` vacía la cola de escrituras diferidas del ORM de la fuente.
  Django escribe en el momento; no hay cola que vaciar. Medido: 0 hits de
  ``flush_all`` en ``src/``.
- ``_setup_models__`` reconstruye los descriptores de campo de un modelo. En
  Django la clase es estática: sus campos se declaran en Python y no se
  releen en ejecución. Medido: 0 hits de ``_setup_models__`` y de
  ``setup_models`` en ``src/orm/registry.py``.

**Lo que la fuente consigue con esos dos** —que ``crm.lead`` deje de ver la
lista vieja de campos de puntuación— aquí se consigue invalidando la familia
``stable``, que es donde ``SystemParameter._get_param`` memoriza su lectura
(``@ormcache('key', 'using', cache='stable')``). Nuestro
``CrmLead._pls_get_safe_fields`` lee el parámetro **en cada llamada** y filtra
por ``_has_field``, así que no hay ninguna lista cacheada por modelo que
reconstruir: la única copia viva es la del parámetro.

*Métrica:* ocurrencias de ``flush_all``/``_setup_models__`` en ``src/``, y
decoradores de caché sobre ``_pls_get_safe_fields``.
*Ciega a:* que un consumidor futuro memorice la lista de campos por su cuenta.
Si aparece, su invalidador se cuelga de este mismo receptor.
"""
from django.db import models as dj_models

from orm import registry

from addons.base.models.ir_config_parameter import SystemParameter

#: La clave que dispara la reconstrucción. Verbatim de la fuente (``:13``).
PLS_FIELDS_KEY = 'crm.pls_fields'


def rebuild_lead_on_pls_change(sender, instance, **kwargs):
    """≙ el cuerpo de ``write``/``create`` (``:12-25``).

    Corre **después** del guardado, que es donde la fuente lo pone
    (``result = super().write(vals)`` primero, cuerpo después).
    """
    if instance.key == PLS_FIELDS_KEY:
        registry.clear_cache('stable')


def rebuild_lead_on_pls_unlink(sender, instance, **kwargs):
    """≙ el cuerpo de ``unlink`` (``:27-33``).

    La fuente calcula ``pls_emptied`` **antes** del borrado y sólo actúa si el
    módulo no se está desinstalando. Aquí:

    - el "antes" lo da ``post_delete``, que recibe la instancia ya cargada;
    - la guarda ``MODULE_UNINSTALL_FLAG`` **no tiene contraparte** — medido: 0
      hits en ``src/`` y en ``addons/``. Es una bandera de contexto del
      desinstalador de la fuente, y este árbol no tiene ese desinstalador. Sin
      él la guarda no puede evaluarse; su ausencia sólo hace que se invalide un
      caché de más durante una desinstalación que aquí no ocurre.
    """
    if instance.key == PLS_FIELDS_KEY:
        registry.clear_cache('stable')


def apply_crm_extensions():
    """Conecta los dos receptores. La llama ``CrmConfig.ready()``."""
    dj_models.signals.post_save.connect(
        rebuild_lead_on_pls_change, sender=SystemParameter,
        dispatch_uid='crm.rebuild_lead_on_pls_change',
    )
    dj_models.signals.post_delete.connect(
        rebuild_lead_on_pls_unlink, sender=SystemParameter,
        dispatch_uid='crm.rebuild_lead_on_pls_unlink',
    )
