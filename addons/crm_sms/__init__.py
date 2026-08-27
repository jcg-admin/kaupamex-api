"""Addon ``crm_sms`` — puente CRM ↔ SMS.

Espejo de ``odoo19c: crm_sms/__init__.py``, que también está vacío: la
referencia NO aporta código Python de modelos (medido por AST sobre sus
``.py``: 0 clases de modelo). Todo su contenido es cliente/seguridad —
``views/crm_lead_views.xml`` (el botón de SMS en el lead),
``security/ir.model.access.csv`` y ``security/sms_security.xml`` — que no
se porta: backend Django REST sin cliente Odoo, y la autorización es de la
capa DRF (DEC-11). La capacidad de fondo (enviar SMS desde un
``crm.lead``) vive en el mixin SMS de ``mail.thread`` del addon ``sms`` de
la referencia, no en este puente.

El addon se porta como marcador del par ``crm`` + ``sms`` (``auto_install``
del manifest), sin ``models/``: crear un directorio de modelos que la
referencia no llena sería fabricar estructura (regla del preámbulo: el
SITIO se lee contra la referencia).
"""
