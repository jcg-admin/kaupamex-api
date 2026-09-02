"""``base_sparse_field`` — los cinco símbolos que faltaban por portar.

Los tres de conversión de ``Serialized`` (``odoo19c:
base_sparse_field/models/fields.py:85-93``) y el ``write`` de ``IrModelFields``
(``models/models.py:29-39``).

Los de conversión no tocan la base: son métodos del campo. El de ``write`` sí,
porque su guarda relee la fila.
"""
import pytest

from addons.base.models.ir_model import (
    IrModel, IrModelFields, STATE_BASE, STATE_MANUAL)
from addons.base_sparse_field.models.fields import Serialized
from addons.base_sparse_field.models.ir_model_fields import SERIALIZED_TTYPE
from exceptions import UserError

#: El modelo de prueba del propio addon, igual que en ``test_ir_model_fields``.
MODEL_LABEL = 'base_sparse_field.SparseFieldsTest'


class TestSerializedConversion:
    """El protocolo de conversión, con los nombres de la fuente."""

    def test_convert_to_cache_passes_a_mapping_through_for_jsonb(self):
        """La fuente hace ``json.dumps``; aquí la columna es ``jsonb``."""
        field = Serialized()
        assert field.convert_to_cache({'integer': 7, 'char': 'x'}, None) == {
            'integer': 7, 'char': 'x'}

    def test_convert_to_cache_normalizes_falsy_to_none(self):
        """``value or None`` de la fuente, verbatim — un ``''`` no se guarda."""
        field = Serialized()
        assert field.convert_to_cache('', None) is None
        assert field.convert_to_cache(None, None) is None
        assert field.convert_to_cache(0, None) is None

    def test_convert_to_cache_leaves_a_non_mapping_alone(self):
        field = Serialized()
        assert field.convert_to_cache('{"a": 1}', None) == '{"a": 1}'

    def test_convert_to_column_insert_delegates_to_convert_to_cache(self):
        """Cuerpo verbatim de la fuente: delega, y ``values`` no participa."""
        field = Serialized()
        payload = {'boolean': True}
        assert (field.convert_to_column_insert(payload, None, values={'x': 1})
                == field.convert_to_cache(payload, None))

    def test_convert_to_record_returns_the_mapping_jsonb_gives_back(self):
        field = Serialized()
        assert field.convert_to_record({'float': 1.5}, None) == {'float': 1.5}

    def test_convert_to_record_still_parses_text(self):
        """La rama que la fuente usa siempre: de texto sale el mapa."""
        field = Serialized()
        assert field.convert_to_record('{"integer": 7}', None) == {'integer': 7}

    def test_convert_to_record_reads_null_as_an_empty_mapping(self):
        """El ``or "{}"`` de la fuente — la promesa se mantiene en las 3 ramas."""
        field = Serialized()
        assert field.convert_to_record(None, None) == {}
        assert field.convert_to_record('', None) == {}


@pytest.mark.django_db
class TestIrModelFieldsWrite:
    """``write`` — la guarda sobre los valores que ENTRAN."""

    @pytest.fixture(autouse=True)
    def _model_row(self):
        """La fila de ``ir.model`` que ``model_id`` exige (no admite nulo)."""
        self.model_row = IrModel.objects.create(
            model=MODEL_LABEL, name='Prueba de campos dispersos',
            state=STATE_BASE)


    def _a_field_row(self, **extra):
        """Fila en estado ``manual``, no ``base``.

        ``base`` cierra la escritura de un campo ``state='base'`` con su propia
        guarda (*"Las propiedades de un campo base no se alteran por esta
        vía"*), que corre ANTES que la de este addon. Medirla aquí mediría esa
        guarda y no la de ``write``, que es el sub-patrón D de
        ``metrica-decide-la-conclusion.md``.

        El nombre lleva el prefijo ``x_`` porque la restricción
        ``ir_model_fields_name_manual_field`` lo exige a todo campo manual —
        misma convención que ``x_plain`` en ``test_ir_model_fields``.
        """
        values = {'model': MODEL_LABEL, 'model_id': self.model_row,
                  'name': 'x_char', 'field_description': 'char',
                  'ttype': 'char', 'state': STATE_MANUAL}
        values.update(extra)
        return IrModelFields.objects.create(**values)

    def test_write_updates_a_plain_field(self):
        row = self._a_field_row()
        returned = row.write(field_description='Cadena')

        assert returned is row
        row.refresh_from_db()
        assert row.field_description == 'Cadena'

    def test_write_refuses_to_change_the_storing_system(self):
        """≙ *'Changing the storing system for field "%s" is not allowed.'*

        La aserción que **discrimina** es la segunda, no la excepción. El
        invariante está cubierto por dos capas —esta guarda y
        ``check_sparse_write``, colgada de ``save``— así que anular ésta deja
        la excepción intacta: medido, el control de neutralización daba
        ``41 passed`` con y sin ella.

        Lo que sólo esta guarda produce es que la instancia **no se toque**:
        corre antes del bucle de ``setattr``. Sin ella, ``self`` queda mutado y
        la excepción llega desde ``save``. Ver
        ``scripts/evidence/neutering-base-sparse-field-write-guard-*.txt``.
        """
        container = self._a_field_row(name='x_data', ttype=SERIALIZED_TTYPE)
        row = self._a_field_row()

        with pytest.raises(UserError):
            row.write(serialization_field_id=container)

        assert row.serialization_field_id_id is None

    def test_write_refuses_to_rename_a_sparse_field(self):
        """≙ *'Renaming sparse field "%s" is not allowed'*."""
        container = self._a_field_row(name='x_data', ttype=SERIALIZED_TTYPE)
        row = self._a_field_row()
        # Se ata al contenedor por la vía del reflejo, que no pasa por la
        # guarda — es el estado que la fuente supone al llegar a ``write``.
        IrModelFields.objects.filter(pk=row.pk).update(
            serialization_field_id=container)
        row.refresh_from_db()

        with pytest.raises(UserError):
            row.write(name='x_caracteres')

        # Discrimina esta guarda de la de ``save``: sin ella el ``setattr`` ya
        # habría corrido y ``row.name`` sería el nombre nuevo.
        assert row.name == 'x_char'

    def test_write_allows_renaming_a_field_that_is_not_sparse(self):
        """La asimetría de la fuente: renombrar sólo se prohíbe si es disperso."""
        row = self._a_field_row()
        row.write(name='x_caracteres')

        row.refresh_from_db()
        assert row.name == 'x_caracteres'

    def test_write_accepts_the_same_serialization_field_it_already_has(self):
        """La guarda mira el CAMBIO, no la presencia de la clave."""
        container = self._a_field_row(name='x_data', ttype=SERIALIZED_TTYPE)
        row = self._a_field_row()
        IrModelFields.objects.filter(pk=row.pk).update(
            serialization_field_id=container)
        row.refresh_from_db()

        row.write(serialization_field_id=container, field_description='Cadena')

        row.refresh_from_db()
        assert row.field_description == 'Cadena'
