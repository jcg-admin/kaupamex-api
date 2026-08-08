# `vendor/fonts/` — catálogo tipográfico del motor de documentos

Fuentes que los helpers de `tools/pdf/` **embeben** en cada PDF. Se versiona
el `.ttf`, igual que `vendor/libharu/` versiona el fuente de la librería.

## Por qué vendorizado y no del sistema

Misma razón que `vendor/README.md` da para libharu: el producto L0 se
distribuye a servidores de terceros, y *asumir que la máquina destino trae la
fuente es la misma clase de suposición que asumir que trae Apache
configurado*. Una fuente de `/usr/share/fonts` reintroduce exactamente ese
hueco.

La referencia hace lo mismo: **138 archivos** bajo
`odoo19c: addons/web/static/fonts/`, con una familia por directorio. Que su
directorio se llame `google/` no significa que se pidan en runtime — se
copiaron una vez.

## Por qué embebida en el PDF y no referenciada

DEC-01 de la iniciativa `integrar-libharu`, con el peso medido del mismo
contenido:

| Variante | Tamaño | |
|---|---|---|
| WinAnsi (sin TTF) | 1 294 B | pierde `€`, comillas tipográficas, no-latinos |
| TTF referenciada | 12 527 B | depende del visor del destinatario |
| **TTF embebida** | **178 567 B** | **elegida** — se ve igual en todas partes |

El documento va a un tercero cuyo visor no controlamos. 178 KB es el precio de
que se vea igual, y es determinista.

## Por qué compilada dentro del binario

El helper no resuelve nada en runtime: es `stdin` → `stdout`. Leer la fuente
de una ruta añadiría el modo de fallo "fuente no encontrada", que obligaría a
elegir entre abortar o degradar en silencio — y el silencio es justo lo que
H-API-290 costó descubrir. El `.ttf` se convierte a un arreglo C en tiempo de
compilación (`gen_font_c.py`) y viaja dentro del ejecutable.

## Estructura

Una familia por directorio, con su licencia al lado:

```
vendor/fonts/
├── README.md                  ← este archivo
└── liberation-sans/
    ├── LICENSE                ← SIL-OFL-1.1
    ├── LiberationSans-Regular.ttf
    └── LiberationSans-Bold.ttf
```

Añadir la segunda familia es copiar un directorio y añadir una fila al enum —
no rediseñar.

## Familias

| Familia | Variantes | Licencia | Por qué |
|---|---|---|---|
| `liberation-sans` | Regular, Bold | SIL-OFL-1.1 | Métricamente compatible con Helvetica, la que el helper usaba antes: el cambio no mueve el diseño existente |

**Se arranca con una.** El catálogo de ocho de la referencia pesa ~6,6 MB, y
todavía no hay quién elija entre ellas: la elección por L1 es la
sub-iniciativa que DEC-03 nombra.

## Qué NO va aquí

Fuentes subidas por un L1. La referencia tampoco lo permite —`res.company.font`
es un `Selection` cerrado, no un `Binary`— y esa restricción es lo que mantiene
acotado el costo: N fuentes vendorizadas una vez, no un binario arbitrario por
compañía.
