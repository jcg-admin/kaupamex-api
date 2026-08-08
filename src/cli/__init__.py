"""``cli`` — registro de comandos del producto L0.

Espejo de ``odoo19c: odoo/cli/__init__.py``, que reexporta ``main`` desde
``command`` y deja el resto para importarse bajo demanda.

Diferencia de fondo con la referencia, y es intencional: allá ``odoo/cli/`` **es**
el registro (clase ``Command`` con auto-registro por ``__init_subclass__``,
``load_internal_commands`` y ``load_addons_commands``). Aquí el registro lo
provee Django —``BaseCommand`` + descubrimiento por app instalada— y este
paquete sólo aporta el ``main()`` que la referencia coloca en el mismo lugar.

Qué cubre Django, y qué NO (medido — H-API-329)
------------------------------------------------

Los dos registros **no son equivalentes**; producen la misma lista en nuestro
árbol porque hoy todo addon en disco está instalado (78 de 78, medido). Las
diferencias reales:

===========================  ==================================  ==================================
Eje                          ``odoo19c: cli/command.py``         Django ``core/management``
===========================  ==================================  ==================================
De dónde descubre            el **addons-path**                  sólo ``INSTALLED_APPS``
Qué importa al cargar        el módulo, sin el ``__init__``      la cadena completa de la app
Resolución                   perezosa, por nombre                dict completo, cacheado
Validación de nombre         regex + clase == módulo             ninguna
===========================  ==================================  ==================================

Al revés, Django aporta lo que la referencia no: preprocesado de
``--settings``/``--pythonpath``, autocompletado y la orquestación de
``django.setup()``.

**No se reimplementa el registro** — sería adoptar la *implementación* en vez de
la *forma*, el error que ``adaptacion-componentes-nativa.md`` documenta para el
lado UI. Pero la decisión se apoya en que la única diferencia con consecuencia
—descubrir fuera de ``INSTALLED_APPS``— hoy no aplica, no en que los registros
sean iguales. Si un addon llega a vivir en disco sin instalarse (lo que el
modelo de suscripción de módulos por empresa hace plausible), esa diferencia se
vuelve real: tarea #121.
"""

from .command import main  # noqa: F401

COMMAND = None
