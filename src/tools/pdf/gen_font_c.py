#!/usr/bin/env python3
"""Convierte las TTF vendorizadas en un módulo C con los bytes embebidos.

El helper no resuelve rutas en runtime —es ``stdin`` → ``stdout``—, así que la
fuente viaja **dentro** del ejecutable en vez de leerse del disco. Eso elimina
el modo de fallo "fuente no encontrada", que obligaría a elegir entre abortar
o degradar en silencio; y el silencio es lo que H-API-290 costó descubrir.

Se genera en tiempo de compilación (``make``), no se versiona: el ``.ttf`` es
la fuente de verdad y el ``.c`` es derivado, mismo criterio que ``build/``.

Se usa Python y no ``xxd`` porque ``xxd`` viene en ``vim-common`` y no está
garantizado en la máquina destino — la misma clase de suposición que el
vendorizado existe para evitar. Python sí: el producto es Django.

Uso::

    python3 gen_font_c.py <salida.c> <nombre_simbolo>=<archivo.ttf> ...
"""
import pathlib
import sys

#: Bytes por línea en el arreglo generado. 16 mantiene el archivo legible en
#: un diff sin volverlo interminable.
POR_LINEA = 16


def emitir(simbolo: str, datos: bytes) -> str:
    """Un arreglo C `const` con los bytes de la fuente, más su tamaño."""
    lineas = []
    for inicio in range(0, len(datos), POR_LINEA):
        trozo = datos[inicio:inicio + POR_LINEA]
        lineas.append('    ' + ' '.join(f'0x{b:02x},' for b in trozo))
    cuerpo = '\n'.join(lineas)
    return (
        f'const unsigned char {simbolo}[] = {{\n{cuerpo}\n}};\n'
        f'const unsigned int {simbolo}_len = {len(datos)}u;\n'
    )


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        sys.stderr.write(__doc__ or '')
        return 2

    salida = pathlib.Path(argv[1])
    partes = [
        '/* GENERADO por gen_font_c.py — no editar; editar el .ttf del vendor. */\n'
    ]
    declarations = []

    for spec in argv[2:]:
        simbolo, _, ruta = spec.partition('=')
        if not simbolo or not ruta:
            sys.stderr.write(f'spec inválida: {spec!r} (esperado nombre=ruta)\n')
            return 2
        datos = pathlib.Path(ruta).read_bytes()
        if not datos:
            sys.stderr.write(f'{ruta} está vacío\n')
            return 1
        partes.append(emitir(simbolo, datos))
        declarations.append(
            f'extern const unsigned char {simbolo}[];\n'
            f'extern const unsigned int {simbolo}_len;\n'
        )

    salida.write_text('\n'.join(partes))
    salida.with_suffix('.h').write_text(
        '/* GENERADO por gen_font_c.py — no editar. */\n'
        '#ifndef PDF_FONTS_H\n#define PDF_FONTS_H\n\n'
        + '\n'.join(declarations)
        + '\n#endif\n'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
