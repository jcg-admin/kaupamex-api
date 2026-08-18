"""El gate de ``chain_method`` vs ``depends`` — con control positivo histórico.

El control **no está fabricado**: es el ``depends`` que
``account_qr_code_emv`` tenía antes de ``api@921c497`` —``['base']`` a secas—,
el estado exacto que :ref:`h-api-564` registró. Se inyecta por
``depends_of``; ningún manifest se toca.

Escribir el incumplidor a mano heredaría el encuadre de quien escribió el
patrón y confirmaría el instrumento en vez de probarlo, que es el modo de fallo
que ``hallazgo-abierto-genera-sucesor.md`` documenta para los gates.
"""
import importlib.util
import pathlib

import pytest

RUTA = (pathlib.Path(__file__).resolve().parents[3]
        / 'scripts' / 'check_chain_method_depends.py')
_spec = importlib.util.spec_from_file_location('check_chain_method_depends', RUTA)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


#: ``depends`` de ``account_qr_code_emv`` antes de ``api@921c497``.
HISTORICO = {'account_qr_code_emv': ['base']}


def historico(addon):
    if addon in HISTORICO:
        return HISTORICO[addon]
    return gate.manifest_depends(addon)


def test_el_arbol_actual_pasa():
    fallas, _, total = gate.violations()
    assert fallas == [], fallas
    assert total > 0, 'sin llamadas medidas el OK no significa nada'


def test_control_positivo_historico_falla():
    """Con el ``depends`` de antes del arreglo, el gate ve el defecto real."""
    fallas, _, _ = gate.violations(depends_of=historico)
    culpables = {(addon, faltan_uno)
                 for addon, _, _, _, _, faltan in fallas
                 for faltan_uno in faltan}
    assert ('account_qr_code_emv', 'account') in culpables, fallas


def test_los_pares_no_se_señalan():
    """``emv`` y ``sepa`` se encadenan sin depender uno del otro: no es falla.

    La referencia los deja igual de incomparables (``odoo19c`` declara
    ``depends: ['account']`` en ambos), así que exigirles orden sería inventar
    una regla que la referencia contradice.
    """
    fallas, _, _ = gate.violations()
    pares = {'account_qr_code_emv', 'account_qr_code_sepa'}
    señalados = {faltan_uno
                 for addon, _, _, _, _, faltan in fallas
                 for faltan_uno in faltan
                 if addon in pares}
    assert señalados & pares == set(), señalados


def test_resuelve_el_nombre_ligado_por_un_for():
    """``account`` instala sus once terminales con un nombre de variable.

    Sin esta resolución el gate sería ciego justo al declarante que el episodio
    dejó fuera del ``depends`` — el defecto quedaría invisible para el
    instrumento que existe para verlo.
    """
    _, _, instala, _ = gate.scan()
    assert 'account' in instala[('ResPartnerBank', '_get_qr_vals')]


def test_una_property_no_cuenta_como_metodo_del_cuerpo():
    """El cuerpo aporta dueños sólo por ``def``; el gate no inventa símbolos."""
    _, cuerpo, _, _ = gate.scan()
    assert all(isinstance(k, tuple) and len(k) == 2 for k in cuerpo)


@pytest.mark.parametrize('flag', ['--quiet', '--strict'])
def test_los_flags_existen(flag, monkeypatch):
    monkeypatch.setattr(gate.sys, 'argv', ['gate', flag])
    assert gate.main() == 0


def test_heredar_la_clase_no_convierte_en_dueno_del_simbolo():
    """``utm.IrHttp`` hereda de ``base.IrHttp``; no es dueña de ``is_a_bot``.

    Control positivo del árbol real, no fabricado: ``is_a_bot`` lo **define e
    instala** ``web`` sobre la clase de ``base``
    (``addons/web/models/ir_http.py:176,213``), y ``utm`` sólo declara una
    subclase — el idioma con el que la referencia extiende ``ir.http`` desde un
    addon (``odoo19c: addons/utm/models/ir_http.py``).

    Resolver el dueño por **nombre corto de clase** hacía que cualquier addon
    con una ``class IrHttp`` entrara en el conjunto, y el gate exigía a ``web``
    un ``depends: ['utm']`` que sería una dependencia inventada. Ver
    :ref:`h-api-635`.
    """
    declara_clase, _, _, _ = gate.scan()
    assert 'base' in declara_clase['IrHttp']
    assert 'utm' not in declara_clase['IrHttp']
