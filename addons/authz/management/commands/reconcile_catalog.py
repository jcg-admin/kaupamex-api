"""Reconcilia el catálogo sembrado en DB contra lo que declaran los addons.

**Qué resuelve (SOL-100 punto 2).** ``check_catalog_declaration.py`` verifica
que las declaraciones sean coherentes **entre sí**; este comando verifica que
la **DB** coincida con ellas. Son problemas distintos y el segundo sólo se ve
en runtime.

El caso que lo motiva es H-API-106 en su forma exacta: el addon ``orders`` se
retiró (``api@77bd1f0``) y su fila ``authz_module`` siguió viva en toda base
ya sembrada, con cuatro aristas ``depends`` apuntando a ella. Ningún comando
lo notaba porque la siembra sólo **añade**: ``get_or_create`` nunca retira lo
que dejó de declararse.

**Tres divergencias que reporta:**

1. **Sembrado sin declarar** — la fila existe en DB y ningún addon la declara.
   Es deuda: se puede suscribir un módulo que ya no significa nada.
2. **Declarado sin sembrar** — falta correr ``seed_authz``. No es deuda, es un
   despliegue a medias.
3. **Metadata divergente** — la fila existe pero su ``name`` /
   ``is_application`` / ``category`` / ``depends`` no coincide con lo
   declarado. Suele ser edición manual en la consola L0.

**Por qué ``--prune`` es opt-in y con freno.** Retirar un ``Module`` no es
inocuo: ``Capability.module`` es ``PROTECT`` y ``CompanyModuleSubscription``
apunta a él. Una company puede estar **pagando** por un módulo cuya declaración
alguien borró; borrar la fila destruiría ese registro. Por eso el comando
**reporta por defecto**, y ``--prune`` se niega a tocar cualquier módulo con
suscripciones.

Uso::

    python manage.py reconcile_catalog            # reporte, exit 0
    python manage.py reconcile_catalog --strict   # exit 1 si hay divergencias
    python manage.py reconcile_catalog --prune    # retira lo no declarado (con freno)
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from addons.authz.declaration import discover
from addons.authz.models import Capability, Module
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
)


class Command(BaseCommand):
    help = 'Compara el catálogo sembrado en DB contra lo declarado por los addons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='Sale con código 1 si hay cualquier divergencia (para CI).',
        )
        parser.add_argument(
            '--prune', action='store_true',
            help='Retira de la DB los módulos y capacidades que nadie declara. '
                 'Se niega a tocar módulos con suscripciones vivas.',
        )

    def handle(self, *args, **options):
        declared_modules, declared_caps = discover()

        db_modules = {m.code: m for m in Module.objects.prefetch_related('depends')}
        db_caps = {c.code: c for c in Capability.objects.all()}

        stale_modules = sorted(set(db_modules) - set(declared_modules))
        missing_modules = sorted(set(declared_modules) - set(db_modules))
        stale_caps = sorted(set(db_caps) - set(declared_caps))
        missing_caps = sorted(set(declared_caps) - set(db_caps))
        diverging = self._diverging_metadata(declared_modules, db_modules)

        self._report('Módulos sembrados que nadie declara', stale_modules)
        self._report('Módulos declarados sin sembrar (falta seed_authz)',
                       missing_modules)
        self._report('Capacidades sembradas que nadie declara', stale_caps)
        self._report('Capacidades declaradas sin sembrar', missing_caps)
        self._report('Metadata divergente entre DB y declaración', diverging)

        total = (len(stale_modules) + len(missing_modules) + len(stale_caps)
                 + len(missing_caps) + len(diverging))

        if options['prune']:
            self._prune(stale_modules, stale_caps, db_modules, db_caps)

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f'Catálogo reconciliado: {len(declared_modules)} módulos y '
                f'{len(declared_caps)} capacidades coinciden con la declaración.'
            ))
            return

        self.stdout.write(self.style.WARNING(f'{total} divergencia(s).'))
        if options['strict'] and not options['prune']:
            raise CommandError(
                'Catálogo divergente. Correr seed_authz si faltan filas, o '
                'reconcile_catalog --prune si sobran.'
            )

    def _diverging_metadata(self, specs, db_modules):
        """Filas cuya metadata no coincide con lo declarado por su addon."""
        result = []
        for code, spec in specs.items():
            row = db_modules.get(code)
            if row is None:
                continue
            diffs = []
            if row.name != spec.name:
                diffs.append(f'name {row.name!r}≠{spec.name!r}')
            if row.is_application != spec.is_application:
                diffs.append(
                    f'is_application {row.is_application}≠{spec.is_application}')
            if row.category != spec.category:
                diffs.append(f'category {row.category!r}≠{spec.category!r}')
            depends_db = set(row.depends.values_list('code', flat=True))
            if depends_db != set(spec.depends):
                diffs.append(
                    f'depends {sorted(depends_db)}≠{sorted(spec.depends)}')
            if diffs:
                result.append(f'{code}: ' + ' · '.join(diffs))
        return result

    @transaction.atomic
    def _prune(self, stale_modules, stale_caps, db_modules, db_caps):
        """Retira lo no declarado, protegiendo lo que una company contrató.

        El orden importa: las capacidades primero, porque ``Capability.module``
        es ``PROTECT`` y una capacidad viva impediría retirar su módulo.
        """
        for code in stale_caps:
            db_caps[code].delete()
        if stale_caps:
            self.stdout.write(f'Retiradas {len(stale_caps)} capacidad(es).')

        with_subscription = set(
            CompanyModuleSubscription.objects
            .filter(module__code__in=stale_modules)
            .values_list('module__code', flat=True)
        )
        removed = 0
        for code in stale_modules:
            if code in with_subscription:
                self.stdout.write(self.style.WARNING(
                    f'  {code}: NO se retira — tiene suscripciones de company. '
                    f'Cancelarlas o volver a declararlo.'
                ))
                continue
            db_modules[code].delete()
            removed += 1
        if removed:
            self.stdout.write(f'Retirados {removed} módulo(s).')

    def _report(self, title, items):
        if not items:
            return
        self.stdout.write(self.style.WARNING(f'{title} ({len(items)}):'))
        for item in items:
            self.stdout.write(f'  - {item}')
