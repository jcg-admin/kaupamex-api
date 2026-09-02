r"""``report_catalog.py`` no le miente al enum — tarea **#268**.

``src/addons/base/report_catalog.py`` decía en su docstring: *"Hoy **sólo**
``pdf``"* para ``ReportSpec.report_type``. Medido, ``REPORT_TYPE_CHOICES``
(``ir_actions_report.py``) ya declara **tres** valores desde ``api@3a620979``
(tarea #196, cerrando H-API-291): ``html``, ``pdf`` y ``text`` —
``_render_qweb_html``/``_render_qweb_text`` los serializan desde el mismo
descriptor que ``builder`` construye, vía
``report_template.descriptor_to_html``/``descriptor_to_text``.

Este caso discrimina dos cosas, cada una con su propio instrumento:

1. **La prosa no vuelve a decir "sólo pdf"** — regresión estática sobre el
   propio texto del módulo, para que un futuro edit no reintroduzca la
   afirmación caducada sin que algo la note.
2. **El código no rechaza un formato que el enum ofrece** — ``ReportSpec``
   acepta los tres valores de ``REPORT_TYPE_CHOICES`` sin levantar, que es
   la forma ejecutable de "el catálogo coincide con el enum".
"""
import inspect

import pytest

from addons.base import report_catalog
from addons.base.models.ir_actions_report import REPORT_TYPE_CHOICES

pytestmark = [pytest.mark.unit]

#: Los formatos que el catálogo tiene que poder declarar sin protestar — el
#: mismo enum que gobierna ``ir.actions.report.report_type``, leído de la
#: fuente real y no transcrito a mano (si el enum crece, este caso crece con
#: él sin que alguien tenga que acordarse de actualizar una lista aparte).
DECLARED_REPORT_TYPES = [value for value, _label in REPORT_TYPE_CHOICES]


def _builder(record, **context):
    return {'title': 'Reporte de prueba'}


def test_at_least_pdf_html_and_text_are_declared():
    """Guarda contra que el propio enum se reduzca sin que este caso lo note.

    *Ciega a:* un cuarto formato que el enum sume — esto no exige "sólo tres",
    exige que los tres conocidos sigan ahí.
    """
    assert set(DECLARED_REPORT_TYPES) >= {'html', 'pdf', 'text'}


@pytest.mark.parametrize('report_type', DECLARED_REPORT_TYPES)
def test_report_spec_accepts_every_declared_report_type(report_type):
    """``ReportSpec`` no rechaza ningún formato que ``REPORT_TYPE_CHOICES``
    ofrece — la forma ejecutable de "el catálogo coincide con el enum".

    Antes de la tarea #196 el docstring afirmaba "sólo pdf", pero el propio
    ``__init__`` ya no lo hacía cumplir (sólo valida ``helper`` cuando
    ``report_type == 'pdf'``); este caso mide el contrato real, no la prosa
    vieja que lo describía de menos.
    """
    spec = report_catalog.ReportSpec(
        report_name=f'base.test_report_{report_type}',
        model='base.ResCompany',
        name=f'Reporte de prueba ({report_type})',
        builder=_builder,
        report_type=report_type,
    )
    assert spec.report_type == report_type


def test_module_docstring_no_longer_claims_pdf_only():
    """Regresión textual: la prosa no vuelve a decir que sólo se emite PDF.

    Ninguno de los dos referentes de esta afirmación —el docstring del
    módulo y el de la clase ``ReportSpec``— puede volver a decir «sólo pdf»
    mientras ``REPORT_TYPE_CHOICES`` siga ofreciendo más de un valor. Si
    alguien reintroduce la frase sin actualizar el enum, o baja el enum a un
    solo valor sin tocar la prosa, este caso cae.
    """
    module_doc = inspect.getdoc(report_catalog) or ''
    spec_doc = inspect.getdoc(report_catalog.ReportSpec) or ''
    stale_claim = 'sólo' in (module_doc + spec_doc).lower() \
        and 'pdf' in (module_doc + spec_doc).lower() \
        and 'html' not in (module_doc + spec_doc).lower()
    assert not stale_claim, (
        'la prosa afirma "sólo pdf" sin nombrar html/text — está desalineada '
        'con REPORT_TYPE_CHOICES, que hoy ofrece '
        f'{DECLARED_REPORT_TYPES!r}')
    # Los tres valores declarados se nombran en alguno de los dos
    # docstrings — no basta con que la frase vieja haya desaparecido; el
    # texto tiene que decir positivamente lo que el enum ofrece.
    combined = (module_doc + spec_doc).lower()
    for report_type in DECLARED_REPORT_TYPES:
        assert report_type in combined, (
            f'{report_type!r} está en REPORT_TYPE_CHOICES pero ningún '
            'docstring de report_catalog.py lo menciona')
