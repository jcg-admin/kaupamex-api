"""``website`` — la configuración de recuperación de carrito que ``website_sale``
le cuelga al sitio (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/website_sale/models/website.py``
(``odoo-tools@622ddc2a``, LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03). El archivo de la referencia tiene **1103 líneas** y declara una
sola clase, ``Website(_inherit='website')``. Este pase porta **una rebanada
nombrada**: la recuperación de carrito abandonado (tarea **#258**). El resto
—precios, posición fiscal, pasos del checkout, imágenes de producto— llega con
su superficie, y no se cuenta aquí para no inflar el denominador.

Universo medido de la rebanada — 9 símbolos
=============================================

Derivados por AST sobre el archivo de la referencia, no a mano: entradas del
cuerpo de ``class Website`` cuyo nombre o cuerpo menciona ``abandoned`` /
``cart_recovery`` / ``recovery``. **Más dos** que el AST no marca y que la
tarea **#568** añadió a la rebanada: ``salesteam_id`` y su ``default``. No
mencionan ninguna de las tres cadenas —no son recuperación de carrito— pero
son la **pieza de la que cuelga** ``crm_team.py`` entero, y portarlos aquí es
lo que lo desbloquea. Es la misma corrección declarada que
``models/sale_order.py`` hace con ``website_id``: la métrica de cadenas es
ciega al ancla del mecanismo.

.. list-table::
   :header-rows: 1
   :widths: 46 12 42

   * - Símbolo de la referencia (línea)
     - Estado
     - Forma aquí
   * - ``_default_recovery_mail_template`` (``:41-45``)
     - portado
     - función de módulo; ``IrModelData.ref`` es el ``env.ref`` del árbol
   * - ``cart_recovery_mail_template_id`` (``:98-103``)
     - portado
     - ``WebsiteSaleSettings.cart_recovery_mail_template``
   * - ``cart_abandoned_delay`` (``:107``)
     - portado
     - ``WebsiteSaleSettings.cart_abandoned_delay``
   * - ``send_abandoned_cart_email`` (``:108-110``)
     - portado
     - ``WebsiteSaleSettings.send_abandoned_cart_email``
   * - ``send_abandoned_cart_email_activation_time`` (``:111-115``)
     - portado
     - ``WebsiteSaleSettings.send_abandoned_cart_email_activation_time``
   * - ``_compute_send_abandoned_cart_email_activation_time`` (``:291-295``)
     - portado
     - cuerpo de ``save()`` — ver D-3
   * - ``_send_abandoned_cart_email`` (``:920-944``)
     - portado
     - ``WebsiteSaleSettings._send_abandoned_cart_email`` (``classmethod``)
   * - ``_default_salesteam_id`` (``:35-39``)
     - portado
     - función de módulo; ver ``WEBSITE_SALESTEAM_XMLID``
   * - ``salesteam_id`` (``:63-69``)
     - portado
     - ``WebsiteSaleSettings.salesteam``, sus 5 atributos — ver D-7

*Métrica:* entradas del cuerpo de ``class Website`` en
``odoo19c: website_sale/models/website.py`` que nombran o mencionan la
recuperación, contadas por AST.
*Ciega a:* (1) los símbolos de la misma clase que no la mencionan —son las
otras rebanadas del addon, y su conteo pertenece a sus tareas—; (2) lo que
**otros** addons cuelgan de ``website`` (``website_sale_stock``,
``website_event_sale``): este conteo sólo ve el archivo de ``website_sale``.

Un símbolo que el AST marcó y **no** entra en el universo:
``_get_and_cache_current_cart`` (``:780-856``). Lo marcó un comentario
—*"No abandoned cart should be returned in this situation"*— pero su trabajo es
resolver el carrito de la sesión, no recuperarlo: pertenece a la tarea del
servicio de carrito, no a #258.

Divergencias declaradas
========================

**D-1 — los campos viven en un modelo propio de ``website_sale``, no en la
tabla ``website``.** La referencia reabre ``website`` y le añade columnas; aquí
el autodetector de migraciones **atribuye la columna al ``app_label`` del
modelo**, no al addon que la contribuye — es la misma restricción de plataforma
que ``models/product_template.py`` ya declara en este addon. Añadir columnas a
``website`` obligaría a escribir la migración en ``addons/website/migrations/``,
que es de otro addon.

La forma que este árbol ya usa para eso es la tabla lateral 1-1 propiedad del
addon que extiende: ``account_check_printing.CheckPrintingJournalSettings``
sobre ``account.journal``, ``delivery.ShipmentGuide`` sobre ``sale.SaleOrder``.
Se sigue ese precedente. Lo que se conserva es lo que importa: ``website`` no
menciona la tienda, y quien decide la política de recuperación es este archivo.

**D-2 — los nombres pierden el sufijo ``_id`` del ``Many2one``, como en todo el
árbol.** ``cart_recovery_mail_template_id`` → ``cart_recovery_mail_template``,
igual que ``partner_id`` → ``partner`` y ``company_id`` → ``company`` en
``sale.SaleOrder``. Los nombres sin sufijo se portan **verbatim**.

**D-3 — el ``compute`` almacenado va en ``save()``.** Este ORM no tiene
``@api.depends``; ``send_abandoned_cart_email_activation_time`` es
``store=True`` en la fuente, así que su cuerpo se ejecuta al guardar. La
condición de disparo se conserva: se sella la hora cuando la casilla está
activa y todavía no hay hora sellada, o cuando acaba de activarse.

**D-4 — ``_send_abandoned_cart_email`` es ``classmethod``, no método de
recordset.** En la fuente es ``@api.model`` y hace ``self.search([])``; aquí el
barrido equivalente es ``cls.objects.all()``. Mismo criterio que
``mail_activity_mixin._search_activity_state``.

**D-5 — el envío es ``MailTemplate.render`` + ``dispatch_email``, no
``template.send_mail``.** ``addons/mail/models/mail_template.py`` declara
``render()`` y deja el envío a ``email_executor.dispatch_email`` — es el idioma
que ya usan ``authz_signup`` y ``authz_totp_mail``. El cálculo de
``email_vals`` de la fuente (usar el destinatario por defecto de la plantilla,
o el del comprador si la plantilla no lo fija) se conserva.

**D-6 — la especificación del cron vive en este módulo, no en
``addons/website_sale/data/``.** Los cuatro precedentes del árbol
(``mail``, ``helpdesk``, ``loyalty``, ``observability``) la ponen en
``<addon>/data/__init__.py``; ``website_sale`` todavía no tiene ese paquete y
crearlo queda fuera del alcance de escritura de este pase. Se mueve cuando el
addon estrene su módulo de datos. Sucesor: tarea **#567**.

**D-7 — el ``related_name`` de ``salesteam`` alcanza esta fila, no el sitio.**
En la referencia el inverso es ``crm.team.website_ids``, un ``One2many`` a
``website`` (``odoo19c: website_sale/models/crm_team.py:9-11``). Aquí la FK
sale de ``WebsiteSaleSettings`` —consecuencia directa de D-1—, así que
``team.websites`` devuelve **filas de política**, y el sitio está un salto más
allá (``settings.website``).

La **cardinalidad es idéntica** porque la relación con el sitio es 1-1: hay
exactamente una fila de política por sitio, así que "cuántos sitios tiene este
equipo" y "cuántas filas de política tiene este equipo" son el mismo número.
Eso es lo que hace que el guard de ``_compute_abandoned_carts`` siga siendo
fiel — es lo único que ese guard pregunta.

Aristas de porte
=================

Porte BLOQUEADO — 0 de 9 símbolos

Ninguno de los nueve quedó fuera. Lo que sí queda fuera, con su pieza y su
sucesor:

- ``:697`` — ``'team_id': self.salesteam_id.id`` en los valores con que el
  sitio prepara un pedido nuevo.
  BLOQUEADO por ``Website._prepare_sale_order_values`` — el método que lo
  contiene pertenece a la rebanada del **servicio de carrito**, que #258 no
  portó y que ``__manifest__.py`` ya registra como tarea **#101**. El campo que
  la línea lee (``salesteam``) sí está portado desde este pase: lo que falta es
  su consumidor, no su pieza. Sucesor: tarea **#101**.
- El **equipo «Website Sales» sembrado** — ``WEBSITE_SALESTEAM_XMLID`` no
  resuelve porque ``addons/sales_team/`` no tiene ``data/``.
  BLOQUEADO por ``sales_team.salesteam_website_sales`` — sembrarlo toca otro
  addon, fuera del alcance de escritura de este pase. El default es fiel
  igualmente (devuelve ``None``, como la fuente cuando el equipo no existe).
  Sucesor: tarea **#568**.
- ``res_config_settings.py`` de la referencia — no es falta de pieza sino el
  bloqueo de forma ya registrado como tarea **#278**; su medición vive en
  ``models/res_config_settings.py`` de este addon, quinto caso idéntico del
  árbol.
"""
import logging

from django.apps import apps
from django.utils import timezone

import fields
import models
from addons.base.models import TimeStampedModel
from addons.base.models.ir_model import IrModelData
from addons.mail.models.email_executor import dispatch_email
from addons.mail.models.mail_template import MailTemplate
from addons.website.models.website import Website

logger = logging.getLogger(__name__)

#: ≙ el identificador externo que la referencia resuelve con ``env.ref`` en
#: ``_default_recovery_mail_template`` (``odoo19c: :43``) y en
#: ``_send_abandoned_cart_email`` (``odoo19c: :938``).
CART_RECOVERY_TEMPLATE_XMLID = 'website_sale.mail_template_sale_cart_recovery'

#: ≙ el identificador externo que la referencia resuelve con ``env.ref`` en
#: ``_default_salesteam_id`` (``odoo19c: :36``).
#:
#: **No está sembrado en este árbol** (medido: ``grep -rn
#: "salesteam_website_sales" addons/ src/`` → 0 hits; ``addons/sales_team/`` no
#: tiene ``data/``). El default devuelve entonces ``None``, que es **el mismo
#: desenlace** que da la fuente cuando el equipo no existe o está archivado
#: (``odoo19c: :37-39``): allá el ``raise_if_not_found=False`` devuelve un
#: recordset vacío y el ``if team and team.active`` cae al ``return None``.
#: Fiel, por tanto — pero declarado, no implícito. La siembra del equipo
#: «Website Sales» toca ``addons/sales_team/``, fuera del alcance de escritura
#: de este pase. Sucesor: tarea **#568**.
WEBSITE_SALESTEAM_XMLID = 'sales_team.salesteam_website_sales'

#: ≙ ``ir_cron_send_availability_email`` (``odoo19c: website_sale/data/
#: ir_cron_data.xml:3-9``, ``odoo-tools@622ddc2a``), cuyo cuerpo es
#: ``model._send_abandoned_cart_email()`` sobre ``model_website``, con
#: ``interval_number=1`` e ``interval_type=hours``.
#:
#: El ``priority`` no lo declara la fuente, así que toma el ``default=5`` del
#: modelo (``src/addons/base/models/ir_cron.py``) y se escribe explícito para
#: que ``sembrar_cron`` no dependa de un default ajeno.
#:
#: El ``model_name`` apunta al modelo que aloja el método aquí
#: (``WebsiteSaleSettings``), no a ``website``: es la consecuencia directa de
#: D-1, donde la configuración vive en la tabla lateral.
CRON_SEND_ABANDONED_CART_EMAIL = {
    'name': 'eCommerce: correo de recuperación de carrito abandonado',
    'model_name': 'website_sale.WebsiteSaleSettings',
    'method_name': '_send_abandoned_cart_email',
    'interval_number': 1,
    'interval_type': 'hours',
    'priority': 5,
}


def _default_recovery_mail_template():
    """≙ ``_default_recovery_mail_template`` (``odoo19c: :41-45``).

    La fuente envuelve el ``env.ref`` en un ``try/except ValueError`` porque su
    ``ref`` levanta cuando el identificador no está. Aquí se pide con
    ``raise_if_not_found=False``, que devuelve ``None`` — misma conducta, sin
    excepción de control de flujo.
    """
    return IrModelData.ref(CART_RECOVERY_TEMPLATE_XMLID,
                           raise_if_not_found=False)


def _default_salesteam_id():
    """≙ ``_default_salesteam_id`` (``odoo19c: :35-39``).

    El equipo de venta «Website Sales» si está sembrado **y activo**; ``None``
    si no. Las dos condiciones de la fuente se conservan: el
    ``raise_if_not_found=False`` (``:36``) y el ``and team.active`` (``:37``)
    — un equipo archivado no se asigna por defecto.

    Divergencia de firma: Django llama al ``default`` de un campo **sin
    argumentos**, así que esto es una función de módulo y no un método del
    modelo como en la fuente. Devuelve la clave primaria, que es lo que aquel
    ``return team.id`` devuelve.

    Hoy devuelve ``None`` siempre porque el identificador externo no está
    sembrado — ver ``WEBSITE_SALESTEAM_XMLID``.
    """
    team = IrModelData.ref(WEBSITE_SALESTEAM_XMLID, raise_if_not_found=False)
    if team is not None and team.active:
        return team.pk
    return None


class WebsiteSaleSettings(TimeStampedModel):
    """La política de recuperación de carrito de un sitio — ≙ los campos
    ``cart_*``/``send_abandoned_cart_email*`` que ``website_sale`` añade a
    ``website``.

    Uno a uno con el sitio: la fuente los declara como columnas de ``website``,
    así que no puede haber dos juegos de política para el mismo sitio. Ver D-1
    del docstring del módulo para por qué es una tabla aparte.
    """

    website = models.OneToOneField(
        Website, on_delete=models.CASCADE,
        related_name='website_sale_settings',
        help_text='Sitio al que aplica esta política (Odoo _inherit website).',
    )
    cart_recovery_mail_template_id = fields.Many2one(
        MailTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        verbose_name='Correo de recuperación de carrito',
        help_text='Plantilla que se envía al carrito abandonado (Odoo '
                  'cart_recovery_mail_template_id). Vacío = la plantilla por '
                  'defecto del addon.',
        db_column='cart_recovery_mail_template_id',
    )
    cart_abandoned_delay = fields.Float(
        default=10.0,
        verbose_name='Retraso de abandono',
        help_text='Horas sin actividad tras las cuales el carrito se considera '
                  'abandonado (Odoo cart_abandoned_delay).',
    )
    send_abandoned_cart_email = fields.Boolean(
        default=False,
        verbose_name='Enviar correo a quien abandonó su carrito',
        help_text='Odoo send_abandoned_cart_email.',
    )
    send_abandoned_cart_email_activation_time = fields.Datetime(
        null=True, blank=True,
        verbose_name='Hora de activación del envío',
        help_text='Momento en que se activó el envío de recuperación; los '
                  'carritos anteriores no se recuperan (Odoo '
                  'send_abandoned_cart_email_activation_time, store=True).',
    )
    #: ≙ ``salesteam_id`` (``odoo19c: :63-69``). Los cinco atributos que la
    #: fuente declara, uno a uno — ver D-7 del docstring del módulo para por
    #: qué el ``related_name`` alcanza esta fila y no el sitio:
    #:
    #: - ``string="Sales Team"`` (``:64``)     → ``verbose_name``
    #: - ``comodel_name='crm.team'`` (``:65``) → ``'sales_team.CrmTeam'``
    #: - ``index='btree_not_null'`` (``:66``)  → el índice parcial de ``Meta``
    #: - ``ondelete='set null'`` (``:67``)     → ``on_delete=models.SET_NULL``
    #: - ``default=_default_salesteam_id`` (``:68``) → ídem, ver la función
    salesteam_id = fields.Many2one(
        'sales_team.CrmTeam', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='websites',
        default=_default_salesteam_id,
        verbose_name='Equipo de venta',
        help_text='Equipo de venta al que se atribuyen los pedidos de este '
                  'sitio (Odoo website.salesteam_id).',
        db_column='salesteam_id',
    )

    class Meta:
        db_table = 'website_sale_settings'
        ordering = ['website_id']
        verbose_name = 'Política de recuperación de carrito'
        verbose_name_plural = 'Políticas de recuperación de carrito'
        indexes = [
            # ≙ ``index='btree_not_null'`` (``odoo19c: :66``). En 19 ese valor
            # pide un btree **parcial**, ``WHERE col IS NOT NULL``: la mayoría
            # de los sitios no fija equipo, y un índice completo pagaría por
            # todas esas filas nulas. ``db_index=True`` daría un btree entero
            # —otro índice, no éste—, así que se declara con su condición.
            models.Index(
                fields=['salesteam_id'],
                condition=models.Q(salesteam_id__isnull=False),
                name='website_sale_salesteam_nn',
            ),
        ]

    def __str__(self):
        return 'Recuperación de carrito — %s' % self.website

    def save(self, *args, **kwargs):
        """Sella la hora de activación — ≙
        ``_compute_send_abandoned_cart_email_activation_time`` (``:291-295``).

        La fuente lo declara ``store=True`` con ``@api.depends
        ('send_abandoned_cart_email')``; este ORM no tiene ``depends``, así que
        el cuerpo vive aquí (D-3). La condición de disparo se conserva: hay
        hora sellada mientras la casilla esté activa, y ninguna cuando no.
        """
        if self.send_abandoned_cart_email:
            if self.send_abandoned_cart_email_activation_time is None:
                self.send_abandoned_cart_email_activation_time = timezone.now()
        else:
            self.send_abandoned_cart_email_activation_time = None
        return super().save(*args, **kwargs)

    def _get_cart_abandoned_delay(self):
        """Las horas de abandono efectivas de este sitio.

        Símbolo **nuestro**, no de la fuente: allá el ``or 1.0`` se repite
        inline en ``_compute_abandoned_cart`` (``sale_order.py:84``) y en
        ``_search_abandoned_cart`` (``:137``). Aquí lo consumen los mismos dos
        sitios más el barrido del cron, y repetirlo tres veces es cómo dos
        copias acaban divergiendo.
        """
        return self.cart_abandoned_delay or 1.0

    @classmethod
    def _send_abandoned_cart_email(cls):
        """≙ ``_send_abandoned_cart_email`` (``odoo19c: :920-944``).

        Cuerpo del cron. Por cada sitio con el envío activo: busca sus carritos
        abandonados aún sin correo y posteriores a la activación, descarta los
        que el filtro rechaza —marcándolos como enviados para no reexaminarlos
        en cada corrida, igual que la fuente— y envía el resto.

        Divergencias: D-4 (``classmethod`` en vez de ``@api.model`` +
        ``search([])``) y D-5 (``render`` + ``dispatch_email`` en vez de
        ``template.send_mail``).
        """
        # ``apps.get_model`` y no un ``import`` del modelo al top: ``sale_order``
        # de este mismo addon importa esta clase para leer el retraso de
        # abandono, así que un import cruzado cerraría el ciclo. Es una llamada
        # en tiempo de ejecución, no un statement — ``apps`` sí está importado
        # arriba, como manda ``no-lazy-imports``.
        sale_order_model = apps.get_model('sale', 'SaleOrder')

        template = IrModelData.ref(CART_RECOVERY_TEMPLATE_XMLID,
                                   raise_if_not_found=False)
        if template is None:
            logger.warning(
                'Recuperación de carrito: la plantilla %s no está sembrada; '
                'no se envía nada en esta corrida.',
                CART_RECOVERY_TEMPLATE_XMLID)
            return 0

        sent = 0
        for settings in cls.objects.select_related('website').all():
            if not settings.send_abandoned_cart_email:
                continue
            activation = settings.send_abandoned_cart_email_activation_time
            if activation is None:
                # No debería ocurrir —``save()`` sella la hora cuando la
                # casilla se activa—, pero una fila escrita por una migración
                # o por SQL directo puede saltarse ``save()``.
                logger.warning(
                    'Recuperación de carrito: el sitio %s tiene el envío '
                    'activo sin hora de activación; se omite.',
                    settings.website_id)
                continue

            all_abandoned_carts = sale_order_model._search_abandoned_cart(
                'in', [True],
            ).filter(
                website_sale_info__website_id=settings.website_id,
                website_sale_info__cart_recovery_email_sent=False,
                date_order__gte=activation,
            )
            if not all_abandoned_carts.exists():
                continue

            abandoned_carts = sale_order_model._filter_can_send_abandoned_cart_mail(
                all_abandoned_carts)
            keepers = {order.pk for order in abandoned_carts}
            # Marca como enviados los que el filtro rechazó, para no volver a
            # examinarlos en cada corrida — verbatim de la fuente (``:935``).
            for order in all_abandoned_carts:
                if order.pk not in keepers:
                    _mark_recovery_email_sent(order)

            for sale_order in abandoned_carts:
                if _send_recovery_email(template, sale_order):
                    _mark_recovery_email_sent(sale_order)
                    sent += 1
        return sent


def _mark_recovery_email_sent(sale_order):
    """≙ ``sale_order.cart_recovery_email_sent = True`` (``:936``, ``:944``).

    Símbolo **nuestro**: la fuente asigna el campo directamente sobre el
    pedido porque allá la columna es suya. Aquí vive en la tabla lateral
    (D-1), así que la asignación necesita nombre propio.
    """
    info = getattr(sale_order, 'website_sale_info', None)
    if info is None:
        return False
    info.cart_recovery_email_sent = True
    info.save(update_fields=['cart_recovery_email_sent'])
    return True


def _send_recovery_email(template, sale_order):
    """Renderiza y despacha el correo de recuperación de un pedido — D-5.

    Conserva el cálculo de ``email_vals`` de la fuente (``:940-943``): si la
    plantilla ya fija destinatario —``email_to``, ``partner_to`` o
    ``use_default_to``— se respeta; si no, se usa el correo del comprador.
    """
    rendered = template.render(sale_order)
    recipient = rendered.get('email_to') or ''
    if not (template.email_to or template.partner_to or template.use_default_to):
        recipient = _buyer_email(sale_order)
    if not recipient:
        logger.warning(
            'Recuperación de carrito: el pedido %s no tiene destinatario; '
            'se omite.', sale_order.pk)
        return False
    dispatch_email(
        rendered['subject'], rendered['body_html'],
        rendered['email_from'] or None, [recipient],
    )
    return True


def _buyer_email(sale_order):
    """El correo del comprador — ≙ ``partner_id.email_formatted``.

    Divergencia declarada: aquí el comprador es un ``res.users`` (cuyo
    ``login`` **es** su correo, ``ResUsers.normalize_email``) o, en el
    checkout anónimo, el ``guest_email`` que ``sale.SaleOrder`` guarda. La
    fuente sólo contempla el primero porque su carrito siempre tiene
    ``partner_id``.
    """
    if sale_order.partner_id:
        return sale_order.partner.login or ''
    return sale_order.guest_email or ''
