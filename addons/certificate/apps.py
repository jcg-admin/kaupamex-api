from django.apps import AppConfig


class CertificateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.certificate'
    verbose_name       = 'Certificados (certificate.certificate, certificate.key)'
