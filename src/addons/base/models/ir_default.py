"""``ir.default`` — valores por defecto de campo por usuario/empresa (Odoo
``base``).

Portación fiel de ``IrDefault``
(``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_default.py:13-236``,
Odoo 18; ``scratchpad/odoo19x/odoo/addons/base/models/ir_default.py:13-253``,
Odoo 19) — la **estructura de control** que persiste un valor por defecto
(serializado en JSON) para un campo de un modelo, opcionalmente acotado a un
usuario y/o una empresa, y opcionalmente condicionado. Parte de la iniciativa
``adaptar-familias-odoo-monolito-modular`` (SOL-096), ÚLTIMO ítem del backlog
de control núcleo ``ir.*`` (H-BASE-01 C-2). Premisa verificada por el
orquestador: ``ir_default`` AUSENTE de ``src/addons/base/models/`` antes de
este commit (``grep -rl "class IrDefault" src/addons/base/models/`` → vacío).

Drift 18→19 observado (ambas fuentes citadas arriba) — no afecta lo portado:

- **19 agrega ``_check_accessible_field_id()``** (19 líneas 44-52, ausente en
  18) — guardrail de control de acceso a nivel de campo (``_check_field_access``)
  invocado desde ``create``/``write``. Pertenece a la capa ACL de Odoo; en este
  monolito la autorización es DRF ``HasCapability`` (DEC-11) a nivel de vista,
  no a nivel de modelo — no aplica aquí.
- **``_evaluate_condition_with_fallback`` cambia de firma** (18 línea 223,
  ``condition`` como tupla de dominio única; 19 línea 237,
  ``field_expr, operator, value`` descompuestos + clase ``Domain``) — mecanismo
  de evaluación de *company-dependent fields* con valor de fallback. No se
  porta (ver más abajo): este monolito no tiene el concepto de campo
  "company-dependent" con fallback de Odoo.
- Los **campos** (``field_id``, ``user_id``, ``company_id``, ``condition``,
  ``json_value``) y el cuerpo de ``set``/``_get``/``_get_model_defaults`` son
  **idénticos** entre 18 y 19 (mismas líneas, mismo texto) — es la parte que
  se porta aquí.

Adaptación clave — ``field_id`` (FK a ``ir.model.fields``) se DROPEA
=====================================================================

Odoo modela el campo objetivo como ``field_id = fields.Many2one('ir.model.fields',
...)`` (18/19 línea 20-21). Este monolito **no porta** ``ir.model.fields``
(decisión H-BASE-08 del orquestador): Django ya provee introspección de
modelo/campo vía su registro de apps (``apps.get_model``) + ``ContentType``,
así que un registro paralelo tipo ``ir.model.fields`` sería duplicación
FRAMEWORK-UI. Sin el modelo destino no hay FK fiel que portar.

La adaptación fiel es almacenar el objetivo directamente como **``model``
(Char) + ``field`` (Char)** — mismo criterio que ``ir_filters.model_id``,
``ir_attachment.res_model``/``res_field`` e ``ir_cron.model_name`` (todos
Char plano, no FK real, resuelto en runtime por la capa de negocio que lo
consume). NO se crea ni se referencia ``ir.model``/``ir.model.fields``.

``json_value`` — ``Text``, no ``Char`` (drift deliberado vs. la firma de Odoo)
=====================================================================

Odoo declara ``json_value = fields.Char('Default Value (JSON format)',
required=True)`` (18/19 misma línea) **sin** parámetro ``size`` — un ``Char``
de Odoo sin ``size`` es una columna sin límite de longitud en PostgreSQL
(equivalente a ``TEXT`` de facto). Django's ``CharField`` **exige**
``max_length``; declarar uno acotado truncaría silenciosamente valores JSON
de estructuras grandes (listas, dicts anidados) — pérdida de datos. Se porta
como ``fields.Text`` (sin límite), mismo criterio que ``ir_filters.py`` usa
para ``domain``/``context`` (Char-sin-tamaño de Odoo → ``Text`` de Django
cuando el límite implícito importa; ``Char`` acotado cuando el campo de Odoo
es naturalmente corto, como ``ir_filters.sort``).

Precedencia de ``get_default`` — resuelta en Python, NO por ``ORDER BY`` SQL
=====================================================================

Odoo resuelve la precedencia (usuario+empresa > usuario > empresa > global)
con ``ORDER BY d.user_id, d.company_id, d.id`` (18/19, dentro de
``_get_model_defaults``) confiando en que PostgreSQL ordena ``NULL`` al
**final** en ``ASC`` (comportamiento default de Postgres: ``NULLS LAST``) —
así los valores no-nulos (más específicos) salen primero.

**MariaDB ordena ``NULL`` al PRINCIPIO en ``ASC``** (comportamiento default
opuesto a Postgres) — portar literalmente ese ``ORDER BY`` invertiría la
precedencia en este stack (el default global ganaría sobre el
usuario-específico). Este drift NO se replica: ``get_default`` resuelve la
precedencia con lookups secuenciales explícitos en Python (usuario+empresa →
usuario → empresa → global), sin depender del orden de ``NULL`` de ningún
motor. Candidato hallazgo H-BASE-NN (ver reporte del commit).

Alcance de esta portación — deliberadamente NO se porta
=====================================================================

- **``_check_json_format`` (constraint de validación de tipo)**: Odoo valida
  el JSON contra el tipo real del campo destino introspeccionando
  ``ir.model.fields``/``model._fields`` (``field.convert_to_cache``). Sin ese
  registro (ver arriba) no hay de dónde introspectar el tipo declarado; una
  validación equivalente usando ``apps.get_model(model)._meta.get_field(field)``
  es posible pero excede este slice — candidato H-BASE-NN.
- **``_get_model_defaults`` (dict batch por modelo + ``@tools.ormcache``)**:
  Odoo devuelve TODOS los defaults de un modelo en una sola consulta cacheada
  (18/19 líneas 156-189/170-203). Este slice sólo pide el lookup singular
  (``get_default``/``set_default`` por campo) — el batch + cache queda
  diferido, candidato H-BASE-NN si el volumen de llamadas lo justifica.
- **``discard_records``/``discard_values``/``_get_field_column_fallbacks``/
  ``_evaluate_condition_with_fallback``**: mecanismos atados a conceptos de
  Odoo sin equivalente en este monolito — *company-dependent fields* con
  valor de fallback computado (``get_company_dependent_fallback``,
  ``convert_to_column``) y el tipo ``Many2oneReference``/dominio de Odoo. No
  aplican sin esos conceptos.
- **Invalidación de caché ORM** (``env.invalidate_all()``,
  ``env.registry.clear_cache()``, ``@tools.ormcache`` en ``create``/``write``/
  ``unlink``): mecanismo de caché de campo por-registro de Odoo, sin
  equivalente en este monolito (no hay capa de caché de valores de campo
  portada). Omitido.
- **``_allow_sudo_commands = False`` / ``_check_accessible_field_id`` (19)**:
  guardrails de control de acceso de la capa ACL de Odoo — ver nota de drift
  18→19 arriba; la autorización de este proyecto es DRF ``HasCapability``
  (DEC-11) a nivel de vista.

Comportamiento SÍ portado (adaptado a classmethods planos, no a los
decoradores ``@api.model``/``@tools.ormcache`` de Odoo):

- ``set_default(model, field, value, user=None, company=None, condition='')``
  — adaptación de ``set()`` (18/19 líneas 66-124/80-138): serializa ``value``
  a JSON y hace upsert atómico (``update_or_create``) sobre el alcance
  ``(model, field, user, company, condition)`` — mismo invariante "cualquier
  entrada para el mismo alcance se reemplaza" que Odoo.
- ``get_default(model, field, user=None, company=None, condition='')`` —
  adaptación de ``_get()`` (18/19 líneas 126-154/140-168): decodifica el JSON
  del default más específico según la precedencia usuario+empresa > usuario >
  empresa > global (ver nota de precedencia arriba), o ``None`` si no hay
  ninguno.

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``, NULL =
default para todos los usuarios). ``company`` → ``company.Company`` (Odoo
``company_id``, NULL = default para todas las empresas) — mismo criterio que
``ir_attachment.company``/``ir_sequence.company``.
"""
import json

from django.conf import settings

import fields
import models


class IrDefault(models.Model):
    """``ir.default`` — valor por defecto de un campo, acotado por usuario/
    empresa/condición. Ver docstring del módulo para el drift respecto a
    Odoo (``field_id`` FK dropeada → ``model``/``field`` Char; precedencia
    resuelta en Python, no por ``ORDER BY`` SQL)."""

    model = fields.Char(
        max_length=128,
        help_text=(
            'Modelo técnico objetivo, p. ej. "orders.Order" (adaptación del '
            'field_id.model_id delegado de Odoo — aquí Char plano, mismo '
            'criterio que ir_filters.model_id / ir_cron.model_name: no es FK '
            'real, ver docstring del módulo).'
        ),
    )
    field = fields.Char(
        max_length=128,
        help_text=(
            'Nombre del campo del modelo objetivo (adaptación del '
            'field_id.name delegado de Odoo — Char plano, no FK real, ver '
            'docstring del módulo).'
        ),
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='ir_defaults',
        help_text=(
            'Usuario al que aplica el default (Odoo user_id). NULL = default '
            'para todos los usuarios.'
        ),
    )
    company = fields.Many2one(
        'company.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='ir_defaults',
        help_text=(
            'Empresa a la que aplica el default (Odoo company_id). NULL = '
            'default para todas las empresas.'
        ),
    )
    condition = fields.Char(
        max_length=256, blank=True, default='',
        help_text=(
            'Condición opcional que acota la aplicabilidad del default '
            '(Odoo condition — string opaco para este modelo de control).'
        ),
    )
    json_value = fields.Text(
        help_text=(
            'Valor por defecto serializado en JSON (Odoo json_value — Text '
            'en vez de Char porque Odoo lo declara sin límite de tamaño, ver '
            'docstring del módulo).'
        ),
    )

    class Meta:
        db_table = 'ir_default'
        ordering = ['model', 'field', '-id']
        verbose_name = 'Valor por defecto'
        verbose_name_plural = 'Valores por defecto'
        constraints = [
            models.UniqueConstraint(
                fields=['model', 'field', 'user', 'company', 'condition'],
                name='uq_ir_default_model_field_user_company_condition',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.model}.{self.field}'

    @classmethod
    def set_default(cls, model, field, value, user=None, company=None, condition=''):
        """Define el valor por defecto de ``model.field`` para el alcance
        ``(user, company, condition)`` — adaptación de ``set()`` de Odoo (ver
        docstring del módulo). Cualquier entrada previa para el mismo alcance
        se reemplaza (``update_or_create`` sobre las columnas del
        ``UniqueConstraint``)."""
        condition = condition or ''
        json_value = json.dumps(value, ensure_ascii=False)
        default, _created = cls.objects.update_or_create(
            model=model, field=field, user=user, company=company, condition=condition,
            defaults={'json_value': json_value},
        )
        return default

    @classmethod
    def get_default(cls, model, field, user=None, company=None, condition=''):
        """Devuelve el valor por defecto de ``model.field`` para el usuario/
        empresa dados, o ``None`` si no hay ninguno — adaptación de ``_get()``
        de Odoo (ver docstring del módulo).

        Precedencia (más específico gana): usuario+empresa > usuario >
        empresa > global. Resuelta con lookups secuenciales explícitos, no
        con el ``ORDER BY d.user_id, d.company_id`` de Odoo — ver nota de
        precedencia en el docstring del módulo (drift de orden de ``NULL``
        entre PostgreSQL y MariaDB)."""
        condition = condition or ''
        scopes = []
        if user is not None and company is not None:
            scopes.append({'user': user, 'company': company})
        if user is not None:
            scopes.append({'user': user, 'company': None})
        if company is not None:
            scopes.append({'user': None, 'company': company})
        scopes.append({'user': None, 'company': None})

        for scope in scopes:
            default = cls.objects.filter(
                model=model, field=field, condition=condition, **scope,
            ).first()
            if default is not None:
                return json.loads(default.json_value)
        return None
