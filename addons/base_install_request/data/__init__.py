"""Semilla de la plantilla de correo de ``base_install_request``.

Adaptación de ``odoo19c: addons/base_install_request/data/mail_template_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03). El dato vive aquí y la migración lo escribe, que es el idioma ya
fijado por ``addons/authz_signup/data.py`` + su migración de semilla.

Divergencia declarada — el cuerpo se escribe en plantilla de Django
====================================================================

La fuente redacta el cuerpo en QWeb (``t-out``, ``t-attf-href``) y este árbol
no tiene motor QWeb: ``MailTemplate._render_str``
(``addons/mail/models/mail_template.py:96``) compone con el motor de Django. Se
conserva **el texto y su estructura**; cambia sólo la sintaxis de
interpolación, que es el mecanismo. Las dos formas de la fuente se traducen
así:

===============================  ====================================
QWeb de la fuente                Aquí
===============================  ====================================
``t-out="object.user_id.name"``  ``{{ object.user_id.name }}``
``{{ object.module_id.shortdesc }}``  igual — la fuente ya usa esa forma
===============================  ====================================

El enlace *Review Request* de la fuente apunta a una ruta del cliente web de
Odoo (``/odoo/<id>/action-…?menu_id=…``). Aquí no hay ese cliente, así que el
enlace se omite del cuerpo y el ``menu_id`` viaja igual en el contexto de
render — el dato se conserva aunque su consumidor no exista todavía.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelData
from addons.mail.models import MailTemplate

#: ≙ ``id="mail_template_base_install_request"`` del ``<record>``, con su
#: módulo. Es la clave con la que ``action_send_request`` la resuelve, igual
#: que la fuente la resuelve con ``env.ref``.
INSTALL_REQUEST_TEMPLATE_XMLID = 'mail_template_base_install_request'
INSTALL_REQUEST_TEMPLATE_MODULE = 'base_install_request'

#: ≙ el ``<record model="mail.template">`` entero, campo a campo.
INSTALL_REQUEST_TEMPLATE = {
    'name': 'Mail: Install Request',
    # ≙ ``model_id ref="…model_base_module_install_request"``: allá es un FK a
    # ``ir.model``, aquí ``MailTemplate.model`` guarda el ``_name`` en texto
    # (``addons/mail/models/mail_template.py:34``).
    'model': 'base.module.install.request',
    'partner_to': '{{ ctx_partner_id }}',
    'use_default_to': False,
    'auto_delete': True,
    'subject': ('Module Activation Request for '
                '"{{ object.module_id.shortdesc }}"'),
    'email_from': '{{ object.user_id.email }}',
    'body_html': (
        '<div style="margin: 0px; padding: 0px;">\n'
        '    <p style="margin: 0px; padding: 0px; font-size: 13px;">\n'
        '        Hello,\n'
        '        <br/><br/>\n'
        '        <span style="font-weight: bold;">'
        '{{ object.user_id.name }}</span> has requested to activate the '
        '<span style="font-weight: bold;">'
        '{{ object.module_id.shortdesc }}</span> module.\n'
        '        <br/><br/>\n'
        '        <blockquote>{{ object.body_html }}</blockquote>\n'
        '        <br/><br/>\n'
        '        Thanks,\n'
        '        <br/><br/>\n'
        '    </p>\n'
        '</div>'
    ),
}


#: El ``model`` que la fila de ``ir.model.data`` guarda: la etiqueta Django del
#: destino, la misma que escribe la migracion de siembra.
INSTALL_REQUEST_TEMPLATE_MODEL_LABEL = 'mail.MailTemplate'


def seed(using=DEFAULT_DB_ALIAS):
    """Re-aplica la plantilla y su identificador externo. Idempotente.

    Equivalente vivo de ``migrations/0002_seed_install_request_mail_template``,
    y por la misma razon que el resto del catalogo de ``tests/conftest.py``: un
    test ``django_db(transaction=True)`` hace ``flush`` de las tablas de modelo
    y ``django_migrations`` no lo es, asi que la siembra queda registrada como
    aplicada sobre una tabla vacia y nunca vuelve a correr. Es H-API-22, y
    ``base_install_request`` entro a la red sin su seeder.
    """
    plantilla = MailTemplate.objects.using(using).filter(
        name=INSTALL_REQUEST_TEMPLATE['name']).first()
    if plantilla is None:
        plantilla = MailTemplate.objects.using(using).create(
            **INSTALL_REQUEST_TEMPLATE)

    IrModelData.objects.using(using).get_or_create(
        module=INSTALL_REQUEST_TEMPLATE_MODULE,
        name=INSTALL_REQUEST_TEMPLATE_XMLID,
        defaults={
            'model': INSTALL_REQUEST_TEMPLATE_MODEL_LABEL,
            'res_id': plantilla.pk,
            'noupdate': True,
        },
    )
