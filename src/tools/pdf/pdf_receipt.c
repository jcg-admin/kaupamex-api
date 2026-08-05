/*
 * pdf_receipt.c — PracticaYoruba PDF receipt generator (UC-PAY-10).
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

/* ------------------------------------------------------------------ *
 *  Layout helpers                                                     *
 * ------------------------------------------------------------------ */

#define MARGIN_L   50.0f
#define MARGIN_R   50.0f
#define PAGE_TOP   790.0f

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

    HPDF_Page page = HPDF_AddPage(pdf);
    HPDF_Page_SetSize(page, HPDF_PAGE_SIZE_A4, HPDF_PAGE_PORTRAIT);
    float page_w = HPDF_Page_GetWidth(page);
    float right_edge = page_w - MARGIN_R;

    char buf[1024];
    float y = PAGE_TOP;

    /* ---- Issuer block + logo ---- */
    const char *issuer = obj_find(root, "issuer");
    if (issuer) {
        char logo_path[1024];
        get_str(issuer, "logo_path", logo_path, sizeof(logo_path));
        if (logo_path[0]) {
            /* PNG only via HPDF_LoadPngImageFromFile (ADR-017). A bad path or
               unreadable file raises into the error handler; we don't want a
               missing logo to abort the whole receipt, so guard with a nested
               setjmp restore. */
            HPDF_Image img = NULL;
            size_t plen = strlen(logo_path);
            if (plen > 4 &&
                (strcmp(logo_path + plen - 4, ".png") == 0 ||
                 strcmp(logo_path + plen - 4, ".PNG") == 0)) {
                img = HPDF_LoadPngImageFromFile(pdf, logo_path);
            }
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
        draw_text(page, font_bold, 18, MARGIN_L, y, buf);
        y -= 22;
        get_str(issuer, "address", buf, sizeof(buf));
        /* La dirección se ENVUELVE, no se corta (T-004): el ancho es la
           mitad izquierda —el logo vive a la derecha— y 3 líneas bastan
           para cualquier dirección postal razonable. */
        if (buf[0]) y = draw_text_wrapped(page, font, 10, MARGIN_L, y,
                                          280.0f, 3, buf);
        get_str(issuer, "email", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, MARGIN_L, y, buf); y -= 14; }
        get_str(issuer, "phone", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, MARGIN_L, y, buf); y -= 14; }
    }

    y -= 10;

    /* ---- Title ---- */
    draw_text(page, font_bold, 15, MARGIN_L, y, "RECIBO DE COMPRA");
    y -= 22;

    /* ---- Order number + date ---- */
    get_str(root, "order_number", buf, sizeof(buf));
    char line[1100];
    snprintf(line, sizeof(line), "Orden: %s", buf);
    draw_text(page, font_bold, 11, MARGIN_L, y, line);
    get_str(root, "date", buf, sizeof(buf));
    snprintf(line, sizeof(line), "Fecha: %s", buf);
    draw_text_right(page, font, 11, right_edge, y, line);
    y -= 24;

    /* ---- Buyer block ---- */
    const char *buyer = obj_find(root, "buyer");
    if (buyer) {
        draw_text(page, font_bold, 11, MARGIN_L, y, "Comprador");
        y -= 15;
        get_str(buyer, "name", buf, sizeof(buf));
        if (buf[0]) { draw_text(page, font, 10, MARGIN_L, y, buf); y -= 13; }
        get_str(buyer, "address", buf, sizeof(buf));
        /* Envuelta a todo el ancho imprimible (T-004). */
        if (buf[0]) y = draw_text_wrapped(page, font, 10, MARGIN_L, y,
                                          right_edge - MARGIN_L, 3, buf);
    }
    y -= 12;

    /* ---- Items table header ---- */
    float col_name = MARGIN_L;
    float col_sku  = 250.0f;
    float col_qty  = 360.0f;   /* right-aligned at */
    float col_pu   = 450.0f;   /* right-aligned at */
    float col_amt  = right_edge;

    /* Banda sombreada del encabezado (T-005): los glifos se pintan con el
       fill color, así que se restaura negro antes de escribir encima. */
    HPDF_Page_SetRGBFill(page, 0.92f, 0.92f, 0.92f);
    HPDF_Page_Rectangle(page, MARGIN_L, y - 4.0f,
                        right_edge - MARGIN_L, 16.0f);
    HPDF_Page_Fill(page);
    HPDF_Page_SetRGBFill(page, 0.0f, 0.0f, 0.0f);

    HPDF_Page_SetLineWidth(page, 0.5f);
    HPDF_Page_MoveTo(page, MARGIN_L, y + 12);
    HPDF_Page_LineTo(page, right_edge, y + 12);
    HPDF_Page_Stroke(page);

    draw_text(page, font_bold, 10, col_name, y, "Producto");
    draw_text(page, font_bold, 10, col_sku, y, "SKU");
    draw_text_right(page, font_bold, 10, col_qty, y, "Cant.");
    draw_text_right(page, font_bold, 10, col_pu, y, "P.Unit");
    draw_text_right(page, font_bold, 10, col_amt, y, "Importe");
    y -= 4;
    HPDF_Page_MoveTo(page, MARGIN_L, y);
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
                    page = HPDF_AddPage(pdf);
                    HPDF_Page_SetSize(page, HPDF_PAGE_SIZE_A4,
                                      HPDF_PAGE_PORTRAIT);
                    y = PAGE_TOP;
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
        draw_text(page, font, 10, MARGIN_L, y, line);
        y -= 14;
        snprintf(line, sizeof(line), "Estado del pago: %s", status);
        draw_text(page, font, 10, MARGIN_L, y, line);
        y -= 14;
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
