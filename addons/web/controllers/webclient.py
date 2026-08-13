"""Bootstrap del cliente web — adaptación de
``odoo19c: addons/web/controllers/webclient.py``, licencia LGPL-3
(``odoo-tools: addons/web/__manifest__.py``, DEC-KX-03).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref, re.M)``,
mismo criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``WebClient``): **6** métodos. **0 portados, 6 declarados ausentes** con
razón — no hay recorte silencioso.

Re-verificación 2026-08-07 (H-API-378) — los 6 se volvieron a medir hoy, no
se heredaron del docstring anterior
================================================================================

``porte-completo-no-parcial.md`` prohíbe tratar una ausencia declarada como
decisión cerrada. Los seis se re-comprobaron con comandos ejecutados en este
pase, no releyendo la prosa previa:

- ``bootstrap_translations`` / ``translations`` — se re-confirmó ``babel``
  ausente y **0** ``.po`` de proyecto (mismo par de comandos que
  ``utils.py::_local_web_translations``, ver ese docstring) y **0**
  referencias a ``/web/webclient/translations`` en ``kaupamex-ui/src``
  (``grep -rn`` → 0).
- ``version_info`` — se releyó ``src/service/common.py`` completo hoy: existe,
  y su tabla dice explícitamente *"``exp_version``/``exp_about`` → endpoint de
  versión propio / metadata del build; no se expone un RPC de versión de
  servidor"*. La afirmación del docstring anterior ("ya resuelto en
  ``service/common.py``") se verificó, no se repitió de memoria — el archivo
  está en ``src/service/common.py`` (paquete ``service`` top-level, hermano
  de ``addons/``, no dentro de un addon).
- ``unit_tests_suite`` / ``test_suite`` — ``find src/addons -type d -iname
  static | wc -l`` → 0 (sigue sin ningún directorio de assets estáticos en
  los addons) y ``find src/addons -iname "*.xml" | wc -l`` → 0 (sin plantillas
  QWeb que renderizar). ``kaupamex-ui/package.json`` confirma
  ``jest: ^29.7.0`` como el runner de pruebas de UI real.
- ``bundle`` — ``base/models/ir_qweb.py`` (releído) declara el motor de
  plantillas sin implementación de compilación; ``base/models/ir_asset.py`` y
  ``base/models/assetsbundle.py`` (ambos releídos) declaran, respectivamente,
  que la resolución de rutas contra manifests y el empaquetado real viven en
  Webpack, en ``ui/``.

Ningún consumidor nuevo apareció en ``kaupamex-ui`` para ninguno de los seis
(mismo grep de arriba, 0 hits) — el veredicto se sostiene con evidencia
propia de hoy, no por herencia del pase anterior.

Por qué los 6 son ausentes — la misma causa raíz, en su forma final
=====================================================================

Este archivo es el **punto de encuentro** de las tres piezas que el resto del
addon ya midió por separado: traducciones runtime, empaquetado de assets y
renderizado de página server-side. Ninguna de las tres tiene mecanismo
propio en este árbol — lo que sigue no abre casos nuevos, cruza los que ya
están resueltos.

**1-2. ``bootstrap_translations`` / ``translations`` — sin infraestructura
de traducción runtime que consultar.**

- ``bootstrap_translations`` depende de ``_local_web_translations`` (parsea
  ``.po`` con ``babel.messages.pofile``), declarada AUSENTE en
  ``controllers/utils.py`` — ``babel`` no es dependencia declarada
  (``grep -in babel pyproject.toml`` → vacío; ``import babel`` →
  ``ModuleNotFoundError``) y no hay ningún ``.po`` fuera de la propia
  referencia (``find … -iname "*.po"`` → 0). También depende de
  ``manifest['bootstrap']`` — ``base.IrModule`` (adaptación de
  ``ir.module.module``, ``base/models/ir_module.py``) no porta ese campo: no
  hay instalador en caliente que lo consulte.
- ``translations`` depende de ``ir.http._get_web_translations_hash`` /
  ``_get_translations_for_webclient``. Ninguno de los dos está en la lista de
  métodos portados de ``web/models/ir_http.py`` (1 de 11, ``is_a_bot``) ni en
  ``base/models/ir_http.py`` — medido, **0** hits de
  ``translations_hash``/``_get_translations_for_webclient`` en todo
  ``src/addons`` (``grep -rn`` sobre el árbol). El frontend
  (``kaupamex-ui``) resuelve su i18n por **mecanismo propio**, no consumiendo
  este endpoint — mismo cierre que ``utils.py`` ya documentó para
  ``_local_web_translations``: "Ninguno de los dos produce ni consume
  ``.po``".

**3. ``version_info`` — ya resuelto como fuera de alcance, en el archivo
hermano que le corresponde.** ``service/common.py`` (adaptación de
``odoo/service/common.py``) documenta explícitamente, en su tabla de
mapeo: *"``exp_version`` / ``exp_about`` → endpoint de versión propio /
metadata del build; no se expone un RPC de versión de servidor"*. Duplicar
esa decisión aquí —con otra forma, otro archivo— divergiría con el primer
cambio que sólo tocara uno de los dos. No se repite: se cruza.

**4-5. ``unit_tests_suite`` / ``test_suite`` — páginas QUnit renderizadas por
QWeb (``web.unit_tests_suite`` / ``web.qunit_suite``).** Misma causa raíz que
``home.py`` y ``webmanifest.py`` ya midieron para el resto del shell: **0**
directorios ``static/`` en los 78 addons, **0** renderizado de página
completa por plantilla en este árbol (``ir_qweb.py``: *"El HTML de este
producto lo genera React en el cliente; el backend sirve JSON por DRF"*, con
**0** archivos ``.xml`` de plantilla medidos). Un test runner JS
server-side no tiene function en un backend API-only — las pruebas de UI de
este proyecto corren con Jest en ``kaupamex-ui`` (``package.json``:
``jest ^29.7.0``), no con QUnit servido por Django.

**6. ``bundle`` — depende del compilador de QWeb, declarado explícitamente
no portado.** ``ir.qweb._get_asset_nodes`` requiere el compilador de
plantillas que ``base/models/ir_qweb.py`` excluye por dos razones
independientes y medidas ("no hay plantillas que compilar" + "toma texto
almacenado en la base y produce bytecode que se ejecuta", el mismo patrón ya
rechazado en ``ir_rule.domain_force``/``ir_actions.server.code``/
``ir_actions_report.attachment``). La resolución de rutas contra manifests
que alimentaría al bundle también está declarada ausente en
``base/models/ir_asset.py``: *"el resolutor de rutas contra manifests no
aplica: lo hace Webpack en ``ui``"*. Y el propio empaquetado — compilar,
minificar, versionar — lo confirma ``base/models/assetsbundle.py``: *"Aquí
el empaquetador es Webpack, en ``ui``"*. Las tres piezas de las que
``bundle`` depende ya están fuera de alcance por decisión propia, no por
omisión de este archivo.

Por qué no se construye un stub de ninguno de los 6
======================================================

Instalar la ruta con una respuesta vacía o parcial (``{"modules": {},
"lang_parameters": None}``, una lista de bundle vacía, etc.) no sería
"hacer lo que hace el de la referencia" — sería exactamente el riesgo que
``web/models/ir_http.py`` ya nombró para ``get_frontend_session_info``:
*"un stub que aparenta cobertura"*. Ninguno de los 6 tiene consumidor real
en ``kaupamex-ui`` (que resuelve i18n, bundling y testing por su cuenta) ni
en ningún otro repo del monorepo.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===============================================================

=================================  ================================================
Referencia                          Aquí
=================================  ================================================
``bootstrap_translations``          AUSENTE — sin ``.po``/``babel``
                                    (≙ ``utils.py::_local_web_translations``)
``translations``                    AUSENTE — sin ``_get_web_translations_hash``
                                    ni ``_get_translations_for_webclient``; i18n
                                    de ``kaupamex-ui`` es mecanismo propio
``version_info``                    AUSENTE — ya resuelto en
                                    ``service/common.py`` (``exp_version``)
``unit_tests_suite``                AUSENTE — página QUnit vía QWeb, sin motor
                                    de plantillas; pruebas de UI en Jest (``ui/``)
``test_suite``                      AUSENTE — misma causa que ``unit_tests_suite``
``bundle``                          AUSENTE — depende del compilador QWeb
                                    (``ir_qweb.py``) y de la resolución de
                                    manifests (``ir_asset.py``); el empaquetado
                                    real es Webpack, en ``ui``
=================================  ================================================

Este archivo no expone rutas: no hay entrada que agregar a
``controllers/urls.py``. Se importa desde ``controllers/__init__.py`` para
que el gate de sintaxis lo alcance, igual que ``schema.py``.
"""
