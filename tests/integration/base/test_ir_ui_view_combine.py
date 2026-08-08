"""``ir.ui.view`` — el combinador de herencia sobre registros reales.

El motor XPath ya tiene su contrato en
``tests/unit/tools/test_template_inheritance.py`` (funciones puras). Aquí se
prueba la **orquestación** que ``get_combined_arch`` porta de la fuente
(``odoo19c: ir_ui_view.py:1010-1100``): qué vistas entran, en qué orden, y
desde dónde parte la combinación.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models.ir_ui_view import (
    MODE_EXTENSION,
    MODE_PRIMARY,
    IrUiView,
)

pytestmark = pytest.mark.django_db


def make_view(name, arch, *, inherit=None, mode=MODE_PRIMARY, priority=16,
              active=True, model=''):
    return IrUiView.objects.create(
        name=name, type='qweb', key=f'test.{name}', arch_db=arch,
        inherit_id=inherit, mode=mode, priority=priority, active=active,
        model=model,
    )


class TestGetCombinedArch:
    def test_sin_heredantes_devuelve_el_arch_propio(self):
        base = make_view('base', '<doc><a/></doc>')
        assert base.get_combined_arch() == '<doc><a/></doc>'

    def test_una_extension_aplica_su_spec(self):
        base = make_view('base', '<doc><a/></doc>')
        make_view('ext', '<xpath expr="//a" position="after"><b/></xpath>',
                  inherit=base, mode=MODE_EXTENSION)
        assert base.get_combined_arch() == '<doc><a/><b/></doc>'

    def test_extension_de_extension_ve_lo_que_su_padre_agrego(self):
        # El recorrido es en profundidad: la nieta se aplica sobre el
        # resultado de su madre, así que puede anclarse en el nodo que la
        # madre insertó.
        base = make_view('base', '<doc><a/></doc>')
        ext = make_view('ext', '<xpath expr="//a" position="after"><b/></xpath>',
                        inherit=base, mode=MODE_EXTENSION)
        make_view('nieta', '<xpath expr="//b" position="inside"><c/></xpath>',
                  inherit=ext, mode=MODE_EXTENSION)
        assert base.get_combined_arch() == '<doc><a/><b><c/></b></doc>'

    def test_prioridad_decide_el_orden_entre_hermanas(self):
        # Dos parches sobre el mismo nodo: el de menor priority se aplica
        # antes y el segundo ve su resultado. La fuente lo advierte — el
        # orden cambia la pantalla, no sólo la presentación.
        base = make_view('base', '<doc><a/></doc>')
        make_view('tarde', '<xpath expr="//a" position="before"><t/></xpath>',
                  inherit=base, mode=MODE_EXTENSION, priority=20)
        make_view('temprano', '<xpath expr="//a" position="before"><e/></xpath>',
                  inherit=base, mode=MODE_EXTENSION, priority=10)
        # ``temprano`` corre primero (priority 10): inserta <e/> pegado a
        # <a/>; ``tarde`` inserta después <t/> también pegado a <a/>, o sea
        # DETRÁS de <e/>. Si el orden se invirtiera saldría t,e,a.
        assert base.get_combined_arch() == '<doc><e/><t/><a/></doc>'

    def test_inactiva_no_extiende(self):
        base = make_view('base', '<doc><a/></doc>')
        make_view('apagada', '<xpath expr="//a" position="after"><b/></xpath>',
                  inherit=base, mode=MODE_EXTENSION, active=False)
        assert base.get_combined_arch() == '<doc><a/></doc>'

    def test_desde_la_extension_se_combina_el_arbol_completo(self):
        # Pedir el arch combinado de una extensión resuelve primero su
        # primaria (root_view) — fuente :1051: el ascenso por inherit_id.
        base = make_view('base', '<doc><a/></doc>')
        ext = make_view('ext', '<xpath expr="//a" position="after"><b/></xpath>',
                        inherit=base, mode=MODE_EXTENSION)
        assert ext.get_combined_arch() == '<doc><a/><b/></doc>'

    def test_hija_primaria_no_parcha_al_padre(self):
        # Una hija en modo primario es OTRA vista (arranca de la combinada
        # del padre por su cuenta); sus specs no entran al combinar el padre.
        base = make_view('base', '<doc><a/></doc>')
        make_view('variante', '<xpath expr="//a" position="after"><v/></xpath>',
                  inherit=base, mode=MODE_PRIMARY)
        assert base.get_combined_arch() == '<doc><a/></doc>'

    def test_spec_roto_nombra_a_la_vista_culpable(self):
        base = make_view('base', '<doc><a/></doc>')
        make_view('rota', '<xpath expr="//inexistente" position="after"><b/></xpath>',
                  inherit=base, mode=MODE_EXTENSION)
        with pytest.raises(ValidationError, match='rota'):
            base.get_combined_arch()
