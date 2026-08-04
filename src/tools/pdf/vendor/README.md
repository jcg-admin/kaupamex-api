# `vendor/` — dependencias nativas vendorizadas

Código de terceros que se compila junto con los helpers de `tools/pdf/`. Se
versiona el **fuente**, no lo compilado (`build/` está en `.gitignore`).

## Por qué vendorizado y no `apt`

El producto L0 se distribuye a servidores de terceros. Asumir que la máquina
destino trae `libhpdf-dev` es la misma clase de suposición que asumir que trae
Apache configurado — precisamente lo que la adopción de Gunicorn embebido
(ADR-027) eliminó. Vendorizar cierra ese hueco para el motor de PDF.

Ventajas medidas frente al camino anterior (`apt-get install libhpdf-dev`):

| Eje | `apt` (antes) | Vendorizado (hoy) |
|---|---|---|
| Origen del paquete | `noble/universe` — repositorio que puede estar deshabilitado | el propio árbol |
| Versión | 2.3.0+dfsg-1build3, la que traiga el distro | **2.4.6**, fija y auditable |
| Deriva entre entornos | posible (cada host su versión) | imposible |
| Herramientas en destino | `apt` + universe habilitado | `gcc` + `make` |

## libharu 2.4.6

- **Upstream:** `github.com/libharu/libharu`, commit `3467749`.
- **Licencia:** ZLIB (`libharu/LICENSE`) — permisiva, permite uso comercial,
  modificación y redistribución; sólo exige no tergiversar el origen y
  conservar el aviso. Compatible con la distribución del producto.
- **Retenido:** 101 de 347 entradas del tarball upstream — `src/` (59 `.c`),
  `include/` (33 `.h`), más `LICENSE`, `CHANGES`, `README.md` y `CMakeLists.txt`
  como procedencia. Pesa 3.5 MB.
- **Descartado:** `bindings/` (C#, Python, Ruby, VB.NET), `demo/`, `win32/`,
  `script/` (makefiles de bcc32/mingw/msvc/cygwin), `.github/`, `doc/`. Ninguno
  participa de un build de C en Linux; conservarlos sería peso muerto en cada
  clon.

### `include/hpdf_config.h` es nuestro, no de upstream

Upstream **no** distribuye ese archivo: lo genera CMake desde
`include/hpdf_config.h.cmake`. Aquí está instanciado a mano —cuatro `#define`—
para que baste `make` en el destino y no haga falta CMake. El archivo documenta
en su cabecera qué decisión se tomó en cada símbolo.

Consecuencia a respetar: los defines y las banderas de enlace del `Makefile`
tienen que decir lo mismo. `LIBHPDF_HAVE_LIBPNG` sin `-lpng` no compila.

## Cómo actualizar libharu

1. Obtener el tarball de la versión nueva desde upstream.
2. Extraer **sólo** `include/`, `src/`, `LICENSE`, `CHANGES`, `README.md` y
   `CMakeLists.txt` sobre `vendor/libharu/`.
3. Reponer `include/hpdf_config.h` — la extracción no lo trae, y sin él no
   compila. Comparar antes `include/hpdf_config.h.cmake` con el de esta versión:
   si upstream añadió símbolos, instanciarlos.
4. `make distclean && make check` — el gate sale distinto de cero si algo rompió.
5. Correr el smoke de ambos helpers (JSON por stdin, PDF por stdout) antes de
   dar por buena la actualización: que compile no prueba que genere PDF.
6. Actualizar la versión citada aquí, en el `Makefile` y en ADR-017.

## Cifrado — lo que esta versión sí y no da

ADR-017 registró que libharu 2.3.0 sólo ofrece RC4 y que AES-256 quedaba para
una fase posterior con `qpdf`. La 2.4.6 trae `src/hpdf_encrypt.c` y
`src/hpdf_encryptdict.c`, pero **eso no se ha medido** contra el requisito de
AES-256: que los archivos existan no dice qué algoritmos implementan. La nota
de ADR-017 sigue vigente hasta que alguien lo verifique leyendo el fuente.
