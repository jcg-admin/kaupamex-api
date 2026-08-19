"""Datos semilla del addon ``base_automation``.

Equivalente nativo de ``base_automation/data/base_automation_data.xml``
(referencia): el cron que corre las automatizaciones basadas en tiempo.
La siembra la aplica una data-migration con ``addons.base.data.sembrar_cron``
(mismo patrón que ``helpdesk``/``loyalty``/``mail``/``observability``/
``website_sale``) — PENDIENTE en este pase: no se generó
``migrations/0001_initial.py`` (fuera de alcance — "NO makemigrations").
Ver el reporte de retorno para el T-NNN que la cierra.

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
    'model_name': 'base_automation.BaseAutomation',
    'method_name': '_cron_process_time_based_actions',
    'interval_number': 4,
    'interval_type': 'hours',
    'priority': 5,
}
