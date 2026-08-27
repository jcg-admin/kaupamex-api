"""``controllers/main.py`` — hueco de porte deliberadamente vacío.

Adaptación de ``odoo19c: addons/web/controllers/main.py`` (8 líneas,
LGPL-3, ``web/__manifest__.py`` — DEC-KX-03). Cierra la tarea **#397**
(``check_mirrored_roots.py``, 13 archivos / 22 ``def`` del addon raíz
``web``); este archivo aporta **0** de esos 22 ``def``.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``): **0** métodos, **0** clases.
La referencia entera es un ``warnings.warn(DeprecationWarning)`` de módulo —
no hay símbolo que portar.

Por qué el archivo existe igual — divergencia de mecanismo, no omisión
==========================================================================

La referencia lo deja ahí como marcador de una migración **interna** de
Odoo: hasta la 15.0, ``controllers/main.py`` concentraba todos los
controladores de ``web``; en la 16.0 se partieron en los submódulos actuales
(``action.py``, ``dataset.py``, ``domain.py``, …) y el archivo se dejó vacío
—con el aviso— para que un ``import odoo.addons.web.controllers.main``
heredado de un addon de terceros no rompiera con ``ImportError``.

Este árbol **nunca tuvo** esa forma previa: no existe un
``addons.web.controllers.main`` histórico que algo importe, así que no hay
compatibilidad retroactiva que preservar. Portar el ``warnings.warn`` sería
documentar una migración de Odoo 15→16 que este proyecto no vivió — el
símbolo que motiva el archivo en la referencia (advertir a quien importe la
ruta vieja) no tiene destinatario aquí.

Se conserva el archivo, vacío salvo este docstring, para que
``check_mirrored_roots.py`` deje de reportarlo como hueco de porte: la
alternativa —omitirlo— mantendría abierto un hallazgo sobre un archivo sin
ningún contenido que portar, lo que ``hallazgo-abierto-genera-sucesor.md``
exige resolver con un desenlace, no dejar pendiente.
"""
