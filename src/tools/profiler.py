"""``tools/profiler`` — el motor de perfilado: colectores, contexto y sesión.

Adaptación de ``odoo19c: odoo/tools/profiler.py`` (747 líneas, 21 símbolos de
primer nivel), medida sobre ``odoo-tools`` con la raíz que declara
``scripts/reference_roots.py``. El manifiesto del núcleo declara **LGPL-3**, así
que el mecanismo es **copia y adaptación con atribución**
(``porte-completo-no-parcial.md``): el cuerpo se porta, los comentarios y
docstrings pasan a español y los identificadores se conservan verbatim.

Qué hace
========

Un :class:`Profiler` es un gestor de contexto que, mientras dura el ``with``,
deja que N :class:`Collector` acumulen muestras. Cada muestra lleva su traza de
pila, el contexto de ejecución del hilo y su marca de tiempo. Al salir, el
perfil se guarda en la tabla ``ir_profile`` — y de ahí lo consume
``tools/speedscope.py``, que lo convierte al formato del visor.

Los cuatro colectores de la fuente se portan enteros:

``sql``
    engancha ``query_hooks`` del hilo y registra cada consulta con su pila.
``traces_async``
    muestrea la pila desde un hilo aparte cada ``frame_interval`` segundos, y
    detecta la congelación del muestreador (una llamada C que no suelta el GIL).
``traces_sync``
    ``sys.settrace``: registra **cada** ``call``/``return`` y reconstruye la
    pila completa en el post-proceso.
``qweb``
    registra la traza de directivas de una plantilla, con su retardo y su
    conteo de consultas por directiva.

Los tres tiempos se capturan **sin parchear** (``real_time``,
``real_cpu_time``, ``real_datetime_now``) porque un perfil tomado bajo
``freezegun`` mediría el reloj falso.

Las cuatro decisiones de este stack, cada una medida
====================================================

1. **``psutil`` es dependencia declarada de la fuente**, no una invención de
   este puerto: ``odoo19c: requirements.txt:57-59`` la fija por versión de
   Python y ``odoo19c: setup.py:49`` la lista en ``install_requires``. Se
   añadió a ``pyproject.toml``. La consume ``memory_profile``, que lee el RSS
   del proceso en cada muestra.

2. **``from psycopg2 import OperationalError`` → ``django.db.OperationalError``.**
   El motor es psycopg 3 (ADR-028) y la escritura del perfil pasa por un cursor
   de Django, así que la excepción que llega es la envoltura de Django, no la
   del driver. Mismo contrato: el fallo al guardar se registra y **no** propaga.

3. **``_logger.runbot`` existe aquí porque se construyó.** La fuente declara el
   nivel ``RUNBOT`` en ``odoo19c: odoo/netsvc.py:339-341`` y el método
   ``Logger.runbot`` en ``:365-367``; ``netsvc.py`` es un módulo top-level que
   este árbol todavía no porta (tarea **#344**). El nivel vive en
   ``tools/logging_handlers.py``, que ya es el hogar declarado de las piezas de
   logging de ``netsvc`` aquí (:ref:`h-api-855`), y este módulo lo instala
   llamando a :func:`~tools.logging_handlers.install_runbot_level` — explícito
   e idempotente, en vez de un import cuyo único efecto sea un side-effect.

4. **``odoo.sql_db.db_connect(self.db).cursor()`` →
   ``connections.create_connection(alias)``.** La fuente abre una conexión
   **aparte** a propósito: el perfil tiene que sobrevivir aunque la transacción
   perfilada se revierta. Aquí se conserva esa propiedad con el constructor de
   conexiones de Django. Dos diferencias de forma, ambas declaradas:

   - la fuente importa ``db_connect`` **dentro** de ``end()`` (*"only import
     from odoo if/when needed"*); aquí el import va al top, que es lo que exige
     ``no-lazy-imports.md``. El efecto es el mismo: la conexión se crea al
     guardar, no al importar.
   - ``self.db`` es, en la fuente, el **nombre de la base**; aquí es el **alias
     de conexión** de Django. El centinela ``db=...`` sigue leyendo
     ``current_thread().dbname`` primero, y sólo si no está cae a
     ``DEFAULT_DB_ALIAS``. La guarda que la fuente expresa como excepción se
     conserva y **puede fallar**: si el alias resuelto no está en
     ``settings.DATABASES``, se levanta antes de intentar nada.

Lo que este puerto NO cambia
============================

``QwebTracker`` y ``QwebCollector`` se portan enteros aunque este árbol no
renderice QWeb: son puntos de enganche que no se activan sin
``thread.qweb_hooks``, y recortarlos sería el porte parcial que
``porte-completo-no-parcial.md`` prohíbe. Lo mismo vale para ``SQLCollector``,
cuyo ``query_hooks`` todavía no tiene emisor en este árbol — medido:
``grep -rn 'query_hooks' src/`` → 0.
"""
from contextlib import nullcontext, ExitStack
from datetime import datetime
import json
import logging
import re
import sys
import threading
import time

import psutil
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, OperationalError, connections

from tools.gc import disabling_gc
from tools.logging_handlers import install_runbot_level
from tools.misc import file_open
from tools.sql import SQL

_logger = logging.getLogger(__name__)

# El nivel RUNBOT no es de la stdlib: lo declara la referencia en netsvc.py y
# aquí lo instala tools/logging_handlers. Ver el punto 3 del docstring.
install_runbot_level()

# Reloj sin parchear, para que un perfil tomado bajo freezegun mida el tiempo
# real y no el congelado.
real_datetime_now = datetime.now
real_time = time.time.__call__
real_cpu_time = time.thread_time.__call__


def _format_frame(frame):
    code = frame.f_code
    return (code.co_filename, frame.f_lineno, code.co_name, '')


def _format_stack(stack):
    return [list(frame) for frame in stack]


def get_current_frame(thread=None):
    if thread:
        frame = sys._current_frames()[thread.ident]
    else:
        frame = sys._getframe()
    while frame.f_code.co_filename == __file__:
        frame = frame.f_back
    return frame


def _get_stack_trace(frame, limit_frame=None):
    stack = []
    while frame is not None and frame != limit_frame:
        stack.append(_format_frame(frame))
        frame = frame.f_back
    if frame is None and limit_frame:
        _logger.runbot("Limit frame was not found")
    return list(reversed(stack))


def stack_size():
    frame = get_current_frame()
    size = 0
    while frame:
        size += 1
        frame = frame.f_back
    return size


def make_session(name=''):
    return f'{real_datetime_now():%Y-%m-%d %H:%M:%S} {name}'


def force_hook():
    """Fuerza a los colectores periódicos a tomar una traza de pila ahora.

    Es útil antes de una llamada larga que no suelta el GIL: sin esto el tiempo
    de esa llamada se atribuye a una pila anterior arbitraria, en vez de a la
    que de verdad estaba activa.
    """
    thread = threading.current_thread()
    for func in getattr(thread, 'profile_hooks', ()):
        func()


class Collector:
    """Base de los objetos que acumulan datos de perfilado.

    Un colector lo usa un perfilador para juntar muestras — normalmente una
    lista de trazas de pila con su tiempo y el contexto que el decorador
    :class:`ExecutionContext` haya puesto en el hilo actual.

    Es la implementación genérica: define el comportamiento por defecto de
    crear una entrada, y se hereda.
    """
    name = None                 # nombre simbólico del colector
    _store = name
    _registry = {}              # mapa de nombre de colector a su clase

    @classmethod
    def __init_subclass__(cls):
        if cls.name:
            cls._registry[cls.name] = cls
            cls._registry[cls.__name__] = cls

    @classmethod
    def make(cls, name, *args, **kwargs):
        """Instancia el colector que corresponde al nombre dado."""
        return cls._registry[name](*args, **kwargs)

    def __init__(self):
        self._processed = False
        self._entries = []
        self.profiler = None

    def start(self):
        """Arranca el colector."""

    def stop(self):
        """Detiene el colector."""

    def add(self, entry=None, frame=None):
        """Añade una entrada (dict) a este colector."""
        sample = {
            'stack': self._get_stack_trace(frame),
            'exec_context': getattr(self.profiler.init_thread, 'exec_context', ()),
            'start': real_time(),
            **(entry or {}),
        }
        self._entries.append(sample)
        return sample

    def progress(self, entry=None, frame=None):
        """Verifica si se alcanzaron los límites y añade la entrada."""
        exceeded_entry_count = bool(self.profiler.entry_count_limit) \
                                and self.profiler.counter >= self.profiler.entry_count_limit
        exceeded_time_limit = bool(self.profiler.time_limit) \
                              and self.profiler.time_limit < real_time() - self.profiler.start_time
        if exceeded_entry_count \
            or exceeded_time_limit:
            self.profiler.end()

        self.profiler.counter += 1
        return self.add(entry=entry, frame=frame)

    def _get_stack_trace(self, frame=None):
        """Devuelve la traza de pila que llevará una entrada dada."""
        frame = frame or get_current_frame(self.profiler.init_thread)
        return _get_stack_trace(frame, self.profiler.init_frame)

    def post_process(self):
        for entry in self._entries:
            stack = entry.get('stack', [])
            self.profiler._add_file_lines(stack)

    @property
    def entries(self):
        """Devuelve las entradas del colector, ya post-procesadas."""
        if not self._processed:
            self.post_process()
            self.processed_entries = self._entries
            self._entries = None  # evita modificarlas después de procesar
            self._processed = True
        return self.processed_entries

    def summary(self):
        return f"{'='*10} {self.name} {'='*10} \n Entries: {len(self._entries)}"


class SQLCollector(Collector):
    """Guarda cada consulta ejecutada en el hilo actual, con su pila."""
    name = 'sql'

    def start(self):
        init_thread = self.profiler.init_thread
        if not hasattr(init_thread, 'query_hooks'):
            init_thread.query_hooks = []
        init_thread.query_hooks.append(self.hook)

    def stop(self):
        self.profiler.init_thread.query_hooks.remove(self.hook)

    def hook(self, cr, query, params, query_start, query_time):
        entry = {
            'query': str(query),
            'full_query': str(cr.mogrify(query, params)),
            'start': query_start,
            'time': query_time,
        }
        sample = self.progress(entry)

        def update_sample(delay):
            sample['time'] = delay

        return update_sample

    def summary(self):
        total_time = sum(entry['time'] for entry in self._entries) or 1
        sql_entries = ''
        for entry in self._entries:
            sql_entries += f"\n{'-' * 100}'\n'{entry['time']}  {'*' * int(entry['time'] / total_time * 100)}'\n'{entry['full_query']}"
        return super().summary() + sql_entries


class _BasePeriodicCollector(Collector):
    """Registra marcos de ejecución de forma asíncrona, como mucho cada
    ``interval`` segundos.

    :param interval: segundos de espera entre dos muestras.
    """
    _min_interval = 0.001  # intervalo mínimo admitido
    _max_interval = 5    # intervalo máximo admitido
    _default_interval = 0.001

    def __init__(self, interval=None):  # verificar duración. ¿dinámico?
        super().__init__()
        self.active = False
        self.frame_interval = interval or self._default_interval
        self.__thread = threading.Thread(target=self.run)
        self.last_frame = None
        self._stop_event = threading.Event()

    def start(self):
        interval = self.profiler.params.get(f'{self.name}_interval')
        if interval:
            self.frame_interval = min(max(float(interval), self._min_interval), self._max_interval)
        init_thread = self.profiler.init_thread
        if not hasattr(init_thread, 'profile_hooks'):
            init_thread.profile_hooks = []
        init_thread.profile_hooks.append(self.progress)
        self.__thread.start()

    def run(self):
        self.active = True
        self.last_time = real_time()
        while self.active:  # ¿añadir una verificación del estado del hilo padre?
            self.progress()
            self._stop_event.wait(self.frame_interval)

    def stop(self):
        self.active = False
        self._stop_event.set()
        self._entries.append({'stack': [], 'start': real_time()})  # marco final
        if self.__thread.is_alive() and self.__thread is not threading.current_thread():
            self.__thread.join()
        self.profiler.init_thread.profile_hooks.remove(self.progress)


class PeriodicCollector(_BasePeriodicCollector):

    name = 'traces_async'

    def start(self):
        self._memory_profile = self.profiler.memory_profile
        self._process = self.profiler.process
        super().start()

    def add(self, entry=None, frame=None):
        """Añade una entrada (dict) a este colector."""
        if self.last_frame:
            duration = real_time() - self._last_time
            if duration > self.frame_interval * 10 and self.last_frame:
                # El perfilador durmió más de diez intervalos sin querer. Pasa
                # al llamar a una librería C que no suelta el GIL: el último
                # marco se tomó antes de la llamada y el siguiente después, así
                # que la llamada no aparece en ninguno y su duración se le
                # atribuye por error al último marco.
                self._entries[-1]['stack'].append(('profiling', 0, '⚠ Profiler freezed for %s s' % duration, ''))
            self.last_frame = None  # se salta la detección de duplicado del siguiente marco
        self._last_time = real_time()

        frame = frame or get_current_frame(self.profiler.init_thread)
        if frame == self.last_frame:
            # no se guarda si el marco es exactamente el mismo que el anterior.
            # ¿quizá modificar la última entrada para añadir un "visto por última vez"?
            return
        self.last_frame = frame
        if self._memory_profile:
            entry = {'memory': self._process.memory_info().rss, **(entry or {})}
        super().add(entry=entry, frame=frame)


class SyncCollector(Collector):
    """Registra la ejecución completa de forma síncrona.

    Puede hacer falta subir ``--limit-memory-hard`` al arrancar.
    """
    name = 'traces_sync'

    def start(self):
        if sys.gettrace() is not None:
            _logger.error("Cannot start SyncCollector, settrace already set: %s", sys.gettrace())
        assert not self._processed, "You cannot start SyncCollector after accessing entries."
        sys.settrace(self.hook)  # pendiente probar setprofile, quizá no sea seguro entre hilos

    def stop(self):
        sys.settrace(None)

    def hook(self, _frame, event, _arg=None):
        if event == 'line':
            return
        entry = {'event': event, 'frame': _format_frame(_frame)}
        if event == 'call' and _frame.f_back:
            # hace falta el marco padre para saber la línea de la llamada
            entry['parent_frame'] = _format_frame(_frame.f_back)
        self.progress(entry, frame=_frame)
        return self.hook

    def _get_stack_trace(self, frame=None):
        # Obtener la pila completa es lento y aquí no aporta: SyncCollector
        # guarda sólo el marco de arriba y el evento de cada llamada, y
        # recompone la pila entera al final.
        return None

    def post_process(self):
        # Convierte las trazas por evento en trazas de pila completas. El paso
        # se podría evitar —speedscope las vuelve a convertir a eventos— pero
        # así encaja con la lógica que speedscope ya tiene, sobre todo al
        # mezclarlas con las de SQLCollector.
        stack = []
        for entry in self._entries:
            frame = entry.pop('frame')
            event = entry.pop('event')
            if event == 'call':
                if stack:
                    stack[-1] = entry.pop('parent_frame')
                stack.append(frame)
            elif event == 'return':
                stack.pop()
            entry['stack'] = stack[:]
        super().post_process()


class QwebTracker():

    def __init__(self, view_id, arch, cr):
        current_thread = threading.current_thread()  # no guardar current_thread en self
        self.execution_context_enabled = getattr(current_thread, 'profiler_params', {}).get('execution_context_qweb')
        self.qweb_hooks = getattr(current_thread, 'qweb_hooks', ())
        self.context_stack = []
        self.cr = cr
        self.view_id = view_id
        for hook in self.qweb_hooks:
            hook('render', self.cr.sql_log_count, view_id=view_id, arch=arch)

    def enter_directive(self, directive, attrib, xpath):
        execution_context = None
        if self.execution_context_enabled:
            directive_info = {}
            if ('t-' + directive) in attrib:
                directive_info['t-' + directive] = repr(attrib['t-' + directive])
            if directive == 'set':
                if 't-value' in attrib:
                    directive_info['t-value'] = repr(attrib['t-value'])
                if 't-valuef' in attrib:
                    directive_info['t-valuef'] = repr(attrib['t-valuef'])

                for key in attrib:
                    if key.startswith('t-set-') or key.startswith('t-setf-'):
                        directive_info[key] = repr(attrib[key])
            elif directive == 'foreach':
                directive_info['t-as'] = repr(attrib['t-as'])
            elif directive == 'groups' and 'groups' in attrib and not directive_info.get('t-groups'):
                directive_info['t-groups'] = repr(attrib['groups'])
            elif directive == 'att':
                for key in attrib:
                    if key.startswith('t-att-') or key.startswith('t-attf-'):
                        directive_info[key] = repr(attrib[key])
            elif directive == 'options':
                for key in attrib:
                    if key.startswith('t-options-'):
                        directive_info[key] = repr(attrib[key])
            elif ('t-' + directive) not in attrib:
                directive_info['t-' + directive] = None

            execution_context = ExecutionContext(**directive_info, xpath=xpath)
            execution_context.__enter__()
            self.context_stack.append(execution_context)

        for hook in self.qweb_hooks:
            hook('enter', self.cr.sql_log_count, view_id=self.view_id, xpath=xpath, directive=directive, attrib=attrib)

    def leave_directive(self, directive, attrib, xpath):
        if self.execution_context_enabled:
            self.context_stack.pop().__exit__()

        for hook in self.qweb_hooks:
            hook('leave', self.cr.sql_log_count, view_id=self.view_id, xpath=xpath, directive=directive, attrib=attrib)


class QwebCollector(Collector):
    """Registra la ejecución de QWeb con la traza de sus directivas."""
    name = 'qweb'

    def __init__(self):
        super().__init__()
        self.events = []

        def hook(event, sql_log_count, **kwargs):
            self.events.append((event, kwargs, sql_log_count, real_time()))
        self.hook = hook

    def _get_directive_profiling_name(self, directive, attrib):
        expr = ''
        if directive == 'set':
            if 't-set' in attrib:
                expr = f"t-set={repr(attrib['t-set'])}"
                if 't-value' in attrib:
                    expr += f" t-value={repr(attrib['t-value'])}"
                if 't-valuef' in attrib:
                    expr += f" t-valuef={repr(attrib['t-valuef'])}"
            for key in attrib:
                if key.startswith('t-set-') or key.startswith('t-setf-'):
                    if expr:
                        expr += ' '
                    expr += f"{key}={repr(attrib[key])}"
        elif directive == 'foreach':
            expr = f"t-foreach={repr(attrib['t-foreach'])} t-as={repr(attrib['t-as'])}"
        elif directive == 'options':
            if attrib.get('t-options'):
                expr = f"t-options={repr(attrib['t-options'])}"
            for key in attrib:
                if key.startswith('t-options-'):
                    expr = f"{expr}  {key}={repr(attrib[key])}"
        elif directive == 'att':
            for key in attrib:
                if key == 't-att' or key.startswith('t-att-') or key.startswith('t-attf-'):
                    if expr:
                        expr += ' '
                    expr += f"{key}={repr(attrib[key])}"
        elif ('t-' + directive) in attrib:
            expr = f"t-{directive}={repr(attrib['t-' + directive])}"
        else:
            expr = f"t-{directive}"

        return expr

    def start(self):
        init_thread = self.profiler.init_thread
        if not hasattr(init_thread, 'qweb_hooks'):
            init_thread.qweb_hooks = []
        init_thread.qweb_hooks.append(self.hook)

    def stop(self):
        self.profiler.init_thread.qweb_hooks.remove(self.hook)

    def post_process(self):
        last_event_query = None
        last_event_time = None
        stack = []
        results = []
        archs = {}
        for event, kwargs, sql_count, time in self.events:
            if event == 'render':
                archs[kwargs['view_id']] = kwargs['arch']
                continue

            # actualiza la directiva activa con el tiempo y las consultas
            if stack:
                top = stack[-1]
                top['delay'] += time - last_event_time
                top['query'] += sql_count - last_event_query
            last_event_time = time
            last_event_query = sql_count

            directive = self._get_directive_profiling_name(kwargs['directive'], kwargs['attrib'])
            if directive:
                if event == 'enter':
                    data = {
                        'view_id': kwargs['view_id'],
                        'xpath': kwargs['xpath'],
                        'directive': directive,
                        'delay': 0,
                        'query': 0,
                    }
                    results.append(data)
                    stack.append(data)
                else:
                    assert event == "leave"
                    data = stack.pop()

        self.add({'results': {'archs': archs, 'data': results}})
        super().post_process()


class ExecutionContext:
    """Añade contexto al hilo, en el nivel actual de la pila de llamadas.

    El colector lo guarda junto a la pila, y speedscope lo usa para añadir un
    nivel con esa información.
    """
    def __init__(self, **context):
        self.context = context
        self.previous_context = None

    def __enter__(self):
        current_thread = threading.current_thread()
        self.previous_context = getattr(current_thread, 'exec_context', ())
        current_thread.exec_context = self.previous_context + ((stack_size(), self.context),)

    def __exit__(self, *_args):
        threading.current_thread().exec_context = self.previous_context


class Profiler:
    """Gestor de contexto que graba la ejecución de un bloque.

    Por defecto guarda el SQL y la traza de pila asíncrona.
    """
    def __init__(self, collectors=None, db=..., profile_session=None,
                 description=None, disable_gc=False, params=None, log=False):
        """
        :param db: alias de conexión donde guardar el resultado. Por defecto se
            deduce del hilo actual y, si el hilo no lo declara, del alias por
            defecto de Django. ``None`` desactiva el guardado.
        :param collectors: lista de cadenas y objetos ``Collector``, p. ej.
            ``['sql', PeriodicCollector(interval=0.2)]``. ``None`` usa los de
            por defecto.
        :param profile_session: descripción de la sesión, para agrupar varios
            perfiles. ``make_session(name)`` da el formato por defecto.
        :param description: descripción de este perfilador (sugerencia: nombre
            de ruta, método de prueba, módulo que se carga…).
        :param disable_gc: desactiva el recolector de basura mientras se
            perfila (útil para que no aparezca durante la ejecución de SQL).
        :param params: parámetros que los colectores consumen (p. ej. el
            intervalo entre marcos).
        """
        self.start_time = 0
        self.duration = 0
        self.start_cpu_time = 0
        self.cpu_duration = 0
        self.profile_session = profile_session or make_session()
        self.description = description
        self.init_frame = None
        self.init_stack_trace = None
        self.init_thread = None
        self.disable_gc = disable_gc
        self.filecache = {}
        self.params = params or {}  # parámetros a medida que usan los colectores
        self.profile_id = None
        self.log = log
        self.sub_profilers = []
        self.entry_count_limit = int(self.params.get("entry_count_limit", 0))
        self.time_limit = int(self.params.get("time_limit", 0))
        self.done = False
        self.exit_stack = ExitStack()
        self.process = psutil.Process()
        self.memory_profile = self.params.get("memory_profile", False)
        self.counter = 0

        if db is ...:
            # deduce el alias del hilo actual; si el hilo no lo declara, el de
            # por defecto de Django (ver el punto 4 del docstring del módulo).
            db = getattr(threading.current_thread(), 'dbname', None) or DEFAULT_DB_ALIAS
        if db and db not in settings.DATABASES:
            raise ValueError(
                f'Database alias {db!r} is not configured. \n'
                'Please provide a valid/falsy db parameter'
            )
        self.db = db

        # colectores
        if collectors is None:
            collectors = ['sql', 'traces_async']
        self.collectors = []
        for collector in collectors:
            if isinstance(collector, str):
                try:
                    collector = Collector.make(collector)
                except Exception:
                    _logger.error("Could not create collector with name %r", collector)
                    continue
            collector.profiler = self
            self.collectors.append(collector)

    def __enter__(self):
        self.init_thread = threading.current_thread()
        try:
            self.init_frame = get_current_frame(self.init_thread)
            self.init_stack_trace = _get_stack_trace(self.init_frame)
        except KeyError:
            # con un pool de hilos (gevent) el hilo no aparece en
            # current_frames. El caso lo cubre la capa HTTP, pero seguiría
            # fallando al añadir un perfilador dentro de código que una ruta de
            # long-polling pueda llamar. Aquí se evita reventar al llamador y
            # se desactivan todos los colectores.
            self.init_frame = self.init_stack_trace = self.collectors = []
            self.db = self.params = None
            message = "Cannot start profiler, thread not found. Is the thread part of a thread pool?"
            if not self.description:
                self.description = message
            _logger.warning(message)

        if self.description is None:
            frame = self.init_frame
            code = frame.f_code
            self.description = f"{frame.f_code.co_name} ({code.co_filename}:{frame.f_lineno})"
        if self.params:
            self.init_thread.profiler_params = self.params
        if self.disable_gc:
            self.exit_stack.enter_context(disabling_gc())
        self.start_time = real_time()
        self.start_cpu_time = real_cpu_time()
        for collector in self.collectors:
            collector.start()
        return self

    def __exit__(self, *args):
        self.end()

    def end(self):
        if self.done:
            return
        self.done = True
        try:
            for collector in self.collectors:
                collector.stop()
            self.duration = real_time() - self.start_time
            self.cpu_duration = real_cpu_time() - self.start_cpu_time
            self._add_file_lines(self.init_stack_trace)

            if self.db:
                # Conexión APARTE: el perfil tiene que sobrevivir aunque la
                # transacción perfilada se revierta.
                connection = connections.create_connection(self.db)
                try:
                    with connection.cursor() as cr:
                        now = real_datetime_now()
                        values = {
                            "name": self.description,
                            "session": self.profile_session,
                            "created_at": now,
                            # ``updated_at`` no existe en la referencia: es la
                            # segunda columna de auditoría de TimeStampedModel,
                            # declarada NOT NULL sin default de base. Un INSERT
                            # crudo que la omita revienta, así que nace igual a
                            # ``created_at`` — que es lo que el ORM haría.
                            "updated_at": now,
                            "init_stack_trace": json.dumps(_format_stack(self.init_stack_trace)),
                            "duration": self.duration,
                            "cpu_duration": self.cpu_duration,
                            "entry_count": self.entry_count(),
                            "sql_count": sum(len(collector.entries) for collector in self.collectors if collector.name == 'sql')
                        }
                        # Las cinco columnas de traza son NOT NULL aquí y
                        # nullables en la referencia: su default vive en el
                        # modelo (``default=''``) y no en la base. Se siembran
                        # vacías para que el colector que sí tenga entradas las
                        # pise justo debajo.
                        values.update(dict.fromkeys(
                            ('sql', 'traces_async', 'traces_sync', 'others', 'qweb'), ''))
                        others = {}
                        for collector in self.collectors:
                            if collector.entries:
                                if collector._store == "others":
                                    others[collector.name] = json.dumps(collector.entries)
                                else:
                                    values[collector.name] = json.dumps(collector.entries)
                        if others:
                            values['others'] = json.dumps(others)
                        # La referencia pasa la fila entera como UNA tupla a un
                        # solo ``%s``: psycopg2 la adapta a la lista ``(a,b,c)``
                        # de un VALUES. psycopg3 la adapta a un literal de tipo
                        # compuesto —medido: ``VALUES '(persistido,"2026-…")'``,
                        # error de sintaxis—, así que aquí cada valor lleva su
                        # propio marcador. Misma fila, otro adaptador.
                        query = SQL(
                            "INSERT INTO ir_profile(%s) VALUES (%s) RETURNING id",
                            SQL(",").join(map(SQL.identifier, values)),
                            SQL(",").join(values.values()),
                        )
                        cr.execute(query.code, query.params)
                        self.profile_id = cr.fetchone()[0]
                        _logger.info('ir_profile %s (%s) created', self.profile_id, self.profile_session)
                finally:
                    connection.close()
        except OperationalError:
            _logger.exception("Could not save profile in database")
        finally:
            self.exit_stack.close()
            if self.params:
                del self.init_thread.profiler_params
            if self.log:
                _logger.info(self.summary())

    def _get_cm_proxy(self):
        return Nested(self)

    def _add_file_lines(self, stack):
        for index, frame in enumerate(stack):
            (filename, lineno, name, line) = frame
            if line != '':
                continue
            # recupera las líneas del archivo desde la caché
            if not lineno:
                continue
            try:
                filelines = self.filecache[filename]
            except KeyError:
                try:
                    with file_open(filename, filter_ext=('.py',)) as f:
                        filelines = f.readlines()
                except (ValueError, FileNotFoundError):  # sobre todo por el "nombre" <decorator>
                    filelines = None
                self.filecache[filename] = filelines
            # rellena la línea
            if filelines is not None:
                line = filelines[lineno - 1]
                stack[index] = (filename, lineno, name, line)

    def entry_count(self):
        """Devuelve el total de entradas que este perfilador ha juntado."""
        return sum(len(collector.entries) for collector in self.collectors)

    def format_path(self, path):
        """Formatea una ruta para este perfilador.

        Sirve sobre todo para que la ruta sea única entre ejecuciones.
        """
        return path.format(
            time=real_datetime_now().strftime("%Y%m%d-%H%M%S"),
            len=self.entry_count(),
            desc=re.sub("[^0-9a-zA-Z-]+", "_", self.description)
        )

    def json(self):
        """Genera la versión JSON de este perfilador.

        Sirve para escribir las entradas de perfilado a un archivo::

            with Profiler(db=None) as profiler:
                do_stuff()

            filename = profiler.format_path('/home/foo/{desc}_{len}.json')
            with open(filename, 'w') as f:
                f.write(profiler.json())
        """
        return json.dumps({
            "name": self.description,
            "session": self.profile_session,
            "create_date": real_datetime_now().strftime("%Y%m%d-%H%M%S"),
            "init_stack_trace": _format_stack(self.init_stack_trace),
            "duration": self.duration,
            "collectors": {collector.name: collector.entries for collector in self.collectors},
        }, indent=4)

    def summary(self):
        result = ''
        for profiler in [self, *self.sub_profilers]:
            for collector in profiler.collectors:
                result += f'\n{self.description}\n{collector.summary()}'
        return result


class Nested:
    """Utilidad para anidar otro gestor de contexto dentro de un perfilador.

    El perfilador sólo debe llamarse directamente en el ``with``, sin anidarlo
    con ``ExitStack``. Si no, la obtención de ``init_frame`` puede salir mal y
    llevar al error "Limit frame was not found" al perfilar. Como la pila
    ignora todos los marcos de este archivo, los marcos anidados también se
    ignoran — que es también la razón de que ``Nested()`` no use
    ``contextlib.contextmanager``.
    """
    def __init__(self, profiler, context_manager=None):
        self._profiler__ = profiler
        self.context_manager = context_manager or nullcontext()

    def __enter__(self):
        self._profiler__.__enter__()
        return self.context_manager.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return self.context_manager.__exit__(exc_type, exc_value, traceback)
        finally:
            self._profiler__.__exit__(exc_type, exc_value, traceback)
