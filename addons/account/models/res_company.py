r"""Lo que ``account`` le cuelga a la empresa — ≙ ``_inherit`` (tarea #140).

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

from addons.account.models.account_fiscal_position import AccountFiscalPosition
from addons.account.models.account_lock_exception import AccountLockException
from addons.account.models.account_payment_term import AccountPaymentTerm
from addons.account.models.chart_template import ChartTemplate
from addons.base.models import ResCompany
from addons.base.models.res_bank import ResBank
from addons.base.models.res_country import ResCountry
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_bank import ResPartnerBank
from addons.product.models.product_template import ProductTemplate
from addons.uom.models.uom_uom import Uom
from exceptions import UserError, ValidationError
from orm.environments import get_current_companies
from tools.translate import _


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


def _compute_force_restrictive_audit_trail(self):
    """≙ ``_compute_force_restrictive_audit_trail`` (``odoo19c:
    company.py:347-349``), cuyo cuerpo entero es ``= False``.

    No es un esbozo: en la referencia el campo existe **para que una
    localización lo redefina**. Mientras nadie lo haga, ninguna empresa tiene
    el rastro forzado y ``check_audit_trail_restriction`` no bloquea nada. El
    primer consumidor real será una localización que exija el rastro por ley;
    ``l10n_mx`` no lo hace hoy — medido: 0 hits de
    ``force_restrictive_audit_trail`` en ``addons/l10n_mx/``.
    """
    return False


def _check_audit_trail_restriction(self):
    """≙ ``_check_audit_trail_restriction`` (``odoo19c: company.py:319-322``).

    Impide **apagar** el rastro restringido cuando la localización lo fuerza.
    Se llama desde ``ResCompany.save()``; la referencia lo declara
    ``@api.constrains('restrictive_audit_trail')``, que es su forma de decir
    "se valida al escribir ese campo".

    El guion bajo se conserva porque la referencia lo declara privado
    (``porte-completo-no-parcial.md``). Las demás funciones libres de este
    archivo lo perdieron antes de que existiera esa regla — deuda #337, que
    se paga al tocar cada una, no aquí.
    """
    if not self.restrictive_audit_trail and self.force_restrictive_audit_trail:
        raise ValidationError(
            _('No se puede desactivar el rastro de auditoría restringido: '
              'lo fuerza la localización.')
        )


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


def compute_account_tax_fiscal_country(self):
    """El país fiscal cae al país de la empresa cuando nadie lo fijó — ≙
    ``compute_account_tax_fiscal_country`` (``odoo19c: company.py:387-390``).

    En la referencia el campo es ``compute=… store=True readonly=False``: se
    calcula al crear, pero el usuario puede sobreescribirlo y su valor
    persiste. Aquí es una **columna con resolutor explícito** — el mismo
    patrón que ``validate_hard_lock_date_change`` en este archivo: lo llama
    quien crea o edita la empresa, no un hook de ``save()``.

    La razón de no auto-engancharlo es medible: ``ResCompany.country`` NO es
    una columna sino una **propiedad delegada al partner**
    (``base/models/res_company.py:179`` lo declara entre los campos de
    dirección que viven en el partner). Un ``save()`` que lea ``self.country``
    dispararía una consulta al partner en cada guardado de empresa, incluidos
    los que no tocan el país.
    """
    if not self.account_fiscal_country and self.country:
        self.account_fiscal_country = self.country
    return self.account_fiscal_country


def account_fiscal_country_group_codes(self):
    """Códigos de las agrupaciones de su país fiscal — ≙
    ``_compute_account_fiscal_country_group_codes``
    (``odoo19c: company.py:363-368``).

    Devuelve ``['']`` cuando no hay país fiscal, igual que la referencia. Ese
    valor **es contrato**, no una rareza: quien compare contra esta lista
    obtiene otro resultado si cambia a lista vacía. Misma decisión, con la
    misma razón, que ``ResCountry.country_group_codes``.
    """
    country = self.account_fiscal_country
    return country.country_group_codes if country else ['']


def get_account_enabled_tax_countries(self, user=None):
    """Países cuyos impuestos esta empresa puede usar — ≙
    ``_compute_account_enabled_tax_country_ids``
    (``odoo19c: company.py:392-403``).

    Son su país fiscal más los de toda posición fiscal con ``foreign_vat``:
    una empresa registrada para IVA en otro país puede emitir con los
    impuestos de ese país sin cambiar su país fiscal.

    DIVERGENCIA DECLARADA — el usuario se recibe explícito, no ambiente.
    La referencia corta con ``if record not in self.env.user.company_ids``
    porque el formulario de empresa es visible sin acceso a su contenido
    (``base.res_company_rule_erp_manager``). Aquí el mismo corte se hace con
    el ``user`` recibido, por la razón que ya fija este archivo para los
    candados: el ORM portado no lleva un ``env`` de sesión.
    """
    if user is not None and not user.company_ids.filter(pk=self.pk).exists():
        return ResCountry.objects.none()
    foreign = AccountFiscalPosition.objects.filter(
        company=self, country__isnull=False,
    ).exclude(foreign_vat__isnull=True).exclude(
        foreign_vat='').values('country')
    condition = Q(pk__in=foreign)
    # `account_fiscal_country_id` es el atributo crudo de la FK: leerlo evita
    # traer la fila del país sólo para pedirle su clave.
    if self.account_fiscal_country_id:
        condition |= Q(pk=self.account_fiscal_country_id)
    return ResCountry.objects.filter(condition)


def get_fiscal_country_codes(company_ids=None):
    """Códigos de país fiscal de las empresas dadas, en su orden.

    Es el cuerpo compartido de los siete ``_get_fiscal_country_codes`` /
    ``_compute_fiscal_country_codes`` que la referencia reparte por el árbol
    (``account``: ``res_currency``, ``product``, ``account_payment_term``,
    ``partner``, ``uom_uom``; ``l10n_mx: res_bank`` ×2).

    Sin argumento usa las empresas **activadas de la sesión** — ≙ el
    ``self.env.companies`` de la referencia, que aquí es
    ``get_current_companies()`` (el canal del dato de ``orm.environments``).

    El orden se preserva a propósito: ``mapped`` en la referencia respeta el
    orden del recordset, y un ``filter(pk__in=…)`` de Django lo perdería a
    favor del ``ordering`` del modelo.
    """
    pks = tuple(company_ids) if company_ids is not None else get_current_companies()
    if not pks:
        return ''
    by_pk = dict(
        ResCompany.objects.filter(pk__in=pks)
        .values_list('pk', 'account_fiscal_country__code'),
    )
    return ','.join(by_pk[pk] for pk in pks if by_pk.get(pk))


def session_fiscal_country_codes(self):
    """≙ el ``fiscal_country_codes`` que sólo mira la sesión.

    Forma de ``odoo19c: account/models/res_currency.py:12-17`` y
    ``uom_uom.py:41-46``, y la que ``l10n_mx: res_bank.py`` repite en sus dos
    clases. En la referencia es ``fields.Char(store=False, default=…)``: una
    columna que no existe en la base. Aquí es ``property`` por lo mismo — no
    hay dato que guardar, y un campo no-almacenado no tiene análogo en este
    ORM.
    """
    return get_fiscal_country_codes()


def record_fiscal_country_codes(self):
    """≙ la forma que antepone la empresa del registro a la sesión.

    ``odoo19c: account/models/product.py:100-105`` y
    ``account_payment_term.py:48-53``: ``record.company_id or
    self.env.companies``. Un producto de una empresa concreta muestra el país
    fiscal de **esa** empresa, no el de las activadas.
    """
    company_id = getattr(self, 'company_id', None)
    return get_fiscal_country_codes([company_id] if company_id else None)


def partner_fiscal_country_codes(self):
    """≙ ``ResPartner._compute_fiscal_country_codes``
    (``odoo19c: account/models/partner.py:342-349``).

    La forma del registro **más el país propio del partner**, deduplicado. La
    referencia usa ``set()``, así que el orden se pierde allá también; aquí se
    deduplica preservando el primer avistamiento, que es un superconjunto
    determinista de su contrato.
    """
    codes = [c for c in record_fiscal_country_codes(self).split(',') if c]
    own_code = self.country.code if self.country_id else None
    if own_code and own_code not in codes:
        codes.append(own_code)
    return ','.join(codes)


def apply_account_extensions():
    """≙ ``_inherit = 'res.company'`` de ``account`` (``odoo19c: company.py``).

    Se llama desde ``AccountConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    # El país fiscal — la raíz que mantenía inertes `fiscal_country_codes` en
    # cinco modelos de `account` y en los dos de `l10n_mx: res_bank.py`.
    # ≙ `odoo19c: company.py:203-209`.
    _add_if_absent(ResCompany, 'account_fiscal_country', fields.Many2one(
        'base.ResCountry', on_delete=dj_models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='País cuyos reportes fiscales usa esta empresa (Odoo '
                  'account_fiscal_country). Cae al país de la empresa '
                  'cuando nadie lo fija.',
    ))
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

    # El interruptor del rastro de auditoría restringido — ≙ ``odoo19c:
    # company.py:257-262``. Es lo que vuelve OPERABLE la guarda que
    # ``addons/account/models/mail_message.py`` ya declaraba completa e inerte:
    # sin este campo, ``account_audit_log_restricted`` era siempre False.
    _add_if_absent(ResCompany, 'restrictive_audit_trail', fields.Boolean(
        default=False, verbose_name='Rastro de auditoría restrictivo',
        help_text='Impide borrar o mutar los mensajes del chatter que '
                  'documentan asientos ya publicados de esta empresa (Odoo '
                  'restrictive_audit_trail).',
    ))
    # ``force_restrictive_audit_trail`` es ``compute=`` SIN ``store`` en la
    # referencia y su cuerpo devuelve False para toda empresa
    # (``odoo19c: company.py:347-349``): es un gancho para que una
    # localización lo redefina y bloquee la desactivación. Sin columna que
    # registrar, la forma equivalente aquí es una ``property`` — mismo criterio
    # que los cinco resolutores de ``mail_message.py`` (:ref:`h-api-611`).
    if not hasattr(ResCompany, 'force_restrictive_audit_trail'):
        ResCompany.force_restrictive_audit_trail = property(
            _compute_force_restrictive_audit_trail)
    if not hasattr(ResCompany, '_check_audit_trail_restriction'):
        ResCompany._check_audit_trail_restriction = _check_audit_trail_restriction

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
        ('compute_account_tax_fiscal_country',
         compute_account_tax_fiscal_country),
        ('account_fiscal_country_group_codes',
         property(account_fiscal_country_group_codes)),
        ('get_account_enabled_tax_countries',
         get_account_enabled_tax_countries),
    ):
        if not hasattr(ResCompany, nombre):
            setattr(ResCompany, nombre, funcion)

    # `fiscal_country_codes` en los siete modelos que la referencia decora y
    # que este árbol tiene. No es un cuerpo repetido siete veces: son TRES
    # formas distintas, y colapsarlas borraría la diferencia (ver los
    # docstrings de arriba).
    #
    # `Uom` es `uom.uom` (`odoo19c: account/models/uom_uom.py:41-46`): allá la
    # clase se llama `UomUom` y aquí `Uom`, así que buscarla por el nombre de
    # la referencia da 0 hits y la deja fuera en silencio. Se resuelve por
    # `_name`, no por nombre de clase.
    #
    # El octavo caso de la referencia, `AccountFiscalPosition`
    # (`odoo19c: account/models/partner.py:55`), NO entra: allá es
    # `related='company_country_id.code'` — mismo nombre, otro símbolo. Su
    # porte depende de `company_country_id`, del Bloque 1 (#137).
    for model, funcion in (
        (ResCurrency, session_fiscal_country_codes),
        (ResBank, session_fiscal_country_codes),
        (ResPartnerBank, session_fiscal_country_codes),
        (Uom, session_fiscal_country_codes),
        (ProductTemplate, record_fiscal_country_codes),
        (AccountPaymentTerm, record_fiscal_country_codes),
        (ResPartner, partner_fiscal_country_codes),
    ):
        if not hasattr(model, 'fiscal_country_codes'):
            model.add_to_class('fiscal_country_codes', fields.Char(
                store=False, default=funcion,
                help_text='Códigos de país fiscal visibles en la sesión '
                          '(Odoo fiscal_country_codes).',
            ))

    dj_models.signals.post_save.connect(
        load_chart_for_new_company, sender=ResCompany,
        dispatch_uid='account.load_chart_for_new_company',
    )
    dj_models.signals.pre_save.connect(
        check_audit_trail_on_save, sender=ResCompany,
        dispatch_uid='account.check_audit_trail_restriction',
    )


def check_audit_trail_on_save(sender, instance, **kwargs):
    """Dispara la restricción del rastro **antes** de escribir la fila.

    ≙ ``@api.constrains('restrictive_audit_trail')`` (``odoo19c:
    company.py:318``). El decorador de la referencia declara *cuándo* se
    valida; aquí ese cuándo lo fija la señal, que es la vía ya usada en este
    archivo para ``load_chart_for_new_company``.

    Va en ``pre_save`` y no en ``post_save`` porque la referencia **impide** la
    escritura: validar después dejaría la fila con el rastro ya apagado y sólo
    levantaría el error a continuación.
    """
    instance._check_audit_trail_restriction()


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
