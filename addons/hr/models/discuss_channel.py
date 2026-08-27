"""``discuss.channel`` — auto-suscripción por departamento (Odoo ``hr``).

Adaptación de Odoo hr/models/discuss_channel.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 35 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte BLOQUEADO — 0 de 4 símbolos: el modelo destino no existe
===============================================================

La referencia extiende ``_inherit = 'discuss.channel'`` para que los
miembros de uno o más departamentos queden auto-suscritos a un canal.
Medido en este pase: ``grep -rln "discuss.channel\\|DiscussChannel"
addons/ src/`` → **0 hits** — el addon ``discuss`` (los canales de chat de
la referencia) no está portado; ``addons/mail`` de este árbol cubre
chatter/actividades/correo, no canales.

===========================================================  ==============
Símbolo de la referencia (línea)                             Estado
===========================================================  ==============
``subscription_department_ids`` (M2M a ``hr.department``,    bloqueado
``:12-14``)
``_constraint_subscription_department_ids_channel``          bloqueado
(``:16-20``)
``_subscribe_users_automatically_get_members`` (``:22-31``)  bloqueado
``write`` (``:33-35``)                                       bloqueado
===========================================================  ==============

Los cuatro símbolos dependen del MISMO ausente — la clase
``discuss.channel`` con su ``channel_type``, ``channel_partner_ids`` y el
mecanismo ``_subscribe_users_automatically`` — así que no hay mitad
portable: sin canal no hay a qué suscribir. Además, dos de ellos consumen
piezas de ``hr`` que también están deferidas (``hr.department.member_ids``
llega vía el gerente/miembros deferidos en ``hr_department.py``).

Sucesor: el porte del addon ``discuss`` (o del subconjunto de canales de
``mail``) es una iniciativa propia — DESCONOCIDO con condición de cierre:
este archivo se completa cuando exista una clase de canal con miembros
suscribibles en ``addons/``; hasta entonces la extensión es un no-op
declarado, mismo patrón que ``product_expiry/models/res_config_settings.py``.
"""


def apply_hr_discuss_channel_extensions():
    """No-op declarado — ver el docstring del módulo (``discuss.channel``
    ausente)."""
    return None


__all__ = ['apply_hr_discuss_channel_extensions']
