# Adaptado de Odoo Community `onboarding/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Onboarding (progreso de configuración)',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'onboarding.onboarding + onboarding.onboarding.step + '
        'onboarding.progress + onboarding.progress.step — el modelo de '
        'progreso; sin el panel web (OWL/QWeb/menus), fuera de scope de la API'
    ),
    # `depends` MEDIDO contra los imports reales de los 4 modelos portados
    # (OnboardingOnboarding, OnboardingOnboardingStep, OnboardingProgress,
    # OnboardingProgressStep), NO copiado de la referencia (que declara sólo
    # `web`: dependencia de UI backend/OWL — este addon no porta
    # `views/onboarding_templates.xml` ni `static/src/**` porque este es un
    # backend Django REST sin cliente web Odoo; no hay a qué adaptar el
    # panel).
    'depends': [
        'base',  # base.ResCompany (FK `company` en Progress/-Step) +
                 # orm.environments.get_current_company (compañía ambiente)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `onboarding` en Odoo Community
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
