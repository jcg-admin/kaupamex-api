"""
signals.py — apps.users

FR-AUTH-01.05: al crear una cuenta nueva (is_active=False),
generar y enviar el token de verificacion de email.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def send_email_verification_on_register(sender, instance, created, **kwargs):
    """
    Envia email de verificacion cuando se crea un usuario nuevo con is_active=False.
    No se envia si el usuario ya esta activo (creado por el admin o superuser).
    """
    if created and not instance.is_active:
        from .tokens_email import create_verification_token, send_verification_email
        plain = create_verification_token(instance)
        send_verification_email(instance, plain)
