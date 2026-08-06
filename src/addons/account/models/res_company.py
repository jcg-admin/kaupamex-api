"""Lo que ``account`` le cuelga a la empresa — ≙ ``_inherit`` (tarea #140).

Adaptación de ``addons/account/models/company.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``). **Sólo dos de los 72 campos del Bloque 1**, y la razón de portar
exactamente esos dos —y no el bloque entero— es que son los que desbloquean una
cadena medida, no una preferencia de orden.

Por qué estos dos ahora
========================

:ref:`h-api-340` midió que la línea de venta extrae el IVA de un parámetro
global en vez de los impuestos del producto. La primera mitad de su sucesora
(#141) ya está: ``compute_all`` existe. La segunda mitad —reapuntar
``SaleOrderLine.price_tax``— tropieza con algo que no es código:

*Métrica:* migraciones que crean filas en ``account_tax``.
*Ciega a:* filas creadas por fixture o comando en un despliegue concreto.
Medido: ``grep -rln "AccountTax" src/addons/*/migrations/*.py`` da dos
archivos, **ambos de esquema** (``0001_initial``, ``0003_…``). **Nadie siembra
un impuesto.** [PROVEN]

Reapuntar ``price_tax`` sobre esa base daría impuesto **0** en toda línea —
un cambio que se ve verde en los tests y borra el IVA en producción. El
eslabón que falta no es el motor: es de dónde sale el impuesto por defecto
cuando un producto no declara el suyo.

La referencia lo responde en dos líneas: la empresa lleva su impuesto de venta
por defecto (``odoo19c: company.py:126-127``) y el producto lo usa como
``default`` de su M2M (``odoo19c: product.py:44``). Con eso, un producto nuevo
nace con el impuesto de su empresa y el eje funciona.

Lo que NO hace falta para esto — y por qué importa decirlo
===========================================================

``account.chart.template`` **puebla** ese campo al instalar un plan contable
(``odoo19c: chart_template.py:731-743``), y son 1537 líneas orientadas a cargar
un plan completo desde CSV. Es trabajo real y sigue pendiente (#140, otra
mitad), pero **no es requisito** de esta cadena: la referencia declara el campo
en ``res.company``, no en el chart, precisamente para que una empresa pueda
fijar su impuesto por defecto sin instalar un plan entero.

Portar el chart primero habría sido el orden intuitivo y el equivocado.

Divergencias declaradas
========================

- **``check_company=True``** no tiene análogo: es una validación del ORM de la
  referencia que comprueba que el registro apuntado pertenece a la misma
  empresa. Aquí se cubre con un ``limit_choices_to`` — que restringe en el
  formulario y en la validación del serializer, **pero no en la base**. Un
  ``AccountTax`` de otra empresa asignado por código pasaría. Es el mismo hueco
  que el resto de los ``check_company`` del porte, y su cierre es el mecanismo
  de row-scoping L1 (tarea #133, :ref:`h-api-259`), no un parche por campo.
- **``account_purchase_receipt_fiscal_position_id``** y los otros 70 del Bloque
  1 siguen fuera: los cierra la tarea **#137** (mapeo campo por campo), que a su
  vez espera la decisión del eje partner (#142).

Los cinco candados de fecha — H-API-320, tarea #110
====================================================

:ref:`h-api-313` midió que 19c absorbió y expandió el addon ``account_lock``
de 18e poniendo cinco fechas de candado en ``ResCompany``. Se portan aquí:
``fiscalyear_lock_date``, ``tax_lock_date``, ``sale_lock_date``,
``purchase_lock_date`` (``odoo19c: account/models/company.py:76-96``,
``SOFT_LOCK_DATE_FIELDS``) y ``hard_lock_date`` (``:97-102``, irreversible,
sin excepciones).

Junto con los campos se porta el mecanismo que les da sentido — los
computados ``user_*_lock_date`` que ``account_lock_exception.py`` declaraba
pendientes ("el llamador… resuelve el máximo con la fecha propia de la
empresa"): ``get_user_lock_date`` (``odoo19c: company.py:607-640``) recorre
``parent_ids`` y aplica la excepción vigente más favorable de
``AccountLockException``; sus cuatro envoltorios nombrados
(``get_user_fiscalyear_lock_date``…) y ``get_user_hard_lock_date``
(``:442-448``, sin excepciones) son los computados en sí. Encima, la API de
consulta que los usa: ``get_violated_soft_lock_date`` (``:656-673``),
``get_lock_date_violations`` (``:675-710``), ``format_lock_dates``
(``:712-721``) y ``get_violated_lock_dates`` (``:723-739``).

DIVERGENCIA DECLARADA — el usuario se recibe explícito, no ambiente
--------------------------------------------------------------------

La referencia resuelve el usuario de ``self.env.user`` (contexto de sesión de
Odoo). Este ORM no tiene contexto de request en el modelo — ``get_user_lock_date``
y sus envoltorios reciben ``user=None`` explícito, que resuelve quien llama
(vista/servicio). Mismo criterio que ``res_currency.assert_rounding_can_change``
recibiendo el valor nuevo en vez de leerlo de un ``write(vals)`` ambiente.

Qué NO se porta de este bloque, con su medición
-------------------------------------------------

``_validate_locks`` (``odoo19c: company.py:552-605``) hace tres cosas; se
porta sólo la primera:

1. **Monotonía de ``hard_lock_date``** — se porta como
   ``validate_hard_lock_date_change`` (guard explícito, no auto-hooked a
   ``save()``, mismo patrón que ``res_currency.py``).
2. **Bloquear asientos en borrador bajo el candado duro** — NO se porta en
   este pase: pertenece a la orquestación de ``write()`` de ``company.py``
   (líneas 741-772), la misma que cuelga las otras 70 columnas del Bloque 1
   ya declaradas fuera de alcance (tarea #137) en este mismo archivo. No es
   parte de "los cinco candados + los computados de AccountLockException"
   que el hallazgo delimita.
3. **Bloquear extractos bancarios sin conciliar** — mismo motivo que (2).

El ``write()`` de la referencia también revoca y recrea las excepciones
activas cuando cambia el candado que modifican
(``AccountLockException._recreate()``/``_get_active_exceptions_domain()``,
``:764-770``). **Bloqueado por algo medido:** el ``AccountLockException``
portado en este árbol no declara esos dos símbolos —
``grep -n "_recreate\|_get_active_exceptions_domain" account_lock_exception.py``
→ **0 hits** [PROVEN]. Añadirlos es trabajo del propio archivo
``account_lock_exception.py``, no de ``ResCompany``; queda como hallazgo para
que el ejecutor lo registre con su propio sucesor.
"""
from datetime import date

from django.db import models as dj_models
from django.db.models import Q
from django.utils import timezone

import fields

from addons.account.models.account_lock_exception import AccountLockException
from addons.account.models.chart_template import ChartTemplate
from addons.base.models import ResCompany
from exceptions import UserError


def _default_tax(help_text, tax_use):
    """FK al impuesto por defecto de la empresa.

    ``on_delete=PROTECT`` y no ``SET_NULL``: borrar un impuesto que es el
    default de una empresa deja productos nuevos sin impuesto de forma
    silenciosa. La referencia usa el default de Odoo (``restrict``) por la
    misma razón.
    """
    return fields.Many2one(
        'account.AccountTax',
        null=True, blank=True, on_delete=dj_models.PROTECT,
        related_name='+', limit_choices_to={'type_tax_use': tax_use},
        help_text=help_text,
    )


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que
    ya existe rompe con ``FieldError``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def get_user_lock_date(self, soft_lock_date_field, user=None, ignore_exceptions=False):
    """Candado vigente para ESTE usuario en ``soft_lock_date_field`` — ≙
    ``_get_user_lock_date`` (``odoo19c: company.py:607-640``).

    Recorre ``self.parent_ids`` y, para cada empresa que declare el candado,
    aplica la excepción vigente más favorable de ``AccountLockException``
    (activa, para ``user`` o global, con ``lock_date`` anterior al candado de
    la empresa) en vez del candado crudo. Sin excepción aplicable, rige el
    candado de la empresa. Es el "llamador… pendiente" que
    ``account_lock_exception.py`` declaraba — cierra el computado.
    """
    soft_lock_date = date.min
    for company in self.parent_ids:
        company_lock_date = getattr(company, soft_lock_date_field)
        if not company_lock_date:
            continue
        exception_date = None
        if not ignore_exceptions:
            exception = AccountLockException.objects.filter(
                company=company, active=True,
                lock_date_field=soft_lock_date_field,
                lock_date__lt=company_lock_date,
            ).filter(
                Q(user=None) | Q(user=user),
            ).filter(
                Q(end_datetime__isnull=True) | Q(end_datetime__gte=timezone.now()),
            ).order_by('lock_date').first()
            if exception is not None:
                exception_date = exception.lock_date
        if exception_date is not None:
            soft_lock_date = max(soft_lock_date, exception_date)
        else:
            soft_lock_date = max(soft_lock_date, company_lock_date)
    return soft_lock_date


def get_user_hard_lock_date(self):
    """Máximo ``hard_lock_date`` en la cadena de ancestros — ≙
    ``_compute_user_hard_lock_date`` (``odoo19c: company.py:442-448``). El
    candado duro es irreversible y no admite excepciones (a diferencia de los
    cuatro candados blandos), así que no consulta ``AccountLockException``.
    """
    dates = [c.hard_lock_date for c in self.parent_ids if c.hard_lock_date]
    return max(dates) if dates else date.min


def get_user_fiscalyear_lock_date(self, user=None, ignore_exceptions=False):
    """≙ ``_compute_user_fiscalyear_lock_date`` (``odoo19c: company.py:414-419``)."""
    return get_user_lock_date(
        self, 'fiscalyear_lock_date', user=user,
        ignore_exceptions=ignore_exceptions)


def get_user_tax_lock_date(self, user=None, ignore_exceptions=False):
    """≙ ``_compute_user_tax_lock_date`` (``odoo19c: company.py:421-426``)."""
    return get_user_lock_date(
        self, 'tax_lock_date', user=user, ignore_exceptions=ignore_exceptions)


def get_user_sale_lock_date(self, user=None, ignore_exceptions=False):
    """≙ ``_compute_user_sale_lock_date`` (``odoo19c: company.py:428-433``)."""
    return get_user_lock_date(
        self, 'sale_lock_date', user=user, ignore_exceptions=ignore_exceptions)


def get_user_purchase_lock_date(self, user=None, ignore_exceptions=False):
    """≙ ``_compute_user_purchase_lock_date`` (``odoo19c: company.py:435-440``)."""
    return get_user_lock_date(
        self, 'purchase_lock_date', user=user,
        ignore_exceptions=ignore_exceptions)


def get_violated_soft_lock_date(self, soft_lock_date_field, accounting_date, user=None):
    """¿``accounting_date`` viola el candado ``soft_lock_date_field``? — ≙
    ``_get_violated_soft_lock_date`` (``odoo19c: company.py:656-673``).

    Devuelve el candado violado (con la excepción ya aplicada) o ``None``.
    """
    regular_lock_date = get_user_lock_date(
        self, soft_lock_date_field, user=user, ignore_exceptions=True)
    if accounting_date > regular_lock_date:
        return None
    user_lock_date = get_user_lock_date(
        self, soft_lock_date_field, user=user, ignore_exceptions=False)
    if accounting_date > user_lock_date:
        return None
    return user_lock_date


def get_lock_date_violations(self, accounting_date, fiscalyear=True, sale=True,
                              purchase=True, tax=True, hard=True, user=None):
    """Todos los candados que afectan ``accounting_date`` — ≙
    ``_get_lock_date_violations`` (``odoo19c: company.py:675-710``).

    Devuelve una lista de tuplas ``(candado_violado, campo)``, no ordenada
    cronológicamente (igual que la fuente).
    """
    locks = []
    if not accounting_date:
        return locks
    checks = (
        ('fiscalyear_lock_date', fiscalyear),
        ('sale_lock_date', sale),
        ('purchase_lock_date', purchase),
        ('tax_lock_date', tax),
    )
    for field, to_check in checks:
        if not to_check:
            continue
        violated_date = get_violated_soft_lock_date(
            self, field, accounting_date, user=user)
        if violated_date:
            locks.append((violated_date, field))
    if hard:
        hard_lock_date = get_user_hard_lock_date(self)
        if accounting_date <= hard_lock_date:
            locks.append((hard_lock_date, 'hard_lock_date'))
    return locks


def format_lock_dates(self, lock_dates):
    """Formatea una lista de candados como texto — ≙ ``_format_lock_dates``
    (``odoo19c: company.py:712-721``).

    DIVERGENCIA DECLARADA: la referencia toma el rótulo traducido de
    ``self.fields_get([field])[field]['string']`` (introspección de campo de
    Odoo); aquí no existe ``fields_get`` — se lee ``verbose_name`` de la
    metadata de Django, que cumple el mismo rol.
    """
    meta = type(self)._meta
    parts = [
        f'{meta.get_field(field).verbose_name} ({lock_date.isoformat()})'
        for lock_date, field in sorted(lock_dates)
    ]
    return ', '.join(parts)


def get_violated_lock_dates(self, accounting_date, has_tax, journal=None, user=None):
    """Candados que afectan ``accounting_date``, ordenados cronológicamente —
    ≙ ``_get_violated_lock_dates`` (``odoo19c: company.py:723-739``).

    :param journal: ``AccountJournal`` o ``None`` — determina si se chequean
        ``sale_lock_date``/``purchase_lock_date`` según su ``type``.
    """
    locks = get_lock_date_violations(
        self, accounting_date,
        fiscalyear=True,
        sale=bool(journal and journal.type == 'sale'),
        purchase=bool(journal and journal.type == 'purchase'),
        tax=has_tax,
        hard=True,
        user=user,
    )
    locks.sort()
    return locks


def validate_hard_lock_date_change(self, new_hard_lock_date):
    """Guard de integridad de ``hard_lock_date`` — ≙ el fragmento de
    ``_validate_locks`` que cubre este campo (``odoo19c: company.py:569-576``).

    Explícito, no auto-hooked a ``save()`` — mismo patrón que
    ``res_currency.assert_rounding_can_change``: lo invoca el
    serializer/servicio que cambia el candado duro, ANTES de guardar. Las
    otras dos validaciones de ``_validate_locks`` (asientos en borrador,
    extractos sin conciliar) NO se portan aquí — ver el docstring del módulo.
    """
    if not self.hard_lock_date:
        return
    if not new_hard_lock_date:
        raise UserError('El candado duro no se puede eliminar.')
    if new_hard_lock_date < self.hard_lock_date:
        raise UserError(
            'Un nuevo candado duro debe ser posterior (o igual) al anterior.')


def apply_account_extensions():
    """≙ ``_inherit = 'res.company'`` de ``account`` (``odoo19c: company.py``).

    Se llama desde ``AccountConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(ResCompany, 'account_sale_tax', _default_tax(
        'Impuesto de venta por defecto de la empresa. Lo hereda todo producto '
        'nuevo que no declare el suyo (Odoo account_sale_tax_id, '
        'company.py:126).',
        'sale',
    ))
    _add_if_absent(ResCompany, 'account_purchase_tax', _default_tax(
        'Impuesto de compra por defecto de la empresa (Odoo '
        'account_purchase_tax_id, company.py:127).',
        'purchase',
    ))
    _add_if_absent(ResCompany, 'chart_template', fields.Char(
        max_length=64, null=True, blank=True,
        help_text='Código del plan contable cargado en esta empresa (Odoo '
                  'chart_template, company.py:117). Una empresa hija hereda '
                  'el de su raíz al crearse.',
    ))
    # Los tres prefijos de código con los que el plan declara sus cuentas de
    # utilidad — ≙ ``odoo19c: company.py:118,119,125``. No son adorno: son lo
    # que ``setup_utility_bank_accounts`` usa para pedirle a
    # ``AccountAccount.search_new_account_code`` el primer hueco libre.
    for prefix_name, prefix_help in (
        ('bank_account_code_prefix', 'bancarias'),
        ('cash_account_code_prefix', 'de efectivo'),
        ('transfer_account_code_prefix', 'de transferencia'),
    ):
        _add_if_absent(ResCompany, prefix_name, fields.Char(
            max_length=64, null=True, blank=True,
            help_text=f'Prefijo de código de las cuentas {prefix_help} '
                      f'(Odoo {prefix_name}).',
        ))

    # Las seis cuentas de utilidad que el plan crea y deja apuntadas en la
    # empresa — ≙ el bloque de ``_get_accounts_data_values``
    # (``odoo19c: chart_template.py:848-887``). Las de cobros/pagos pendientes
    # NO están aquí a propósito: la referencia las crea con identificador
    # externo y **sin** campo en la empresa ("No fields on company").
    for account_name, account_help in (
        ('account_journal_suspense_account', 'transitoria de banco'),
        ('account_journal_early_pay_discount_loss_account',
         'de pérdida por descuento por pronto pago'),
        ('account_journal_early_pay_discount_gain_account',
         'de ganancia por descuento por pronto pago'),
        ('default_cash_difference_income_account',
         'de sobrante de efectivo'),
        ('default_cash_difference_expense_account',
         'de faltante de efectivo'),
        ('transfer_account', 'de transferencia de liquidez'),
    ):
        _add_if_absent(ResCompany, account_name, fields.Many2one(
            'account.AccountAccount', on_delete=dj_models.SET_NULL,
            null=True, blank=True, related_name=f'company_{account_name}',
            help_text=f'Cuenta {account_help} (Odoo {account_name}_id).',
        ))

    # Los cinco candados de fecha — ≙ ``SOFT_LOCK_DATE_FIELDS`` +
    # ``hard_lock_date`` (``odoo19c: company.py:57-102``). H-API-320, #110.
    for lock_name, lock_verbose, lock_help in (
        ('fiscalyear_lock_date', 'Candado global',
         'Cualquier asiento hasta esta fecha inclusive se pospone a una '
         'fecha posterior, según la secuencia de su diario (Odoo '
         'fiscalyear_lock_date).'),
        ('tax_lock_date', 'Candado de declaración de impuestos',
         'Cualquier asiento con impuestos hasta esta fecha inclusive se '
         'pospone a una fecha posterior. Se fija automáticamente al '
         'publicar el asiento de cierre fiscal (Odoo tax_lock_date).'),
        ('sale_lock_date', 'Candado de ventas',
         'Cualquier asiento de venta anterior a esta fecha inclusive se '
         'pospone a una fecha posterior (Odoo sale_lock_date).'),
        ('purchase_lock_date', 'Candado de compras',
         'Cualquier asiento de compra anterior a esta fecha inclusive se '
         'pospone a una fecha posterior (Odoo purchase_lock_date).'),
        ('hard_lock_date', 'Candado duro',
         'Cualquier asiento hasta esta fecha inclusive se pospone a una '
         'fecha posterior. Este candado es irreversible y no admite '
         'ninguna excepción (Odoo hard_lock_date).'),
    ):
        _add_if_absent(ResCompany, lock_name, fields.Date(
            null=True, blank=True, verbose_name=lock_verbose,
            help_text=lock_help,
        ))

    # El mecanismo que le da sentido a los cinco candados — cierra los
    # computados que ``account_lock_exception.py`` declaraba pendientes.
    for nombre, funcion in (
        ('get_user_lock_date', get_user_lock_date),
        ('get_user_hard_lock_date', get_user_hard_lock_date),
        ('get_user_fiscalyear_lock_date', get_user_fiscalyear_lock_date),
        ('get_user_tax_lock_date', get_user_tax_lock_date),
        ('get_user_sale_lock_date', get_user_sale_lock_date),
        ('get_user_purchase_lock_date', get_user_purchase_lock_date),
        ('get_violated_soft_lock_date', get_violated_soft_lock_date),
        ('get_lock_date_violations', get_lock_date_violations),
        ('format_lock_dates', format_lock_dates),
        ('get_violated_lock_dates', get_violated_lock_dates),
        ('validate_hard_lock_date_change', validate_hard_lock_date_change),
    ):
        if not hasattr(ResCompany, nombre):
            setattr(ResCompany, nombre, funcion)

    dj_models.signals.post_save.connect(
        load_chart_for_new_company, sender=ResCompany,
        dispatch_uid='account.load_chart_for_new_company',
    )


def load_chart_for_new_company(sender, instance, created, **kwargs):
    """Carga el plan de la raíz en la empresa recién creada.

    ≙ el ``create`` de ``odoo19c: account/models/company.py:486-498``: si la
    raíz de su jerarquía declara un plan, la nueva empresa lo instancia.

    **Por qué se lee el padre y no ``instance.parent_ids``.** La referencia usa
    ``parent_ids[0]`` y difiere la carga a ``cr.precommit`` — no por capricho:
    ese cálculo necesita el estado del registro ya asentado. Aquí ocurre lo
    mismo por otra vía: ``ResCompany.save()`` calcula ``parent_path`` **después**
    del ``INSERT`` (``res_company.py:581-586``), así que en el instante del
    ``post_save`` la ruta materializada todavía está vacía y ``parent_ids``
    devuelve sólo la propia empresa. Leer ``instance.parent`` —una FK, escrita
    ya— y pedirle a él su raíz evita depender de un valor que aún no existe.

    Una empresa **raíz** (``parent is None``) no entra por aquí, igual que en la
    referencia: su plan lo elige quien la aprovisiona (allá,
    ``res_config_settings.py:223``). Esa mitad es la tarea #156.

    ``dispatch_uid`` porque ``ready()`` puede correr dos veces con el
    autoreloader, y sin él el receptor se conectaría por duplicado.
    """
    if not created or instance.parent is None:
        return
    template_code = getattr(instance.parent.root_id, 'chart_template', None)
    if template_code:
        ChartTemplate.try_loading(template_code, instance)
