"""Parcheo perezoso de módulos — raíz espejada de ``odoo/_monkeypatches/``.

Adaptación de ``odoo/_monkeypatches/__init__.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3 → copia con atribución, DEC-KX-03), **parcial y
declarada**: aquí vive el paquete y la convención, no todavía el cargador.

Traducción del docstring de la fuente: los submódulos se nombran como el
módulo —de la biblioteca estándar o de terceros— que necesitan parchear, y
definen una función ``patch_module``. Esa función se llama de inmediato si el
módulo a parchear ya está importado cuando corre el parcheador, o justo
después de que se importe si no lo está.

**Lo que este paquete NO trae todavía, y por qué.** La fuente instala un
``PatchImportHook`` en ``sys.meta_path`` que descubre los submódulos con
``pkgutil.iter_modules`` y engancha cada uno a la importación de su módulo
homónimo; ``patch_init()`` además fija ``TZ=UTC`` y llama a ``time.tzset()``.
Ese cargador tiene un punto de invocación único —el arranque del servidor— y
aquí ese punto es ``kaupamex-bin`` / la carga de aplicaciones de Django, que
es una decisión de arranque, no de este archivo. Hasta que se tome, cada
consumidor llama a ``patch_module()`` de su submódulo directamente, que es lo
que hace ``tools/safe_eval`` con ``pytz``.

De los 22 submódulos de la referencia —``_cpython``, ``ast``, ``bs4``,
``csv``, ``docutils``, ``email``, ``locale``, ``lxml``, ``markupsafe``,
``mimetypes``, ``num2words``, ``pytz``, ``re``, ``requests``, ``site``,
``stdnum``, ``urllib3``, ``werkzeug``, ``xlrd``, ``xlsxwriter``, ``xlwt``,
``zeep``— aquí está **uno**: ``pytz``, el que ``safe_eval`` necesita.
``werkzeug`` queda fuera por decisión del ejecutor (servimos con gunicorn);
los otros veinte son trabajo pendiente, con su tarea propia.
"""
