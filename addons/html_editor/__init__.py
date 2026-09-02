"""Addon ``html_editor`` — la mitad de servidor del editor de contenido.

Puerto de Odoo Community ``html_editor/`` (``odoo19c:``, LGPL-3 — copia +
adaptación con atribución, DEC-KX-03).

**El editor en sí vive en ``ui`` (React).** La referencia reparte este addon
entre 12 archivos Python y un árbol de ``static/`` con el componente y su
sistema de *plugins*; aquí sólo entra la mitad de servidor. Lo que queda es
exactamente lo que un editor necesita del backend y no puede resolver en el
navegador:

- **guardar lo editado** — ``models/ir_ui_view.py``;
- **el historial de revisiones de un campo** — ``models/diff_utils.py`` y
  ``models/html_field_history_mixin.py``;
- **los adjuntos de imagen** — ``models/ir_attachment.py`` y los endpoints de
  ``controllers/main.py``;
- **la vuelta del HTML editado al valor del campo** —
  ``models/ir_qweb_fields.py``;
- **el canal de coedición y su guarda de acceso** —
  ``models/ir_websocket.py`` y ``tools.py``.

El censo símbolo a símbolo, las divergencias de mecanismo y sus sucesores
viven en el docstring de cada archivo. No se resumen aquí para que haya una
sola fuente de cada afirmación.

Este archivo **no importa nada**, y es deliberado
=================================================

La referencia abre su ``__init__.py`` con ``from . import models`` y
``from . import controllers``. Aquí eso rompería el arranque de **todo el
árbol**, y el motivo está medido: ``modules.module.get_modules()`` declara un
addon por *"directorio con ``__init__.py`` bajo alguna raíz de addons"*, así
que este archivo entra en ``INSTALLED_APPS`` (``src/config/settings/base.py``,
``_local_apps()``). Django lo importa dentro de ``apps.populate``, **antes** de
que el registro esté poblado; un ``import fields`` en esa ventana arrastra
``django.contrib.contenttypes`` y levanta ``AppRegistryNotReady``.

Quien importa los modelos es Django, en su fase ``import_models``, que es
posterior. Es la misma forma que ya tienen ``addons/http_routing/__init__.py``
(sólo docstring), ``addons/bus/__init__.py`` y ``addons/web/__init__.py``
(vacíos): el ``from . import models`` de la referencia lo hace aquí el
framework.
"""
