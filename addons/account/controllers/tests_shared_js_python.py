"""``tests_shared_js_python`` — el puente de tests compartidos JS↔Python.

Adaptación de Odoo ``addons/account/controllers/tests_shared_js_python.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

La referencia usa este par de rutas para que su suite de tours ejecute los
mismos casos de cálculo de impuestos en el cliente JS y en Python,
intercambiando los casos y resultados por ``ir.config_parameter``. Los dos
métodos se portan sobre ``SystemParameter`` (mismo parámetro, mismo
nombre); el cableado de URLs y el ``auth='user'`` (capa DRF) son del
orquestador (``urls.py`` queda fuera de este pase por directiva).

Divergencia declarada: ``request.render('account.tests_shared_js_python',
{'props': …})`` monta el template QWeb del runner — QWeb no es superficie
de este árbol; ``route_init_tests_shared_js_python`` devuelve los ``props``
como dict (el SPA los consume directo).
"""
import json

from addons.base.models import SystemParameter

#: El parámetro que transporta los casos/resultados — mismo nombre que la
#: referencia usa en ambas rutas.
_PARAM_KEY = 'account.tests_shared_js_python'


class TestsSharedJsPython:
    """≙ ``TestsSharedJsPython`` — leer y publicar los tests compartidos."""

    def route_init_tests_shared_js_python(self, request):
        """≙ ``GET /account/init_tests_shared_js_python`` — los casos
        guardados, como ``props`` (divergencia QWeb declarada en el
        docstring del módulo)."""
        tests = json.loads(SystemParameter.get_param(_PARAM_KEY, '[]'))
        return {'props': {'tests': tests}}

    def route_post_tests_shared_js_python(self, request, results):
        """≙ ``POST /account/post_tests_shared_js_python`` — persiste los
        resultados del lado JS."""
        SystemParameter.set_param(_PARAM_KEY, json.dumps(results or []))
        return True
