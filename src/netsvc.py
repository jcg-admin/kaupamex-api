"""Colores del registro — ≙ ``odoo/netsvc.py`` (Odoo 19), el bloque de color.

Adaptación de Odoo ``odoo/netsvc.py`` (LGPL-3, copia y adaptación con
atribución), líneas 101-170: los códigos de color ANSI, ``COLOR_PATTERN``,
``LEVEL_COLOR_MAPPING`` y ``ColoredFormatter``. Su consumidor es
``Html._convert`` (``orm/fields_textual.py``), que colorea el diff del valor
que un usuario no puede editar cuando el manejador raíz usa este formateador.

Pendiente, con su condición de cierre: el resto del módulo —``log``,
``WatchedFileHandler``, ``PostgreSQLHandler``, ``PerfFilter``,
``ColoredPerfFilter``, ``LogRecord``, ``init_logger``,
``DEFAULT_LOG_CONFIGURATION``, ``PSEUDOCONFIG_MAPPER``, ``IGNORE``,
``showwarning_with_traceback`` y ``runbot``—. Es el arranque del registro de
``odoo-bin``; aquí el registro lo configura ``LOGGING`` de
``config/settings``, y la paridad de ``PostgreSQLHandler`` es deuda de
``DatabaseLogHandler`` (diseño ``request-unit-of-work-durable-writes.md``).
Se porta cuando ``kaupamex-bin`` configure el registro por sí mismo.
"""
import logging

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, _NOTHING, DEFAULT = (
    range(10))
# El fondo es 40 más el número del color y el primer plano 30 más el número;
# estas son las secuencias que colorean la salida
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLOR_PATTERN = f"{COLOR_SEQ}{COLOR_SEQ}%s{RESET_SEQ}"
LEVEL_COLOR_MAPPING = {
    logging.DEBUG: (BLUE, DEFAULT),
    logging.INFO: (GREEN, DEFAULT),
    logging.WARNING: (YELLOW, DEFAULT),
    logging.ERROR: (RED, DEFAULT),
    logging.CRITICAL: (WHITE, RED),
}


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        fg_color, bg_color = LEVEL_COLOR_MAPPING.get(
            record.levelno, (GREEN, DEFAULT))
        record.levelname = COLOR_PATTERN % (
            30 + fg_color, 40 + bg_color, record.levelname)
        return super().format(record)
