"""``res.partner`` — estado de mensajería con sufijo de ubicación.

Adaptación de Odoo hr_homeworking/models/res_partner.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 19 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO DECLARADO — 0 de 1 símbolo
============================================

El único símbolo de la referencia, ``_compute_im_status`` (``:10-18``),
decora el ``im_status`` del partner (``online``/``away``/``busy``/
``offline``) con el tipo de ubicación del día
(``home_online``, ``office_busy``, …).

**BLOQUEADO por ``base.ResUsers.im_status``** — medido:
``grep -rn "im_status" src/addons/base/models/res_users.py`` → 0;
``hr/models/hr_employee.py:144-148`` ya lo registra: *"``base.ResUsers``
no declara ``im_status`` — es infraestructura de presencia (``bus``) no
portada aquí. Sucesor: tarea #21 (integración de la familia ``bus``)"*.
Sin ``im_status`` base no hay cadena que sufijar; el símbolo entra con la
tarea #21, encadenado sobre el ``_compute_im_status`` que esa familia
traiga.
"""


def apply_hr_homeworking_res_partner_extensions():
    """No-op declarado — el ``im_status`` destino no existe (ver docstring;
    mismo patrón que ``apply_hr_mail_activity_plan_template_extensions``)."""
    return None
