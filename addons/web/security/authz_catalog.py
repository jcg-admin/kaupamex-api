"""Declaración del catálogo L0 que dueña ``web`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

Por qué estos códigos son de este addon: ``web`` dueña el streaming y la
subida de binarios genéricos (``controllers/binary.py``, H-API-369/DEC-FW-04)
— mismo criterio que ``base/authz_catalog.py`` (el addon que declara la vista
declara también sus derechos de acceso, análogo a
``<addon>/security/ir.model.access.csv`` en la referencia).

Sin esta declaración, ``content_common``/``content_image``/
``upload_attachment`` quedan gateadas por códigos que ningún rol —ni
``superadmin``— puede tener nunca (``seed_authz`` sólo otorga las capacidades
que ``discover()`` recolecta): las rutas resolverían, pero todo request
devolvería 403 sin excepción. Ambas capacidades son deliberadamente amplias
(leen/escriben sobre cualquier modelo con ``res_id`` válido, sin ACL por
registro — ver divergencia 3 del docstring de ``binary.py``), de ahí
``is_sensitive=True``: mismo criterio que ``platform.provision``/``users``/
``settings``.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='web', name='Cliente web', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(
        code='web.content.view',
        name='Ver el contenido binario de cualquier registro',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='web.attachment.create',
        name='Subir adjuntos vinculados a un registro',
        is_sensitive=True,
    ),
]
