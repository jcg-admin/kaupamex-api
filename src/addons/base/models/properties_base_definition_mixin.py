"""``properties.base.definition.mixin`` — propiedades de usuario sin padre.

Adaptación de ``odoo/addons/base/models/properties_base_definition_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 56 líneas). Un modelo que hereda este
mixin gana un campo ``properties`` —pares clave/valor definidos por el
usuario— cuyo **esquema** vive en una fila de ``properties.base.definition``,
no en el padre del registro.

Archivo propio, como en la referencia
=====================================

La referencia tiene ``image_mixin.py``, ``avatar_mixin.py`` y éste: **un
archivo por mixin**, no un ``mixins.py`` que los agrupe por naturaleza. Este
árbol ya sigue esa forma (``timestamped_mixin.py``, ``append_only_mixin.py``,
``soft_delete_mixin.py``, ``image_mixin.py``, ``avatar_mixin.py``), y este
archivo la completa.

Por qué el vínculo es derivado y no una columna
==============================================

``properties_base_definition_id`` es ``compute`` **sin** ``store`` en la
referencia, y la razón se lee en su propio cómputo: la definición **no
depende del registro**, depende de *(modelo, nombre del campo)*. Todas las
filas de un mismo modelo comparten exactamente la misma definición.

Guardarlo como columna sería replicar el mismo id en cada fila y abrir la
puerta a que dos filas del mismo modelo apunten a definiciones distintas —un
estado que el modelo no admite—. Aquí es una **propiedad** derivada, que es lo
que un ``compute`` sin ``store`` significa.

Su ``_search_properties_base_definition_id`` lo confirma: no filtra fila por
fila, devuelve ``TRUE`` o ``FALSE`` **para todo el modelo** según si el id
buscado es el suyo.

Qué NO se porta, con su medición
================================

- **``_field_to_sql``**: enseña al motor de consultas de Odoo a emitir el id
  de la definición como constante para que la exportación funcione. Es una
  optimización atada a su constructor de SQL; en Django la propiedad se lee
  en Python y no hay consulta que reescribir.
- **``create`` inyectando ``properties_base_definition_id`` en los valores**:
  allá hace falta para que el ORM aplique los valores por defecto de las
  propiedades al crear. Aquí el vínculo es derivado y siempre está disponible,
  así que no hay nada que inyectar; lo que sí se porta es
  ``ensure_definition()``, que garantiza que la fila de definición exista.
"""
import logging

import fields
import models

from addons.base.models.properties_base_definition import (
    PropertiesBaseDefinition,
)

_logger = logging.getLogger(__name__)

#: Nombre del campo de propiedades que este mixin aporta. La definición se
#: resuelve por *(modelo, este nombre)*, no por registro.
PROPERTIES_FIELD_NAME = 'properties'


class PropertiesBaseDefinitionMixin(models.Model):
    """Mixin que añade propiedades **sin padre** a un modelo."""

    properties = fields.Json(
        default=dict, blank=True, verbose_name='Propiedades',
        help_text='Pares clave/valor definidos por el usuario. Su esquema vive '
                  'en properties.base.definition, resuelto por (modelo, '
                  'campo) — no por registro.',
    )

    class Meta:
        abstract = True

    @classmethod
    def properties_model_label(cls):
        """El nombre técnico del modelo, tal como lo guarda ``ir.model.fields``."""
        return f'{cls._meta.app_label}.{cls._meta.object_name}'

    @classmethod
    def ensure_definition(cls):
        """La fila de definición de este modelo, creándola si falta.

        Equivale a lo que el ``create`` de la fuente garantiza al insertar:
        que exista una definición a la que referirse. Aquí no hace falta
        inyectarla en cada registro — ver el docstring del módulo.
        """
        return PropertiesBaseDefinition.definition_for(
            cls.properties_model_label(), PROPERTIES_FIELD_NAME)

    @property
    def properties_base_definition(self):
        """``_compute_properties_base_definition_id`` — derivado, no columna.

        La definición depende de *(modelo, campo)*, no del registro: todas las
        filas de este modelo comparten la misma. Ver el docstring del módulo
        sobre por qué guardarla sería un error.
        """
        return type(self).ensure_definition()

    @classmethod
    def matches_definition(cls, definition_ids):
        """``_search_properties_base_definition_id`` — para todo el modelo.

        No filtra fila por fila: devuelve si la definición de **este modelo**
        está entre las buscadas. Es lo que hace la fuente devolviendo
        ``Domain.TRUE`` o ``Domain.FALSE``.
        """
        if not isinstance(definition_ids, (list, tuple, set, frozenset)):
            definition_ids = (definition_ids,)
        own = PropertiesBaseDefinition.definition_id_for(
            cls.properties_model_label(), PROPERTIES_FIELD_NAME)
        return own in definition_ids
