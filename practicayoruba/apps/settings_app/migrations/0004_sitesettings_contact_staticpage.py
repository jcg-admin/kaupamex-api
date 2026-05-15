"""Sprint 10: UC-CFG-04 (StaticPage/Version) y UC-CFG-05 (campos contacto en SiteSettings)."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('settings_app', '0003_paymentgateway_shippingmethod'),
    ]

    operations = [
        # UC-CFG-05: campos de contacto en SiteSettings
        migrations.AddField(
            model_name='sitesettings',
            name='support_email',
            field=models.EmailField(blank=True, default='', max_length=254,
                                    verbose_name='Email de soporte'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=30,
                                   verbose_name='Telefono de contacto'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='address',
            field=models.TextField(blank=True, default='', verbose_name='Direccion fisica'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='social_links',
            field=models.JSONField(blank=True, default=dict, verbose_name='Redes sociales'),
        ),
        # UC-CFG-04: páginas estáticas
        migrations.CreateModel(
            name='StaticPage',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('slug',       models.SlugField(
                    max_length=20, unique=True,
                    choices=[('about','Acerca de nosotros'),('terms','Términos y condiciones'),
                             ('privacy','Política de privacidad'),
                             ('returns','Política de devoluciones'),('faq','Preguntas frecuentes')],
                )),
                ('title',      models.CharField(max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'settings_static_page', 'verbose_name': 'Página estática'},
        ),
        migrations.CreateModel(
            name='StaticPageVersion',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('version',    models.PositiveIntegerField(verbose_name='Número de versión')),
                ('content',    models.TextField(verbose_name='Contenido HTML')),
                ('status',     models.CharField(
                    max_length=12, db_index=True, default='DRAFT',
                    choices=[('DRAFT','Borrador'),('PUBLISHED','Publicado'),('ARCHIVED','Archivado')],
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('publish_at', models.DateTimeField(blank=True, null=True,
                                                    verbose_name='Publicar en fecha futura')),
                ('page',       models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions', to='settings_app.staticpage',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='static_page_versions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'settings_static_page_version',
                'ordering': ['-version'],
                'verbose_name': 'Versión de página estática',
            },
        ),
        migrations.AddConstraint(
            model_name='staticpageversion',
            constraint=models.UniqueConstraint(
                fields=['page', 'version'], name='unique_page_version'
            ),
        ),
    ]
