"""Conserva rutas históricas y enlaza el árbol sin fusionar identidades."""
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError
from django.db.models.functions import Length


def _xml_id(segments):
    """Algoritmo de la referencia abe4040e, congelado para esta migración."""
    return 'module_category_' + '_'.join(
        part.lower() for part in segments
    ).replace('&', 'and').replace(' ', '_')


def populate_category_tree(apps, schema_editor):
    using = schema_editor.connection.alias
    module = apps.get_model('base', 'IrModule')
    category = apps.get_model('base', 'IrModuleCategory')
    identity = apps.get_model('base', 'IrModelData')
    modules = module.objects.using(using)
    categories = category.objects.using(using)
    identities = identity.objects.using(using)
    label = category._meta.label
    name_limit = identity._meta.get_field('name').max_length
    sources = {}

    # Preflight completo antes de escribir datos; DDL y datos se revierten
    # juntos si dos rutas históricas normalizan a una misma identidad.
    for path in modules.values_list('category_path', flat=True).distinct():
        prefix = []
        for segment in path.split('/') if path else []:
            prefix.append(segment)
            xml_id = _xml_id(prefix)
            source = tuple(prefix)
            previous = sources.setdefault(xml_id, source)
            if previous != source:
                raise RuntimeError(f'colisión de rutas históricas: base.{xml_id}.')
            if name_limit is not None and len(xml_id) > name_limit:
                raise RuntimeError(f'Identidad de categoría supera {name_limit} caracteres.')

    for row in modules.order_by('pk').iterator():
        parent_id = None
        prefix = []
        for segment in row.category_path.split('/') if row.category_path else []:
            prefix.append(segment)
            xml_id = _xml_id(prefix)
            external = identities.select_for_update().filter(
                module='base', name=xml_id,
            ).first()
            if external is not None:
                node = categories.filter(pk=external.res_id).first()
                if (external.model != label or node is None
                        or node.parent_id != parent_id):
                    raise RuntimeError(f'Identidad histórica incompatible: base.{xml_id}.')
            else:
                node = categories.create(name=segment, parent_id=parent_id)
                identities.create(
                    module='base', name=xml_id, model=label,
                    res_id=node.pk, noupdate=True,
                )
            parent_id = node.pk
        modules.filter(pk=row.pk).update(category_id=parent_id)


def guard_reverse(apps, schema_editor):
    using = schema_editor.connection.alias
    module = apps.get_model('base', 'IrModule')
    identity = apps.get_model('base', 'IrModelData')
    category = apps.get_model('base', 'IrModuleCategory')
    modules = module.objects.using(using)
    if modules.annotate(path_length=Length('category_path')).filter(
            path_length__gt=100).exists():
        raise IrreversibleError('La reversión truncaría rutas de más de 100 caracteres.')
    for row in modules.exclude(category_id=None).iterator():
        if not row.category_path or not identity.objects.using(using).filter(
                module='base', name=_xml_id(row.category_path.split('/')),
                model=category._meta.label, res_id=row.category_id).exists():
            raise IrreversibleError(
                'La relación de categoría no puede reconstruirse desde su ruta.')


class Migration(migrations.Migration):
    dependencies = [('base', '0089_demo_failure_error_length')]
    operations = [
        migrations.RenameField(
            model_name='irmodule', old_name='category', new_name='category_path',
        ),
        migrations.AlterField(
            model_name='irmodule', name='category_path',
            field=models.CharField(
                blank=True, default='Uncategorized', editable=False,
                help_text='Ruta original del manifiesto; preserva historia y contrato HTTP.',
            ),
        ),
        migrations.AddField(
            model_name='irmodule', name='category',
            field=models.ForeignKey(
                to='base.irmodulecategory', on_delete=models.PROTECT,
                null=True, blank=True, related_name='modules',
                help_text='Odoo category_id: hoja del árbol técnico de categorías.',
            ),
        ),
        migrations.RunPython(populate_category_tree, guard_reverse),
    ]
