# Makefile — PDF helpers
#
# Construye los dos helpers basados en libharu:
#   pdf_receipt — recibo de compra
#   pdf_report  — export de tabla de reporte
#
# libharu 2.4.6 va VENDORIZADO en vendor/libharu (licencia ZLIB; ver
# vendor/README.md). No se instala `libhpdf-dev` del sistema: el producto es
# autocontenido y un servidor de terceros no tiene por qué traer libharu —
# misma premisa que llevó a Gunicorn embebido. Tampoco hace falta CMake: el
# hpdf_config.h está instanciado a mano en vendor-config/, FUERA del árbol
# vendorizado, porque ese archivo es nuestro y el `.gitignore` del tarball de
# libharu lo lista como salida de build — dentro de vendor/ nunca llegaba a
# versionarse y un clon limpio moría en el primer objeto. Ver H-API-397.
#
# Únicas dependencias de la máquina que compila (ambas en `main` de Ubuntu, no
# en universe como lo estaba libhpdf-dev):
#
#     sudo apt-get install -y build-essential zlib1g-dev libpng-dev
#     make            # produce ./pdf_receipt y ./pdf_report
#
# Los binarios quedan JUNTO A ESTE Makefile porque es donde los busca Django:
# HELPER_PATH = Path(settings.BASE_DIR)/'tools'/'pdf'/'pdf_<x>' y BASE_DIR es
# src/. Están gitignored (se compilan por entorno). Las vistas los invocan por
# subprocess — ADR-017: un fallo de libharu no debe tumbar al worker.

CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra
LDLIBS  := -lpng -lz -lm

VENDOR    := vendor/libharu
VENDORCFG := vendor-config
BUILD     := build
OBJ       := $(BUILD)/obj
LIBHPDF_A := $(BUILD)/libhpdf.a

HPDF_SRCS := $(wildcard $(VENDOR)/src/*.c)
HPDF_OBJS := $(patsubst $(VENDOR)/src/%.c,$(OBJ)/%.o,$(HPDF_SRCS))
INCLUDES  := -I$(VENDORCFG) -I$(VENDOR)/include -I$(BUILD)

# Catálogo tipográfico embebido (DEC-01/DEC-02 de `integrar-libharu`). El .ttf
# es la fuente de verdad y el .c es derivado: se genera aquí, no se versiona.
# Embeber la fuente en el binario evita que el helper resuelva rutas en
# runtime — no tiene un modo de fallo "fuente no encontrada" que obligue a
# elegir entre abortar y degradar en silencio.
FONTS_DIR := vendor/fonts/liberation-sans
FONTS_TTF := $(FONTS_DIR)/LiberationSans-Regular.ttf \
             $(FONTS_DIR)/LiberationSans-Bold.ttf
FONTS_C   := $(BUILD)/pdf_fonts.c
FONTS_H   := $(BUILD)/pdf_fonts.h
FONTS_O   := $(BUILD)/pdf_fonts.o

# libharu se compila con LAS MISMAS advertencias que nuestro código. Al
# vendorizarlo dejamos de consumir un paquete del distro y pasamos a
# distribuirlo dentro del producto: su superficie de fallo es nuestra.
#
# Medido sobre los 59 archivos con -Wall -Wextra: **3 warnings**, no un muro.
# Se listan como línea base heredada para que uno NUEVO destaque:
#
#   hpdf_fontdef_tt.c:2099  sign-compare       (embebido de TrueType)
#   hpdf_image_png.c:463    cast-function-type (png_rw_ptr 32 vs size_t 64)
#   hpdf_pdfa.c:298         enum-conversion    (PDF/A)
#
# Qué caminos ejercemos: al 2026-08-04 sólo el de PNG —
# HPDF_LoadPngImageFromFile, el logo del emisor en pdf_receipt.
#
# Eso es un estado FECHADO, no una exención. El árbol de familias está a medio
# portar, y los otros dos caminos están a una familia de distancia: PDF/A es el
# estándar de archivo de largo plazo (conservación de comprobantes), y las
# base-14 sólo cubren WinAnsi — una tipografía de marca por Company o un glifo
# fuera de Latin-1 enciende el embebido TrueType. No leer esta lista como "esos
# dos no aplican": leerla como "hoy no se ejercen, y hay que volver a medir
# cuando la familia que los use aterrice". Ver H-API-287.
#
# No se parchea ninguno aquí: corregir upstream crea una divergencia que habría
# que reaplicar en cada actualización, y esa es una decisión aparte, no un
# efecto colateral de este Makefile.
VENDOR_CFLAGS ?= $(CFLAGS)

TARGETS := pdf_receipt pdf_report

.PHONY: all build check clean distclean

all: build

build: $(TARGETS)

# --- libharu vendorizado -> archivo estático --------------------------------

$(OBJ):
	@mkdir -p $(OBJ)

$(OBJ)/%.o: $(VENDOR)/src/%.c | $(OBJ)
	$(CC) $(VENDOR_CFLAGS) $(INCLUDES) -c $< -o $@

$(LIBHPDF_A): $(HPDF_OBJS)
	$(AR) rcs $@ $(HPDF_OBJS)

# --- catálogo tipográfico -> arreglo C --------------------------------------
# Se usa Python y no `xxd`: xxd viene en vim-common y no está garantizado en
# la máquina destino — la misma suposición que el vendorizado existe para
# evitar. Python sí está: el producto es Django.

$(FONTS_C): $(FONTS_TTF) gen_font_c.py | $(OBJ)
	python3 gen_font_c.py $(FONTS_C) \
	    liberation_sans_regular=$(FONTS_DIR)/LiberationSans-Regular.ttf \
	    liberation_sans_bold=$(FONTS_DIR)/LiberationSans-Bold.ttf

$(FONTS_H): $(FONTS_C)

$(FONTS_O): $(FONTS_C)
	$(CC) $(CFLAGS) -c $(FONTS_C) -o $(FONTS_O)

# --- nuestros helpers -------------------------------------------------------

pdf_receipt: pdf_receipt.c $(LIBHPDF_A) $(FONTS_O) $(FONTS_H)
	$(CC) $(CFLAGS) $(INCLUDES) pdf_receipt.c $(FONTS_O) $(LIBHPDF_A) -o pdf_receipt $(LDLIBS)

pdf_report: pdf_report.c $(LIBHPDF_A) $(FONTS_O) $(FONTS_H)
	$(CC) $(CFLAGS) $(INCLUDES) pdf_report.c $(FONTS_O) $(LIBHPDF_A) -o pdf_report $(LDLIBS)

# --- gate de compilación (ADR-017 gate 2) -----------------------------------
# Sale distinto de cero si alguno no compila. Los binarios desechables van a
# $(BUILD)/, NUNCA a /tmp: el árbol del proyecto es dueño de sus artefactos, y
# /tmp no es escribible por el usuario de servicio en todos los entornos (el
# propio contenedor tiene TMPDIR=/tmp/claude-0, que mysql no puede escribir).

check: $(LIBHPDF_A) $(FONTS_O) $(FONTS_H) | $(OBJ)
	$(CC) $(CFLAGS) $(INCLUDES) pdf_receipt.c $(FONTS_O) $(LIBHPDF_A) -o $(BUILD)/pdf_receipt_check $(LDLIBS)
	$(CC) $(CFLAGS) $(INCLUDES) pdf_report.c  $(FONTS_O) $(LIBHPDF_A) -o $(BUILD)/pdf_report_check  $(LDLIBS)
	@echo "pdf_receipt + pdf_report compilan OK (libharu vendorizado 2.4.6)"

clean:
	rm -f $(TARGETS)

# Borra también los objetos de libharu (recompilar los 59 toma bastante más).
distclean: clean
	rm -rf $(BUILD)
