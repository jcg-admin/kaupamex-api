"""Tests unitarios — la FORMA de los ``Char`` de los satélites ``hr_*`` (H-API-760).

Hermano de ``test_hr_reference_shape.py``, y su **contrapunto**: allí
``CAPPED_BY_DECISION`` está vacío porque la fuente declaraba sus 93
``fields.Char`` sin tamaño; aquí **no** lo está, porque en esta superficie la
referencia sí pone tope — tres veces, y las tres con una razón visible.

Por eso el sucesor se midió **campo a campo** y no addon por addon. Medido
sobre ``odoo19c`` (``odoo-tools@abe4040ec1``)::

    git grep -n 'size=' origin/main -- ".../addons/hr_recruitment/" ".../addons/hr_work_entry/"
      hr_recruitment/models/hr_applicant.py:47        size=128   (email_from)
      hr_recruitment/models/hr_applicant.py:57        size=32    (partner_phone)
      hr_work_entry/models/hr_work_entry_type.py:12   size=3     (display_code)

    hr_skills · hr_timesheet · hr_homeworking   ->  0 size=

Un campo cuyo contrato **es** su longitud conserva el tope: el ``display_code``
lo dice en su propio ``help`` — *"This code can be changed, it is only for a
display purpose (3 letters max)"*. Los demás lo pierden, porque
``pg_varchar(self.size)`` con tamaño nulo devuelve un ``VARCHAR`` sin límite
(``odoo19c: odoo/tools/sql.py:644-654``).
"""
import pytest
from django.apps import apps
from django.db import connection

pytestmark = [pytest.mark.unit]

#: Modelos de los satélites cuyos ``Char`` se miden enteros. Enumerados por
#: etiqueta, no barriendo la app, para que un modelo nuevo entre por decisión.
SATELLITE_LABELS = [
    'hr_recruitment.HrApplicant',
    'hr_recruitment.HrApplicantCategory',
    'hr_recruitment.HrApplicantRefuseReason',
    'hr_recruitment.HrJobPlatform',
    'hr_recruitment.HrRecruitmentDegree',
    'hr_recruitment.HrRecruitmentStage',
    'hr_recruitment.HrTalentPool',
    'hr_skills.HrResumeLine',
    'hr_skills.HrResumeLineType',
    'hr_skills.HrSkill',
    'hr_skills.HrSkillLevel',
    'hr_skills.HrSkillType',
    'hr_work_entry.HrWorkEntry',
    'hr_work_entry.HrWorkEntryType',
]

#: El campo que ``hr_timesheet`` cuelga de ``uom.uom`` por extensión. Su columna
#: vive en ``uom`` —y por eso su migración salió ahí, no en ``hr_timesheet``—,
#: pero el campo es del satélite y se mide con los demás. El resto de los
#: ``Char`` de ``uom.Uom`` NO entra: son de su propio addon.
UOM_FIELD = ('uom.Uom', 'timesheet_widget')

#: Topes con tope **declarado y justificado**: los tres que la referencia
#: impone con ``size=``. Retirarlos sería divergir de la fuente, no alinearse.
CAPPED_BY_DECISION: dict[tuple[str, str], int] = {
    ('hr_recruitment.HrApplicant', 'email_from'): 128,
    ('hr_recruitment.HrApplicant', 'partner_phone'): 32,
    ('hr_work_entry.HrWorkEntryType', 'display_code'): 3,
}


def _char_fields(label):
    model = apps.get_model(label)
    return [
        f for f in model._meta.get_fields()
        if getattr(f, 'get_internal_type', None) and f.get_internal_type() == 'CharField'
    ]


@pytest.mark.parametrize('label', SATELLITE_LABELS)
def test_only_the_three_capped_by_the_source_declare_a_cap(label):
    """Ningún ``Char`` lleva tope salvo los tres que la fuente sí impone.

    La aserción corre en los dos sentidos, y ésa es la mitad que importa: un
    tope **de más** rompe (se inventó un límite), y un tope **de menos** también
    (se retiró el que la fuente declara). Un barrido en bloque habría fallado
    por el segundo lado sin que nadie lo notara.
    """
    measured = {
        f.name: f.max_length
        for f in _char_fields(label)
        if getattr(f, 'max_length', None)
    }
    expected = {
        name: limit
        for (lbl, name), limit in CAPPED_BY_DECISION.items()
        if lbl == label
    }
    assert measured == expected, (
        f'{label}: topes medidos {measured}, esperados {expected} — la fuente '
        f'declara size= sólo donde la longitud es el contrato '
        f'(odoo19c, odoo-tools@abe4040ec1)'
    )


def test_the_uom_field_hung_by_hr_timesheet_declares_no_cap():
    """``hr_timesheet`` extiende ``uom.uom`` — el campo es suyo, la tabla no.

    ``odoo19c: addons/hr_timesheet/models/uom_uom.py`` lo declara
    ``fields.Char("Widget", export_string_translation=False)``, sin tamaño.
    """
    label, name = UOM_FIELD
    field = apps.get_model(label)._meta.get_field(name)
    assert field.max_length is None, (
        f'{label}.{name} declara max_length={field.max_length}'
    )


@pytest.mark.django_db
def test_the_satellite_char_columns_match_the_declared_caps():
    """El tope se retiró en la base, no sólo en el modelo — y el que se
    conserva llegó a la columna.

    Sin esta aserción, una migración futura podría reponer un límite o dejar de
    generarse, y nadie se enteraría hasta el próximo truncamiento — que es
    exactamente cómo se destapó :ref:`h-api-750`.
    """
    expected: dict[tuple[str, str], int | None] = {}
    for label in SATELLITE_LABELS:
        model = apps.get_model(label)
        if not model._meta.managed:
            continue
        for f in _char_fields(label):
            if getattr(f, 'column', None):
                expected[(model._meta.db_table, f.column)] = \
                    CAPPED_BY_DECISION.get((label, f.name))
    uom_model = apps.get_model(UOM_FIELD[0])
    expected[(uom_model._meta.db_table, UOM_FIELD[1])] = None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name, character_maximum_length
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name  = ANY(%s)
            """,
            [sorted({t for t, _ in expected})],
        )
        measured = {
            (t, c): limit
            for t, c, limit in cursor.fetchall()
            if (t, c) in expected
        }

    assert set(measured) == set(expected), (
        f'columnas no encontradas en el schema: {set(expected) - set(measured)}'
    )
    divergent = {k: (v, expected[k]) for k, v in measured.items() if v != expected[k]}
    assert not divergent, (
        f'columnas cuyo varchar(n) no coincide con lo declarado '
        f'(medido, esperado): {divergent}'
    )
