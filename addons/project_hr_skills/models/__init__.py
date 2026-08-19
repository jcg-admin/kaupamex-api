"""Modelos del addon ``project_hr_skills``.

Sin modelos concretos: las dos piezas (``project_task.py``, ``res_users.py``)
son extensiones sobre modelos ajenos y NO se importan aquí — van por
``apps.py:ready()`` vía ``importlib`` (mismo patrón que
``addons/hr_skills/models/__init__.py``).
"""
