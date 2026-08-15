r"""Lo que ``stock`` le cuelga a la empresa — ≙ ``_inherit = 'res.company'``.

Adaptación de Odoo ``stock/models/res_company.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 215 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué es: la **topología mínima que toda empresa necesita para mover mercancía**.
Crear una empresa no basta: hace falta una ubicación de tránsito para moverse
entre sus almacenes, una de ajuste de inventario, una de producción, una de
desecho con su secuencia, y el horizonte de reabastecimiento que decide con
cuánta antelación se dispara un punto de pedido. Este archivo declara esas
piezas y los métodos que las crean para la empresa que no las tenga.

Por qué entra ahora — dos consumidores medidos que ya lo esperan
=================================================================

1. **``horizon_days``** lo lee ``stock_rule.py:1029`` a través de
   ``orderpoint_model.get_horizon_days()``, y lo consume el punto de pedido en
   ``_compute_deadline_date`` y ``_procure_orderpoint_confirm``. Sin el campo,
   el orderpoint (tarea #257) no tiene de dónde leer el horizonte.
2. **``internal_transit_location_id``** lo lee ``stock_warehouse.py:736``
   (``empresa.internal_transit_location``), y el docstring de ese archivo lo
   listaba explícitamente como *«símbolo que falta / quién lo espera aquí»*.

Medido antes de este pase: ``grep -rn horizon_days addons/ src/`` → **5 hits,
todos en** ``stock_rule.py``, ninguno una declaración. Ver :ref:`h-api-615`.

Porte símbolo por símbolo — 27 de 27
======================================

Medido por AST sobre el cuerpo de ``class ResCompany`` de la referencia: **29**
entradas. ``_inherit`` no es un símbolo a portar (aquí se expresa colgando de
``addons.base.models.ResCompany``), y ``_default_confirmation_mail_template``
se porta como el ``default`` de su campo. Quedan **27** que sí se portan.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Bloque
     - Símbolos
   * - Atributo de clase (1)
     - ``_check_company_auto``
   * - Campos (8)
     - ``internal_transit_location_id``, ``stock_move_email_validation``,
       ``stock_mail_confirmation_template_id``, ``annual_inventory_month``,
       ``annual_inventory_day``, ``horizon_days``, ``stock_text_confirmation``,
       ``stock_confirmation_type``
   * - Creadores por empresa (5)
     - ``_create_transit_location``, ``_create_inventory_loss_location``,
       ``_create_production_location``, ``_create_scrap_location``,
       ``_create_scrap_sequence``
   * - Reparadores del parque instalado (6)
     - ``create_missing_warehouse``, ``create_missing_transit_location``,
       ``create_missing_inventory_loss_location``,
       ``create_missing_production_location``, ``create_missing_scrap_location``,
       ``create_missing_scrap_sequence``
   * - Ganchos de composición (4)
     - ``_create_per_company_locations``, ``_create_per_company_sequences``,
       ``_create_per_company_picking_types``, ``_create_per_company_rules``
   * - Ciclo de vida (3)
     - ``create``, ``_set_per_company_inter_company_locations``,
       ``_get_text_validation``
   * - Default del campo (1)
     - ``_default_confirmation_mail_template``

*Métrica:* entradas del cuerpo de ``class ResCompany``, contadas por AST sobre
el archivo de la referencia.
*Ciega a:* lo que otros addons cuelgan de ``res.company`` — este conteo sólo ve
el archivo de ``stock``. ``account`` y ``sale`` ya cuelgan lo suyo en sus
propios ``models/res_company.py``, y esa es la forma que este archivo repite.

Dos divergencias de mecanismo declaradas
==========================================

**D-1 — ``create`` no se sobreescribe; se cuelga de una señal.** La referencia
extiende ``create`` de ``res.company`` desde este archivo. Aquí ``ResCompany``
vive en ``base`` y no es nuestra para sobreescribir su ``save()`` desde
``stock``; el equivalente es un receptor ``post_save`` que corre lo mismo —
``_create_per_company_locations``, ``_create_per_company_sequences``,
``_create_per_company_picking_types``, ``_create_per_company_rules``,
``_set_per_company_inter_company_locations``— sólo al crear. Los cinco métodos
se portan **con su cuerpo real** y quedan invocables a mano; lo que cambia es
quién los dispara, no qué hacen.

**D-2 — ``ir.default`` en vez de la propiedad de plantilla.** La referencia
guarda las ubicaciones de ajuste y de producción como *default por empresa* de
``product.template.property_stock_inventory`` / ``property_stock_production``.
Aquí se llama a ``IrDefault.set`` con la misma terna (modelo, campo, empresa),
que es el mismo mecanismo: ``ir.default`` **sí** está portado
(``src/addons/base/models/ir_default.py:145``). No es divergencia de fondo, sí
de firma — se anota porque el lector que compare línea a línea lo verá.

Lo que este archivo NO cierra
===============================

- ``modules.module.current_test`` de ``create`` (``odoo19c: :193-194``) — la
  referencia crea un almacén automático **sólo en modo test**. Aquí ese
  interruptor no existe; el receptor no lo replica y el test que necesite
  almacén lo crea explícitamente. Sucesor: tarea **#330**.
- El XML ID ``stock.stock_location_inter_company`` que ``create`` desarchiva
  (``:184-186``) — la siembra de datos de ``stock`` es alcance de **#330**; el
  receptor lo busca por ``ir.model.data`` y no falla si aún no está.
"""
import fields
import models
from django.apps import apps

from addons.base.models import ResCompany
from tools.translate import _

#: ≙ ``annual_inventory_month`` (``odoo19c: :24-38``) — el vocabulario de la
#: fuente, verbatim y en el mismo orden.
ANNUAL_INVENTORY_MONTH_CHOICES = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'),
    ('12', 'December'),
]

#: ≙ ``stock_confirmation_type`` (``odoo19c: :51``).
STOCK_CONFIRMATION_TYPE_CHOICES = [('sms', 'SMS')]


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que ya
    existe rompe con ``FieldError``. Mismo criterio que
    ``sale/models/res_company.py::_add_if_absent``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _default_confirmation_mail_template(self=None):
    """≙ ``_default_confirmation_mail_template`` (``odoo19c: :10-14``).

    La plantilla de correo con que se avisa al cliente que su pedido salió. La
    fuente la resuelve por XML ID y devuelve ``False`` si aún no está sembrada;
    aquí se devuelve ``None`` por la misma razón y con la misma tolerancia — la
    siembra de datos de ``stock`` es alcance de la tarea #330.
    """
    ir_model_data = apps.get_model('base', 'IrModelData')
    registro = ir_model_data.objects.filter(
        module='stock', name='mail_template_data_delivery_confirmation',
    ).first()
    return registro.res_id if registro is not None else None


# --------------------------------------------------------------------------- #
# Creadores por empresa (≙ :53-113)                                            #
# --------------------------------------------------------------------------- #

def _create_transit_location(self):
    """≙ ``_create_transit_location`` (``odoo19c: :53-71``).

    «Create a transit location with company_id being the given company_id. This
    is needed in case of resuply routes between warehouses belonging to the same
    company, because we don't want to create accounting entries at that time.»

    Nace **archivada** (``active=False``): sólo se ve cuando alguien configura
    de verdad un reabastecimiento entre almacenes.
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    partner_model = apps.get_model('base', 'ResPartner')

    location = stock_location.objects.create(
        name=_('Tránsito entre almacenes'),
        usage='transit',
        company=self,
        active=False,
    )
    type(self).objects.filter(pk=self.pk).update(
        internal_transit_location=location)
    self.internal_transit_location = location

    if self.partner_id is not None:
        partner_model.objects.filter(pk=self.partner_id).update(
            property_stock_customer=location,
            property_stock_supplier=location,
        )
    return location


def _create_inventory_loss_location(self):
    """≙ ``_create_inventory_loss_location`` (``odoo19c: :73-80``).

    La contrapartida de un ajuste de inventario: lo que aparece o desaparece al
    contar sale de aquí. Queda como default por empresa de
    ``product.template.property_stock_inventory`` (D-2).
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    ir_default = apps.get_model('base', 'IrDefault')

    location = stock_location.objects.create(
        name='Inventory adjustment', usage='inventory', company=self,
    )
    ir_default.set_default('product.template', 'property_stock_inventory',
                           location.pk, company=self)
    return location


def _create_production_location(self):
    """≙ ``_create_production_location`` (``odoo19c: :82-89``).

    De donde sale lo fabricado y a donde van los componentes consumidos.
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    ir_default = apps.get_model('base', 'IrDefault')

    location = stock_location.objects.create(
        name='Production', usage='production', company=self,
    )
    ir_default.set_default('product.template', 'property_stock_production',
                           location.pk, company=self)
    return location


def _create_scrap_location(self):
    """≙ ``_create_scrap_location`` (``odoo19c: :91-97``).

    Desecho. La fuente le da ``usage='inventory'`` —no un tipo propio—, y el
    porte lo conserva: lo desechado sale del inventario por la misma puerta que
    un ajuste negativo.
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    return stock_location.objects.create(
        name='Scrap', usage='inventory', company=self,
    )


def _create_scrap_sequence(self):
    """≙ ``_create_scrap_sequence`` (``odoo19c: :99-113``).

    La secuencia ``SP/00001`` con que se numeran los desechos de esta empresa.
    """
    sequence_model = apps.get_model('base', 'IrSequence')
    return sequence_model.objects.create(
        name='%s Sequence scrap' % self.name,
        code='stock.scrap',
        company=self,
        prefix='SP/',
        padding=5,
        number_next=1,
        number_increment=1,
    )


# --------------------------------------------------------------------------- #
# Reparadores del parque instalado (≙ :115-161)                                #
# --------------------------------------------------------------------------- #

def create_missing_warehouse(cls):
    """≙ ``create_missing_warehouse`` (``odoo19c: :115-127``).

    «This hook is used to add a warehouse on the first company of the database.»
    Sin almacén no hay ubicación de existencias, así que la base recién
    instalada necesita al menos uno.
    """
    warehouse_model = apps.get_model('stock', 'StockWarehouse')
    if warehouse_model.objects.exists():
        return None
    primera = ResCompany.objects.order_by('pk').first()
    if primera is None:
        return None
    return warehouse_model.objects.create(
        name=primera.name,
        code=(primera.name or '')[:5],
        company=primera,
        partner_id=primera.partner_id,
    )


def create_missing_transit_location(cls):
    """≙ ``create_missing_transit_location`` (``odoo19c: :129-132``)."""
    for empresa in ResCompany.objects.filter(
            internal_transit_location__isnull=True):
        _create_transit_location(empresa)


def create_missing_inventory_loss_location(cls):
    """≙ ``create_missing_inventory_loss_location`` (``odoo19c: :134-140``).

    La fuente resta a todas las empresas las que ya tienen el default puesto; el
    porte hace la misma resta sobre ``ir.default``.
    """
    for empresa in _companies_without_default('property_stock_inventory'):
        _create_inventory_loss_location(empresa)


def create_missing_production_location(cls):
    """≙ ``create_missing_production_location`` (``odoo19c: :142-148``)."""
    for empresa in _companies_without_default('property_stock_production'):
        _create_production_location(empresa)


def create_missing_scrap_location(cls):
    """≙ ``create_missing_scrap_location`` (``odoo19c: :150-155``).

    La fuente detecta «tiene desecho» por la existencia de **alguna** ubicación
    ``usage='inventory'`` de esa empresa — no por nombre. El porte conserva ese
    criterio, con su consecuencia: una empresa que ya tenga la de ajuste no
    recibe la de desecho.
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    con_desecho = set(stock_location.objects.filter(usage='inventory')
                      .exclude(company__isnull=True)
                      .values_list('company_id', flat=True))
    for empresa in ResCompany.objects.exclude(pk__in=con_desecho):
        _create_scrap_location(empresa)


def create_missing_scrap_sequence(cls):
    """≙ ``create_missing_scrap_sequence`` (``odoo19c: :157-161``)."""
    sequence_model = apps.get_model('base', 'IrSequence')
    con_secuencia = set(sequence_model.objects.filter(code='stock.scrap')
                        .exclude(company__isnull=True)
                        .values_list('company_id', flat=True))
    for empresa in ResCompany.objects.exclude(pk__in=con_secuencia):
        _create_scrap_sequence(empresa)


def _companies_without_default(field_name):
    """Las empresas que aún no tienen ese default de ``product.template``.

    **No es un símbolo de la referencia**: es el denominador común de
    ``create_missing_inventory_loss_location`` y
    ``create_missing_production_location``, que allá lo escriben dos veces
    idéntico (``:134-148``). Se factoriza aquí en vez de duplicarlo — misma
    consulta, un solo sitio donde equivocarse.

    La referencia llega al default por ``ir.model.fields._get(modelo, campo)`` y
    filtra ``ir.default`` por esa FK. Aquí ``IrDefault.field`` es el **nombre**
    del campo, no una FK (``src/addons/base/models/ir_default.py:160``), así que
    el filtro es directo: un salto menos, mismo conjunto.
    """
    ir_default = apps.get_model('base', 'IrDefault')
    con_propiedad = set(ir_default.objects
                        .filter(model='product.template', field=field_name)
                        .exclude(company__isnull=True)
                        .values_list('company_id', flat=True))
    return ResCompany.objects.exclude(pk__in=con_propiedad)


# --------------------------------------------------------------------------- #
# Ganchos de composición y ciclo de vida (≙ :163-215)                          #
# --------------------------------------------------------------------------- #

def _create_per_company_locations(self):
    """≙ ``_create_per_company_locations`` (``odoo19c: :163-168``)."""
    _create_transit_location(self)
    _create_inventory_loss_location(self)
    _create_production_location(self)
    _create_scrap_location(self)


def _create_per_company_sequences(self):
    """≙ ``_create_per_company_sequences`` (``odoo19c: :170-172``)."""
    _create_scrap_sequence(self)


def _create_per_company_picking_types(self):
    """≙ ``_create_per_company_picking_types`` (``odoo19c: :174-175``).

    Vacío en la fuente **a propósito**: es el punto de extensión que otros
    addons rellenan. Se porta con su cuerpo real —ninguno— porque su valor es el
    contrato, no el cálculo (mismo criterio que
    ``product._get_quantity_in_progress``).
    """


def _create_per_company_rules(self):
    """≙ ``_create_per_company_rules`` (``odoo19c: :177-179``).

    Vacío en la fuente, igual que el anterior y por la misma razón.
    """


def _set_per_company_inter_company_locations(self, inter_company_location):
    """≙ ``_set_per_company_inter_company_locations`` (``odoo19c: :197-211``).

    Con multi-empresa activo, cada empresa ve a las **otras** a través de la
    ubicación inter-empresa: lo que sale de una entra en esa ubicación y de ahí
    a la otra. La fuente lo escribe en los dos sentidos —las otras empresas
    hacia ésta y ésta hacia cada una de las otras— y el porte conserva ambos.
    """
    partner_model = apps.get_model('base', 'ResPartner')
    if inter_company_location is None:
        return
    otras = ResCompany.objects.exclude(pk=self.pk)
    partner_ids = [c.partner_id for c in otras if c.partner_id]
    if partner_ids:
        partner_model.objects.filter(pk__in=partner_ids).update(
            property_stock_customer=inter_company_location,
            property_stock_supplier=inter_company_location,
        )
    if self.partner_id:
        partner_model.objects.filter(pk=self.partner_id).update(
            property_stock_customer=inter_company_location,
            property_stock_supplier=inter_company_location,
        )


def _get_text_validation(self, confirmation_type):
    """≙ ``_get_text_validation`` (``odoo19c: :213-215``).

    ¿Esta empresa avisa por texto, y por este canal?
    """
    return bool(self.stock_text_confirmation
                and self.stock_confirmation_type == confirmation_type)


def setup_new_company(company):
    """≙ el ``create`` de la referencia (``odoo19c: :181-195``) — D-1.

    Corre lo mismo que su ``create`` tras llamar a ``super()``: desarchiva la
    ubicación inter-empresa, y para la empresa recién creada monta ubicaciones,
    secuencias, tipos de operación y reglas, más el enlace inter-empresa.

    Lo dispara el receptor ``post_save`` de ``handlers.py``, no un override de
    ``save()``: ``ResCompany`` es de ``base`` y ``stock`` no la posee.
    """
    stock_location = apps.get_model('stock', 'StockLocation')
    ir_model_data = apps.get_model('base', 'IrModelData')

    registro = ir_model_data.objects.filter(
        module='stock', name='stock_location_inter_company').first()
    inter_company = (
        stock_location.objects.filter(pk=registro.res_id).first()
        if registro is not None else None
    )
    if inter_company is not None and not inter_company.active:
        stock_location.objects.filter(pk=inter_company.pk).update(active=True)
        inter_company.active = True

    _create_per_company_locations(company)
    _create_per_company_sequences(company)
    _create_per_company_picking_types(company)
    _create_per_company_rules(company)
    _set_per_company_inter_company_locations(company, inter_company)


def apply_stock_res_company_extensions():
    """≙ ``_inherit = 'res.company'`` de ``stock``.

    Se llama desde ``StockConfig.ready()``, no al importar: en tiempo de import
    el registro de modelos aún no está poblado.
    """
    # ≙ ``_check_company_auto = True`` (``odoo19c: :8``).
    if not hasattr(ResCompany, '_check_company_auto'):
        ResCompany._check_company_auto = True

    _add_if_absent(ResCompany, 'internal_transit_location', fields.Many2one(
        'stock.StockLocation', null=True, blank=True,
        on_delete=models.RESTRICT, related_name='companies_as_transit',
        verbose_name='Ubicación de tránsito interna',
        help_text='Ubicación por la que pasa la mercancía al moverse entre dos '
                  'almacenes de esta misma empresa '
                  '(Odoo internal_transit_location_id).',
    ))
    _add_if_absent(ResCompany, 'stock_move_email_validation', fields.Boolean(
        default=False, verbose_name='Confirmación por correo de la transferencia',
        help_text='Envía un correo al cliente cuando la transferencia se '
                  'completa (Odoo stock_move_email_validation).',
    ))
    _add_if_absent(
        ResCompany, 'stock_mail_confirmation_template',
        fields.Many2one(
            'mail.MailTemplate', null=True, blank=True,
            on_delete=models.SET_NULL,
            related_name='companies_as_stock_confirmation',
            default=_default_confirmation_mail_template,
            verbose_name='Plantilla de confirmación de transferencia',
            help_text='Correo que recibe el cliente cuando su pedido sale '
                      '(Odoo stock_mail_confirmation_template_id).',
        ))
    _add_if_absent(ResCompany, 'annual_inventory_month', fields.Selection(
        choices=ANNUAL_INVENTORY_MONTH_CHOICES, max_length=2, default='12',
        null=True, blank=True, verbose_name='Mes del inventario anual',
        help_text='Mes del inventario anual para los productos que no están en '
                  'una ubicación con conteo cíclico; vacío desactiva el '
                  'inventario anual automático (Odoo annual_inventory_month).',
    ))
    _add_if_absent(ResCompany, 'annual_inventory_day', fields.Integer(
        default=31, verbose_name='Día del mes',
        help_text='Día del mes en que ocurre el inventario anual. Cero o '
                  'negativo se toma como el primer día del mes; mayor que el '
                  'último día del mes, como el último '
                  '(Odoo annual_inventory_day).',
    ))
    _add_if_absent(ResCompany, 'horizon_days', fields.Float(
        default=365.0, verbose_name='Horizonte de reabastecimiento',
        help_text='Cuántos días antes se dispara una regla de reabastecimiento '
                  'para adelantarse a los retrasos; 0 la dispara justo a tiempo '
                  'y evita sobrestock (Odoo horizon_days, required=True).',
    ))
    _add_if_absent(ResCompany, 'stock_text_confirmation', fields.Boolean(
        default=False, verbose_name='Confirmación por texto',
        help_text='Avisa por texto (SMS) al completar la transferencia '
                  '(Odoo stock_text_confirmation).',
    ))
    _add_if_absent(ResCompany, 'stock_confirmation_type', fields.Selection(
        choices=STOCK_CONFIRMATION_TYPE_CHOICES, max_length=8, default='sms',
        null=True, blank=True, verbose_name='Canal de confirmación',
        help_text='Canal del aviso por texto (Odoo stock_confirmation_type).',
    ))

    for nombre, funcion in (
        ('_create_transit_location', _create_transit_location),
        ('_create_inventory_loss_location', _create_inventory_loss_location),
        ('_create_production_location', _create_production_location),
        ('_create_scrap_location', _create_scrap_location),
        ('_create_scrap_sequence', _create_scrap_sequence),
        ('_create_per_company_locations', _create_per_company_locations),
        ('_create_per_company_sequences', _create_per_company_sequences),
        ('_create_per_company_picking_types', _create_per_company_picking_types),
        ('_create_per_company_rules', _create_per_company_rules),
        ('_set_per_company_inter_company_locations',
         _set_per_company_inter_company_locations),
        ('_get_text_validation', _get_text_validation),
    ):
        if not hasattr(ResCompany, nombre):
            setattr(ResCompany, nombre, funcion)

    for nombre, funcion in (
        ('create_missing_warehouse', create_missing_warehouse),
        ('create_missing_transit_location', create_missing_transit_location),
        ('create_missing_inventory_loss_location',
         create_missing_inventory_loss_location),
        ('create_missing_production_location', create_missing_production_location),
        ('create_missing_scrap_location', create_missing_scrap_location),
        ('create_missing_scrap_sequence', create_missing_scrap_sequence),
    ):
        if not hasattr(ResCompany, nombre):
            setattr(ResCompany, nombre, classmethod(funcion))
