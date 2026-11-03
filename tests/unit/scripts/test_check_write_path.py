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
    'check_write_path', _SCRIPTS / 'check_write_path.py'
)
check_write_path = importlib.util.module_from_spec(_SPEC)
sys.modules['check_write_path'] = check_write_path
_SPEC.loader.exec_module(check_write_path)

counterpart_body = sys.modules['counterpart_body']

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

    @pytest.mark.parametrize(
        'code, expected',
        [
            ('def f(self):\n    self.objects.bulk_create([x])', BELOW_ORM),
            (
                'def f(self):\n    Model.objects.filter(pk=1).update(a=2)',
                BELOW_ORM,
            ),
            ('def f(self):\n    row.save()', VIA_ORM),
            # El ``write`` de la mezcla de ``orm.models`` guarda con
            # ``save(update_fields=...)``: es el enganche, no la tabla.
            ("def f(self):\n    row.write({'revoked': True})", VIA_ORM),
            ('def f(self):\n    Model.objects.update_or_create(a=1)', VIA_ORM),
            ('def f(self):\n    return 1 + 1', NO_WRITE),
        ],
    )
    def test_our_vocabulary(self, code, expected):
        assert classify(_body(code), OURS) == expected

    @pytest.mark.parametrize(
        'code, expected',
        [
            (
                'def f(self):\n    upsert_en(self, cols, rows, ["model"])',
                BELOW_ORM,
            ),
            (
                'def f(self):\n    self.env.execute_query(SQL("UPDATE x"))',
                BELOW_ORM,
            ),
            ('def f(self):\n    self.create(vals)', VIA_ORM),
            ('def f(self):\n    record.write(vals)', VIA_ORM),
            ('def f(self):\n    return self.name', NO_WRITE),
        ],
    )
    def test_reference_vocabulary(self, code, expected):
        assert classify(_body(code), REFERENCE) == expected

    @pytest.mark.parametrize(
        'code',
        [
            'def f(self):\n    pks = set()\n    pks.update(rows)',
            'def f(self):\n    result.update(values)',
        ],
    )
    def test_a_positional_update_is_a_container_not_a_queryset(self, code):
        # ``QuerySet.update(self, **kwargs)`` (``django/db/models/query.py``)
        # no admite posicionales: ``x.update(y)`` es ``set``/``dict.update``,
        # un homonimo que no escribe en ninguna tabla.
        assert classify(_body(code), OURS) == NO_WRITE

    def test_a_method_using_both_is_not_silently_one_of_them(self):
        both = _body(
            'def f(self):\n    row.save()\n    Q.objects.bulk_create([])'
        )
        assert classify(both, OURS) == check_write_path.MIXED


class TestTheDirectionIsNotSymmetric:
    """Las dos direcciones son riesgos distintos y se nombran distinto."""

    def test_crossing_a_guard_the_source_avoids(self):
        # El caso de H-API-1058: la fuente esquiva su write a proposito.
        assert (
            check_write_path.direction(VIA_ORM, BELOW_ORM)
            == check_write_path.CROSSES_GUARD
        )

    def test_skipping_a_hook_the_source_uses(self):
        assert (
            check_write_path.direction(BELOW_ORM, VIA_ORM)
            == check_write_path.SKIPS_HOOK
        )

    def test_agreement_is_not_a_finding(self):
        assert check_write_path.direction(VIA_ORM, VIA_ORM) is None
        assert check_write_path.direction(BELOW_ORM, BELOW_ORM) is None

    def test_a_side_that_does_not_write_is_not_compared(self):
        # Sin escritura en un lado no hay nada que comparar: emitir un
        # hallazgo ahi seria concluir sobre lo que el instrumento no ve.
        assert check_write_path.direction(NO_WRITE, BELOW_ORM) is None
        assert check_write_path.direction(VIA_ORM, NO_WRITE) is None


class TestTheAlignedWritersStayAligned:
    """Control de regresion de los alineados del 2026-11-03.

    Hasta ese dia el arbol tenia positivos reales —``_reflect_constraint``,
    luego ``_reschedule_asap``, luego ``ResPartner._fields_sync``— y cada uno
    se alineo con la fuente. Sin positivo vivo, el control real es este: cada
    caso nombra un escritor que el gate SI marcaba. Anulado uno
    (``_reschedule_asap`` devuelto a ``objects.create``), cae exactamente su
    caso y ningun otro.
    """

    @pytest.mark.parametrize(
        'path, symbol',
        [
            ('src/addons/base/models/ir_cron.py', '_reschedule_asap'),
            ('src/addons/base/models/ir_cron.py', '_trigger_list'),
            ('src/addons/base/models/res_device.py', '_update_device'),
            ('src/addons/base/models/res_device.py', '__update_revoked'),
            ('src/addons/base/models/res_device.py', '_revoke'),
            ('src/addons/base/models/res_users.py', '_generate'),
            ('src/addons/base/models/ir_actions.py', '_get_eval_context'),
            ('src/addons/base/models/ir_attachment.py', 'generate_access_token'),
            ('src/addons/base/models/res_partner.py', '_fields_sync'),
            ('src/addons/base/models/res_partner.py', '_commercial_sync_from_company'),
            ('src/addons/base/models/res_partner.py', '_commercial_sync_to_descendants'),
            ('src/addons/base/models/res_partner.py', '_company_dependent_commercial_sync'),
        ],
    )
    def test_no_longer_flagged(self, path, symbol):
        flagged = {f.symbol for f in check_write_path.scan([pathlib.Path(path)])}
        assert symbol not in flagged, sorted(flagged)


class TestTheAlignedReflectionsStayAligned:
    """Control de regresion de #345 — que haria fallar a este control.

    Los tres reflejos de ``ir_model.py`` cruzaban el enganche de ``save()``
    donde la fuente escribe por SQL crudo. Se alinearon a ``bulk_create`` y
    ``QuerySet.update()``. Si alguien devuelve un ``update_or_create`` o un
    ``get_or_create`` a cualquiera de los tres, el gate vuelve a nombrarlo y
    este caso se pone rojo — que es exactamente lo que tiene que pasar.
    """

    @pytest.mark.parametrize(
        'symbol',
        ['_reflect_constraint', '_reflect_relation', '_reflect_inherits'],
    )
    def test_no_longer_crosses_a_guard_the_source_avoids(self, symbol):
        findings = check_write_path.scan(
            [pathlib.Path('src/addons/base/models/ir_model.py')]
        )
        flagged = {f.symbol for f in findings}
        assert symbol not in flagged, sorted(flagged)


class TestTheInstrumentDeclaresWhatItCannotDecide:
    """``BOTH`` que contiene la categoria del otro NO es un desacuerdo.

    La unidad de esta comparacion es el **metodo**, y un metodo puede escribir
    por dos mecanismos para dos operaciones distintas: la fuente de
    ``_update_selection`` inserta con ``query_insert`` —por debajo— y borra con
    ``unlink`` —por el enganche—. Nosotros insertamos por debajo y borramos con
    ``QuerySet.delete()``, que es el enganche de este stack. No hay
    divergencia,
    y con la granularidad del metodo tampoco hay forma de afirmarlo: el
    instrumento lo declara indeterminado en vez de inventar un hallazgo.
    """

    def test_a_contained_category_is_indeterminate_not_a_finding(self):
        assert check_write_path.direction(
            check_write_path.BELOW_ORM, check_write_path.MIXED
        ) == (counterpart_body.INDETERMINATE)
        assert check_write_path.direction(
            check_write_path.MIXED, check_write_path.VIA_ORM
        ) == (counterpart_body.INDETERMINATE)

    def test_the_scope_counts_them_apart(self):
        # Contarlos como acuerdo publicaria un verde que no discrimina.
        findings, scope = check_write_path.scan_with_scope(
            [pathlib.Path('src/addons/base/models/ir_model.py')]
        )
        assert scope.pairs_indeterminate >= 2, scope
        assert not [
            f
            for f in findings
            if f.direction == counterpart_body.INDETERMINATE
        ]


class TestTheGateDeclaresWhatItMeasured:
    """Un conteo sin denominador no es un resultado."""

    def test_the_report_carries_its_scope(self):
        findings, scope = check_write_path.scan_with_scope(
            [pathlib.Path('src/addons/base/models/ir_model.py')]
        )
        assert scope.pairs_compared > 0
        assert scope.files_with_counterpart > 0
        assert len(findings) <= scope.pairs_compared
