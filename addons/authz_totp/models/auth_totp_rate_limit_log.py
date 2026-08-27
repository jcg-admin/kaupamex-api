"""``auth.totp.rate.limit.log`` — el registro que cuenta los intentos de 2FA.

Adaptación de Odoo ``auth_totp/models/auth_totp_rate_limit_log.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Es la tabla sobre la que se apoyan ``_totp_rate_limit`` y
``_totp_rate_limit_purge`` (``res_users.py``). Sin ella los dos métodos no se
pueden portar, y sin ellos el segundo factor **no tiene freno**: quien conoce
la contraseña puede probar códigos de seis dígitos sin límite, y también puede
pedir correos de código sin límite. Ése es el hueco que este archivo cierra.

Divergencia declarada — la clase base
======================================

La fuente lo declara ``models.TransientModel``, es decir una tabla real que
``ir.autovacuum`` barre periódicamente vía ``_transient_vacuum``
(``odoo19c: odoo/orm/models_transient.py:30``).

Aquí ``TransientModel`` declara ``class Meta: managed = False``
(``src/orm/models_transient.py``): **no crea tabla**. Un limitador cuyo
almacén no existe no limita nada — la cuenta daría siempre cero y la guarda
pasaría siempre, que es el «verde que no discrimina» del sub-patrón D de
``metrica-decide-la-conclusion.md``. Por eso el porte es un modelo **real**
sobre ``TimeStampedModel``, y el barrido que la fuente hereda de su base se
declara aquí como ``_gc_rate_limit_log``.

Los tres atributos de clase que la fuente declara se portan verbatim
(``atributos-de-clase-de-modelo.md``): ``_name``, ``_description`` y su objeto
de tabla ``_user_id_limit_type_create_date_idx``, cuyo hogar es
``Meta.indexes``.

Divergencia declarada — el NOMBRE del índice
=============================================

La regla manda conservar el nombre del objeto de tabla, y aquí no se puede:
``auth_totp_rate_limit_log_user_id_limit_type_create_date_idx`` mide **59**
caracteres y ``django.db.models.Index.max_name_length`` vale **30** (medido en
este árbol). Con el nombre de la fuente, ``manage.py migrate`` aborta con
``models.E034`` antes de tocar la base — el mismo desenlace que
:func:`addons.base.models.res_users.index_name_for` documenta para las tablas
de claves. Se acorta a ``authz_totp_rate_limit_idx`` (25) conservando las tres
columnas y su orden, que es lo que el índice hace.

Los otros dos renombres son de stack, no de contenido: ``user_id`` es ``user``
—la FK de Django, igual que en ``totp_secret.py`` y ``auth_totp.py``— y
``create_date`` es el ``created_at`` de ``TimeStampedModel``.
"""
import logging
from datetime import timedelta

from django.utils import timezone

import api
import fields
import models

from addons.base.models import TimeStampedModel

_logger = logging.getLogger(__name__)

#: ≙ los dos valores del ``Selection`` de la fuente (``:12-15``), verbatim.
LIMIT_TYPES = [
    ('send_email', 'Send Email'),
    ('code_check', 'Code Checking'),
]

#: Piso del barrido, verbatim de ``_transient_clean_rows_older_than``
#: (``odoo19c: odoo/orm/models_transient.py:76``): *"Never delete rows used in
#: last 5 minutes"*. Aquí además es una garantía del limitador — borrar una
#: fila dentro del intervalo vigente sería regalarle un intento al atacante.
GC_FLOOR_SECONDS = 300

#: Edad a partir de la cual una fila se barre. ≙ ``_transient_max_hours``, que
#: la fuente resuelve con la opción ``transient_age_limit`` de su configuración
#: (``odoo19c: odoo/orm/models_transient.py:26``), cuyo valor por omisión es
#: **1.0 h**. Que coincida con los 3600 s de ``TOTP_RATE_LIMITS`` no es
#: casualidad ni se puede dar por hecho: ``res_users.py`` lo **verifica** al
#: importar, porque un barrido más corto que el intervalo le devolvería al
#: atacante los intentos que ya gastó.
GC_MAX_AGE_SECONDS = 3600


class AuthTotpRateLimitLog(TimeStampedModel):
    """``auth.totp.rate.limit.log`` — ≙ ``AuthTotpRateLimitLog`` (``:4-15``)."""

    _name = 'auth.totp.rate.limit.log'
    _description = 'TOTP rate limit logs'

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='totp_rate_limit_logs', verbose_name='Usuario',
        help_text=(
            'Odoo user_id (required, readonly) — de quién es el intento que '
            'se cuenta. El readonly de la fuente es de su capa de vista y no '
            'tiene receptor en el modelo Django.'
        ),
    )
    ip = fields.Char(
        max_length=45, blank=True, default='', verbose_name='IP',
        help_text=(
            'Odoo ip — forense. La fuente lo lee de su petición global '
            '(request.httprequest.environ["REMOTE_ADDR"]); aquí llega como '
            'argumento de _totp_rate_limit, que puede no tenerlo. Ningún '
            'consumidor lo lee: medido sobre odoo19c, los dos únicos '
            'consumidores del modelo son escribir y borrar.'
        ),
    )
    limit_type = fields.Selection(
        max_length=16, choices=LIMIT_TYPES, verbose_name='Tipo de límite',
        help_text='Odoo limit_type — qué acción se está contando.',
    )

    class Meta:
        db_table = 'auth_totp_rate_limit_log'
        ordering = ['-id']
        verbose_name = 'Intento 2FA contado'
        verbose_name_plural = 'Intentos 2FA contados'
        indexes = [
            # ≙ ``_user_id_limit_type_create_date_idx`` (``:8``). Mismas tres
            # columnas y mismo orden; el nombre se acorta por el límite de
            # Django (ver la cabecera del módulo).
            models.Index(fields=['user', 'limit_type', 'created_at'],
                         name='authz_totp_rate_limit_idx'),
        ]

    def __str__(self):
        return f'RateLimitLog[{self.user_id}] {self.limit_type}'

    @classmethod
    @api.autovacuum
    def _gc_rate_limit_log(cls):
        """Barre las filas que ya no cuentan para ningún intervalo.

        Ocupa el lugar de ``_transient_vacuum``, que la fuente **hereda** de
        ``TransientModel`` y que este árbol no puede proveer (ver la cabecera).
        El decorador es el mismo mecanismo: ``ir.autovacuum`` recorre los
        métodos marcados desde su único cron.

        El corte es ``GC_MAX_AGE_SECONDS`` con el piso de
        ``GC_FLOOR_SECONDS``: una fila dentro de su propio intervalo todavía es
        evidencia de un intento, y borrarla le devolvería el intento a quien lo
        gastó. Que el corte cubra el intervalo más largo lo verifica
        ``res_users.py`` al importar, que es quien conoce los dos.
        """
        corte = timezone.now() - timedelta(
            seconds=max(GC_MAX_AGE_SECONDS, GC_FLOOR_SECONDS))
        borradas, _resto = cls.objects.filter(created_at__lt=corte).delete()
        _logger.info('GC TOTP rate limit log delete %d entries', borradas)
