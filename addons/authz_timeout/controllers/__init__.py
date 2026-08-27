"""Controladores — ``addons.authz_timeout``.

Adaptación de ``auth_timeout/controllers/`` de Odoo
(``odoo-tools@abe4040ec1``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

La referencia tiene **tres** archivos aquí y sólo uno declara rutas propias:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Archivo de la fuente
     - Aquí
   * - ``main.py`` (3 defs)
     - ``main.py`` — los tres, adaptados a REST
   * - ``web_home.py`` (1 def)
     - **no es un archivo**: su cuerpo entero es re-declarar
       ``check_identity=False`` sobre una ruta heredada. Aquí eso es el
       atributo ``check_identity = False`` sobre la vista, y se declara en
       la vista misma — ver la nota de abajo
   * - ``auth_passkey_webauthn.py`` (1 def)
     - idem

**Por qué los dos últimos no se copian como archivo.** En la referencia, un
addon extiende una ruta ajena heredando su controlador y volviendo a decorar
el método con ``@http.route(check_identity=False)``; el archivo existe sólo
para alojar esa herencia. Aquí el middleware lee un **atributo de la vista**
(``_view_declares_check_identity`` en ``models/ir_http.py``), así que la
exención se declara donde vive la vista y no hay nada que heredar. Copiar el
archivo produciría una clase vacía sin consumidor — el defecto que
``porte-completo-no-parcial.md`` llama racionalizar la ausencia, sólo que al
revés: fabricar presencia.

Las dos vistas que la fuente exime, y su contraparte medida aquí:

- ``/web/webclient/load_menus`` → ``authz/controllers/main.py::MyMenuView``
  (``GET /api/v2/authz/me/menu/``), que ``web/controllers/home.py:51-59`` ya
  declara como su hogar.
- ``/auth/passkey/start-auth`` → ``authz_passkey/controllers/main.py::auth_options``
  (``GET /api/v2/authz/passkey/auth-options/``).
"""
from addons.authz_timeout.controllers import main  # noqa: F401
