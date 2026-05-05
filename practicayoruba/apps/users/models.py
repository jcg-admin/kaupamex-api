import os
from django.contrib.auth.models import AbstractUser
from django.db import models


def avatar_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return os.path.join('profiles', f'user_{instance.pk}_avatar.{ext}')


class User(AbstractUser):
    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        null=True, blank=True
    )
    phone = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'users_user'

    def __str__(self):
        return self.get_full_name() or self.username

    def get_avatar_url(self):
        """Retorna la URL del avatar o None si no tiene."""
        if self.avatar and hasattr(self.avatar, 'url'):
            try:
                return self.avatar.url
            except ValueError:
                return None
        return None
