# Adaptado de Odoo Community `certificate/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Certificados criptográficos',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'certificate.certificate + certificate.key — X.509 y llaves',
    # `depends` MEDIDO contra los imports reales de CertificateCertificate /
    # CertificateKey, no copiado de la referencia (que declara `base_setup`,
    # el addon de ajustes de Settings de Odoo — sin uso en este corte, que no
    # porta vistas).
    'depends': [
        'base',      # TimeStampedModel, ResCompany
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `certificate` en Odoo
    # Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
