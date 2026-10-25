"""El setup relacionado debe invalidar mapas derivados de declaraciones previas."""
import pytest
from django.db import models
from django.test.utils import isolate_apps

from orm import model_classes, registry


@pytest.fixture
def late_related_model(monkeypatch):
    """Aísla declaraciones reales sin crear tablas ni alterar modelos productivos."""
    with isolate_apps():
        class RelatedSetupSample(models.Model):
            source = models.CharField()
            projected = models.CharField(related='source')

            class Meta:
                app_label = 'base'

        monkeypatch.setattr(
            model_classes.apps, 'get_models',
            lambda **kwargs: [RelatedSetupSample],
        )
        registry.clear_field_depends()
        try:
            yield RelatedSetupSample
        finally:
            registry.clear_field_depends()
            # Los modelos productivos conservan sus propias marcas; la próxima
            # lectura vuelve a comprobarlas con el registro Django restaurado.
            model_classes.ensure_field_setup.pending = True


def test_related_compute_joins_a_group_built_before_setup(late_related_model):
    field = late_related_model._meta.get_field('projected')
    assert field.compute is None
    assert field not in registry.field_computed

    assert model_classes.ensure_field_setup() > 0

    assert callable(field.compute)
    assert registry.field_computed[field] == [field]


def test_setup_without_pending_models_keeps_the_derived_map(late_related_model):
    model_classes.ensure_field_setup()
    field = late_related_model._meta.get_field('projected')
    group = registry.field_computed[field]

    assert model_classes.ensure_field_setup() == 0
    assert registry.field_computed[field] is group


def test_noncomputed_field_still_fails_closed(late_related_model):
    model_classes.ensure_field_setup()
    field = late_related_model._meta.get_field('source')

    with pytest.raises(KeyError):
        registry.field_computed[field]
