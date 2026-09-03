"""Control del gate que compara el CAMINO DE ESCRITURA contra la referencia.

El defecto que mide nacio en H-API-1058: ``_reflect_models`` escribia con
``update_or_create`` —que pasa por ``save()`` y por tanto por la guarda de los
cuatro campos inmodificables— mientras la fuente escribe con ``upsert_en``,
SQL con ``ON CONFLICT``, fuera del alcance de su ``write``. Se descubrio por
casualidad: ninguno de los 29 gates del repo mira el CUERPO de un metodo, solo
su presencia, su cabecera o su sitio.

Los casos usan positivos REALES del arbol, no fabricados: quien escribe el
patron no puede validarlo con su propio encuadre
(``hallazgo-abierto-genera-sucesor.md``).
"""
import ast
import importlib.util
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[3] / 'scripts'
_SPEC = importlib.util.spec_from_file_location(
    'check_write_path', _SCRIPTS / 'check_write_path.py')
check_write_path = importlib.util.module_from_spec(_SPEC)
sys.modules['check_write_path'] = check_write_path
_SPEC.loader.exec_module(check_write_path)

classify = check_write_path.classify
Vocabulary = check_write_path.Vocabulary
OURS = check_write_path.OURS
REFERENCE = check_write_path.REFERENCE
VIA_ORM = check_write_path.VIA_ORM
BELOW_ORM = check_write_path.BELOW_ORM
NO_WRITE = check_write_path.NO_WRITE


def _body(code):
    return ast.parse(code).body[0]


class TestTheClassifierSeparatesTheTwoPaths:
    """Lo que decide no es la llamada literal sino si pasa por el enganche."""

    @pytest.mark.parametrize('code, expected', [
        ('def f(self):\n    self.objects.bulk_create([x])', BELOW_ORM),
        ('def f(self):\n    Model.objects.filter(pk=1).update(a=2)', BELOW_ORM),
        ('def f(self):\n    row.save()', VIA_ORM),
        ('def f(self):\n    Model.objects.update_or_create(a=1)', VIA_ORM),
        ('def f(self):\n    return 1 + 1', NO_WRITE),
    ])
    def test_our_vocabulary(self, code, expected):
        assert classify(_body(code), OURS) == expected

    @pytest.mark.parametrize('code, expected', [
        ('def f(self):\n    upsert_en(self, cols, rows, ["model"])', BELOW_ORM),
        ('def f(self):\n    self.env.execute_query(SQL("UPDATE x"))', BELOW_ORM),
        ('def f(self):\n    self.create(vals)', VIA_ORM),
        ('def f(self):\n    record.write(vals)', VIA_ORM),
        ('def f(self):\n    return self.name', NO_WRITE),
    ])
    def test_reference_vocabulary(self, code, expected):
        assert classify(_body(code), REFERENCE) == expected

    def test_a_method_using_both_is_not_silently_one_of_them(self):
        both = _body('def f(self):\n    row.save()\n    Q.objects.bulk_create([])')
        assert classify(both, OURS) == check_write_path.MIXED


class TestTheDirectionIsNotSymmetric:
    """Las dos direcciones son riesgos distintos y se nombran distinto."""

    def test_crossing_a_guard_the_source_avoids(self):
        # El caso de H-API-1058: la fuente esquiva su write a proposito.
        assert check_write_path.direction(VIA_ORM, BELOW_ORM) == check_write_path.CROSSES_GUARD

    def test_skipping_a_hook_the_source_uses(self):
        assert check_write_path.direction(BELOW_ORM, VIA_ORM) == check_write_path.SKIPS_HOOK

    def test_agreement_is_not_a_finding(self):
        assert check_write_path.direction(VIA_ORM, VIA_ORM) is None
        assert check_write_path.direction(BELOW_ORM, BELOW_ORM) is None

    def test_a_side_that_does_not_write_is_not_compared(self):
        # Sin escritura en un lado no hay nada que comparar: emitir un
        # hallazgo ahi seria concluir sobre lo que el instrumento no ve.
        assert check_write_path.direction(NO_WRITE, BELOW_ORM) is None
        assert check_write_path.direction(VIA_ORM, NO_WRITE) is None


class TestTheGateSeesTheRealPositive:
    """Control positivo REAL: el metodo que #345 identifico a mano."""

    def test_it_flags_reflect_constraint(self):
        findings = check_write_path.scan([
            pathlib.Path('src/addons/base/models/ir_model.py')])
        flagged = {f.symbol for f in findings}
        assert '_reflect_constraint' in flagged, sorted(flagged)

    def test_the_flagged_direction_is_the_dangerous_one(self):
        findings = check_write_path.scan([
            pathlib.Path('src/addons/base/models/ir_model.py')])
        one = next(f for f in findings if f.symbol == '_reflect_constraint')
        assert one.direction == check_write_path.CROSSES_GUARD


class TestTheGateDeclaresWhatItMeasured:
    """Un conteo sin denominador no es un resultado."""

    def test_the_report_carries_its_scope(self):
        findings, scope = check_write_path.scan_with_scope([
            pathlib.Path('src/addons/base/models/ir_model.py')])
        assert scope.pairs_compared > 0
        assert scope.files_with_counterpart > 0
        assert len(findings) <= scope.pairs_compared
