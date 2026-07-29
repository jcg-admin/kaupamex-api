"""
create_seed_catalog — seed de catálogo E2E (iniciativa seed-catalogo-e2e).

Crea (o actualiza idempotentemente) los datos mínimos de catálogo,
pago y envío para que el flujo de checkout E2E funcione sin
intervención manual:

  - Category        : categoría raíz de collar QA
  - Product         : producto con is_published=True, stock≥1
  - VariantType     : tipo de variante "Tamaño"
  - VariantOption   : opción "Único"
  - ProductVariant  : variante con stock≥1, is_active=True
  - ShippingZone    : prefix "066" cubre CP 06600 (CDMX Cuauhtémoc)
  - ShippingMethod  : método de envío "Estándar QA", costo=0
  - PaymentGateway  : gateway=TEST, is_active=True, credentials sandbox

No requiere variables de entorno adicionales.
La SECRET_KEY (para cifrar credenciales Fernet) la lee del .env
del proyecto (ya cargado por Django en el momento de invocación).

Idempotente: doble ejecución no produce IntegrityError ni datos
duplicados. Usa update_or_create / get_or_create en cada modelo.

Uso:
  python manage.py create_seed_catalog
  python manage.py create_seed_catalog --dry-run
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.chartsize.models import VariantOption, VariantType, ProductVariant
from addons.delivery.models import ShippingZone
from addons.delivery.models import ShippingMethod
from addons.payment.models import PaymentGateway

# ── Constantes de seed ────────────────────────────────────────────────────────
_CAT_SLUG    = 'collar-qa-e2e'
_CAT_NAME    = 'Collares QA E2E'

_PROD_SKU    = 'QA-001'
_PROD_SLUG   = 'qa-001-collar-e2e'
_PROD_NAME   = 'Collar QA E2E'
_PROD_PRICE  = Decimal('100.00')
_PROD_STOCK  = 5

_VT_NAME     = 'Tamaño'
_VO_LABEL    = 'Único'

_PV_STOCK    = 5

_ZONE_PREFIX = '066'
_ZONE_NAME   = 'CDMX Cuauhtémoc'

_SM_NAME     = 'Estándar QA'
_SM_COST     = Decimal('0')
_SM_DAYS     = 3

_GW_CREDS    = {'mode': 'sandbox'}


class Command(BaseCommand):
    help = 'Seed de catálogo E2E: producto, pasarela de pago y zona de envío.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra el plan sin escribir en la base de datos.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']

        if dry_run:
            self.stdout.write(self.style.NOTICE('DRY-RUN — no se escribe nada.'))
            self.stdout.write(f'  Category       : {_CAT_NAME!r} (slug={_CAT_SLUG!r})')
            self.stdout.write(f'  Product        : {_PROD_NAME!r} sku={_PROD_SKU} '
                              f'price={_PROD_PRICE} stock={_PROD_STOCK}')
            self.stdout.write(f'  VariantType    : {_VT_NAME!r}')
            self.stdout.write(f'  VariantOption  : {_VO_LABEL!r}')
            self.stdout.write(f'  ProductVariant : stock={_PV_STOCK}')
            self.stdout.write(f'  ShippingZone   : prefix={_ZONE_PREFIX!r} ({_ZONE_NAME})')
            self.stdout.write(f'  ShippingMethod : {_SM_NAME!r} cost={_SM_COST} days={_SM_DAYS}')
            self.stdout.write(f'  PaymentGateway : gateway=TEST credentials={_GW_CREDS}')
            return

        with transaction.atomic():
            cat,     cat_new  = _upsert_category()
            product, prod_new = _upsert_product(cat)
            vtype,   vt_new   = _upsert_variant_type(product)
            voption, vo_new   = _upsert_variant_option(vtype)
            variant, var_new  = _upsert_product_variant(product, voption)
            zone,    zone_new = _upsert_shipping_zone()
            method,  meth_new = _upsert_shipping_method()
            gw,      gw_new   = _upsert_payment_gateway()

        def _lbl(created):
            return 'creado' if created else 'actualizado'

        self.stdout.write(self.style.SUCCESS(
            f'  Category       : {cat.name!r} — {_lbl(cat_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  Product        : {product.sku} — {_lbl(prod_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  VariantType    : {vtype.name!r} — {_lbl(vt_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  VariantOption  : {voption.label!r} — {_lbl(vo_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  ProductVariant : stock={variant.stock} — {_lbl(var_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  ShippingZone   : prefix={zone.zip_code_prefix!r} — {_lbl(zone_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  ShippingMethod : {method.name!r} — {_lbl(meth_new)}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  PaymentGateway : {gw.gateway} — {_lbl(gw_new)}'
        ))


# ── Funciones de upsert ───────────────────────────────────────────────────────

def _upsert_category():
    cat, created = Category.objects.get_or_create(
        slug=_CAT_SLUG,
        defaults={'name': _CAT_NAME, 'is_active': True},
    )
    if not created:
        # Asegurar coherencia en re-ejecuciones. updated_at explícito
        # porque auto_now=True se ignora en .update() (lección H-TS-02).
        Category.objects.filter(pk=cat.pk).update(
            is_active=True, updated_at=timezone.now()
        )
        cat.refresh_from_db()
    return cat, created


def _upsert_product(category):
    product, created = Product.objects.update_or_create(
        sku=_PROD_SKU,
        defaults={
            'name': _PROD_NAME,
            'slug': _PROD_SLUG,
            'price': _PROD_PRICE,
            'stock': _PROD_STOCK,
            'is_active': True,
            'is_published': True,
        },
    )
    # UC-CAT-13: M2M — assign category after save.
    product.categories.add(category)
    return product, created


def _upsert_variant_type(product):
    vtype, created = VariantType.objects.get_or_create(
        product=product,
        name=_VT_NAME,
        defaults={'is_active': True, 'order': 0},
    )
    return vtype, created


def _upsert_variant_option(vtype):
    voption, created = VariantOption.objects.get_or_create(
        variant_type=vtype,
        label=_VO_LABEL,
        defaults={'is_active': True, 'order': 0},
    )
    return voption, created


def _upsert_product_variant(product, option):
    variant, created = ProductVariant.objects.update_or_create(
        product=product,
        option=option,
        defaults={'stock': _PV_STOCK, 'is_active': True},
    )
    return variant, created


def _upsert_shipping_zone():
    zone, created = ShippingZone.objects.get_or_create(
        zip_code_prefix=_ZONE_PREFIX,
        defaults={'name': _ZONE_NAME, 'is_active': True},
    )
    if not created:
        ShippingZone.objects.filter(pk=zone.pk).update(is_active=True)
        zone.refresh_from_db()
    return zone, created


def _upsert_shipping_method():
    method, created = ShippingMethod.objects.update_or_create(
        name=_SM_NAME,
        defaults={
            'cost': _SM_COST,
            'estimated_days': _SM_DAYS,
            'is_active': True,
        },
    )
    return method, created


def _upsert_payment_gateway():
    # BinaryField requiere credenciales antes del primer save.
    # Se usa get_or_create con credentials=b'' como placeholder,
    # luego set_credentials() + save() en un paso separado.
    # Esto garantiza que Fernet cifra con la SECRET_KEY activa.
    gw, created = PaymentGateway.objects.get_or_create(
        gateway=PaymentGateway.GATEWAY_TEST,
        defaults={
            'name': 'Test Gateway E2E',
            'is_active': True,
            'credentials': b'',
        },
    )
    gw.name = 'Test Gateway E2E'
    gw.is_active = True
    gw.set_credentials(_GW_CREDS)
    gw.save(update_fields=['name', 'is_active', 'credentials', 'updated_at'])
    return gw, created
