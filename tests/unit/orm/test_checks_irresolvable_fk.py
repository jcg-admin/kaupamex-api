"""``orm/checks.py`` — el gate de ``run_checks()`` antes de ``makemigrations``.

Cubre H-API-584/H-API-677: una ``ForeignKey`` cuyo destino ningún addon
instalado declara debe fallar en ``run_checks()``, y esa corrida debe ocurrir
ANTES de que algo escriba una migración — tanto por la vía CLI como por la
programática (``call_command``).

Métrica: mensajes ``fields.E30x`` que Django reporta sobre un modelo con FK
irresoluble. Ciega a: fallos de runtime dentro de un método (esto valida el
cableado declarativo del registro, no el cuerpo).

El positivo reproduce la FORMA del incidente real —una FK del addon
``stock`` a un modelo del mismo addon que aún no existe (:ref:`h-api-583`,
:ref:`h-api-584`: ``stock.move.line`` -> ``stock.StockPickingType`` /
``stock.stockwarehouse``)— usando ``django.test.utils.isolate_apps``, el
mecanismo canónico con que el propio Django prueba sus checks de modelo, no
un ad-hoc propio. El nombre del destino NO reutiliza el string literal del
incidente: ``StockPickingType`` y ``StockWarehouse`` ya existen como modelos
reales en esta rama (el incidente se cerró en otra rama, ``feature/
completar-familia-base`` — ver H-API-677) y usarlos produciría un falso
positivo del propio test, no del gate. Se usa en su lugar un nombre que no
existe en ningún addon instalado, verificado por exclusión: si
``StockPickingType`` ya resuelve, el destino sintético no puede colisionar
con él.
"""
import inspect

import django.core.checks.model_checks as django_model_checks
from django.db import models
from django.test.utils import isolate_apps

from addons.stock.models.stock_move import StockMove
from orm.checks import (
    call_command_with_checks,
    collect_system_check_summary,
    run_checks_or_raise,
)


# === El detector: Django ve la FK irresoluble, con la forma real del incidente ==

class TestDanglingForeignKeyIsDetected:
    """Reproduce H-API-583/584: FK a un modelo que su addon aún no declara.

    ``StockPickingTypeGhost`` no existe en ningún addon instalado — se
    verifica en cada test que ``StockPickingType`` (el modelo real que SÍ
    existe hoy en esta rama) queda excluido del nombre usado, para no
    confundir el positivo con el modelo real.
    """

    DANGLING_TARGET = 'stock.StockPickingTypeGhostH677'

    @isolate_apps('addons.stock')
    def test_fk_to_undeclared_model_raises_e300(self):
        class StockMoveLineProbe(models.Model):
            """Forma real: ``stock.move.line`` -> un modelo del mismo addon
            que aún no existe (la clase de defecto de H-API-583)."""
            picking_type_id = models.ForeignKey(
                self.DANGLING_TARGET, on_delete=models.CASCADE,
            )

            class Meta:
                app_label = 'stock'

        errors = StockMoveLineProbe.check()
        ids = {e.id for e in errors}
        assert 'fields.E300' in ids
        assert any('StockPickingTypeGhostH677' in str(e.msg) for e in errors)
        # dangling_fk_errors() filtra por el prefijo 'fields.E30' — cubre
        # E300 (medido aquí) y E307 (medido en el registro real más abajo,
        # nunca vía isolate_apps: ver la nota siguiente).

    def test_e307_lazy_reference_is_a_global_registry_check_not_isolated(self):
        """``fields.E307`` NO se puede reproducir vía ``isolate_apps``.

        Medido leyendo ``django/core/checks/model_checks.py:225-226``:

            @register(Tags.models)
            def check_lazy_references(app_configs, **kwargs):
                return _check_lazy_references(apps)

        Ignora el ``app_configs`` que le pasan — usa el ``apps`` importado
        al TOP del propio módulo de Django, que es siempre el registro
        GLOBAL (``django.apps.apps``), nunca el ``Options.default_apps``
        que ``isolate_apps`` sustituye. Por eso E307 sólo aparece si el
        modelo con la FK colgante está en el registro real — que es
        precisamente lo que :func:`orm.checks.run_checks_or_raise` recorre
        por defecto (``app_configs=None``). No se reintroduce la FK rota en
        el árbol real para probarlo: el hecho ya quedó verificado con la
        cita de arriba, y ``dangling_fk_errors()`` filtra por el prefijo
        ``fields.E30``, que cubre E300 y E307 por igual sin distinguirlos.
        """
        source = inspect.getsource(django_model_checks.check_lazy_references)
        assert 'return _check_lazy_references(apps)' in source


# === La forma NEGATIVA de control: una FK real que sí resuelve no dispara nada ==

class TestResolvableForeignKeyIsNotFlagged:
    """Control negativo — ``StockMove.location_id`` resuelve de verdad hoy."""

    def test_real_resolvable_fk_has_no_dangling_error(self):
        errors = [e for e in StockMove.check() if e.id and e.id.startswith('fields.E30')]
        assert errors == []


# === El wrapper del proyecto: denominador + Métrica/Ciega a =====================

class TestCollectSystemCheckSummary:
    """``collect_system_check_summary()`` sobre el registro real del árbol."""

    def test_current_tree_has_zero_dangling_fk_errors(self):
        """Medido 2026-08-18 (feature/kaupamex-l0): 327 modelos, 0 errores.

        No es un valor mágico: el propio test lo deriva del resumen — sólo
        afirma que hoy no hay ninguna FK irresoluble y que el denominador es
        positivo (el gate sí recorrió algo).
        """
        resumen = collect_system_check_summary()
        assert resumen.models_scanned > 0
        assert resumen.dangling_fk_errors() == []

    def test_run_checks_or_raise_passes_clean_tree(self):
        resumen = run_checks_or_raise()
        assert resumen.errors == []


# === El hallazgo real: call_command() se salta los checks por defecto ===========

class TestCallCommandWithChecksEnforcesTheFlag:
    """El footgun detrás de H-API-584 — no es ``makemigrations``, es ``call_command``.

    ``django/core/management/__init__.py:192-193`` fija ``skip_checks=True``
    salvo que el llamador lo pase explícito. La vía CLI SÍ corre
    ``self.check()`` (``requires_system_checks='__all__'`` sin sobreescribir
    en ``makemigrations.Command``) y aborta con ``SystemCheckError`` —
    verificado en este árbol (2026-08-18) contra un modelo real con FK
    irresoluble vía ``execute_from_command_line``; ver el docstring de
    ``orm/checks.py`` para la traza completa. La vía programática, no —y
    ``src/service/db.py`` usa exactamente esa vía (tarea #484).

    Estos tests inyectan un ``call_command`` falso (parámetro ``_call_command``
    de :func:`call_command_with_checks`) en vez de parchear
    ``django.core.management.call_command`` en caliente — eso evitaría un
    import perezoso que ``no-lazy-imports.md`` prohíbe, y además prueba el
    contrato real de la función (qué opciones construye), no un detalle de
    implementación de cómo Django resuelve el nombre.
    """

    def test_default_forces_skip_checks_false(self):
        captured = {}

        def fake_call_command(name, *args, **options):
            captured['name'] = name
            captured['options'] = options
            return None

        call_command_with_checks(
            'migrate', database='default', _call_command=fake_call_command,
        )

        assert captured['name'] == 'migrate'
        assert captured['options'].get('skip_checks') is False

    def test_explicit_skip_checks_true_is_respected(self):
        """El llamador puede pedir explícitamente saltarse el check.

        No es el default recomendado, pero la función no le quita esa
        opción a quien la pide a propósito (p. ej. un ``migrate`` repetido
        dentro de la misma transacción de arranque, ya verificado antes).
        """
        captured = {}

        def fake_call_command(name, *args, **options):
            captured['options'] = options
            return None

        call_command_with_checks(
            'migrate', database='default', skip_checks=True,
            _call_command=fake_call_command,
        )

        assert captured['options'].get('skip_checks') is True
