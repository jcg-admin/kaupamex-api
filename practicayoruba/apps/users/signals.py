"""
signals.py — apps.users

FR-AUTH-01.05: al crear una cuenta nueva (is_active=False),
generar y enviar el token de verificacion de email.

NOTA: El envio del email se difiere a post-commit para evitar
deadlocks en transacciones de test con MySQL.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def send_email_verification_on_register(sender, instance, created, **kwargs):
    """
    Envia email de verificacion cuando se crea un usuario nuevo con is_active=False.
    El envio se diferire a post-commit para no interferir con la transaccion activa.
    """
    if created and not instance.is_active:
        user_id = instance.pk

        def _send():
            from .models import User as U
            from .tokens_email import create_verification_token, send_verification_email
            try:
                user = U.objects.get(pk=user_id)
                plain = create_verification_token(user)
                send_verification_email(user, plain)
            except U.DoesNotExist:
                pass

        transaction.on_commit(_send)
