"""El chequeo de coherencia de ``auto_install`` en ``update_module_list``.

La referencia corre el punto fijo de ``auto_install`` dentro de ``initialize()``
(``odoo19c: odoo/modules/db.py:91-124``) y marca ``state='to install'``:
**instala**. Este árbol no tiene instalador dinámico —``INSTALLED_APPS`` es una
lista explícita—, así que el mismo cálculo se usa para **verificar**: qué addon
declara ``auto_install``, tiene sus dependencias requeridas presentes, y aun así
no está cargado.

Estos tests fijan que el chequeo existe y **discrimina**. Sin el segundo, un
reporte que siempre dijera "coherente" pasaría por bueno: un instrumento que no
puede ver el fallo publica su silencio como éxito.

Cierra :ref:`h-api-410` — ``ModuleGraph.auto_installable`` estaba portado, era
fiel, y no lo llamaba nadie.
"""
import io

import pytest
from django.conf import settings
from django.core.management import call_command

from modules import ModuleGraph
from modules.module import get_modules

pytestmark = pytest.mark.django_db


def installed_addon_names():
    return {
        app.rsplit('.', 1)[-1]
        for app in settings.INSTALLED_APPS
        if app.startswith('addons.')
    }


def module_graph():
    graph = ModuleGraph()
    graph.extend(sorted(get_modules()))
    return graph


def test_the_command_reports_auto_install_coherence():
    """El chequeo corre dentro del comando, no es una función suelta."""
    out = io.StringIO()
    call_command('update_module_list', '--dry-run', stdout=out)
    salida = out.getvalue()

    assert 'auto_install coherente: 0 pendientes' in salida
    # El denominador va junto al conteo: un 0 sin alcance no es un resultado.
    assert 'alcance medido:' in salida


def test_the_published_scope_is_what_the_check_can_see():
    """El denominador es "con manifest", no el total del árbol.

    Un addon sin ``__manifest__.py`` no tiene dónde declarar ``auto_install``,
    así que es **invisible** para este cálculo aunque esté cargado. Publicar el
    total como alcance sería el denominador oculto.

    Cuando este test se escribió el hueco era de 4.5× —20 addons con manifest
    de 90 en el árbol— y su aserción era ``<``. La tarea #296 cerró el hueco
    (:ref:`h-api-561`: la referencia declara manifiesto en 653 de 653), así
    que hoy los dos conteos coinciden y lo que el test protege cambia de
    sentido: ya no vigila que el denominador sea menor, vigila que **siga
    publicándose**. Si alguien añade un addon sin manifiesto, el alcance baja
    y la desigualdad de abajo lo delata.
    """
    out = io.StringIO()
    call_command('update_module_list', '--dry-run', stdout=out)

    graph = module_graph()
    modules = sorted(get_modules())
    with_manifest = [name for name in modules if graph[name].manifest]

    assert len(with_manifest) == len(modules), (
        'un addon del árbol perdió su __manifest__.py — el alcance del '
        'chequeo vuelve a ser menor que el árbol (ver #296)')
    assert (f'alcance medido: {len(with_manifest)} addon(s) con manifest '
            f'de {len(modules)} en el árbol') in out.getvalue()


def test_no_auto_install_addon_is_missing_from_installed_apps():
    """El estado que el chequeo existe para sostener.

    Si este test empieza a fallar, alguien añadió un addon puente al árbol y
    olvidó ``INSTALLED_APPS`` — que es el modo de fallo de :ref:`h-api-364`,
    donde cinco métodos no se instalaron nunca y sólo lo vieron sus tests.
    """
    assert module_graph().auto_installable(installed_addon_names()) == []


def test_the_check_sees_an_addon_left_out_of_installed_apps():
    """Control positivo: quitar un addon puente lo hace aparecer.

    ``account_qr_code_sepa`` declara ``auto_install: True`` y depende de
    ``base``, ``account`` y ``base_iban``, los tres cargados. Retirarlo del
    conjunto de presentes reproduce exactamente el olvido que el chequeo
    persigue — sin tocar ``INSTALLED_APPS`` real, que recargaría el registro
    de apps.
    """
    graph = module_graph()
    bridge = 'account_qr_code_sepa'
    assert graph[bridge].manifest.get('auto_install') is True
    assert set(graph[bridge].depends) <= installed_addon_names()

    reduced = installed_addon_names() - {bridge}
    assert bridge in graph.auto_installable(reduced)


def test_an_addon_without_auto_install_never_appears():
    """El chequeo no reclama addons que no lo declaran.

    Delimita el falso positivo: retirar de la lista un addon **sin**
    ``auto_install`` no lo convierte en pendiente — es una decisión de
    despliegue, no una incoherencia.
    """
    graph = module_graph()
    plain = 'base_iban'
    assert graph[plain].manifest.get('auto_install', False) is False

    reduced = installed_addon_names() - {plain}
    assert plain not in graph.auto_installable(reduced)
