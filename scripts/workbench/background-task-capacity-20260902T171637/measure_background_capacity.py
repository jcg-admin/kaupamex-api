"""Cuantas tareas en segundo plano admite esta sesion, medido en tres ejes.

La pregunta parece una y son tres mecanismos distintos, con caps distintos:

1. **Anchura de herramienta** — cuantas llamadas de UN turno se sirven a la
   vez. La acota el ejecutable.
2. **Procesos desprendidos** — ``nohup ... &`` dentro de una llamada Bash. No
   los acota el ejecutable: los acota la maquina.
3. **Subagentes** — fuera de alcance por directiva del ejecutor.

Este instrumento mide el eje 2 por conducta —lanza N y cuenta cuantos corren
de verdad a la vez— y lee el eje 1 del binario. El eje 1 no se mide por
conducta desde dentro: quien lo ejerce es el cliente, no este proceso.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def tool_use_width(binary):
    """El cap del eje 1, leido del guard del ejecutable.

    Se busca la funcion completa, no un fragmento: un recorrido no codicioso
    con un largo arbitrario captura un guard distinto segun el largo elegido.
    """
    found = subprocess.run(
        ['grep', '-aoE',
         r'[A-Za-z_$]{1,6}\(\)\{return [A-Za-z_$.]{1,24}'
         r'\.CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY[^}]{0,40}\}', binary],
        capture_output=True, text=True).stdout.strip()
    default = re.search(r'\?\?\s*(\d+)\}', found)
    return {
        'guard': found or None,
        'default': int(default.group(1)) if default else None,
        'env_value': os.environ.get('CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY'),
    }


def background_cap_declared(binary):
    """Un cap sobre el NUMERO de tareas en segundo plano, si el binario lo trae.

    Su ausencia es un resultado, no un fallo de la sonda: dice que el limite
    no lo pone el cliente. Por eso se devuelve la lista, vacia o no, y nunca
    un booleano — un ``False`` no distingue «no hay» de «no busque bien».
    """
    found = subprocess.run(
        ['grep', '-aoE',
         r'(MAX|LIMIT)[A-Z_]*BACKGROUND[A-Z_]*|BACKGROUND[A-Z_]*(MAX|LIMIT)[A-Z_]*',
         binary], capture_output=True, text=True).stdout.split()
    return sorted(set(found))


def measure_detached(count, seconds, workdir):
    """Lanza ``count`` procesos desprendidos y cuenta el solape real.

    Cada uno escribe su marca de inicio y de fin. El solape maximo se calcula
    barriendo los eventos en orden, que es lo unico que distingue «se lanzaron
    N» de «corrieron N a la vez»: lanzar no es correr.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    for stale in workdir.glob('worker-*.txt'):
        stale.unlink()
    for index in range(count):
        mark = workdir / f'worker-{index:03d}.txt'
        subprocess.Popen(
            ['nohup', 'bash', '-c',
             f'date +%s.%N > {mark}; sleep {seconds}; date +%s.%N >> {mark}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    deadline = time.time() + seconds + 30
    while time.time() < deadline:
        done = [m for m in workdir.glob('worker-*.txt')
                if len(m.read_text().split()) == 2]
        if len(done) == count:
            break
        time.sleep(0.5)

    events = []
    incomplete = 0
    for mark in sorted(workdir.glob('worker-*.txt')):
        parts = mark.read_text().split()
        if len(parts) != 2:
            incomplete += 1
            continue
        events.append((float(parts[0]), +1))
        events.append((float(parts[1]), -1))
    events.sort()
    running = peak = 0
    for _instant, delta in events:
        running += delta
        peak = max(peak, running)
    return {'launched': count, 'completed': len(events) // 2,
            'incomplete': incomplete, 'peak_concurrent': peak}


def machine():
    return {
        'cpus': os.cpu_count(),
        'memory_mb': round(os.sysconf('SC_PAGE_SIZE')
                           * os.sysconf('SC_PHYS_PAGES') / 1024 ** 2),
        'max_user_processes': subprocess.run(
            ['bash', '-c', 'ulimit -u'], capture_output=True,
            text=True).stdout.strip(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=24)
    parser.add_argument('--seconds', type=int, default=6)
    parser.add_argument('--workdir', default=None)
    args = parser.parse_args()

    binary = os.path.realpath(shutil.which('claude') or '')
    workdir = Path(args.workdir or (Path(__file__).parent / 'outputs' / 'workers'))
    report = {
        'measured_at': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
        'binary': binary,
        'machine': machine(),
        'axis_1_tool_use_width': tool_use_width(binary) if binary else None,
        'axis_2_detached_processes': measure_detached(
            args.count, args.seconds, workdir),
        'background_caps_declared_by_the_client':
            background_cap_declared(binary) if binary else None,
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
