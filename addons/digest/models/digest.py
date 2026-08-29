"""``digest.digest`` — un digest periódico de KPIs enviado por correo (Odoo
``digest``).

Adaptación de Odoo digest/models/digest.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias declaradas
========================

1. **``currency_id``/``company_id`` no son ``related=``/``default=lambda
   self: ...`` resueltos en tiempo de lectura por el ORM.** ``company_id`` es
   una columna real con ``default=get_current_company`` (el análogo de
   ``env.company.id`` — ``orm.environments``, mismo mecanismo ya usado por
   ``CompanySetting``); ``currency`` se expone como ``@property`` de sólo
   lectura que delega a ``self.company_id.currency`` — mismo patrón de
   passthrough usado en ``fleet_vehicle_log_services.py`` (``self.vehicle.
   model.brand``, sin denormalizar).

2. **``is_subscribed`` no depende implícitamente de ``self.env.user``.** Se
   expone como ``@property`` que llama ``get_current_user()``
   (``orm.environments`` — el análogo de ``env.user``); ``action_subscribe``/
   ``action_unsubscribe`` hacen lo mismo. Sin un usuario "actual" en contexto
   (fuera de una request autenticada), ambos devuelven ``False``/no-op — fail
   closed, no fail silent con un usuario arbitrario.

3. **``available_fields`` se computa por introspección de Django
   (``self._meta.get_fields()``), no de ``self._fields.items()`` de Odoo** —
   mismo mecanismo (detectar columnas ``Boolean`` con prefijo ``kpi_``
   activadas en la instancia), adaptado al framework. Sólo el addon dueño de
   una columna puede declararla (Django no distribuye esquema entre apps
   como el ``_inherit`` de Odoo — ver ``resource/models/res_company.py`` para
   el mismo límite ya documentado); un futuro addon que agregue un KPI nuevo
   declara su propia migración con una columna ``kpi_<nombre>`` y esta
   introspección la recoge sin tocar este archivo.

4. **Los dos KPIs base escalan por compañía vía ``company_id.user_ids``/
   ``author__in``, no por el ``_calculate_company_based_kpi`` genérico de la
   referencia** (que combina el conjunto de compañías visibles del usuario
   con ``env.company`` cuando el digest no tiene compañía). Ninguno de los
   dos modelos fuente (``ResUsersLog``, ``MailMessage``) tiene una FK directa
   a compañía — la companía se deriva vía el usuario. Documentado como
   reducción de alcance, no como incapacidad: el álgebra de conjuntos es
   idéntica, sólo cambia el camino de un salto adicional.

5. **La aritmética de mes/trimestre usa ``_add_months``
   (``addons.base.models.ir_cron``, ya portada) en vez de
   ``dateutil.relativedelta``** — ``dateutil`` no es dependencia del
   proyecto (mismo criterio que ``resource_calendar_leaves.py`` y
   ``certificate.py``).

6. **``_onchange_periodicity`` no se porta** — es un ``@api.onchange`` de
   formulario Odoo (recalcula mientras el usuario edita, antes de guardar);
   sin vistas XML no hay onchange que disparar. El efecto equivalente
   (recalcular ``next_run_date`` al cambiar la periodicidad) se logra
   llamando ``action_set_periodicity``, que sí persiste.

7. **El envío queda PENDIENTE DE INTEGRAR, no diferido por alcance** —
   ``action_send``/``action_send_manual``/``_action_send``/
   ``_action_send_to_user``/``_cron_send_digest_email``/
   ``_get_unsubscribe_token``/``_compute_tips``/``_compute_kpis_actions``/
   ``_compute_preferences``/``_check_daily_logs``/``_format_currency_amount``
   (los ~230 LOC de ``digest.py:130-484`` que no aparecen abajo).

   La redacción previa lo llamaba "gap de alcance" y era falsa en su mitad
   principal: **tres de las cuatro piezas del envío ya existen** (H-API-302,
   medido pieza por pieza contra ``_action_send`` de la referencia):

   - ``mail.render.mixin._render_template`` → **``MailTemplate.render()``**
     (``addons/mail/models/mail_template.py:102``), que renderiza con
     plantillas Django y la **misma sintaxis** ``{{ object.campo }}`` — su
     propio docstring lo declara. No hay que construirlo.
   - ``mail.mail.create(...)`` → ``MailMail``.
   - drenaje de la cola → ``mail/management/commands/send_pending_emails``.
   - ``_render_encapsulate`` (envolver el cuerpo en un layout) es
     **composición de plantilla**, no una capacidad ausente.

   Lo que sí falta es **un ejecutor de ``ir.cron``**: el modelo existe
   (``base/models/ir_cron.py``) pero ningún management command del árbol
   despacha los vencidos. Ese hueco es **transversal** —bloquea igual el
   cron de expiración de ``fleet``—, no propio de este addon, y la forma
   que use la referencia (un hilo del servidor) no existe aquí: hay que
   decidirla.

   Por eso el trabajo que falta se llama **integrar la familia ``mail``**,
   no "construir el motor de envío". Lo que SÍ se porta aquí es el **motor
   de cómputo** (KPIs + periodicidad + suscripción), consumible tal cual por
   ese cableado sin reabrir este archivo.

8. **``ensure_one()`` no aplica** — Django no tiene recordsets; cada método
   opera sobre una única instancia.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

import fields
import models
from exceptions import ValidationError

from addons.base.models import ResUsersLog, TimeStampedModel
from addons.base.models.ir_cron import _add_months
from addons.mail.models import MailMessage
from orm import registry
from orm.environments import get_current_company, get_current_user


class DigestPeriodicity(models.TextChoices):
    """``periodicity`` — cada cuánto se recalcula/envía el digest
    (``digest.py:28-32``)."""

    DAILY = 'daily', 'Diaria'
    WEEKLY = 'weekly', 'Semanal'
    MONTHLY = 'monthly', 'Mensual'
    QUARTERLY = 'quarterly', 'Trimestral'


class DigestState(models.TextChoices):
    """``state`` — activado/desactivado (``digest.py:38``)."""

    ACTIVATED = 'activated', 'Activado'
    DEACTIVATED = 'deactivated', 'Desactivado'


class DigestDigest(TimeStampedModel):
    """``digest.digest`` — un digest de KPIs con su lista de destinatarios.

    Motor portado: suscripción, periodicidad/``next_run_date``, y cómputo de
    KPIs (valor + margen vs. periodo anterior) para 3 ventanas de tiempo
    (24 h / 7 días / 30 días). El envío por correo queda pendiente de
    **cablear** a la familia ``mail`` (que ya tiene render, cola y drenaje),
    no de construir — ver divergencia 7 del módulo.
    """

    name = fields.Char(
        max_length=255,
        help_text='Odoo name (required, translate) — nombre del digest.',
    )
    user_ids = fields.Many2many(
        'base.ResUsers', blank=True, related_name='digests',
        verbose_name='Destinatarios',
        help_text=(
            'Odoo user_ids (domain share=False en la referencia — no '
            'enforced a nivel de columna, ver action_subscribe).'
        ),
    )
    periodicity = fields.Selection(
        max_length=10, choices=DigestPeriodicity.choices,
        default=DigestPeriodicity.DAILY, verbose_name='Periodicidad',
    )
    next_run_date = fields.Date(
        null=True, blank=True, verbose_name='Próximo envío',
        help_text='Se calcula en save() si no se da explícitamente (Odoo create()).',
    )
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='digests', default=get_current_company,
        verbose_name='Compañía',
        help_text='Odoo company_id (default=env.company.id → get_current_company()).',
        db_column='company_id',
    )
    state = fields.Selection(
        max_length=12, choices=DigestState.choices,
        default=DigestState.ACTIVATED, verbose_name='Estado',
    )
    kpi_res_users_connected = fields.Boolean(
        default=False, verbose_name='Usuarios conectados',
        help_text='KPI base: cuenta filas de ResUsersLog (accesos) en el periodo.',
    )
    kpi_mail_message_total = fields.Boolean(
        default=False, verbose_name='Mensajes enviados',
        help_text='KPI base: cuenta MailMessage creados en el periodo.',
    )

    class Meta:
        db_table = 'digest_digest'
        ordering = ['-id']
        verbose_name = 'Digest'
        verbose_name_plural = 'Digests'

    def __str__(self) -> str:
        return self.name

    @property
    def currency(self):
        """≙ ``currency_id`` (``related="company_id.currency_id"``,
        ``digest.py:34``). Divergencia 1: propiedad de sólo lectura, sin
        columna — passthrough a ``self.company_id.currency``."""
        return self.company_id.currency if self.company_id else None

    def save(self, *args, **kwargs):
        """Calcula ``next_run_date`` al crear si no se dio explícitamente —
        equivalente al ``create()`` override de la referencia
        (``digest.py:91-97``): ahí se resuelve en un segundo save tras el
        primero (necesita el registro creado); aquí no hace falta —
        ``_get_next_run_date`` sólo depende de ``self.periodicity``, así
        que se resuelve ANTES del único ``save()``."""
        if self.pk is None and not self.next_run_date:
            self.next_run_date = self._get_next_run_date()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------
    # SUSCRIPCIÓN
    # ------------------------------------------------------------

    @property
    def is_subscribed(self):
        """≙ ``_compute_is_subscribed`` (``digest.py:45-48``): ``self.env.user
        in digest.user_ids`` → ``get_current_user()`` en vez de ``env.user``
        (divergencia 2)."""
        user = get_current_user()
        return user is not None and self.pk is not None and (
            self.user_ids.filter(pk=user.pk).exists()
        )

    def action_subscribe(self):
        """≙ ``digest.py:103-105``: sólo usuarios internos (``not share``)
        pueden auto-suscribirse."""
        user = get_current_user()
        if user is not None and not user.share:
            self._action_subscribe_users(user)

    def _action_subscribe_users(self, users):
        """≙ ``digest.py:107-110``."""
        self.user_ids.add(users)

    def action_unsubscribe(self):
        """≙ ``digest.py:112-114``."""
        user = get_current_user()
        if user is not None and not user.share:
            self._action_unsubscribe_users(user)

    def _action_unsubscribe_users(self, users):
        """≙ ``digest.py:116-119``."""
        self.user_ids.remove(users)

    # ------------------------------------------------------------
    # ACTIONS — estado y periodicidad
    # ------------------------------------------------------------

    def action_activate(self):
        """≙ ``digest.py:121-122``."""
        self.state = DigestState.ACTIVATED
        self.save(update_fields=['state', 'updated_at'])

    def action_deactivate(self):
        """≙ ``digest.py:124-125``."""
        self.state = DigestState.DEACTIVATED
        self.save(update_fields=['state', 'updated_at'])

    def action_set_periodicity(self, periodicity):
        """≙ ``digest.py:127-129``. Recalcula ``next_run_date`` (reemplaza el
        onchange de formulario que la referencia dispara vía UI — divergencia 6)."""
        if periodicity not in DigestPeriodicity.values:
            raise ValidationError(
                f'periodicity inválida: {periodicity!r} '
                f'(esperado uno de {DigestPeriodicity.values})'
            )
        self.periodicity = periodicity
        self.next_run_date = self._get_next_run_date()
        self.save(update_fields=['periodicity', 'next_run_date', 'updated_at'])

    def _get_next_run_date(self):
        """≙ ``_get_next_run_date`` (``digest.py:367-377``). Divergencia 5:
        ``_add_months`` de stdlib en vez de ``dateutil.relativedelta``.

        ``localdate()``, no ``timezone.now().date()``: la referencia usa
        ``date.today()`` —la fecha **local** del despliegue— y reserva
        ``datetime.utcnow()`` para las ventanas de KPI
        (``digest.py:380``). Es una separación deliberada: la ventana mide
        tiempo absoluto, la agenda es de calendario. Con ``USE_TZ`` y
        ``TIME_ZONE='America/Mexico_City'``, el equivalente fiel de
        ``date.today()`` es ``timezone.localdate()``; la fecha UTC adelanta
        un día entre las 18:00 y la medianoche locales. Ver H-API-303.
        """
        today = timezone.localdate()
        if self.periodicity == DigestPeriodicity.DAILY:
            return today + timedelta(days=1)
        if self.periodicity == DigestPeriodicity.WEEKLY:
            return today + timedelta(weeks=1)
        if self.periodicity == DigestPeriodicity.MONTHLY:
            return _add_months(today, 1)
        return _add_months(today, 3)  # quarterly

    def _get_next_periodicity(self):
        """≙ ``_get_next_periodicity`` (``digest.py:473-478``) — usado por el
        slowdown de ``_check_daily_logs`` en la referencia (DEFERIDO aquí,
        divergencia 7); se conserva porque es pura y barata de mantener."""
        if self.periodicity == DigestPeriodicity.DAILY:
            return DigestPeriodicity.WEEKLY
        if self.periodicity == DigestPeriodicity.WEEKLY:
            return DigestPeriodicity.MONTHLY
        return DigestPeriodicity.QUARTERLY

    # ------------------------------------------------------------
    # KPIS — el motor de cómputo (mecanismo pedido por el encargo)
    # ------------------------------------------------------------

    def _get_kpi_field_names(self):
        """≙ ``_get_kpi_fields`` (``digest.py:440-443``): columnas ``Boolean``
        con prefijo ``kpi_`` activadas en esta instancia. Divergencia 3:
        introspección de Django (``self._meta.fields`` — sólo columnas
        concretas propias, no relaciones inversas de otros modelos) en vez
        de ``self._fields.items()`` de Odoo."""
        return [
            f.name for f in self._meta.fields
            if f.get_internal_type() == 'BooleanField'
            and f.name.startswith('kpi_')
            and getattr(self, f.name)
        ]

    @property
    def available_fields(self):
        """≙ ``_compute_available_fields`` (``digest.py:50-56``)."""
        return ', '.join(f'{name}_value' for name in self._get_kpi_field_names())

    def _compute_timeframes(self):
        """≙ ``_compute_timeframes`` (``digest.py:379-395``). Divergencia 1
        (de facto): no busca la zona horaria de ``company.resource_calendar_id``
        (la referencia sí) — ``ResCompany`` de este proyecto no tiene esa
        columna (``resource`` la expone como propiedad calculada, no un FK
        directo en ``base``); se usa ``timezone.now()`` (UTC-aware, Django
        ``USE_TZ=True``). Divergencia 5 para el salto de -1/-2 meses."""
        now = timezone.now()
        return [
            ('Últimas 24 horas', (
                (now - timedelta(days=1), now),
                (now - timedelta(days=2), now - timedelta(days=1)),
            )),
            ('Últimos 7 días', (
                (now - timedelta(weeks=1), now),
                (now - timedelta(weeks=2), now - timedelta(weeks=1)),
            )),
            ('Últimos 30 días', (
                (_add_months(now, -1), now),
                (_add_months(now, -2), _add_months(now, -1)),
            )),
        ]

    def _compute_kpi_res_users_connected_value(self, start, end):
        """≙ ``_compute_kpi_res_users_connected_value`` (``digest.py:71-76``,
        delega en ``_calculate_company_based_kpi`` con ``date_field=
        'login_date'``). Divergencia 4: ``ResUsersLog`` no tiene FK a
        compañía — se filtra por ``user__in company_id.user_ids``."""
        qs = ResUsersLog.objects.filter(created_at__gte=start, created_at__lt=end)
        if self.company_id:
            qs = qs.filter(user__in=self.company_id.user_ids.all())
        return qs.count()

    def _compute_kpi_mail_message_total_value(self, start, end):
        """≙ ``_compute_kpi_mail_message_total_value`` (``digest.py:78-85``).
        Divergencia 4: sin el filtro de ``subtype_id=mail.mt_comment`` (sin
        fixture XML estable — mismo criterio que ``fleet``/``certificate``
        para external IDs ausentes); cuenta todo ``MailMessage`` del rango,
        acotado por compañía vía el autor."""
        qs = MailMessage.objects.filter(created_at__gte=start, created_at__lt=end)
        if self.company_id:
            qs = qs.filter(author__in=self.company_id.user_ids.all())
        return qs.count()

    def _get_company_field(self, model):
        """≙ ``_get_company_field`` (``digest.py:437-438``).

        Devuelve el nombre del campo por el que ese modelo se acota a empresa.
        ``res.users`` usa el plural porque su pertenencia es múltiple; el resto,
        el singular. Verbatim de la fuente, con el nombre de modelo de este
        árbol (``_name``, no la etiqueta de Django).
        """
        return 'company_ids' if model in ['res.users'] else 'company_id'

    def _calculate_company_based_kpi(self, model, start, end,
                                     date_field='created_at',
                                     additional_domain=None, sum_field=None):
        """≙ ``_calculate_company_based_kpi`` (``digest.py:401-435``).

        Cuenta (o suma ``sum_field``) los registros de ``model`` en la ventana,
        acotados a la empresa del digest. Es el genérico que la referencia usa
        para todo KPI cuyo modelo tenga campo de empresa.

        Tres divergencias de FORMA, ninguna de alcance:

        1. **Devuelve el valor**; la fuente lo escribe en ``digest[campo]``. Es
           la forma que este archivo ya establece para sus dos KPIs base y que
           ``compute_kpi_value`` espera.
        2. **``start``/``end`` llegan por parámetro** en vez de salir de
           ``_get_kpi_compute_parameters``: aquí la ventana la reparte
           ``compute_kpis`` desde ``_compute_timeframes``, que es el mismo
           dato calculado una vez para las tres columnas.
        3. **``date_field`` por defecto es ``created_at``**, el nombre de la
           columna de auditoría de este árbol (la fuente dice ``create_date``).
        4. **``additional_domain`` es un dict de lookups de Django**, no una
           lista de tuplas: el motor de dominios no interviene en un filtro que
           se construye aquí mismo. El álgebra es la misma conjunción.

        El modelo se resuelve por su ``_name``, no por su etiqueta de Django —
        así el llamador escribe ``'crm.lead'`` como la fuente.
        """
        model_cls = registry.model_by_name(model)
        if model_cls is None:
            return 0
        company_field = self._get_company_field(model)
        filtros = {
            f'{date_field}__gte': start,
            f'{date_field}__lt': end,
        }
        if self.company_id:
            filtros[f'{company_field}__in'] = [self.company_id.pk]
        qs = model_cls.objects.filter(**filtros)
        if additional_domain:
            qs = qs.filter(**additional_domain)
        if sum_field:
            return qs.aggregate(total=Sum(sum_field))['total'] or 0
        return qs.count()

    def compute_kpi_value(self, field_name, start, end):
        """Despacha al ``_compute_<field_name>_value`` correspondiente —
        equivalente al acceso dinámico ``digest[field_name + '_value']`` de
        la referencia (``digest.py:284``, dentro de ``_compute_kpis``)."""
        method = getattr(self, f'_compute_{field_name}_value', None)
        return method(start, end) if method is not None else None

    @staticmethod
    def _get_margin_value(value, previous_value=0.0):
        """≙ ``_get_margin_value`` (``digest.py:445-449``) — variación
        porcentual redondeada a 2 decimales, ``0.0`` si no hay base de
        comparación válida."""
        if value != previous_value and value != 0.0 and previous_value != 0.0:
            return round((float(value - previous_value) / previous_value) * 100, 2)
        return 0.0

    def compute_kpis(self):
        """≙ ``_compute_kpis`` (``digest.py:246-307``): un dict por KPI activo,
        con valor + margen para las 3 ventanas de ``_compute_timeframes``.
        Sin la parte de presentación (``kpi_action``/``kpi_fullname`` vía
        ``ir.model.fields`` — aquí ``verbose_name`` de Django hace el mismo
        papel)."""
        timeframes = self._compute_timeframes()
        kpis = []
        for field_name in self._get_kpi_field_names():
            verbose_name = str(self._meta.get_field(field_name).verbose_name)
            kpi = {
                'kpi_name': field_name,
                'kpi_fullname': verbose_name,
                'kpi_col1': {}, 'kpi_col2': {}, 'kpi_col3': {},
            }
            for col_index, (label, (current, previous)) in enumerate(timeframes, start=1):
                value = self.compute_kpi_value(field_name, *current)
                previous_value = self.compute_kpi_value(field_name, *previous)
                kpi[f'kpi_col{col_index}'] = {
                    'value': value,
                    'margin': self._get_margin_value(value, previous_value),
                    'col_subtitle': label,
                }
            kpis.append(kpi)
        return kpis
