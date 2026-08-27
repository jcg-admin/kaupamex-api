"""``hr_homeworking`` — trabajo remoto: ubicación por día (Odoo ``Remote Work``).

Adaptación de Odoo ``hr_homeworking`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: cada empleado declara en qué sede (``hr.work.location``: casa,
oficina, otra) trabaja cada día de la semana, y puede registrar una
excepción puntual para una fecha (``hr.employee.location``, el ÚNICO modelo
propio de este addon). El icono de presencia y el nombre/tipo de la
ubicación de trabajo del empleado pasan a derivar de la ubicación del día
en curso (o de su excepción).

Estructura — 1 modelo propio + 5 archivos de extensión:

- ``models/hr_homeworking.py`` — ``DAYS`` + ``hr.employee.location``.
- ``models/hr_employee.py`` / ``hr_employee_public.py`` /
  ``hr_work_location.py`` / ``res_partner.py`` / ``res_users.py`` —
  extensiones (≙ ``_inherit``) aplicadas desde
  ``HrHomeworkingConfig.ready()`` con el patrón
  ``apply_hr_homeworking_<archivo>_extensions()``.

Alta en ``INSTALLED_APPS``: automática — ``LOCAL_APPS`` se deriva del grafo
de manifiestos (``config/settings/base.py:152``, ``_local_apps()``); el
``depends: ['hr', 'base']`` de este addon lo coloca después de ``hr``.

Wiring pendiente (fuera del alcance de este agente): las migraciones — la
tabla ``hr_employee_location`` vive en ESTE addon; las 7 columnas
``<día>_location_id`` que se cuelgan sobre ``hr.employee`` viven en
``hr/migrations/`` (la migración de una columna pertenece a la app dueña
del modelo — mismo criterio que ``account_fleet``). ``makemigrations`` es
del orquestador.
"""
