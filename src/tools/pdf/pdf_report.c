/*
 * pdf_report.c — PDF report table generator
 *
 * Reads a JSON report descriptor from stdin and writes a PDF document to
 * stdout, generated with libharu (libhpdf 2.3.0). Sibling of pdf_receipt.c;
 * see ADR-017 (adr-017-libreria-pdf-libharu) for the architecture decision:
 * a compiled C helper invoked via subprocess, isolating the WSGI worker from
 * any native libharu crash.
 *
 * Build:
 *   gcc pdf_report.c -o pdf_report -lhpdf
 *
 * Contract (stdin JSON):
 *   {
 *     "title": "Reporte de ventas",
 *     "subtitle": "Periodo: ultimos 30 dias",
 *     "generated_at": "2026-06-03T05:08:08",
 *     "columns": [ "Metrica", "Valor", ... ],
 *     "rows": [ [ "Revenue", "1500.00" ], ... ]
 *   }
 *
 * All cell values are passed as strings from Django; the helper only lays
 * them out. Column widths are distributed evenly across the printable area.
 *
 * Exit codes:
 *   0  success (PDF on stdout)
 *   1  bad / unparseable JSON on stdin
 *   2  libharu error (PDF generation failed)
 *   3  read error
 *
 * NOTE: reuses the same self-contained JSON reader shape as pdf_receipt.c so
 * the helper links only against libharu (-lhpdf).
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
 *  Minimal JSON reader (purpose-built; same subset as pdf_receipt.c)  *
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
    while (*p && *p != ',' && *p != '}' && *p != ']' &&
           *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r')
        p++;
    return p;
}

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
 * (size cap). Returns pointer just past the string value, or p unchanged if
 * p is not a string.
 */
static const char *
json_string(const char *p, char *out, size_t cap)
{
    p = skip_ws(p);
    if (*p != '"') { if (cap) out[0] = '\0'; return p; }
    p++;
    size_t o = 0;
    while (*p && *p != '"') {
        if (*p == '\\') {
            p++;
            switch (*p) {
                case 'n': if (o + 1 < cap) out[o++] = '\n'; break;
                case 't': if (o + 1 < cap) out[o++] = ' ';  break;
                case 'r': break;
                case '"': if (o + 1 < cap) out[o++] = '"';  break;
                case '\\': if (o + 1 < cap) out[o++] = '\\'; break;
                case '/': if (o + 1 < cap) out[o++] = '/';  break;
                case 'u': {
                    /* Decodifica \uXXXX a UTF-8, que es lo que el documento
                       habla desde que la fuente es TrueType embebida. Antes
                       plegaba a UN byte WinAnsi y mandaba '?' arriba de
                       U+00FF, lo que perdía el '€' y el em-dash; con la
                       fuente UTF ese plegado además da mojibake. Ver
                       H-API-290 y la sonda de T-002. */
                    if (p[1] && p[2] && p[3] && p[4]) {
                        char hex[5] = { p[1], p[2], p[3], p[4], 0 };
                        unsigned long cp = strtoul(hex, NULL, 16);
                        p += 4;
                        /* Par suplente UTF-16: dos escapes, un codepoint. */
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
                        if (o + 1 < cap)
                            o += utf8_encode(cp, out + o, cap - o - 1);
                    }
                    break;
                }
                default: if (o + 1 < cap) out[o++] = *p; break;
            }
            if (*p) p++;
        } else {
            if (o + 1 < cap) out[o++] = *p;
            p++;
        }
    }
    if (o < cap) out[o] = '\0';
    else if (cap) out[cap - 1] = '\0';
    if (*p == '"') p++;
    return p;
}

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
 *  Layout                                                             *
 * ------------------------------------------------------------------ */

#define MARGIN_L   50.0f
#define MARGIN_R   50.0f
#define MARGIN_T   50.0f
#define MARGIN_B   60.0f
#define MAX_COLS   12

/* Un milimetro en puntos PostScript, que es la unidad del PDF (72 / 25.4). */
#define MM_TO_PT   2.8346457f

/*
 * Geometria de pagina — los ajustes de papel que el descriptor trae.
 *
 * El motor es libharu, no wkhtmltopdf, asi que la clave `paperformat` NO
 * viaja como argumentos de linea de comandos: llega ya resuelta a milimetros
 * por `_paperformat_geometry` de ir_actions_report, que consulta las 31
 * claves de `report.paperformat`. Aqui solo se convierte a puntos.
 *
 * Se resuelve en Python y no aqui a proposito: el enum de libharu
 * (HPDF_PageSizes) declara 12 tamanos y el modelo declara 31, asi que
 * HPDF_Page_SetSize dejaria 19 formatos sin receptor. SetWidth/SetHeight los
 * cubre todos.
 *
 * Sin la clave se conservan las cuatro constantes de arriba, que son las que
 * este helper uso desde su primera version: cambiarlas para quien no declara
 * paperformat moveria documentos que hoy salen bien.
 */
typedef struct {
    float width, height;                          /* puntos; 0 = no fijar */
    float margin_l, margin_r, margin_t, margin_b; /* puntos */
} paper_t;

/*
 * Un numero del descriptor, o `fallback` si la clave no esta.
 *
 * Acepta el numero desnudo y el numero entre comillas: `_build_wkhtmltopdf_args`
 * emite cadenas porque wkhtmltopdf recibia argumentos de texto, y el porte
 * conserva esa forma (H-API-946).
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
 * Una pagina nueva con la geometria pedida.
 *
 * Sin `paperformat` cae en A4 apaisado, que es lo que este helper hacia antes
 * de que el descriptor pudiera declararlo.
 */
static HPDF_Page
new_page(HPDF_Doc pdf, const paper_t *paper)
{
    HPDF_Page page = HPDF_AddPage(pdf);
    HPDF_Page_SetSize(page, HPDF_PAGE_SIZE_A4, HPDF_PAGE_LANDSCAPE);
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

/*
 * Recorta `txt` in situ para que quepa en `ancho_max` PUNTOS, no en un número
 * de bytes o de caracteres.
 *
 * Reemplaza a `truncate_chars`, que cortaba por bytes con un presupuesto
 * derivado de `col_w / 5.0` — una aproximación al ancho medio de **Helvetica**,
 * que ya no es la fuente (T-002 la cambió por LiberationSans embebida). Medir
 * el ancho real elimina de una vez las dos aproximaciones: la de la métrica y
 * la de la unidad.
 *
 * Se retrocede hasta el inicio del carácter UTF-8 anterior (los bytes de
 * continuación son 10xxxxxx): cortar a media secuencia dejaría el ancho
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

static void
draw_header_row(HPDF_Page page, HPDF_Font font_bold, float y,
                float *col_x, int ncols, char cells[][256])
{
    /* Banda sombreada del encabezado (T-005): los glifos se pintan con el
       fill color, así que se restaura negro antes de escribir encima. */
    HPDF_Page_SetRGBFill(page, 0.92f, 0.92f, 0.92f);
    HPDF_Page_Rectangle(page, col_x[0], y - 4.0f,
                        col_x[ncols] - col_x[0], 16.0f);
    HPDF_Page_Fill(page);
    HPDF_Page_SetRGBFill(page, 0.0f, 0.0f, 0.0f);

    HPDF_Page_SetLineWidth(page, 0.5f);
    HPDF_Page_MoveTo(page, col_x[0], y + 12);
    HPDF_Page_LineTo(page, col_x[ncols], y + 12);
    HPDF_Page_Stroke(page);
    /* El recorte va aquí y no al parsear: el ancho de columna sólo se conoce
       cuando ya se sabe cuántas columnas hay. Es idempotente, así que
       redibujar la cabecera en cada página no acumula recortes. */
    for (int c = 0; c < ncols; c++)
        truncar_a_ancho(page, font_bold, 9, cells[c],
                        col_x[c + 1] - col_x[c] - 6.0f);
    for (int c = 0; c < ncols; c++)
        draw_text(page, font_bold, 9, col_x[c], y, cells[c]);
    HPDF_Page_MoveTo(page, col_x[0], y - 4);
    HPDF_Page_LineTo(page, col_x[ncols], y - 4);
    HPDF_Page_Stroke(page);
}

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
        fprintf(stderr, "pdf_report: failed to read stdin\n");
        return 3;
    }
    if (g_len == 0) {
        fprintf(stderr, "pdf_report: empty stdin\n");
        return 1;
    }
    const char *root = skip_ws(g_input);
    if (*root != '{') {
        fprintf(stderr, "pdf_report: stdin is not a JSON object\n");
        free(g_input);
        return 1;
    }

    HPDF_Doc pdf = HPDF_New(hpdf_error_handler, NULL);
    if (!pdf) {
        fprintf(stderr, "pdf_report: HPDF_New failed\n");
        free(g_input);
        return 2;
    }

    if (setjmp(g_env)) {
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }

    HPDF_SetCompressionMode(pdf, HPDF_COMP_ALL);

    if (HPDF_UseUTFEncodings(pdf) != HPDF_OK) {
        fprintf(stderr, "pdf_report: no se pudo registrar el encoder UTF-8\n");
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }
    HPDF_Font font      = cargar_fuente(pdf, liberation_sans_regular,
                                        liberation_sans_regular_len);
    HPDF_Font font_bold = cargar_fuente(pdf, liberation_sans_bold,
                                        liberation_sans_bold_len);
    if (!font || !font_bold) {
        fprintf(stderr, "pdf_report: no se pudo cargar la fuente embebida\n");
        HPDF_Free(pdf);
        free(g_input);
        return 2;
    }

    paper_t paper;
    read_paper(root, &paper);

    HPDF_Page page = new_page(pdf, &paper);
    float page_w = HPDF_Page_GetWidth(page);
    float printable_w = page_w - paper.margin_l - paper.margin_r;
    float right_edge = page_w - paper.margin_r;

    char buf[1024];
    float y = HPDF_Page_GetHeight(page) - paper.margin_t;

    /* ---- Title ---- */
    get_str(root, "title", buf, sizeof(buf));
    draw_text(page, font_bold, 16, paper.margin_l, y, buf[0] ? buf : "Reporte");
    y -= 22;

    get_str(root, "subtitle", buf, sizeof(buf));
    if (buf[0]) { draw_text(page, font, 10, paper.margin_l, y, buf); y -= 14; }

    get_str(root, "generated_at", buf, sizeof(buf));
    if (buf[0]) {
        char line[1100];
        snprintf(line, sizeof(line), "Generado: %s", buf);
        draw_text(page, font, 9, paper.margin_l, y, line);
        y -= 18;
    }
    (void)right_edge;

    /* ---- Columns ---- */
    char headers[MAX_COLS][256];
    int ncols = 0;
    const char *columns = obj_find(root, "columns");
    if (columns) {
        const char *p = skip_ws(columns);
        if (*p == '[') {
            p++;
            while (ncols < MAX_COLS) {
                p = skip_ws(p);
                if (*p == ']' || *p == '\0') break;
                /* La cabecera NO se recorta aquí: su ancho de columna depende
                   de cuántas columnas resulten, y eso sólo se sabe al terminar
                   este bucle. El recorte vive en `draw_header_row`. */
                p = json_string(p, headers[ncols], sizeof(headers[ncols]));
                ncols++;
                p = skip_ws(p);
                if (*p == ',') p++;
            }
        }
    }
    if (ncols == 0) {
        /* nothing to render — still emit a valid (near-empty) PDF */
        strcpy(headers[0], "");
        ncols = 1;
    }

    /* Even column widths across the printable area. col_x[ncols] = far edge. */
    float col_x[MAX_COLS + 1];
    float col_w = printable_w / (float)ncols;
    for (int c = 0; c <= ncols; c++)
        col_x[c] = paper.margin_l + col_w * (float)c;

    draw_header_row(page, font_bold, y, col_x, ncols, headers);
    y -= 16;

    /* ---- Rows ---- */
    const char *rows = obj_find(root, "rows");
    if (rows) {
        const char *p = skip_ws(rows);
        if (*p == '[') {
            p++;
            for (;;) {
                p = skip_ws(p);
                if (*p == ']' || *p == '\0') break;
                if (*p != '[') break;  /* each row is an array of cells */
                p++;
                int c = 0;
                char cell[256];
                while (c < ncols) {
                    p = skip_ws(p);
                    if (*p == ']' || *p == '\0') break;
                    p = json_string(p, cell, sizeof(cell));
                    truncar_a_ancho(page, font, 9, cell, col_w - 6.0f);
                    draw_text(page, font, 9, col_x[c], y, cell);
                    c++;
                    p = skip_ws(p);
                    if (*p == ',') p++;
                }
                /* consume any extra cells past ncols */
                while (*p && *p != ']') {
                    p = skip_ws(p);
                    if (*p == ']' || *p == '\0') break;
                    p = skip_value(p);
                    p = skip_ws(p);
                    if (*p == ',') p++;
                }
                if (*p == ']') p++;  /* close row array */

                y -= 13;
                if (y < paper.margin_b) {
                    page = new_page(pdf, &paper);
                    y = HPDF_Page_GetHeight(page) - paper.margin_t;
                    draw_header_row(page, font_bold, y, col_x, ncols, headers);
                    y -= 16;
                }

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
