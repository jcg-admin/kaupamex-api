"""``ir.profile`` — resultados de perfilado guardados.

Adaptación fiel de ``odoo/addons/base/models/ir_profile.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 251 líneas). La referencia declara
**dos** modelos en este archivo, y aquí también: ``ir.profile`` (una ejecución
de perfilado con sus trazas) y ``base.enable.profiling.wizard`` (el asistente
que habilita el perfilado por un rato acotado).

El modelo entero, campo por campo
=================================

Todas las columnas de la referencia se portan con su nombre y su tipo:
``session`` (indexada), ``name``, ``duration`` y ``cpu_duration`` (ambas
``digits=(9, 3)`` → ``max_digits=9, decimal_places=3``), ``init_stack_trace``,
``sql``, ``sql_count``, ``traces_async``, ``traces_sync``, ``others``,
``qweb`` y ``entry_count``. Y los **tres campos computados** del visor —
``speedscope``, ``speedscope_url`` y ``config_url``— con el mecanismo sin
columna que este árbol construyó para el ``store=False`` de la fuente.

El ``prefetch=False`` que la referencia pone en los cinco campos de traza es
una directiva de su ORM: "no traigas esta columna al leer el registro, pesa
demasiado". El equivalente de Django es ``.defer()`` en el queryset, que es
propiedad del consumidor y no del campo — por eso el manager por defecto
difiere los cinco: leer una lista de perfiles no debe arrastrar megabytes de
JSON. ``objects_full`` los trae cuando sí se necesitan, y es el manager que
debe usar quien vaya a generar un speedscope: con ``objects`` cada traza se
carga en una consulta aparte al tocarla.

``_log_access = False`` de la referencia (con el comentario *"avoid useless
foreign key on res_user"*) se respeta: el modelo hereda de ``TimeStampedModel``
por las marcas de tiempo, y **no** lleva FK a usuario.

El ``self`` de la fuente es un CONJUNTO, y aquí son dos objetos
===============================================================

Siete símbolos de la referencia operan sobre un **recordset**, no sobre una
fila: ``_has_memory_traces`` recorre ``for profile in self``,
``_generate_speedscope`` lee ``self[0].init_stack_trace`` y compara ``len(self)
> 1``, ``action_view_speedscope`` une los ids con coma. Su llamador real lo
confirma — ``odoo19c: addons/web/controllers/profiling.py:33-48`` invoca
``profiles._default_profile_params()``, ``profiles._parse_params(params)`` y
``profiles._generate_speedscope(parsed)`` sobre el conjunto que acaba de
buscar.

En Django ese conjunto es un ``QuerySet`` y la fila es una instancia: son dos
tipos distintos, y la fuente los llama a los dos con la misma sintaxis
(``_compute_speedscope`` hace ``execution._generate_speedscope(params)`` sobre
un singleton, ``:100``). Por eso los siete cuerpos viven **una sola vez** en
:class:`ProfileSetMixin`, que ambos adoptan: ``IrProfileQuerySet`` se resuelve
a sí mismo como conjunto y ``IrProfile`` se resuelve a ``[self]``. Los dos
sitios de llamada quedan idénticos a los de la fuente, sin consultas extra y
sin duplicar ningún cuerpo. Es la misma lectura que
:class:`~addons.base.models.res_device.ResDeviceQuerySet` ya tomó para
``_revoke``, con el eslabón añadido de que aquí la fuente llama también desde
la fila.

Divergencias declaradas
=======================

- **``set_profiling`` recibe ``request`` explícito.** La fuente lo lee del
  global ``odoo.http.request`` (``:12``); aquí no hay tal global —``src/http``
  no existe, medido con ``ls src/``— y la petición se pasa como argumento,
  igual que en ``res_device.py:316``. El contenido es el mismo: la sesión de
  Django es un ``dict`` con la misma superficie (``__setitem__``/``get``) que
  la de la fuente.
- **Los tres ``_compute_*`` devuelven el valor en vez de asignarlo.** La
  fuente asigna dentro de un bucle (``profile.config_url = …``) porque su ORM
  computa sobre el recordset entero. El mecanismo sin columna de este árbol
  —``orm.fields_nonstored.NonStored``— resuelve **por fila** al leerla, así
  que el cuerpo devuelve. Es la forma que ``ir_actions.py:1291`` ya fijó para
  ``warning``.
- **El ``@api.autovacuum`` de ``_gc_profile``** y el resto del comportamiento
  se portan verbatim.

Lo que este archivo NO trae, y por qué
======================================

- **Las rutas ``/web/speedscope/<id>`` y ``/web/profile_config/<ids>``** que
  ``speedscope_url``, ``config_url`` y ``action_view_speedscope`` publican.
  Viven en ``odoo19c: addons/web/controllers/profiling.py``, que es otro
  archivo y otro addon; medido: ``find src -path '*web/controllers*'`` → 0.
  Los tres campos son el **contrato** —la URL que el cliente pide— y se portan
  completos; el manejador que la atiende es el porte de ese controlador,
  registrado como tarea **#361**.

.. note::

   Hasta ``api@d9a05f6f`` este archivo declaraba bloqueados los tres campos
   computados y su motor *"porque dependen de ``odoo.tools.speedscope`` y
   ``odoo.tools.profiler``; medido: 0 archivos cada uno"*. Los dos módulos
   entraron en ``api@9bb9b3e1`` y ``api@d9a05f6f``, y ``ir.actions.act_window``
   / ``act_url`` existen desde el porte de ``ir_actions.py``: las dos causas
   dejaron de existir y el bloqueo quedó caduco. Ver :ref:`h-api-1081`.
"""
import base64
import datetime
import json
import logging

from django.utils import timezone

import api
import fields
import models

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import UserError
from orm.environments import get_context
from orm.models_transient import TransientModel
from tools.constants import GC_UNLINK_LIMIT
from tools.misc import str2bool
from tools.profiler import make_session
from tools.speedscope import Speedscope
from tools.translate import _

_logger = logging.getLogger(__name__)

#: Clave del parámetro que habilita el perfilado — nombre verbatim de la
#: referencia, para que el valor sea intercambiable con el suyo.
PROFILING_ENABLED_UNTIL = 'base.profiling_enabled_until'

#: Días que se conserva un perfil antes de que el recolector lo borre.
GC_RETENTION_DAYS = 30

#: Campos de traza: pesados y rara vez necesarios al listar. La referencia los
#: marca ``prefetch=False``; aquí el manager por defecto los difiere.
_TRACE_FIELDS = (
    'init_stack_trace', 'sql', 'traces_async', 'traces_sync', 'others', 'qweb',
)
