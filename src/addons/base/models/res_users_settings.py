"""``res.users.settings`` — preferencias por usuario (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_users_settings.py``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**El contraste con ``res.users.deletion``** es lo que hay que conservar: allí la
FK es ``ondelete='set null'`` y el registro sobrevive al usuario; aquí es
``ondelete='cascade'`` y las preferencias **mueren con él**. Son decisiones
opuestas sobre la misma pregunta, y sólo se ven leyendo los dos archivos.

**Qué campos lleva.** En ``base`` la referencia declara únicamente ``user_id``:
el modelo es el **contenedor**, y cada addon le añade sus preferencias por
``_inherit`` (``bus`` tiene su propio ``res_users_settings.py``). Se porta con
esa forma — un contenedor con la FK— en vez de rellenarlo con campos que
ningún addon nuestro pide todavía. Inventar preferencias aquí sería fabricar
superficie.
"""
import fields
import models

from addons.base.models.mixins import TimeStampedModel


class ResUsersSettings(TimeStampedModel):
    """``res.users.settings`` — contenedor de preferencias de un usuario.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users_settings.py:8-12``.
    """

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE,
        related_name='settings',
        help_text=(
            'Usuario dueño de las preferencias (Odoo user_id, requerido, '
            'ondelete=cascade).'
        ),
    )

    class Meta:
        db_table            = 'res_users_settings'
        verbose_name        = 'Preferencias de usuario'
        verbose_name_plural = 'Preferencias de usuario'
        # La unicidad es una **constraint declarada aparte**, no el tipo del
        # campo — igual que en la referencia, que mantiene ``user_id`` como
        # ``Many2one`` y añade ``_unique_user_id = models.Constraint(
        # 'UNIQUE(user_id)', "One user should only have one user settings.")``
        # (``res_users_settings.py:14-17``). Un ``unique=True`` sobre la FK
        # daría el mismo índice, pero Django avisa (W342) que eso es un
        # ``OneToOneField`` disfrazado — y un OneToOne no es lo que la
        # referencia declara.
        constraints = [
            models.UniqueConstraint(
                fields=['user'], name='res_users_settings_unique_user',
            ),
        ]

    def __str__(self) -> str:
        return f'preferencias de {self.user_id}'
