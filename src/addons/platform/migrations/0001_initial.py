import addons.base_vat.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("account", "0001_initial"),
        ("authz", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(unique=True, verbose_name="Código")),
                ("name", models.CharField(max_length=150, verbose_name="Nombre")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("trial", "En prueba"),
                            ("active", "Activo"),
                            ("suspended", "Suspendido"),
                            ("cancelled", "Cancelado"),
                        ],
                        default="trial",
                        max_length=12,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "is_system",
                    models.BooleanField(
                        default=False,
                        help_text="Company de datos compartidos de plataforma (L0), no un tenant.",
                        verbose_name="Company de sistema",
                    ),
                ),
                (
                    "billing_email",
                    models.EmailField(
                        blank=True,
                        default="",
                        max_length=254,
                        verbose_name="Correo de facturación",
                    ),
                ),
                (
                    "billing_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=150,
                        verbose_name="Razón social",
                    ),
                ),
                (
                    "tax_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="RFC del SAT (12 moral / 13 física). Validado por base_vat.",
                        max_length=30,
                        validators=[addons.base_vat.validators.validate_rfc],
                        verbose_name="RFC / Tax ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "Empresa",
                "verbose_name_plural": "Empresas",
                "db_table": "company",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="CompanyModuleSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("trial", "En prueba"),
                            ("active", "Activo"),
                            ("suspended", "Suspendido"),
                            ("cancelled", "Cancelado"),
                        ],
                        default="active",
                        max_length=12,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Inicio"),
                ),
                (
                    "expires_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Expira"),
                ),
                (
                    "billing_cycle",
                    models.CharField(
                        blank=True,
                        choices=[("monthly", "Mensual"), ("annual", "Anual")],
                        default="",
                        max_length=8,
                        verbose_name="Ciclo de cobro",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Precio",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="platform.company",
                        verbose_name="Empresa",
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="authz.module",
                        verbose_name="Módulo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Suscripción de módulo",
                "verbose_name_plural": "Suscripciones de módulo",
                "db_table": "company_module_subscription",
                "ordering": ["company__code", "module__code"],
                "unique_together": {("company", "module")},
            },
        ),
        migrations.CreateModel(
            name="SubscriptionBillingRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.CharField(max_length=7, verbose_name="Periodo")),
                (
                    "triggered_by",
                    models.CharField(
                        choices=[
                            ("time", "Planificador (Actor Tiempo)"),
                            ("operator", "Corrida manual del operador"),
                        ],
                        default="time",
                        max_length=8,
                        verbose_name="Disparada por",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Inicio"),
                ),
                (
                    "finished_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Fin"),
                ),
                (
                    "invoices_issued",
                    models.IntegerField(default=0, verbose_name="Facturas emitidas"),
                ),
                (
                    "amount_charged",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=12,
                        verbose_name="Monto cobrado",
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        default="MXN", max_length=3, verbose_name="Moneda"
                    ),
                ),
                (
                    "failures",
                    models.IntegerField(default=0, verbose_name="Cobros fallidos"),
                ),
            ],
            options={
                "verbose_name": "Corrida de facturación",
                "verbose_name_plural": "Corridas de facturación",
                "db_table": "subscription_billing_run",
                "ordering": ["-started_at"],
                "indexes": [
                    models.Index(
                        fields=["period"], name="subscriptio_period_f11bdd_idx"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Subsidiary",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150, verbose_name="Nombre")),
                (
                    "country",
                    models.CharField(
                        blank=True, default="", max_length=2, verbose_name="País"
                    ),
                ),
                (
                    "base_currency",
                    models.CharField(
                        blank=True,
                        default="MXN",
                        max_length=3,
                        verbose_name="Moneda base",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Activa")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subsidiaries",
                        to="platform.company",
                        verbose_name="Empresa (tenant)",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="platform.subsidiary",
                        verbose_name="Subsidiaria padre",
                    ),
                ),
            ],
            options={
                "verbose_name": "Subsidiaria",
                "verbose_name_plural": "Subsidiarias",
                "db_table": "org_subsidiary",
                "ordering": ["company__code", "name"],
            },
        ),
        migrations.CreateModel(
            name="CompanySetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=255, verbose_name="Clave")),
                ("value", models.TextField(verbose_name="Valor")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settings",
                        to="platform.company",
                        verbose_name="Empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración de empresa",
                "verbose_name_plural": "Configuraciones de empresa",
                "db_table": "company_setting",
                "ordering": ["company_id", "key"],
                "unique_together": {("company", "key")},
            },
        ),
        migrations.CreateModel(
            name="ModulePrice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "billing_cycle",
                    models.CharField(
                        choices=[("monthly", "Mensual"), ("annual", "Anual")],
                        max_length=8,
                        verbose_name="Ciclo de cobro",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Precio"
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        default="MXN", max_length=3, verbose_name="Moneda"
                    ),
                ),
                ("effective_from", models.DateTimeField(verbose_name="Vigente desde")),
                (
                    "effective_to",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Vigente hasta"
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prices",
                        to="authz.module",
                        verbose_name="Módulo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tarifa de módulo",
                "verbose_name_plural": "Tarifas de módulo",
                "db_table": "module_price",
                "ordering": ["module__code", "billing_cycle", "-effective_from"],
                "indexes": [
                    models.Index(
                        fields=["module", "billing_cycle", "effective_from"],
                        name="module_pric_module__7622e7_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionInvoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.CharField(max_length=7, verbose_name="Periodo")),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Monto"
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        default="MXN", max_length=3, verbose_name="Moneda"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Borrador"),
                            ("issued", "Emitida"),
                            ("paid", "Pagada"),
                            ("failed", "Cobro fallido"),
                            ("void", "Anulada"),
                        ],
                        default="draft",
                        max_length=8,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "issued_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Emitida en"
                    ),
                ),
                (
                    "paid_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Pagada en"
                    ),
                ),
                (
                    "failure_reason",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Motivo de fallo",
                    ),
                ),
                (
                    "account_move",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="account.accountmove",
                        verbose_name="Asiento contable",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_invoices",
                        to="platform.company",
                        verbose_name="Empresa",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="platform.subscriptionbillingrun",
                        verbose_name="Corrida",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="platform.companymodulesubscription",
                        verbose_name="Suscripción",
                    ),
                ),
            ],
            options={
                "verbose_name": "Factura de suscripción",
                "verbose_name_plural": "Facturas de suscripción",
                "db_table": "subscription_invoice",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["company", "status"],
                        name="subscriptio_company_8cb2e1_idx",
                    ),
                    models.Index(fields=["run"], name="subscriptio_run_id_83d8c5_idx"),
                ],
                "unique_together": {("subscription", "period")},
            },
        ),
    ]
