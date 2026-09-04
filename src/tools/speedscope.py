"""``tools.speedscope`` — espejo de ``odoo19c: odoo/tools/speedscope.py``.

Convierte las entradas crudas que produce un colector de perfilado al formato
de archivo que consume https://www.speedscope.app — un visor de perfiles que
se abre en el navegador y no exige instalar nada del lado del servidor.

El formato tiene dos variantes y las dos se emiten aquí:

* **evented** — una lista de eventos de apertura (``O``) y cierre (``C``) de
  marco, cada uno con su instante. Es la que usa el perfil de tiempo y la de
  consultas SQL.
* **sampled** — una lista de pilas con su peso. Es la que usa el perfil de
  memoria, donde no hay duración sino incremento de RSS.

Los marcos se deduplican en ``shared.frames`` y cada perfil los referencia por
índice, que es lo que hace manejable un archivo con cientos de miles de
eventos.

Adaptado de Odoo Community (LGPL-3, declarado en el ``__manifest__`` del
núcleo) — copia con adaptación y atribución preservada (DEC-KX-03).
"""
import reprlib

#: El acortador de la cadena de consulta que va al nombre del marco SQL. La
#: fuente fija 150 caracteres: una consulta entera haría ilegible la etiqueta
#: del marco en el visor, y el texto completo viaja aparte en ``file``.
shortener = reprlib.Repr()
shortener.maxstring = 150
shorten = shortener.repr


class Speedscope:
    """Acumula perfiles crudos y los emite en el formato de speedscope."""

    def __init__(self, name='Speedscope', init_stack_trace=None):
        self.init_stack_trace = init_stack_trace or []
        self.init_stack_trace_level = len(self.init_stack_trace)
        self.caller_frame = None
        self.convert_stack(self.init_stack_trace)

        self.init_caller_frame = None
        if self.init_stack_trace:
            self.init_caller_frame = self.init_stack_trace[-1]
        self.profiles_raw = {}
        self.name = name
        self.frames_indexes = {}
        self.frame_count = 0
        self.profiles = []

    def add(self, key, profile):
        """Registra un perfil crudo bajo ``key``, normalizando sus pilas.

        Una entrada con ``query`` es de un colector SQL: se le añade un marco
        sintético al final de la pila cuyo nombre es la consulta acortada y
        cuyo «archivo» es la consulta completa, de modo que el visor muestre
        la corta y deje la larga en el detalle.
        """
        for entry in profile:
            self.caller_frame = self.init_caller_frame
            self.convert_stack(entry['stack'] or [])
            if 'query' in entry:
                query = entry['query']
                full_query = entry['full_query']
                entry['stack'].append((f'sql({shorten(query)})', full_query, None))
        self.profiles_raw[key] = profile

    def convert_stack(self, stack):
        """Reescribe cada marco como ``(metodo, linea_del_llamador, numero)``.

        La posición que interesa al leer un perfil no es dónde está definido el
        método sino desde dónde se llamó, así que el marco toma la información
        de su llamador — el marco anterior de la misma pila.
        """
        for index, frame in enumerate(stack):
            method = frame[2]
            line = ''
            number = ''
            if self.caller_frame and len(self.caller_frame) == 4:
                line = f"called at {self.caller_frame[0]} ({self.caller_frame[3].strip()})"
                number = self.caller_frame[1]
            stack[index] = (method, line, number,)
            self.caller_frame = frame

    def add_output(self, names, complete=True, display_name=None, use_context=True, constant_time=False, context_per_name=None, **params):
        """Añade una salida de perfil a la lista de perfiles.

        :param names: claves a combinar en esta salida; son las que se usaron
            en :meth:`add`.
        :param display_name: nombre de la pestaña de esta salida.
        :param complete: muestra la pila completa. Con ``False`` no se muestra
            la pila por debajo del perfilador.
        :param use_context: usa el contexto de ejecución (el que añade el
            gestor de contexto ``ExecutionContext``) para mostrar el perfil.
        :param constant_time: oculta la temporalidad. Útil para comparar
            conteos de consultas.
        :param context_per_name: diccionario de contexto adicional por nombre.
        """
        entries = []
        display_name = display_name or ','.join(names)
        for name in names:
            raw = self.profiles_raw.get(name)
            if not raw:
                continue
            entries += raw
        entries.sort(key=lambda e: e['start'])
        result = self.process(entries, use_context=use_context, constant_time=constant_time, **params)
        if not result:
            return self
        start = result[0]['at']
        end = result[-1]['at']

        if complete:
            start_stack = []
            end_stack = []
            init_stack_trace_ids = self.stack_to_ids(self.init_stack_trace, use_context and entries[0].get('exec_context'))
            for frame_id in init_stack_trace_ids:
                start_stack.append({
                    "type": "O",
                    "frame": frame_id,
                    "at": start
                })
            for frame_id in reversed(init_stack_trace_ids):
                end_stack.append({
                    "type": "C",
                    "frame": frame_id,
                    "at": end
                })
            result = start_stack + result + end_stack

        self.profiles.append({
            "name": display_name,
            "type": "evented",
            "unit": "entries" if constant_time else "seconds",
            "startValue": 0,
            "endValue": end - start,
            "events": result
        })
        return self

    def add_memory_output(self, names, display_name=None, use_context=True, **params):
        """Añade una salida de perfil muestreado por memoria.

        Para cada par de entradas consecutivas de ``names`` se calcula la
        diferencia de memoria RSS. Las diferencias positivas (asignaciones) se
        atribuyen como heurística a la pila **anterior** y a la actual, porque
        la asignación ocurrió en algún punto del intervalo entre las dos
        muestras.

        :param names: claves añadidas previamente con :meth:`add`.
        :param display_name: nombre de la pestaña de esta salida.
        :param use_context: incluye los marcos del contexto de ejecución.
        """
        entries = []
        display_name = display_name or f'Memory {",".join(names)}'
        for name in names:
            raw = self.profiles_raw.get(name)
            if not raw:
                continue
            entries += raw
        entries.sort(key=lambda e: e['start'])

        samples = []
        weights = []
        total_weight = 0
        init_ids = self.stack_to_ids(self.init_stack_trace, None)

        for i in range(len(entries) - 1):
            current = entries[i]
            nxt = entries[i + 1]
            current_mem = current.get('memory')
            nxt_mem = nxt.get('memory')
            if current_mem is None or nxt_mem is None:
                continue
            diff = nxt_mem - current_mem
            if diff <= 0:
                continue
            stack = current.get('stack') or []
            context = use_context and current.get('exec_context')
            stack_ids = self.stack_to_ids(stack, context, False, self.init_stack_trace_level)
            full_ids = init_ids + stack_ids
            if full_ids:
                samples.append(full_ids)
                weights.append(diff)
                total_weight += diff

        if not samples:
            return self

        self.profiles.append({
            "name": display_name,
            "type": "sampled",
            "unit": "bytes",
            "startValue": 0,
            "endValue": total_weight,
            "samples": samples,
            "weights": weights,
        })
        return self

    def add_default(self, **params):
        """Emite las salidas por defecto para lo que se haya acumulado.

        Un perfil cuyas entradas traen ``query`` es SQL y admite dos vistas —
        sin huecos y por densidad—; el resto es de marcos y admite una.
        """
        if len(self.profiles_raw) > 1:
            if params['combined_profile']:
                self.add_output(self.profiles_raw, display_name='Combined', **params)
        for key, profile in self.profiles_raw.items():
            sql = profile and profile[0].get('query')
            if sql:
                if params['sql_no_gap_profile']:
                    self.add_output([key], hide_gaps=True, display_name=f'{key} (no gap)', **params)
                if params['sql_density_profile']:
                    self.add_output([key], continuous=False, complete=False, display_name=f'{key} (density)', **params)

            elif params['frames_profile']:
                self.add_output([key], display_name=key, **params)
        return self

    def make(self, **params):
        """Devuelve el documento completo, listo para serializar a JSON."""
        if not self.profiles:
            self.add_default(**params)
        return {
            "name": self.name,
            "activeProfileIndex": 0,
            "$schema": "https://www.speedscope.app/file-format-schema.json",
            "shared": {
                "frames": [{
                    "name": frame[0],
                    "file": frame[1],
                    "line": frame[2]
                } for frame in self.frames_indexes]
            },
            "profiles": self.profiles,
        }

    def get_frame_id(self, frame):
        """Devuelve el índice de ``frame`` en la tabla compartida, creándolo."""
        if frame not in self.frames_indexes:
            self.frames_indexes[frame] = self.frame_count
            self.frame_count += 1
        return self.frames_indexes[frame]

    def stack_to_ids(self, stack, context, aggregate_sql=False, stack_offset=0):
        """Ensambla pila y contexto y devuelve la lista de identificadores.

        :param stack: lista de marcos hashables.
        :param context: iterable de ``(nivel, valor)`` ordenado por nivel.
        :param aggregate_sql: colapsa la posición del marco SQL, para que
            todas las ocurrencias de la misma consulta compartan identificador.
        :param stack_offset: nivel de desplazamiento de la pila.

        Cada contexto se inserta en el nivel que le corresponde.
        """
        stack_ids = []
        context_iterator = iter(context or ())
        context_level, context_value = next(context_iterator, (None, None))
        # Se consume el iterador hasta rebasar stack_offset.
        while context_level is not None and context_level < stack_offset:
            context_level, context_value = next(context_iterator, (None, None))
        for level, frame in enumerate(stack, start=stack_offset + 1):
            if aggregate_sql:
                frame = (frame[0], '', frame[2])
            while context_level == level:
                context_frame = (", ".join(f"{k}={v}" for k, v in context_value.items()), '', '')
                stack_ids.append(self.get_frame_id(context_frame))
                context_level, context_value = next(context_iterator, (None, None))
            stack_ids.append(self.get_frame_id(frame))
        return stack_ids

    def process(self, entries, continuous=True, hide_gaps=False, use_context=True, constant_time=False, aggregate_sql=False, **params):
        """Convierte las entradas ordenadas en la lista de eventos ``O``/``C``.

        El emparejamiento se hace por prefijo común: entre dos entradas
        consecutivas sólo se cierran los marcos que dejan de estar en la pila y
        sólo se abren los que entran, que es lo que produce el gráfico de llama
        en vez de una sucesión de picos independientes.
        """
        # El parámetro constant_time sirve sobre todo para ocultar la
        # temporalidad cuando lo que se compara es el determinismo del SQL.
        entry_end = previous_end = None
        if not entries:
            return []
        events = []
        current_stack_ids = []
        frames_start = entries[0]['start']

        # Se añade la última entrada de cierre si falta.
        last_entry = entries[-1]
        if last_entry['stack']:
            entries.append({'stack': [], 'start': last_entry['start'] + last_entry.get('time', 0)})

        for index, entry in enumerate(entries):
            if constant_time:
                entry_start = close_time = index
            else:
                previous_end = entry_end
                if hide_gaps and previous_end:
                    entry_start = previous_end
                else:
                    entry_start = entry['start'] - frames_start

                if previous_end and previous_end > entry_start:
                    # Se salta la entrada si empieza después del fin de otra.
                    continue

                if previous_end:
                    close_time = min(entry_start, previous_end)
                else:
                    close_time = entry_start

                entry_time = entry.get('time')
                entry_end = None if entry_time is None else entry_start + entry_time

            entry_stack_ids = self.stack_to_ids(
                entry['stack'] or [],
                use_context and entry.get('exec_context'),
                aggregate_sql,
                self.init_stack_trace_level
            )
            level = 0
            if continuous:
                level = -1
                for current, new in zip(current_stack_ids, entry_stack_ids):
                    level += 1
                    if current != new:
                        break
                else:
                    level += 1

            for frame in reversed(current_stack_ids[level:]):
                events.append({
                    "type": "C",
                    "frame": frame,
                    "at": close_time
                })
            for frame in entry_stack_ids[level:]:
                events.append({
                    "type": "O",
                    "frame": frame,
                    "at": entry_start
                })
            current_stack_ids = entry_stack_ids

        return events
