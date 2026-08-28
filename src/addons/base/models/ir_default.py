"""``ir.default`` — valores por defecto de campo por usuario/empresa (Odoo
``base``).

Portación de ``IrDefault`` (``odoo19c: odoo/addons/base/models/ir_default.py``)
— la estructura de control que persiste un valor por defecto, serializado en
JSON, para un campo de un modelo, opcionalmente acotado a un usuario y/o una
empresa, y opcionalmente condicionado.

Los doce símbolos de la fuente están **todos** portados (tarea #128). Hasta
este pase había cuatro, y los ocho restantes se declaraban fuera de alcance por
razones que ya no se sostenían — ver la sección de abajo.

Las dos adaptaciones de forma, y por qué
========================================

**1. ``field_id`` (FK a ``ir.model.fields``) se guarda como ``model`` +
``field`` (Char).** La fuente modela el campo objetivo con
``field_id = fields.Many2one('ir.model.fields', ...)``. Aquí el objetivo se
almacena como dos columnas de texto, mismo criterio que ``ir_filters.model_id``,
``ir_attachment.res_model``/``res_field`` e ``ir_cron.model_name``.

``ir.model.fields`` **sí existe** en este árbol desde el porte de
``ir_model.py`` (medido: ``grep -rn "^class IrModelFields\b" src/`` → 1 clase),
así que la conversión a FK real es posible; lo que la difiere es que migra esta
tabla y va en su propio pase, igual que ``ir_filters.action_id``.

Consecuencia para los métodos que la fuente resuelve por la FK: aquí el tipo,
la relación y el modelo del campo se **introspeccionan del registro de Django**
(``apps.get_model(model)._meta.get_field(field)``), que es la misma información
por otra vía. Es lo que hacen ``_check_json_format``, ``discard_records`` y
``_get_field_column_fallbacks``.

**2. ``json_value`` es ``Text``, no ``Char``.** La fuente declara
``fields.Char(...)`` **sin** ``size``, que en PostgreSQL es una columna sin
límite. ``CharField`` de Django exige ``max_length``, y uno acotado truncaría en
silencio un JSON de estructura grande. Mismo criterio que ``ir_filters.domain``.

La precedencia se resuelve en Python, y ya no por el motor
==========================================================

La fuente ordena con ``ORDER BY d.user_id, d.company_id, d.id`` y confía en que
PostgreSQL ponga los ``NULL`` al final en ``ASC``, de modo que lo específico
salga primero. Aquí la prioridad se calcula por fila.

> **Corregido.** Este párrafo justificaba la divergencia diciendo que *"MariaDB
> ordena NULL al PRINCIPIO"*. El motor es PostgreSQL desde ADR-028, así que esa
> razón **caducó con su mecanismo**. Lo que sostiene la divergencia hoy es otra
> cosa, y es más débil: calcular la prioridad por fila no depende de una
> garantía del motor y se lee igual en los dos métodos que la usan
> (``_get_model_defaults`` y ``_get``). Volver al ``ORDER BY`` de la fuente
> sería igual de correcto contra PostgreSQL — es una decisión de forma, no una
> imposición del stack, y así queda declarada.

Lo que se construyó en este pase — y las razones que ya no valían
=================================================================

- **``_check_json_format``** — decía *"sin ese registro no hay de dónde
  introspectar el tipo declarado"*. Falso por dos vías: ``ir.model.fields``
  existe, y el registro de Django siempre estuvo ahí. Construido con
  ``apps.get_model``.
- **``_check_accessible_field_id``** — decía *"la autorización de este proyecto
  es DRF ``HasCapability`` a nivel de vista"*. Eso describe **otra** capa: la
  ACL de modelo y las reglas de fila se adoptaron en la tarea #93
  (``_check_access``, ``check_access``), y ``_check_field_access`` vive en
  ``orm/models.py``. Construido.
- **``create``/``write``/``unlink``** — decían que la invalidación de caché
  *"no tiene equivalente en este monolito"*. Lo tiene: ``registry.clear_cache``
  existe desde ``api@c636e68c`` y ``set_default`` ya lo llamaba. Construidos, y
  además ``save``/``delete`` invalidan — son el camino de escritura real de
  Django, y dejarlos fuera habría hecho que la guarda se saltara sin que nadie
  lo notara.
- **``discard_records``/``discard_values``** — su razón era *"no aplican sin
  esos conceptos"*, nombrando los campos dependientes de empresa; el concepto
  se construyó en la tarea #111. Construidos.
- **``_get_field_column_fallbacks``/``_evaluate_condition_with_fallback``** —
  el segundo exigía ``filtered_domain``, que **no existía** en el árbol. Ya
  existe: se construyó en este mismo pase (``orm/models.py``,
  ``orm/domains.py::_as_predicate``, ``orm/fields.py::filter_function``).
- **``set``/``_get``** — existían con los nombres ``set_default``/
  ``get_default``. Renombrados a los de la fuente: el guion bajo de ``_get`` es
  el contrato (``porte-completo-no-parcial.md``), y ``set_default`` publicaba
  como API un nombre que la fuente no tiene.

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``, NULL =
default para todos los usuarios). ``company`` → ``base.ResCompany`` (Odoo
``company_id``, NULL = default para todas las empresas).
"""
import json

from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import DEFAULT_DB_ALIAS

import fields
import models
from orm import registry
from orm.domains import Domain
from orm.environments import get_current_company, is_su
from orm.models import filtered_domain
from orm.utils import parse_field_expr
from tools.cache import ormcache


class IrDefault(models.Model):
    """``ir.default`` — valor por defecto de un campo, acotado por usuario/
    empresa/condición. Ver docstring del módulo para el drift respecto a
    Odoo (``field_id`` FK dropeada → ``model``/``field`` Char; precedencia
    resuelta en Python, no por ``ORDER BY`` SQL)."""

    # Los cuatro atributos de clase que la referencia declara
    # (``atributos-de-clase-de-modelo.md``; medidos con el recorrido AST que
    # esa regla fija). ``_rec_name`` diverge: allá apunta a ``field_id``, la FK
    # que este puerto no tiene — aquí es el ``field`` Char que la sustituye, el
    # mismo drift que el docstring del módulo ya declara.
    _name = 'ir.default'
    _description = 'Default Values'
    _rec_name = 'field'
    _allow_sudo_commands = False

    model = fields.Char(
        max_length=128,
        help_text=(
            'Modelo técnico objetivo, p. ej. "sale.SaleOrder" (adaptación del '
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
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
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

    # === introspección del campo objetivo ==================================
    #
    # Los tres métodos que la fuente resuelve navegando ``field_id`` —su FK a
    # ``ir.model.fields``— aquí lo resuelven contra el registro de Django. Es
    # la misma información por otra vía; ver la adaptación 1 del docstring.

    def _target_field(self):
        """El campo de Django al que apunta esta fila, o ``None``.

        Devuelve ``None`` cuando el modelo o el campo ya no existen: una fila
        de ``ir.default`` puede sobrevivir al símbolo que nombraba, y eso no
        es un error de la fila sino un dato caduco.
        """
        try:
            target_model = apps.get_model(self.model)
        except (LookupError, ValueError):
            return None
        try:
            return target_model._meta.get_field(self.field)
        except FieldDoesNotExist:
            return None

    def _check_json_format(self):
        """El JSON guardado tiene que caber en el tipo del campo — ≙ ``:34``.

        La fuente decodifica y pasa el valor por ``field.convert_to_cache``,
        que levanta si el tipo no encaja. Aquí lo hace ``field.to_python``,
        que es el mismo contrato de Django: convertir o levantar
        ``ValidationError``.

        Se llama desde :meth:`clean`, que es donde Django corre las
        validaciones de modelo — el equivalente de ``@api.constrains``.
        """
        try:
            value = json.loads(self.json_value)
        except (TypeError, json.JSONDecodeError):
            raise ValidationError(
                'Formato JSON inválido en el valor por defecto.')

        target_field = self._target_field()
        if target_field is None:
            # El campo ya no existe: no hay tipo contra el que validar. No es
            # un JSON mal formado, así que no se rechaza por esta vía.
            return
        if value is None:
            return
        try:
            target_field.to_python(value)
        except (ValidationError, TypeError, ValueError):
            raise ValidationError(
                f'Valor inválido en el campo de valor por defecto. Se '
                f'esperaba el tipo {type(target_field).__name__!r} para '
                f'{self.model}.{self.field}.')

    def _check_accessible_field_id(self):
        """Quien escribe el default tiene que poder escribir el campo.

        ≙ ``_check_accessible_field_id`` (``:43-51``). Bajo elevación no
        comprueba nada, igual que allá (``if self.env.su: return``).

        Lo que esto cierra: la razón anterior para omitirlo decía que *"la
        autorización de este proyecto es DRF ``HasCapability`` a nivel de
        vista"*. Eso es cierto y **describe otra capa**. Sin este check, quien
        no puede escribir un campo puede fijar su valor por defecto — que es
        escribirlo para todos.
        """
        if is_su():
            return
        target_field = self._target_field()
        if target_field is None:
            return
        target_model = apps.get_model(self.model)
        if not hasattr(target_model, '_check_field_access'):
            # El check vive en ``FieldSqlMixin``, y no todo modelo lo adopta
            # todavía (tarea **#96**). Sin el mixin no hay a quién preguntar;
            # decirlo aquí es mejor que fingir que se comprobó.
            return
        # La fuente lo llama sobre ``self.env[field.model]``, un recordset
        # vacío. Aquí el equivalente es una instancia sin guardar: el método
        # sólo usa ``_meta`` y el permiso del usuario activo, no la fila.
        target_model()._check_field_access(target_field, 'write')

    def clean(self):
        """Valida antes de guardar — el hogar de ``@api.constrains`` aquí."""
        super().clean()
        self._check_json_format()

    # === escritura: la caché se invalida en el camino real =================

    def save(self, *args, **kwargs):
        """Guarda e invalida lo memorizado.

        La fuente pone la invalidación en ``create``/``write``
        (``:53-70``). Aquí va **también** en ``save``, que es el camino de
        escritura real de Django: un ``instancia.save()`` no pasa por
        ``create`` ni por ``write``, así que dejar la guarda sólo en aquéllos
        la haría saltarse sin que nada lo delatara.
        """
        result = super().save(*args, **kwargs)
        registry.clear_cache('default')
        self._check_accessible_field_id()
        return result

    def delete(self, *args, **kwargs):
        """Borra e invalida — la otra mitad de la guarda de ``save``."""
        result = super().delete(*args, **kwargs)
        registry.clear_cache('default')
        return result

    @classmethod
    def create(cls, vals_list):
        """Crea varias filas de una vez — ≙ ``create`` (``:53-60``).

        ``@api.model_create_multi`` allá; aquí un ``classmethod`` que recibe la
        misma lista de diccionarios. Cada fila pasa por ``save``, así que la
        invalidación y el check de acceso al campo corren una vez por fila,
        como allá corren una vez por lote.
        """
        return [cls.objects.create(**vals) for vals in vals_list]

    def write(self, vals):
        """Actualiza esta fila — ≙ ``write`` (``:62-70``).

        La fuente comprueba ``check_access('write')`` **después** de escribir;
        aquí igual, para que el orden de las dos guardas sea el mismo.
        """
        for name, value in vals.items():
            setattr(self, name, value)
        self.save()
        return True

    def unlink(self):
        """Borra esta fila — ≙ ``unlink`` (``:72-77``)."""
        return self.delete()

    # === la API de lectura y escritura de defaults =========================

    @classmethod
    def set(cls, model_name, field_name, value, user=None, company=None,
            condition=''):
        """Fija el valor por defecto de ``model.field`` — ≙ ``set`` (``:79``).

        Cualquier entrada para el mismo alcance ``(campo, usuario, empresa,
        condición)`` se reemplaza, que es el invariante que la fuente declara.

        > Se llamaba ``set_default``. Renombrado al nombre de la fuente: un
        > alias público que la referencia no tiene es drift, y aquí no había
        > razón de mecanismo para él — ``set`` no colisiona con nada de Django
        > en un ``classmethod``.
        """
        condition = condition or ''
        json_value = json.dumps(value, ensure_ascii=False)
        default, _created = cls.objects.update_or_create(
            model=model_name, field=field_name, user=user, company=company,
            condition=condition, defaults={'json_value': json_value},
        )
        # ``save`` ya invalidó; se repite aquí porque ``update_or_create`` con
        # una fila existente y el mismo valor puede no llamar a ``save``.
        registry.clear_cache('default')
        return default

    @classmethod
    def _get(cls, model_name, field_name, user=None, company=None,
             condition=''):
        """El valor por defecto, o ``None`` — ≙ ``_get`` (``:139``).

        Precedencia (más específico gana): usuario+empresa > usuario >
        empresa > global. Ver la nota de precedencia del docstring del módulo.

        > Se llamaba ``get_default``. El guion bajo es el contrato: la fuente
        > lo declara ``_get``, o sea *uso interno*, y publicarlo sin él
        > prometía una API que allá nadie ofrece
        > (``porte-completo-no-parcial.md``).
        """
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
                model=model_name, field=field_name, condition=condition,
                **scope,
            ).first()
            if default is not None:
                return json.loads(default.json_value)
        return None

    @classmethod
    @ormcache('model_name', 'condition', 'user_id', 'company_id', 'using',
              cache='default')
    def _get_model_defaults(cls, model_name, condition=False, user_id=None,
                            company_id=None, using=DEFAULT_DB_ALIAS):
        """Todos los defaults de un modelo, como dict ``campo -> valor``.

        ≙ ``_get_model_defaults`` (``:170-203``). La fuente hace **una**
        consulta y se queda con el default de mayor prioridad por campo; aquí
        igual, y la prioridad es la misma que :meth:`_get` resuelve.

        La clave del ``ormcache`` nombra ``using`` además de los cuatro ejes
        de la fuente — la divergencia de clave que ``tools/cache.py`` declara:
        allá el ``Registry`` es por base y esa dimensión va implícita en él.
        """
        condition = condition or ''
        rows = cls.objects.using(using).filter(
            model=model_name, condition=condition,
        ).filter(
            models.Q(user__isnull=True) | models.Q(user_id=user_id),
        ).filter(
            models.Q(company__isnull=True) | models.Q(company_id=company_id),
        ).values_list('field', 'json_value', 'user_id', 'company_id', 'id')

        def priority(row):
            """Más específico primero — el orden que la fuente pide al motor."""
            _field, _value, row_user, row_company, row_id = row
            return (row_user is None, row_company is None, row_id)

        result = {}
        for field_name, json_value, _u, _c, _i in sorted(rows, key=priority):
            # Se queda con el de mayor prioridad de cada campo, como la fuente.
            if field_name not in result:
                result[field_name] = json.loads(json_value)
        return result

    # === limpieza de defaults que quedaron sin referente ===================

    @classmethod
    def discard_records(cls, records):
        """Descarta los defaults de Many2one que apunten a estos registros.

        ≙ ``discard_records`` (``:205-213``). Su llamador es el borrado de un
        registro: un default que guardaba su id apunta a algo que ya no está,
        y dejarlo haría que el formulario propusiera un id muerto.

        **La divergencia de mecanismo, y es de dónde sale el filtro.** La
        fuente lo expresa como dominio sobre la FK —``field_id.ttype =
        'many2one'`` y ``field_id.relation = records._name``— porque su
        ``ir.model.fields`` guarda el tipo y la relación en columnas. Aquí eso
        no está en la tabla: se deriva del registro de Django, buscando qué
        pares ``(modelo, campo)`` son una FK al modelo dado. Con esa lista el
        filtro vuelve a ser una sola consulta.

        :param records: un ``QuerySet`` o una lista de instancias del mismo
            modelo. Vacío es un no-op.
        """
        records = list(records)
        if not records:
            return 0
        target_label = type(records[0])._meta.label
        json_values = [json.dumps(record.pk) for record in records]

        pairs = cls._many2one_pairs_to(target_label)
        if not pairs:
            return 0

        condition = models.Q()
        for model_label, field_name in pairs:
            condition |= models.Q(model=model_label, field=field_name)
        deleted, _detail = cls.objects.filter(
            condition, json_value__in=json_values).delete()
        registry.clear_cache('default')
        return deleted

    @staticmethod
    def _many2one_pairs_to(target_label):
        """Los pares ``(modelo, campo)`` cuya FK apunta a ``target_label``.

        NO tiene contraparte con este nombre: es la mitad que la fuente lee de
        las columnas ``ttype``/``relation`` de ``ir.model.fields``. Aquí la
        pone el registro de Django, que es la fuente de verdad de las
        relaciones en este stack.

        Cubre las **dos** formas que un default por id puede tomar: la FK
        normal, y el ``Many2one`` dependiente de empresa, cuyo destino viaja
        en ``company_dependent_comodel`` porque un ``jsonb`` no aloja FK.
        """
        pairs = []
        for model in apps.get_models():
            label = model._meta.label
            for field in model._meta.get_fields():
                if getattr(field, 'company_dependent', False):
                    if getattr(field, 'company_dependent_comodel',
                               None) == target_label:
                        pairs.append((label, field.name))
                    continue
                if not getattr(field, 'many_to_one', False):
                    continue
                related = getattr(field, 'related_model', None)
                if related is not None and related._meta.label == target_label:
                    pairs.append((label, field.name))
        return pairs

    @classmethod
    def discard_values(cls, model_name, field_name, values):
        """Descarta los defaults de un campo que valgan alguno de estos valores.

        ≙ ``discard_values`` (``:215-220``). Su llamador es el retiro de una
        opción de un ``Selection``: el default que la nombraba ya no es
        elegible.
        """
        json_values = [json.dumps(value, ensure_ascii=False)
                       for value in values]
        deleted, _detail = cls.objects.filter(
            model=model_name, field=field_name,
            json_value__in=json_values).delete()
        registry.clear_cache('default')
        return deleted

    # === el respaldo de un campo dependiente de empresa ====================

    @classmethod
    @ormcache('model_name', 'field_name', cache='default')
    def _get_field_column_fallbacks(cls, model_name, field_name):
        """El respaldo del campo, por empresa, como el ``jsonb`` de la columna.

        ≙ ``_get_field_column_fallbacks`` (``:222-234``). Su consumidor es la
        migración de un campo a ``company_dependent``: al convertir la columna
        hay que sembrar el mapa ``{empresa: valor}``, y el valor de cada
        empresa es el que ``ir.default`` responde para ella.

        La divergencia, declarada: allá el valor pasa por
        ``field.convert_to_column`` con el entorno cambiado de empresa; aquí
        se serializa a JSON directamente, porque la columna **es** un ``jsonb``
        y psycopg adapta el valor sin paso intermedio — el mismo colapso de dos
        pasos en uno que ``get_company_dependent_fallback_sql`` ya declara.
        """
        Company = apps.get_model('base', 'ResCompany')
        company_ids = list(Company.objects.values_list('id', flat=True))
        fallbacks = {
            str(company_id): cls._get_model_defaults(
                model_name, company_id=company_id).get(field_name)
            for company_id in company_ids
        }
        return json.dumps(fallbacks, ensure_ascii=False)

    @classmethod
    def _evaluate_condition_with_fallback(cls, model_name, field_expr,
                                          operator, value):
        """¿El respaldo del campo satisface la condición? — ≙ ``:236-252``.

        Devuelve ``True``, ``False``, o ``None`` cuando no se puede decidir.

        **Por qué no se puede preguntar al motor.** Cuando un campo dependiente
        de empresa no tiene valor propio para la empresa activa, lo que se lee
        es el respaldo de ``ir.default`` — y ese valor **no está en ninguna
        fila**. Un ``WHERE`` no lo puede evaluar: no hay fila que devolver. Por
        eso la condición se construye sobre un registro en memoria y se filtra
        con ``filtered_domain``, que evalúa el dominio sin ir a la base.

        Ése era el bloqueo real de este método, y se levantó construyendo
        ``filtered_domain`` en el mismo pase (``orm/models.py``).
        """
        field_name, _property_name = parse_field_expr(field_expr)
        target_model = apps.get_model(model_name)
        target_field = target_model._meta.get_field(field_name)
        # La fuente pasa ``self.env[model_name]``, un recordset vacío; el
        # equivalente aquí es una instancia sin guardar — el método sólo
        # necesita el modelo, no la fila.
        fallback = target_field.get_company_dependent_fallback(target_model())
        # Allá el valor pasa por ``field.convert_to_write`` y se siembra con
        # ``model.new({...})``, que escribe en la caché del ORM. Aquí no hace
        # falta convertir —el respaldo sale de ``json.loads``, ya en la forma
        # que el campo escribe— pero sí hay que sembrarlo por la puerta
        # correcta: un ``setattr`` sobre un campo dependiente de empresa
        # **rehúsa** si no hay empresa activa, y con razón (no sabría a cuál
        # escribir).
        record = target_model()
        company_id = get_current_company()
        if company_id is None:
            # Sin empresa activa el campo ya lee su respaldo: es exactamente
            # lo que ``value_for_current_company`` devuelve cuando no hay a
            # quién preguntarle. No hay nada que sembrar.
            pass
        elif hasattr(target_field, 'set_for_company'):
            target_field.set_for_company(record, company_id, fallback)
        else:
            setattr(record, field_name, fallback)

        try:
            return bool(filtered_domain(
                [record], Domain(field_expr, operator, value)))
        except ValueError:
            return None
