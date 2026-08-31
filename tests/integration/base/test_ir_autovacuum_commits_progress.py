"""Tests — el barrido cede el turno con el trabajo comiteado (#250).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_autovacuum.py:50``:
``self.env['ir.cron']._commit_progress()`` **dentro** del bucle, tras cada
método de barrido.

El porte lo declinaba diciendo que *"pertenece al runner del cron, que
``ir_cron.py`` declara explícitamente como diferido"*. Medido al barrer la
prosa, ``ir_cron.py:62`` dice **"El runner del cron — PORTADO COMPLETO"** y
``_commit_progress`` está en ``:1130``.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from addons.base.models.ir_autovacuum import IrAutovacuum
from addons.base.models.ir_cron import IrCron
from orm.environments import context_scope

pytestmark = pytest.mark.integration


@pytest.fixture
def counted_commits(monkeypatch):
    """Cuenta las cesiones de turno sin tocar la base."""
    calls = []
    monkeypatch.setattr(IrCron, '_commit_progress',
                        classmethod(lambda cls, *a, **k: calls.append(1)))
    return calls


def _plant(monkeypatch, *methods):
    """Sustituye el censo de métodos por los que el caso quiere ejercer."""
    monkeypatch.setattr(
        IrAutovacuum, '_collect_methods',
        staticmethod(lambda: [(object, f'probe_{i}', f)
                              for i, f in enumerate(methods)]))


class TestTheSweepYieldsAfterEachMethod:

    def test_it_commits_once_per_method(self, monkeypatch, counted_commits):
        """``:50`` — la llamada va **dentro** del bucle, no al final.

        Qué lo haría fallar: comitear una sola vez al terminar. Un barrido
        largo mantendría la transacción abierta durante todo el recorrido, que
        es exactamente lo que ceder el turno existe para evitar.
        """
        _plant(monkeypatch, lambda: None, lambda: None, lambda: None)
        with context_scope(cron_id=1):
            IrAutovacuum._run_vacuum_cleaner()
        assert len(counted_commits) == 3

    def test_a_method_that_raises_does_not_commit_its_own_work(
            self, monkeypatch, counted_commits):
        """CONTROL del SITIO de la llamada dentro del ``try``.

        La fuente comitea **después** de ``func(model)``: un método que
        revienta salta al ``except`` sin pasar por ahí, y su trabajo a medias
        se descarta con el rollback.

        Qué lo haría fallar: comitear antes de llamar, o en un ``finally``.
        El barrido dejaría asentado el trabajo parcial de un método roto.
        """
        def boom():
            raise RuntimeError('barrido roto')

        _plant(monkeypatch, boom, lambda: None)
        with context_scope(cron_id=1):
            IrAutovacuum._run_vacuum_cleaner()
        assert len(counted_commits) == 1

    def test_a_method_that_asks_for_another_turn_commits_each_time(
            self, monkeypatch, counted_commits):
        """El método que devuelve ``(hechos, restantes)`` vuelve a la cola
        (``:56``), y cada vuelta cede el turno otra vez.

        Qué lo haría fallar: comitear por método en vez de por pasada. El
        barrido por lotes —que es para lo que existe el par— acumularía todas
        sus vueltas en una transacción.
        """
        turnos = iter([(10, 5), (5, 0)])

        _plant(monkeypatch, lambda: next(turnos))
        with context_scope(cron_id=1):
            IrAutovacuum._run_vacuum_cleaner()
        assert len(counted_commits) == 2

    def test_without_a_cron_in_context_nothing_runs(self, monkeypatch,
                                                    counted_commits):
        """CONTROL de la guarda de arranque, que es anterior a todo esto.

        Qué lo haría fallar: barrer sin cron. La fuente lo prohíbe
        (``:32-33``) porque el barrido borra filas.
        """
        _plant(monkeypatch, lambda: None)
        with pytest.raises(PermissionError):
            IrAutovacuum._run_vacuum_cleaner()
        assert counted_commits == []
