"""``res.company`` — el esquema de propiedades de puesto (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/res_company.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 9 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 1 de 1 símbolo.

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.ResCompany`` no declara ``_name``. Mismo mecanismo que
``hr/models/res_company.py::employee_properties_definition``.
"""
import fields
from orm.model_classes import extend_model


def apply_hr_recruitment_res_company_extensions():
    """Cuelga sobre ``res.company`` lo que ``hr_recruitment`` le añade —
    ≙ ``_inherit``."""
    extend_model('base', 'ResCompany', campos={
        'job_properties_definition': fields.PropertiesDefinition(
            null=True, blank=True,
            help_text='Odoo job_properties_definition ("Job Properties") — '
                      'esquema de propiedades dinámicas de los puestos de '
                      'esta empresa.',
        ),
    })
