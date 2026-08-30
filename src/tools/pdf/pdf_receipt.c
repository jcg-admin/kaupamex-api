/*
 * pdf_receipt.c — PDF receipt generator
 *
 * Reads a JSON receipt descriptor from stdin and writes a PDF document to
 * stdout, generated with libharu (libhpdf 2.3.0). See ADR-017
 * (adr-017-libreria-pdf-libharu) for the architecture decision: a compiled
 * C helper invoked via subprocess, isolating the WSGI worker from any native
 * libharu crash.
 *
 * Build:
 *   gcc pdf_receipt.c -o pdf_receipt -lhpdf
 *
 * Contract (stdin JSON):
 *   {
 *     "issuer":  { "name", "address", "email", "phone", "logo_path" },
 *     "buyer":   { "name", "address" },
 *     "order_number": "PY-XXXXXXXX",
 *     "date": "2026-06-03T05:08:08",
 *     "currency": "MXN",
 *     "items": [ { "name", "sku", "quantity", "unit_price", "amount" }, ... ],
 *     "totals":  { "subtotal", "tax", "shipping", "discount", "total" },
 *     "payment": { "method", "status" }
 *   }
 *
 * All numeric fields are passed as already-formatted strings from Django to
 * avoid float/Decimal drift; the helper only lays them out.
 *
 * Exit codes:
 *   0  success (PDF on stdout)
 *   1  bad / unparseable JSON on stdin
 *   2  libharu error (PDF generation failed)
 *   3  read error
 *
 * NOTE: a small self-contained JSON reader is used so the helper links only
 * against libharu (-lhpdf) and needs no extra system JSON library.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <zlib.h>
#include <hpdf.h>
#include "pdf_fonts.h"

/* ------------------------------------------------------------------ *
 *  Input buffering                                                    *
 * ------------------------------------------------------------------ */

static char  *g_input = NULL;
static size_t g_len   = 0;

static int
read_all_stdin(void)
{
    size_t cap = 65536;
    size_t n   = 0;
    char  *buf = malloc(cap);
    if (!buf) return -1;
    for (;;) {
        if (n + 4096 > cap) {
            cap *= 2;
            char *nb = realloc(buf, cap);
            if (!nb) { free(buf); return -1; }
            buf = nb;
        }
        size_t r = fread(buf + n, 1, 4096, stdin);
        n += r;
        if (r < 4096) {
            if (feof(stdin)) break;
            if (ferror(stdin)) { free(buf); return -1; }
        }
    }
    buf[n]  = '\0';
    g_input = buf;
    g_len   = n;
    return 0;
}

/* ------------------------------------------------------------------ *
 *  Minimal JSON reader                                                *
 *                                                                     *
 *  Supports just the subset the receipt contract uses:                *
 *  objects, arrays, strings (with \" \\ \n \t \/ \uXXXX escapes),     *
 *  scoped lookup by key.  Not a general parser — purpose-built.       *
 * ------------------------------------------------------------------ */

static const char *
skip_ws(const char *p)
{
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
    return p;
}

/* Skip a complete JSON value starting at p, return pointer just past it. */
static const char *
skip_value(const char *p)
{
    p = skip_ws(p);
    if (*p == '"') {
        p++;
        while (*p && *p != '"') {
            if (*p == '\\' && p[1]) p += 2;
            else p++;
        }
        if (*p == '"') p++;
        return p;
    }
    if (*p == '{' || *p == '[') {
        char open  = *p;
        char close = (open == '{') ? '}' : ']';
        int depth  = 0;
        for (; *p; p++) {
            if (*p == '"') {
                p++;
                while (*p && *p != '"') {
                    if (*p == '\\' && p[1]) p++;
                    p++;
                }
                if (!*p) break;
            } else if (*p == open) {
                depth++;
            } else if (*p == close) {
                depth--;
                if (depth == 0) { p++; break; }
            }
        }
        return p;
    }
    /* number / true / false / null */
    while (*p && *p != ',' && *p != '}' && *p != ']' &&
           *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r')
        p++;
    return p;
}

/*
 * Within the object whose body starts at obj (pointing AT the '{'), find the
 * value for key. Returns pointer to the start of the value (after ':') or
 * NULL. Only scans the top level of that object.
 */
static const char *
obj_find(const char *obj, const char *key)
{
    const char *p = skip_ws(obj);
    if (*p != '{') return NULL;
    p++;
    for (;;) {
        p = skip_ws(p);
        if (*p == '}' || *p == '\0') return NULL;
        if (*p != '"') return NULL;
        /* read key */
        const char *ks = ++p;
        const char *ke = ks;
        while (*ke && *ke != '"') {
            if (*ke == '\\' && ke[1]) ke += 2;
            else ke++;
        }
        size_t klen = (size_t)(ke - ks);
        p = (*ke == '"') ? ke + 1 : ke;
        p = skip_ws(p);
        if (*p == ':') p++;
        p = skip_ws(p);
        int match = (strlen(key) == klen && strncmp(ks, key, klen) == 0);
        if (match) return p;
        p = skip_value(p);
        p = skip_ws(p);
        if (*p == ',') p++;
    }
}

/*
 * Escribe `cp` como UTF-8 en `out`; devuelve los bytes escritos, o 0 si no
 * caben en `espacio`. El documento habla UTF-8 desde que la fuente es
 * LiberationSans embebida con HPDF_UseUTFEncodings (DEC-01 de
 * `integrar-libharu`) — antes hablaba WinAnsi, un byte por carácter.
 */
static size_t
utf8_encode(unsigned long cp, char *out, size_t espacio)
{
    if (cp < 0x80) {
        if (espacio < 1) return 0;
        out[0] = (char)cp;
        return 1;
    }
    if (cp < 0x800) {
        if (espacio < 2) return 0;
        out[0] = (char)(0xC0 | (cp >> 6));
        out[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        if (espacio < 3) return 0;
        out[0] = (char)(0xE0 | (cp >> 12));
        out[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    }
    if (cp <= 0x10FFFF) {
        if (espacio < 4) return 0;
        out[0] = (char)(0xF0 | (cp >> 18));
        out[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
        out[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[3] = (char)(0x80 | (cp & 0x3F));
        return 4;
    }
    return 0;
}

/*
 * Decode a JSON string value at p (pointing AT the opening '"') into out
 * (size cap). Returns 1 on success, 0 if p is not a string.
 */
static int
json_string(const char *p, char *out, size_t cap)
{
    p = skip_ws(p);
    if (*p != '"') { if (cap) out[0] = '\0'; return 0; }
    p++;
    size_t o = 0;
    while (*p && *p != '"' && o + 1 < cap) {
        if (*p == '\\') {
            p++;
            switch (*p) {
                case 'n': out[o++] = '\n'; break;
                case 't': out[o++] = ' ';  break;
                case 'r': break;
                case '"': out[o++] = '"';  break;
                case '\\': out[o++] = '\\'; break;
                case '/': out[o++] = '/';  break;
                case 'u': {
                    /* Decodifica \uXXXX a UTF-8, que es lo que el documento
                       habla desde que la fuente es TrueType embebida.

                       Antes esta rama plegaba a UN byte WinAnsi y mandaba
                       '?' para todo lo que pasara de U+00FF: perdía el '€',
                       el em-dash y las comillas tipográficas. Con la fuente
                       UTF ese plegado además producía mojibake ("José" ->
                       "Jos?u"), porque el byte Latin-1 llegaba a un lector
                       que espera UTF-8. Medido en la sonda de T-002.

                       El productor manda \uXXXX (ensure_ascii=True), así que
                       esta rama es la que reconstruye el carácter; la rama
                       `default` copia bytes tal cual, lo que ahora también es
                       correcto para UTF-8 crudo. Ver H-API-290. */
                    if (p[1] && p[2] && p[3] && p[4]) {
                        char hex[5] = { p[1], p[2], p[3], p[4], 0 };
                        unsigned long cp = strtoul(hex, NULL, 16);
                        p += 4;
                        /* Par suplente UTF-16: 😀 es UN codepoint.
                           Sin esto cada mitad se escribiría por separado y el
                           resultado no es un carácter válido. */
                        if (cp >= 0xD800 && cp <= 0xDBFF &&
                            p[1] == '\\' && p[2] == 'u' &&
                            p[3] && p[4] && p[5] && p[6]) {
                            char bajo[5] = { p[3], p[4], p[5], p[6], 0 };
                            unsigned long lo = strtoul(bajo, NULL, 16);
                            if (lo >= 0xDC00 && lo <= 0xDFFF) {
                                cp = 0x10000UL + ((cp - 0xD800) << 10)
                                   + (lo - 0xDC00);
                                p += 6;
                            }
                        }
                        o += utf8_encode(cp, out + o, cap - o - 1);
                    }
                    break;
                }
                default: out[o++] = *p; break;
            }
            if (*p) p++;
        } else {
            out[o++] = *p++;
        }
    }
    out[o] = '\0';
    return 1;
}

/* Valor base64 de un carácter, o -1 fuera del alfabeto (RFC 4648). */
static int
b64_value(unsigned char c)
{
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

/*
 * Decodifica base64 a un buffer malloc'eado; ignora espacio en blanco y el
 * padding '='. Devuelve NULL ante un carácter fuera del alfabeto: un logo
 * corrupto degrada a "sin logo" aguas arriba, no aborta el documento.
 */
static unsigned char *
base64_decode(const char *src, size_t src_len, size_t *out_len)
{
    unsigned char *out = malloc(src_len / 4 * 3 + 3);
    if (!out) return NULL;
    size_t o = 0;
    unsigned int acc = 0;
    int nbits = 0;
    for (size_t i = 0; i < src_len; i++) {
        unsigned char c = (unsigned char)src[i];
        if (c == '=' || c == '\n' || c == '\r' || c == ' ' || c == '\t')
            continue;
        int v = b64_value(c);
        if (v < 0) { free(out); return NULL; }
        acc = (acc << 6) | (unsigned int)v;
        nbits += 6;
        if (nbits >= 8) {
            nbits -= 8;
            out[o++] = (unsigned char)((acc >> nbits) & 0xFF);
        }
    }
    *out_len = o;
    return out;
}

/* Convenience: obj.key -> string into out. Empty string if missing. */
static void
get_str(const char *obj, const char *key, char *out, size_t cap)
{
    const char *v = obj_find(obj, key);
    if (!v) { if (cap) out[0] = '\0'; return; }
    json_string(v, out, cap);
}

/* ------------------------------------------------------------------ *
 *  libharu error handling                                             *
 * ------------------------------------------------------------------ */

static jmp_buf g_env;

#ifndef HPDF_NOPNGLIB
#define HPDF_NOPNGLIB 0
#endif

static void
hpdf_error_handler(HPDF_STATUS error_no, HPDF_STATUS detail_no,
                   void *user_data)
{
    (void)user_data;
    fprintf(stderr, "libharu error: error_no=0x%04X detail_no=%lu\n",
            (unsigned)error_no, (unsigned long)detail_no);
    longjmp(g_env, 1);
}

/*
 * Verifica la integridad estructural de un PNG: firma, camino de chunks con
 * longitudes acotadas al buffer, CRC de cada chunk (crc32 de zlib, ya
 * enlazada), IHDR primero e IEND al final exacto.
 *
 * No es paranoia: el PngErrorFunc del libharu vendorizado RETORNA, y libpng
 * exige que su callback de error no retorne — con un cuerpo corrupto tras
 * la firma el proceso queda COLGADO, no abortado (medido: timeout con
 * `\x89PNG...` + basura; ver H-API-294). A libpng sólo se le entrega un
 * PNG que pasó este camino; lo demás degrada a "sin logo".
 */
static int
png_is_structurally_valid(const unsigned char *p, size_t n)
{
    static const unsigned char firma[8] =
        { 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A };
    if (n < 8 + 25 + 12) return 0;   /* firma + IHDR(13) + IEND vacio */
    if (memcmp(p, firma, 8) != 0) return 0;
    size_t off = 8;
    int primero = 1;
    while (off + 12 <= n) {
        size_t len = ((size_t)p[off] << 24) | ((size_t)p[off + 1] << 16)
                   | ((size_t)p[off + 2] << 8) | (size_t)p[off + 3];
        if (len > n - off - 12) return 0;      /* chunk truncado */
        const unsigned char *tag = p + off + 4;
        unsigned long crc_leido =
              ((unsigned long)p[off + 8 + len] << 24)
            | ((unsigned long)p[off + 9 + len] << 16)
            | ((unsigned long)p[off + 10 + len] << 8)
            |  (unsigned long)p[off + 11 + len];
        if (crc32(0L, tag, (uInt)(len + 4)) != crc_leido) return 0;
        if (primero) {
            if (memcmp(tag, "IHDR", 4) != 0) return 0;
            primero = 0;
        }
        off += 12 + len;
        if (memcmp(tag, "IEND", 4) == 0)
            return off == n;                   /* sin basura al final */
    }
    return 0;                                  /* se acabó sin IEND */
}

/*
 * Carga un PNG desde memoria aislando el fallo: LoadPngImageFromMem falla
 * vía CheckError -> handler -> longjmp, y un logo corrupto no debe abortar
 * el recibo. El setjmp anidado vive en ESTA función para no exponer las
 * variables de main a -Wclobbered; `img` es volatile porque se escribe
 * entre el setjmp y un posible longjmp.
 */
static HPDF_Image
load_logo_guarded(HPDF_Doc pdf, const unsigned char *png, size_t nb)
{
    jmp_buf salvado;
    memcpy(salvado, g_env, sizeof(jmp_buf));
    volatile HPDF_Image img = NULL;
    if (setjmp(g_env) == 0)
        img = HPDF_LoadPngImageFromMem(pdf, png, (HPDF_UINT)nb);
    else {
        img = NULL;                          /* degrada a "sin logo" */
        HPDF_ResetError(pdf);
    }
    memcpy(g_env, salvado, sizeof(jmp_buf));
    return img;
}

/* ------------------------------------------------------------------ *
 *  Layout helpers                                                     *
 * ------------------------------------------------------------------ */

#define MARGIN_L   50.0f
#define MARGIN_R   50.0f
#define MARGIN_T   52.0f
#define MARGIN_B   60.0f

/* Un milimetro en puntos PostScript, que es la unidad del PDF (72 / 25.4). */
#define MM_TO_PT   2.8346457f

/*
 * Geometria de pagina — los ajustes de papel que el descriptor trae.
 *
 * Gemelo del bloque de pdf_report.c, duplicado a proposito: cada helper se
 * enlaza solo contra libharu y no comparte unidad de compilacion, que es la
 * forma que este directorio ya seguia con su lector de JSON.
 *
 * La clave `paperformat` llega resuelta a milimetros por
 * `_paperformat_geometry` de ir_actions_report, que consulta las 31 claves de
 * `report.paperformat`. Se resuelve alli y no aqui porque HPDF_PageSizes solo
 * declara 12 tamanos: SetWidth/SetHeight cubre los 31.
 *
 * Sin la clave se conservan las constantes de arriba.
 */
typedef struct {
    float width, height;                          /* puntos; 0 = no fijar */
    float margin_l, margin_r, margin_t, margin_b; /* puntos */
} paper_t;

/*
 * Un numero del descriptor, o `fallback` si la clave no esta. Acepta el
 * numero desnudo y el numero entre comillas: el porte de
 * `_build_wkhtmltopdf_args` conserva la forma de texto de wkhtmltopdf.
 */
static float
get_num(const char *obj, const char *key, float fallback)
{
    const char *v = obj_find(obj, key);
    if (!v) return fallback;
    if (*v == '"') v++;
    char *end = NULL;
    float value = strtof(v, &end);
    return (end == v) ? fallback : value;
}

static void
read_paper(const char *root, paper_t *paper)
{
    paper->width    = 0.0f;
    paper->height   = 0.0f;
    paper->margin_l = MARGIN_L;
    paper->margin_r = MARGIN_R;
    paper->margin_t = MARGIN_T;
    paper->margin_b = MARGIN_B;

    const char *pf = obj_find(root, "paperformat");
    if (!pf) return;
    pf = skip_ws(pf);
    if (*pf != '{') return;

    paper->width    = get_num(pf, "page_width_mm",  0.0f) * MM_TO_PT;
    paper->height   = get_num(pf, "page_height_mm", 0.0f) * MM_TO_PT;
    paper->margin_l = get_num(pf, "margin_left_mm",
                              MARGIN_L / MM_TO_PT) * MM_TO_PT;
    paper->margin_r = get_num(pf, "margin_right_mm",
                              MARGIN_R / MM_TO_PT) * MM_TO_PT;
    paper->margin_t = get_num(pf, "margin_top_mm",
                              MARGIN_T / MM_TO_PT) * MM_TO_PT;
    paper->margin_b = get_num(pf, "margin_bottom_mm",
                              MARGIN_B / MM_TO_PT) * MM_TO_PT;
}

/*
 * Una pagina nueva con la geometria pedida. Sin `paperformat` cae en A4
 * vertical, que es lo que este helper hacia antes de que el descriptor
 * pudiera declararlo.
 */
static HPDF_Page
new_page(HPDF_Doc pdf, const paper_t *paper)
{
    HPDF_Page page = HPDF_AddPage(pdf);
    HPDF_Page_SetSize(page, HPDF_PAGE_SIZE_A4, HPDF_PAGE_PORTRAIT);
    if (paper->width > 0.0f && paper->height > 0.0f) {
        HPDF_Page_SetWidth(page, paper->width);
        HPDF_Page_SetHeight(page, paper->height);
    }
    return page;
}

static void
draw_text(HPDF_Page page, HPDF_Font font, float size,
          float x, float y, const char *txt)
{
    HPDF_Page_SetFontAndSize(page, font, size);
    HPDF_Page_BeginText(page);
    HPDF_Page_TextOut(page, x, y, txt ? txt : "");
    HPDF_Page_EndText(page);
}

/* Right-aligned text ending at right_x. */
static void
draw_text_right(HPDF_Page page, HPDF_Font font, float size,
                float right_x, float y, const char *txt)
{
    if (!txt) txt = "";
    HPDF_Page_SetFontAndSize(page, font, size);
    float w = HPDF_Page_TextWidth(page, txt);
    HPDF_Page_BeginText(page);
    HPDF_Page_TextOut(page, right_x - w, y, txt);
    HPDF_Page_EndText(page);
}

/*
 * Dibuja `txt` envuelto por palabras dentro de `width` puntos desde (x, y).
 * Devuelve la `y` de la línea SIGUIENTE al texto dibujado (T-004).
 *
 * Se apoya en HPDF_Page_TextRect, que envuelve y reporta en `len` cuántos
 * bytes entraron. Ante caja insuficiente devuelve
 * HPDF_PAGE_INSUFFICIENT_SPACE SIN pasar por el manejador de errores
 * (hpdf_page_operator.c:2631, medido en el vendor) — así que no dispara el
 * setjmp del main: el texto simplemente se corta en la última línea que
 * cupo. `max_lines` acota la caja: una dirección kilométrica no debe
 * comerse el recibo.
 */
static float
draw_text_wrapped(HPDF_Page page, HPDF_Font font, float size, float x,
                  float y, float width, int max_lines, const char *txt)
{
    if (!txt || !txt[0]) return y;
    float line_h = size + 4.0f;
    float top = y + size;            /* TextRect recibe el TOPE de la caja */
    float bottom = top - line_h * (float)max_lines;
    HPDF_UINT len = 0;

    HPDF_Page_SetFontAndSize(page, font, size);
    HPDF_Page_BeginText(page);
    HPDF_Page_TextRect(page, x, top, x + width, bottom, txt,
                       HPDF_TALIGN_LEFT, &len);
    /* La posición de texto quedó donde TextRect terminó; su `y` relativa a
       `top` dice cuántas líneas se consumieron de verdad. */
    HPDF_Point pos = HPDF_Page_GetCurrentTextPos(page);
    HPDF_Page_EndText(page);

    float used = top - pos.y;        /* alto consumido dentro de la caja */
    if (used < line_h) used = line_h;
    return y - used;
}

/*
 * Recorta `txt` in situ para que quepa en `ancho_max` PUNTOS, no en un número
 * de bytes.
 *
 * El corte por bytes que esto reemplaza (`if (strlen(name) > 36)`) medía la
 * unidad equivocada: en UTF-8 un acento ocupa dos, así que el presupuesto de
 * columna dependía del juego de caracteres — 36 bytes son 36 letras latinas
 * pero sólo 18 acentuadas. Medido en el pase de T-002.
 *
 * Se retrocede hasta el inicio del carácter UTF-8 anterior (los bytes de
 * continuación son 10xxxxxx). Cortar a media secuencia no corrompe el papel
 * —libharu descarta el byte huérfano, también medido— pero dejaría el ancho
 * dibujado por debajo del que se acaba de medir.
 */
static void
truncar_a_ancho(HPDF_Page page, HPDF_Font font, float size,
                char *txt, float ancho_max)
{
    HPDF_Page_SetFontAndSize(page, font, size);
    size_t n = strlen(txt);
    while (n > 0 && HPDF_Page_TextWidth(page, txt) > ancho_max) {
        do { n--; } while (n > 0 && ((unsigned char)txt[n] & 0xC0) == 0x80);
        txt[n] = '\0';
    }
}

/* ------------------------------------------------------------------ *
 *  Main                                                               *
 * ------------------------------------------------------------------ */

/* --- catálogo tipográfico embebido (DEC-01/DEC-02 de `integrar-libharu`) ---
 *
 * La fuente viaja DENTRO del binario (build/pdf_fonts.c, generado desde el
 * .ttf vendorizado). No se lee de /usr/share/fonts ni de ninguna ruta: el
 * helper no resuelve nada en runtime, así que no tiene un modo de fallo
 * "fuente no encontrada" que obligara a elegir entre abortar y degradar en
 * silencio — y el silencio es lo que H-API-290 costó descubrir.
 *
 * Con UTF-8 + TrueType desaparecen las tres limitaciones que WinAnsi imponía:
 * el plegado a un byte, el '?' para todo lo que pase de U+00FF, y la
 * aproximación en 80-9F. LiberationSans es métricamente compatible con
 * Helvetica —la que se usaba antes—, así que el diseño no se mueve.
 */
static HPDF_Font
cargar_fuente(HPDF_Doc pdf, const unsigned char *datos, unsigned int largo)
{
    const char *nombre = HPDF_LoadTTFontFromMemory(pdf, datos, largo, HPDF_TRUE);
    if (!nombre)
        return NULL;
    return HPDF_GetFont(pdf, nombre, "UTF-8");
}

int
main(void)
{
    if (read_all_stdin() != 0) {
        fprintf(stderr, "pdf_receipt: failed to read stdin\n");
        return 3;
    }
    if (g_len == 0) {
        fprintf(stderr, "pdf_receipt: empty stdin\n");
        return 1;
    }
    const char *root = skip_ws(g_input);
    if (*root != '{') {
        fprintf(stderr, "pdf_receipt: stdin is not a JSON object\n");
        free(g_input);
        return 1;
    }

    HPDF_Doc pdf = HPDF_New(hpdf_error_handler, NULL);
    if (!pdf) {
        fprintf(stderr, "pdf_receipt: HPDF_New failed\n");
        free(g_input);
        return 2;
    }

    if (setjmp(g_env)) {
        /* libharu raised an error somewhere below */
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }

    HPDF_SetCompressionMode(pdf, HPDF_COMP_ALL);

    if (HPDF_UseUTFEncodings(pdf) != HPDF_OK) {
        fprintf(stderr, "pdf_receipt: no se pudo registrar el encoder UTF-8\n");
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }
    HPDF_Font font      = cargar_fuente(pdf, liberation_sans_regular,
                                        liberation_sans_regular_len);
    HPDF_Font font_bold = cargar_fuente(pdf, liberation_sans_bold,
                                        liberation_sans_bold_len);
    if (!font || !font_bold) {
        fprintf(stderr, "pdf_receipt: no se pudo cargar la fuente embebida\n");
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }

    paper_t paper;
    read_paper(root, &paper);

    HPDF_Page page = new_page(pdf, &paper);
    float page_w = HPDF_Page_GetWidth(page);
    float right_edge = page_w - paper.margin_r;

    char buf[1024];
    float y = HPDF_Page_GetHeight(page) - paper.margin_t;

    /* ---- Issuer block + logo ---- */
    const char *issuer = obj_find(root, "issuer");
    if (issuer) {
        /* Logo embebido en el descriptor (T-006): base64 de un PNG, cargado
           con HPDF_LoadPngImageFromMem. El helper no toca el filesystem —
           antes leía ``logo_path`` con LoadPngImageFromFile. El alfabeto
           base64 no contiene '"' ni '\\', así que el fin de la cadena JSON
           es la próxima comilla, sin escapes que decodificar. */
        const char *logoval = obj_find(issuer, "logo");
        if (logoval) {
            const char *q = skip_ws(logoval);
            const char *b64 = (*q == '"') ? q + 1 : NULL;
            const char *b64_end = b64 ? strchr(b64, '"') : NULL;
            unsigned char *png = NULL;
            size_t nb = 0;
            if (b64_end && b64_end > b64)
                png = base64_decode(b64, (size_t)(b64_end - b64), &nb);
            /* La validación estructural es la que evita el CUELGUE del
               vendor con PNG corrupto (H-API-294); el setjmp anidado de
               load_logo_guarded cubre lo que aún pase el filtro. */
            HPDF_Image img = NULL;
            if (png && png_is_structurally_valid(png, nb))
                img = load_logo_guarded(pdf, png, nb);
            free(png);
            if (img) {
                float iw = (float)HPDF_Image_GetWidth(img);
                float ih = (float)HPDF_Image_GetHeight(img);
                float draw_w = 120.0f;
                float draw_h = (iw > 0) ? draw_w * ih / iw : 60.0f;
                if (draw_h > 80.0f) { draw_h = 80.0f; draw_w = (ih > 0) ? draw_h * iw / ih : 120.0f; }
                HPDF_Page_DrawImage(page, img,
                                    right_edge - draw_w, y - draw_h,
                                    draw_w, draw_h);
            }
        }

        get_str(issuer, "name", buf, sizeof(buf));
        draw_text(page, font_bold, 18, paper.margin_l, y, buf);
        y -= 22;
        get_str(issuer, "address", buf, sizeof(buf));
        /* La dirección se ENVUELVE, no se corta (T-004): el ancho es la
           mitad izquierda —el logo vive a la derecha— y 3 líneas bastan
           para cualquier dirección postal razonable. */
        if (buf[0]) y = draw_text_wrapped(page, font, 10, paper.margin_l, y,
                                          280.0f, 3, buf);
        get_str(issuer, "email", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, paper.margin_l, y, buf); y -= 14; }
        get_str(issuer, "phone", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, paper.margin_l, y, buf); y -= 14; }
    }

    y -= 10;

    /* ---- Title ---- */
    draw_text(page, font_bold, 15, paper.margin_l, y, "RECIBO DE COMPRA");
    y -= 22;

    /* ---- Order number + date ---- */
    get_str(root, "order_number", buf, sizeof(buf));
    char line[1100];
    snprintf(line, sizeof(line), "Orden: %s", buf);
    draw_text(page, font_bold, 11, paper.margin_l, y, line);
    get_str(root, "date", buf, sizeof(buf));
    snprintf(line, sizeof(line), "Fecha: %s", buf);
    draw_text_right(page, font, 11, right_edge, y, line);
    y -= 24;

    /* ---- Buyer block ---- */
    const char *buyer = obj_find(root, "buyer");
    if (buyer) {
        draw_text(page, font_bold, 11, paper.margin_l, y, "Comprador");
        y -= 15;
        get_str(buyer, "name", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, paper.margin_l, y, buf); y -= 13; }
        get_str(buyer, "address", buf, sizeof(buf));
        /* Envuelta a todo el ancho imprimible (T-004). */
        if (buf[0]) y = draw_text_wrapped(page, font, 10, paper.margin_l, y,
                                          right_edge - paper.margin_l, 3, buf);
    }
    y -= 12;

    /* ---- Items table header ---- */
    float col_name = paper.margin_l;
    float col_sku  = 250.0f;
    float col_qty  = 360.0f;   /* right-aligned at */
    float col_pu   = 450.0f;   /* right-aligned at */
    float col_amt  = right_edge;

    /* Banda sombreada del encabezado (T-005): los glifos se pintan con el
       fill color, así que se restaura negro antes de escribir encima. */
    HPDF_Page_SetRGBFill(page, 0.92f, 0.92f, 0.92f);
    HPDF_Page_Rectangle(page, paper.margin_l, y - 4.0f,
                        right_edge - paper.margin_l, 16.0f);
    HPDF_Page_Fill(page);
    HPDF_Page_SetRGBFill(page, 0.0f, 0.0f, 0.0f);

    HPDF_Page_SetLineWidth(page, 0.5f);
    HPDF_Page_MoveTo(page, paper.margin_l, y + 12);
    HPDF_Page_LineTo(page, right_edge, y + 12);
    HPDF_Page_Stroke(page);

    draw_text(page, font_bold, 10, col_name, y, "Producto");
    draw_text(page, font_bold, 10, col_sku, y, "SKU");
    draw_text_right(page, font_bold, 10, col_qty, y, "Cant.");
    draw_text_right(page, font_bold, 10, col_pu, y, "P.Unit");
    draw_text_right(page, font_bold, 10, col_amt, y, "Importe");
    y -= 4;
    HPDF_Page_MoveTo(page, paper.margin_l, y);
    HPDF_Page_LineTo(page, right_edge, y);
    HPDF_Page_Stroke(page);
    y -= 14;

    /* ---- Items rows ---- */
    const char *items = obj_find(root, "items");
    if (items) {
        const char *p = skip_ws(items);
        if (*p == '[') {
            p++;
            for (;;) {
                p = skip_ws(p);
                if (*p == ']' || *p == '\0') break;
                if (*p != '{') break;
                const char *item = p;

                char name[256], sku[128], qty[32], pu[64], amt[64];
                get_str(item, "name", name, sizeof(name));
                get_str(item, "sku", sku, sizeof(sku));
                get_str(item, "quantity", qty, sizeof(qty));
                get_str(item, "unit_price", pu, sizeof(pu));
                get_str(item, "amount", amt, sizeof(amt));

                /* Recorte por ancho real de la columna, con un canalón de 6 pt
                   para que el texto no bese la columna siguiente (T-003). */
                truncar_a_ancho(page, font, 9, name, col_sku - col_name - 6.0f);
                truncar_a_ancho(page, font, 9, sku,  col_qty - col_sku - 6.0f);

                draw_text(page, font, 9, col_name, y, name);
                draw_text(page, font, 9, col_sku, y, sku);
                draw_text_right(page, font, 9, col_qty, y, qty);
                draw_text_right(page, font, 9, col_pu, y, pu);
                draw_text_right(page, font, 9, col_amt, y, amt);
                y -= 13;

                if (y < 140) {
                    /* overflow to a new page (long orders) */
                    page = new_page(pdf, &paper);
                    y = HPDF_Page_GetHeight(page) - paper.margin_t;
                }

                p = skip_value(item);
                p = skip_ws(p);
                if (*p == ',') p++;
            }
        }
    }

    y -= 4;
    HPDF_Page_MoveTo(page, col_qty, y + 12);
    HPDF_Page_LineTo(page, right_edge, y + 12);
    HPDF_Page_Stroke(page);
    y -= 4;

    /* ---- Totals ---- */
    const char *totals = obj_find(root, "totals");
    if (totals) {
        struct { const char *key; const char *label; } rows[] = {
            { "subtotal", "Subtotal" },
            { "tax",      "IVA (16%)" },
            { "shipping", "Envio" },
            { "discount", "Descuento" },
        };
        for (size_t i = 0; i < sizeof(rows) / sizeof(rows[0]); i++) {
            char val[64];
            get_str(totals, rows[i].key, val, sizeof(val));
            if (!val[0]) continue;
            draw_text_right(page, font, 10, col_pu, y, rows[i].label);
            draw_text_right(page, font, 10, col_amt, y, val);
            y -= 14;
        }
        char total[64];
        get_str(totals, "total", total, sizeof(total));
        y -= 2;
        HPDF_Page_MoveTo(page, col_qty, y + 12);
        HPDF_Page_LineTo(page, right_edge, y + 12);
        HPDF_Page_Stroke(page);
        y -= 4;
        draw_text_right(page, font_bold, 12, col_pu, y, "TOTAL");
        draw_text_right(page, font_bold, 12, col_amt, y, total);
        y -= 24;
    }

    /* ---- Payment block ---- */
    const char *payment = obj_find(root, "payment");
    if (payment) {
        char method[128], status[64];
        get_str(payment, "method", method, sizeof(method));
        get_str(payment, "status", status, sizeof(status));
        snprintf(line, sizeof(line), "Metodo de pago: %s", method);
        draw_text(page, font, 10, paper.margin_l, y, line);
        y -= 14;
        snprintf(line, sizeof(line), "Estado del pago: %s", status);
        draw_text(page, font, 10, paper.margin_l, y, line);
        y -= 14;
    }

    /* ---- Notes — superficie de extensión (forma propia, declarada) ----
       En la referencia el reporte es HTML libre y una extensión XPath puede
       insertar bloques donde quiera (sale_stock añade su Incoterm así). Este
       helper tiene layout fijo, así que las extensiones anclan en UNA
       superficie genérica: el objeto ``notes`` del descriptor — cada valor
       no vacío se dibuja como una línea. El intérprete lo produce desde
       ``<section name="notes">``, donde los addons parchan con XPath. */
    const char *notes = obj_find(root, "notes");
    if (notes) {
        const char *p = skip_ws(notes);
        if (*p == '{') {
            p++;
            y -= 6;
            for (;;) {
                p = skip_ws(p);
                if (*p == '}' || *p == '\0') break;
                if (*p != '"') break;
                /* La clave se salta: el orden del arch decide el orden. */
                p++;
                while (*p && *p != '"') {
                    if (*p == '\\' && p[1]) p += 2;
                    else p++;
                }
                if (*p == '"') p++;
                p = skip_ws(p);
                if (*p == ':') p++;
                p = skip_ws(p);
                char nota[512];
                json_string(p, nota, sizeof(nota));
                if (nota[0]) {
                    draw_text(page, font, 9, paper.margin_l, y, nota);
                    y -= 12;
                }
                p = skip_value(p);
                p = skip_ws(p);
                if (*p == ',') p++;
            }
        }
    }

    /* ---- Stream PDF to stdout ---- */
    if (HPDF_SaveToStream(pdf) != HPDF_OK) {
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }
    HPDF_ResetStream(pdf);

    for (;;) {
        HPDF_BYTE  out[4096];
        HPDF_UINT32 size = sizeof(out);
        HPDF_STATUS st = HPDF_ReadFromStream(pdf, out, &size);
        if (size == 0) break;
        if (fwrite(out, 1, size, stdout) != (size_t)size) {
            HPDF_Free(pdf);
            free(g_input);
            return 2;
        }
        if (st != HPDF_OK && st != HPDF_STREAM_EOF) break;
    }
    fflush(stdout);

    HPDF_Free(pdf);
    free(g_input);
    return 0;
}
