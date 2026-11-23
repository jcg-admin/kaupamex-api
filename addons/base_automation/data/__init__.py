"""Datos semilla del addon ``base_automation``.

Equivalente nativo de ``base_automation/data/base_automation_data.xml``
(referencia): el cron que corre las automatizaciones basadas en tiempo.
La siembra la aplica ``migrations/0008_seed_cron_check.py`` con
``addons.base.data.sembrar_cron`` (mismo patrón que ``helpdesk``/``loyalty``/
``mail``/``website_sale``). Hasta esa migración el cron sólo existía en las
bases que siembra el fixture de ``tests/conftest.py``
(``designs/cron-xml-id-natural-key.md``).

``digest_data.xml`` (KPI de automatizaciones activas en el panel de
digest) NO se porta — es una integración periférica (UI de reporting), no
un símbolo del modelo ``base.automation``; declarado en el reporte de
retorno, no en un hallazgo de porte parcial de ``base_automation.py``.
"""

#: interval_number/interval_type ≙ el default de la referencia (4 horas);
#: active=False de fábrica (odoo19c: base_automation_data.xml, eval="False")
#: — se activa solo cuando exista >=1 automatización con trigger de tiempo
#: (ver BaseAutomation._update_cron).
CRON_BASE_AUTOMATION_CHECK = {
    'name': 'Automation Rules: check and execute',
    'model_name': 'base.automation',
    'method_name': '_cron_process_time_based_actions',
    'xml_id': 'base_automation.ir_cron_data_base_automation_check',
    'active': False,
    'interval_number': 4,
    'interval_type': 'hours',
    'priority': 5,
}
