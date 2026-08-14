/*
 * hpdf_config.h — instancia a mano de include/hpdf_config.h.cmake (libharu 2.4.6).
 *
 * Upstream genera este archivo con CMake. Aquí se escribe fijo para que el
 * producto compile con `make` plano: un servidor de terceros recibe el árbol y
 * ejecuta `make` sin necesitar CMake instalado. Es la misma premisa que llevó a
 * Gunicorn embebido — no asumir herramientas en la máquina destino.
 *
 * Por qué vive AQUÍ y no en vendor/libharu/include/
 * --------------------------------------------------
 * Porque es NUESTRO, no de upstream: lo escribimos nosotros al decidir
 * prescindir de CMake. El `.gitignore` que viene dentro del tarball de libharu
 * lista `hpdf_config.h` (línea 2) porque para upstream es una salida de build —
 * y esa regla heredada lo mantuvo fuera del repositorio en silencio. El árbol
 * local compilaba con una copia sin versionar; un clon limpio recibía sólo la
 * plantilla `.cmake` y moría en el primer objeto:
 *
 *     vendor/libharu/include/hpdf_utils.h:21:10: fatal error:
 *         hpdf_config.h: No such file or directory
 *
 * Sacarlo del árbol vendorizado resuelve las dos mitades a la vez: el archivo
 * se versiona (ninguna regla ajena lo alcanza) y `vendor/` sigue idéntico al
 * tarball, así que actualizar libharu no obliga a reaplicar un parche nuestro
 * sobre su `.gitignore`. Ver H-API-397.
 *
 * Los cuatro símbolos de la plantilla, con la decisión tomada para cada uno:
 *
 *   LIBHPDF_HAVE_LIBPNG   ON  — pdf_receipt dibuja el logo del emisor con
 *                               HPDF_LoadPngImageFromFile. Sin esto, libharu
 *                               compila el stub que devuelve HPDF_NOPNGLIB y el
 *                               recibo sale sin logo (degradación ya prevista en
 *                               pdf_receipt.c, no un fallo).
 *   LIBHPDF_HAVE_ZLIB     ON  — HPDF_SetCompressionMode(HPDF_COMP_ALL) sólo
 *                               comprime si zlib está enlazado.
 *   LIBHPDF_DEBUG         OFF — build de producción.
 *   LIBHPDF_DEBUG_TRACE   OFF — idem.
 *
 * Si se cambia alguno, ajustar también LDLIBS en el Makefile: los defines y las
 * banderas de enlace tienen que decir lo mismo o el enlace falla por símbolos
 * ausentes.
 */

/* Define to 1 if you have the `png' library (-lpng). */
#define LIBHPDF_HAVE_LIBPNG

/* Define to 1 if you have the `z' library (-lz). */
#define LIBHPDF_HAVE_ZLIB

/* debug build */
/* #undef LIBHPDF_DEBUG */

/* debug trace enabled */
/* #undef LIBHPDF_DEBUG_TRACE */
