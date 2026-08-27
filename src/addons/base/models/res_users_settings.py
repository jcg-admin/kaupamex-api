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

from addons.base.models.timestamped_mixin import TimeStampedModel


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

    #: ≙ las *magic columns* de la referencia (``id``, ``create_uid``,
    #: ``create_date``, ``write_uid``, ``write_date``): las que el formato por
    #: defecto nunca incluye salvo que se pidan. Aquí el log-access son dos
    #: —``created_at`` y ``updated_at``, ver ``TimeStampedModel``— y los dos
    #: ``*_uid`` no existen (DEC-09: la autoría se difiere a la capa ``orm``).
    AUDIT_COLUMNS = ('created_at', 'updated_at')

    @classmethod
    def _get_fields_blacklist(cls):
        """≙ ``_get_fields_blacklist`` (``odoo19c: :20-23``).

        Docstring de la fuente: *"Get list of fields that won't be
        formatted."* Se porta su valor **verbatim**: ``display_name`` no es
        una columna de este modelo, pero el enganche existe para que un addon
        que sí la añada la excluya, y cambiar el valor por una lista vacía
        borraría esa intención sin ganar nada.
        """
        return ['display_name']

    @classmethod
    def _find_or_create_for_user(cls, user):
        """≙ ``_find_or_create_for_user`` (``:25-29``).

        La fuente lo hace en dos pasos —leer la inversa, crear si viene
        vacía— con ``sudo()`` para saltarse las reglas de fila. Aquí es un
        ``get_or_create``, que además cierra la carrera entre dos peticiones
        del mismo usuario: la constraint ``UNIQUE(user)`` la arbitra la base,
        no el código.
        """
        settings, _created = cls.objects.get_or_create(user=user)
        return settings

    def _res_users_settings_format(self, fields_to_format=None):
        """≙ ``_res_users_settings_format`` (``:31-39``).

        Decide **qué** se formatea y delega el **cómo** en
        ``_format_settings``. Sin lista explícita toma ``id`` más cada campo
        que no sea de auditoría ni esté en la lista negra; con lista explícita
        respeta la petición y sólo aplica la lista negra.

        El recorrido es ``_meta.get_fields()``, no ``_meta.concrete_fields``:
        la fuente enumera ``self._fields``, que **incluye los One2many**, y
        aquí un One2many es el reverso de un ``ForeignKey`` declarado por el
        addon hijo (``orm/fields_relational.py``). Con ``concrete_fields`` el
        formato por defecto era ciego justo a lo que cada addon aporta —
        ``embedded_actions_config_ids`` de ``web`` no aparecía nunca.
        """
        blacklist = self._get_fields_blacklist()
        if fields_to_format:
            fields_to_format = [f for f in fields_to_format if f not in blacklist]
        else:
            fields_to_format = ['id'] + [
                f.name for f in self._meta.get_fields()
                if f.name not in self.AUDIT_COLUMNS and f.name not in blacklist
                and f.name != 'id'
            ]
        return self._format_settings(fields_to_format)

    def _format_settings(self, fields_to_format):
        """≙ ``_format_settings`` (``:41-45``) — el enganche.

        Enterprise 19 lo extiende en dos clases con
        ``_inherit = 'res.users.settings'``: es por aquí por donde un addon
        cambia la forma de un valor sin tocar la selección de campos.

        Dos divergencias de nombre, las dos por el sustrato:

        - la fuente devuelve la FK bajo la clave ``user_id`` porque así se
          llama su campo; aquí el campo es ``user`` y la clave es ``user``.
          El **contenido** es el mismo: ``{'id': <pk>}``, no el registro
          entero.
        - la fuente lee con ``_read_format``, el serializador del ORM. Aquí
          no existe: se leen los atributos del modelo, que es lo que ese
          método hace del otro lado. Para un **reverso de FK** —el One2many
          de la fuente— ``_read_format`` devuelve la lista de ids, y eso es
          lo que devuelve la rama ``reverse``: ``values_list('pk')``, no el
          ``RelatedManager``, que no es serializable.
        """
        reverse = {f.name for f in self._meta.get_fields() if not f.concrete}
        values = {}
        for name in fields_to_format:
            if name == 'id':
                values['id'] = self.pk
            elif name == 'user':
                values['user'] = {'id': self.user_id}
            elif name in reverse:
                values[name] = list(
                    getattr(self, name).values_list('pk', flat=True))
            else:
                values[name] = getattr(self, name)
        return values

    def set_res_users_settings(self, new_settings):
        """≙ ``set_res_users_settings`` (``:47-55``).

        Escribe **sólo lo que cambia** y devuelve el diff formateado más el
        ``id``. Un valor igual al que ya está no entra en el diff, que es lo
        que permite al cliente saber qué se movió de verdad.
        """
        changed = {
            name: value for name, value in new_settings.items()
            if any(f.name == name for f in self._meta.concrete_fields)
            and getattr(self, name) != value
        }
        for name, value in changed.items():
            setattr(self, name, value)
        if changed:
            self.save(update_fields=list(changed))
        return self._res_users_settings_format([*changed, 'id'])
