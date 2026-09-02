"""Hasta cuantos trabajadores PAGA repartir, con trabajo que usa CPU.

La sonda principal mide con procesos dormidos y da el solape del planificador:
24 de 24. Eso responde «cuantos caben», no «cuantos sirven». Con trabajo real
la CPU es el recurso escaso, asi que el reparto deja de pagar donde el numero
de trabajadores pasa al de nucleos.

Reparte una carga FIJA entre N trabajadores y mide el reloj de pared. El
trabajo total es constante: lo que cambia es en cuantas partes se corta.
"""
import os
import subprocess
import sys
import time

TOTAL_UNITS = 24
BODY = ("python3 -c \"import hashlib;"
        "d=b'x'*4096;"
        "[hashlib.sha256(d*64).digest() for _ in range(1200)]\"")


def run_with(workers):
    """Corre TOTAL_UNITS unidades repartidas en ``workers`` procesos a la vez."""
    started = time.time()
    pending, running = list(range(TOTAL_UNITS)), []
    while pending or running:
        while pending and len(running) < workers:
            pending.pop()
            running.append(subprocess.Popen(
                ['bash', '-c', BODY],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        running = [p for p in running if p.poll() is None] or running
        for process in list(running):
            if process.poll() is not None:
                running.remove(process)
        time.sleep(0.05)
    return time.time() - started


def main():
    print(f'nucleos: {os.cpu_count()} · unidades fijas: {TOTAL_UNITS}')
    print(f'{"trabajadores":>12} {"reloj (s)":>10} {"aceleracion":>12}')
    base = None
    for workers in (1, 2, 4, 8, 16):
        elapsed = run_with(workers)
        base = base or elapsed
        print(f'{workers:>12} {elapsed:>10.2f} {base / elapsed:>11.2f}x')


if __name__ == '__main__':
    sys.exit(main())
