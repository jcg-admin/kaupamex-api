"""Seed idempotente del catálogo authz — **recolector**, no fuente (#179).

**DEC-11 (sustantivo + nivel).** Las capacidades **CRUD** se siembran como
**sustantivo puro** (``catalogue``, ``payments``, …): el nivel de acceso
(``VIEW<CREATE<EDIT<FULL``) vive en ``RoleCapability.level``, no en el código.
El resolver expande ``noun@nivel → {noun.view, noun.create, noun.edit,
noun.full}`` (``addons.authz.services.resolve_capabilities``). Las **acciones
nombradas** (``account.*``, ``inventory.adjust``/``import``, ``reports.export``,
``platform.provision``) se siembran **con punto** (membresía, sin nivel).

**Qué cambió (SOL-100).** Este comando **ya no declara** el catálogo: lo
**recoge**. Cada addon declara sus ``ModuleSpec``/``CapabilitySpec`` en su
propio ``authz_catalog.py`` y ``addons.authz.declaration.discover()`` los junta
recorriendo ``INSTALLED_APPS``.

El motivo es medido, no estético: mientras las listas vivieron aquí, agregar un
addon no agregaba nada al catálogo —había que acordarse de editar este
archivo—, y el resultado fue H-API-106 (9 de 77 carpetas con ``Module.code``
homónimo; el código ``orders`` sobreviviendo al addon retirado en
``api@77bd1f0`` con cuatro aristas colgando). Con la declaración en el addon,
el catálogo nace y muere con su dueño.

El rol ``superadmin`` agrupa todas las capacidades a nivel FULL (default de
``RoleCapability``) y además hace *bypass* en el resolver. Idempotente
(``get_or_create``); re-ejecutable sin duplicar.

Uso: ``python manage.py seed_authz [--skip-checks]``.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from addons.authz.declaration import (
    discover, orphan_capabilities, unknown_depends,
)
from addons.authz.models import Capability, Module, Role
from addons.authz.services import BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE


class Command(BaseCommand):
    help = 'Siembra módulos, capacidades y el rol superadmin de addons.authz.'

    @transaction.atomic
    def handle(self, *args, **options):
        # Recolección: cada addon declara lo suyo en su authz_catalog.py.
        specs_modules, specs_caps = discover()

        # Dos checks ANTES de tocar la DB. Son el assert_valid_permission de
        # pretix aplicado a la declaración: sin ellos, una capacidad huérfana
        # rompe el seed con un KeyError opaco y una arista colgante no rompe
        # nada — que es exactamente cómo pasó H-API-106.
        huerfanas = orphan_capabilities(specs_modules, specs_caps)
        if huerfanas:
            raise CommandError(
                'Capacidades cuyo módulo nadie declara: '
                + ', '.join(huerfanas)
            )
        colgantes = unknown_depends(specs_modules)
        if colgantes:
            raise CommandError(
                'Aristas depends hacia un módulo no declarado: '
                + ', '.join(f'{o}->{d}' for o, d in colgantes)
            )

        modules = {}
        for code, spec in specs_modules.items():
            modules[code], _ = Module.objects.get_or_create(
                code=code, defaults={'name': spec.name},
            )

        # Metadata de catálogo L0 (#179). Idempotente; refresca filas ya
        # existentes. ``tier`` se deja en su default (free) — pricing es #180.
        for code, spec in specs_modules.items():
            mod = modules[code]
            if (mod.is_application != spec.is_application
                    or mod.category != spec.category):
                mod.is_application = spec.is_application
                mod.category = spec.category
                mod.save(update_fields=[
                    'is_application', 'category', 'updated_at',
                ])

        # Grafo de dependencias (SOL-085 S3). ``set`` es idempotente.
        for code, spec in specs_modules.items():
            if spec.depends:
                modules[code].depends.set([modules[d] for d in spec.depends])

        caps = []
        for code, spec in specs_caps.items():
            cap, _ = Capability.objects.get_or_create(
                code=code,
                defaults={
                    'module': modules[spec.module], 'name': spec.name,
                    'is_sensitive': spec.is_sensitive,
                },
            )
            caps.append(cap)

        # Superadmin: todas las capacidades. Las CRUD quedan a nivel FULL (default
        # de RoleCapability) → implican view/create/edit/full; las nombradas por
        # membresía. Además hace bypass en el resolver.
        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        role.capabilities.set(caps)

        # Rol base del comprador (DEC-AUTHZ-BUYER): las acciones nombradas
        # ``account.*`` que gobiernan el menú de cuenta dinámico.
        buyer_caps = [c for c in caps if c.code.startswith('account.')]
        buyer_role, _ = Role.objects.get_or_create(
            code=BUYER_ROLE_CODE, defaults={'name': 'Comprador'},
        )
        buyer_role.capabilities.set(buyer_caps)

        # Capacidades de "cuenta propia": todo usuario autenticado —incluido
        # staff no-superadmin— gestiona SU propia cuenta (perfil, contraseña,
        # baja, historial de pago). Se siembran en TODOS los roles para no dejar
        # a nadie fuera de su propia cuenta (DEC-ENF-01). ``add`` es idempotente.
        # DEC-ENF-01: capacidades de cuenta propia — se siembran en TODOS los
        # roles para que nadie quede fuera de su propia cuenta.
        # 'account.bus' entra aquí porque el endpoint del bus deriva el canal de
        # la sesión y sólo devuelve mensajes del propio usuario: gatearlo con una
        # capacidad de dominio (p. ej. notificaciones) dejaría sin eventos de pago
        # a quien no la tenga, siendo suyos.
        self_account_codes = {
            'account.profile', 'account.password', 'account.security',
            'account.deactivate', 'account.payments', 'account.bus',
        }
        self_account_caps = [c for c in caps if c.code in self_account_codes]
        roles_patched = 0
        for r in Role.objects.all():
            r.capabilities.add(*self_account_caps)
            roles_patched += 1

        self.stdout.write(self.style.SUCCESS(
            f'authz self-account caps sembradas en {roles_patched} roles.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'authz seed OK: {len(modules)} módulos, {len(caps)} capacidades '
            f'recolectadas de los authz_catalog.py de INSTALLED_APPS, '
            f'rol {SUPERADMIN_ROLE_CODE} con {role.capabilities.count()} y '
            f'rol {BUYER_ROLE_CODE} con {buyer_role.capabilities.count()}.'
        ))
