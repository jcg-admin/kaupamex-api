"""``hr.individual.skill.mixin`` — el nivel de una habilidad ligada a un
"individuo" (empleado, puesto o candidato).

Adaptación fiel de Odoo hr_skills/models/hr_individual_skill_mixin.py
(odoo-tools@abe4040ec1, odoo19c:, LGPL-3, 537 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03). Diseño del porte:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-individual-skill-mixin-full-port.md``.

Porte símbolo por símbolo — 12 campos + 16 métodos
=====================================================

Los nombres de los ``Many2one`` son los de Django (``skill``,
``skill_level``, ``skill_type``); su columna conserva el nombre de la fuente
(``skill_id``…) y los dominios y ``@api.constrains`` aceptan los dos.

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``skill_id`` / ``skill_level_id`` / ``skill_type_id`` /
       ``valid_from`` / ``valid_to`` / ``display_warning_message``
       (``:47-63``)
     - portados (columnas reales); ``skill_id`` y ``skill_level_id`` son
       ``compute`` almacenados y editables, como en la fuente
   * - ``level_progress`` / ``color`` / ``levels_count`` /
       ``is_certification`` (``related``) y
       ``certification_skill_type_count`` (``compute``), ``:54-62``
     - portados como campos sin almacenar
   * - ``_linked_field_name`` / ``_get_passive_fields`` /
       ``_can_edit_certification_validity_period`` (``:17-40``)
     - portados
   * - ``_default_skill_type_id`` (``:42-45``)
     - portado; el ``default=`` del campo lee el mismo contexto
   * - ``_check_not_overlapping_regular_skill`` (``:64-110``) /
       ``_get_overlapping_individual_skill`` (``:111-195``)
     - portados — ``@api.constrains`` por lote
   * - ``_check_date`` / ``_check_skill_type`` / ``_check_skill_level``
       (``:196-219``)
     - portados — ``@api.constrains``
   * - ``_compute_certification_skill_type_count`` (``:220-225``)
     - portado
   * - ``_onchange_is_certification`` / ``_onchange_valid_date``
       (``:226-231``, ``:254-256``)
     - portados — ``@api.onchange``
   * - ``_compute_skill_id`` / ``_compute_skill_level_id`` (``:232-248``)
     - portados — ``@api.depends``; se calculan en un registro de ``new()``
       y al cambiar el tipo
   * - ``_compute_display_name`` (``:249-253``)
     - portado
   * - ``_expire_individual_skills`` / ``_create_individual_skills`` /
       ``_write_individual_skills`` / ``_get_transformed_commands``
       (``:257-537``)
     - portados (U5). Los consumen ``hr.job.write``, ``hr.employee.create``
       y ``hr.employee.write`` (``overrides=``, ≙ ``super()``). DIVERGENCIA
       de defecto en ``_get_transformed_commands``: la fuente llama
       ``updated_ids.append`` sobre un ``set`` (``:525``); se porta la
       intención con ``set.add``. En ``_write_individual_skills`` el
       registro escrito se archiva dos veces, igual que en la fuente
       (``:479``): ``_create_individual_skills`` lo encuentra vigente.


Divergencia declarada
=====================

``create`` y ``write`` no son atómicos, igual que en la fuente: una
restricción que falla deshace la transacción que envuelve la llamada, no la
llamada sola.
"""

from collections import defaultdict
from datetime import date, timedelta

import api
import fields
import models

from addons.base.models import TimeStampedModel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from exceptions import ValidationError
from orm.environments import get_context


def _skill_type_for_context(context):
    """La rama de ``_default_skill_type_id`` (``:42-45``) para un contexto.

    ``search([], limit=1)`` sobre ``hr.skill.type`` sigue su ``_order =
    "sequence, name"``; ``name`` es traducible, así que el orden es el del
    texto del idioma activo (TASK-GEN-0060).
    """
    types = HrSkillType.objects.order_by(
        'sequence', models.TranslatedValue('name'))
    if context.get('certificate_skill', False):
        types = types.filter(is_certification=True)
    return types.first()


def _default_skill_type():
    """El ``default=`` del campo ``skill_type`` — ≙ ``_default_skill_type_id``.

    Django invoca el default sin argumentos, así que no hay recordset que
    pasar; el contexto se lee del canal en curso, que es el mismo
    ``env.context`` que la fuente consulta: un ``with_context`` llega aquí
    porque el despacho del método activa su entorno. Devuelve la clave
    primaria porque las migraciones serializan esta función por su ruta.
    """
    record = _skill_type_for_context(get_context())
    return record.pk if record else None


def _overlaps(matching_ind_skill, vals):
    """La comparación de ``:183-191``: ¿el registro guardado se solapa con
    el alta ``vals``? Un ``valid_to`` vacío es un periodo abierto."""
    return (
        matching_ind_skill.valid_from <= vals['valid_from']
        and (not matching_ind_skill.valid_to
             or matching_ind_skill.valid_to >= vals['valid_from'])
    ) or (
        vals['valid_to'] is not None
        and matching_ind_skill.valid_from <= vals['valid_to']
        and (not matching_ind_skill.valid_to
             or matching_ind_skill.valid_to >= vals['valid_to'])
    )


class HrIndividualSkillMixin(models.BaseModel, TimeStampedModel):
    """``hr.individual.skill.mixin`` — nivel de habilidad de un individuo.

    ≙ ``class HrIndividualSkillMixin(models.AbstractModel)`` (``:11``): un
    ``BaseModel`` abstracto, así que sus consumidores son recordsets con
    ``env``, ``search`` y ``Domain`` (H-API-1083). ``TimeStampedModel``
    conserva las columnas y el ``Meta`` del esquema ya migrado, como en
    ``test_orm.TestOrmModel``.
    """

    _name = 'hr.individual.skill.mixin'
    _description = 'Skill level'
    _order = 'skill_type_id, skill_level_id'
    _rec_name = 'skill_id'

    skill = fields.Many2one(
        'hr_skills.HrSkill',
        compute='_compute_skill_id', store=True, readonly=False,
        null=False, on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_skill_set',
        verbose_name='Habilidad',
        help_text=(
            'Odoo skill_id (compute+store, readonly=False, '
            'required) — poblado por _compute_skill_id() o directo.'
        ),
    )
    skill_level = fields.Many2one(
        'hr_skills.HrSkillLevel',
        compute='_compute_skill_level_id', store=True, readonly=False,
        null=False, on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_skill_level_set',
        verbose_name='Nivel',
        help_text=(
            'Odoo skill_level_id (compute+store, readonly=False, '
            'required) — poblado por _compute_skill_level_id() o '
            'directo.'
        ),
    )
    skill_type = fields.Many2one(
        'hr_skills.HrSkillType',
        null=False, on_delete=models.CASCADE,
        default=_default_skill_type,
        related_name='%(app_label)s_%(class)s_skill_type_set',
        verbose_name='Tipo de habilidad',
    )
    valid_from = fields.Date(
        default=date.today,
        verbose_name='Inicio de validez',
    )
    valid_to = fields.Date(
        null=True, blank=True, verbose_name='Fin de validez'
    )
    display_warning_message = fields.Boolean(
        default=False,
        verbose_name='Mostrar advertencia',
        help_text=(
            'Odoo display_warning_message — poblado por '
            '_onchange_valid_date() (divergencia: sin motor de '
            'onchange, no auto-wireado).'
        ),
    )

    level_progress = fields.Integer(related='skill_level.level_progress')
    color = fields.Integer(related='skill_type.color')
    levels_count = fields.Integer(related='skill_type.levels_count')
    certification_skill_type_count = fields.Integer(
        compute='_compute_certification_skill_type_count')
    is_certification = fields.Boolean(related='skill_type.is_certification')

    class Meta(TimeStampedModel.Meta):
        abstract = True

    # ------------------------------------------------------------------
    # Métodos — comportamiento por sub-modelo
    # ------------------------------------------------------------------

    def _linked_field_name(self):
        """≙ ``_linked_field_name`` (``:17-18``) — abstracto; devuelve el
        nombre del campo Django (sin ``_id``) que liga con el individuo
        (``'employee'``/``'job'``)."""
        raise NotImplementedError()

    def _get_passive_fields(self):
        """≙ ``_get_passive_fields`` (``:20-33``) — verbatim (``[]``)."""
        return []

    def _can_edit_certification_validity_period(self):
        """≙ ``_can_edit_certification_validity_period`` (``:35-39``) —
        verbatim (``True``)."""
        return True

    def _default_skill_type_id(self):
        """≙ ``_default_skill_type_id`` (``:42-45``)."""
        return _skill_type_for_context(self.env.context)

    # ------------------------------------------------------------------
    # Restricciones — ≙ los cuatro ``@api.constrains`` de la fuente
    # ------------------------------------------------------------------

    @api.constrains(lambda self: [
        'valid_from', 'valid_to', 'skill_id', 'skill_type_id',
        'skill_level_id', self._linked_field_name(),
    ])
    def _check_not_overlapping_regular_skill(self):
        """≙ ``_check_not_overlapping_regular_skill`` (``:64-110``).

        Habilidades: una sola activa por ``skill_id`` en cada individuo.
        Certificaciones: varias con la misma habilidad y nivel mientras su
        periodo de validez difiera. En ambos casos no se admiten dos registros
        con exactamente los mismos valores. El lote entero se valida en una
        sola búsqueda, así que dos altas del mismo ``create`` que chocan entre
        sí también se rechazan.
        """
        linked = self._linked_field_name()
        overlapping_dict = self._get_overlapping_individual_skill([{
            linked: skill_ind[linked].id,
            'skill_id': skill_ind.skill.id,
            'id': skill_ind.id,
            'valid_from': skill_ind.valid_from,
            'valid_to': skill_ind.valid_to,
            'skill_level_id': skill_ind.skill_level.id,
            'is_certification': skill_ind.is_certification,
        } for skill_ind in self])
        if overlapping_dict:
            errors = []
            for existing_ind_skill, new_ind_skills in overlapping_dict.items():
                conflicting = ', '.join(
                    [str(ind_skill) for ind_skill in new_ind_skills])
                errors.append(
                    f'• {conflicting} '
                    f'conflicts with the existing skill/certification '
                    f'{existing_ind_skill.display_name} from '
                    f'{existing_ind_skill.valid_from} to '
                    f'{existing_ind_skill.valid_to}',
                )
            error_msg = self.env._(
                "The following skills can't be created as they overlap or "
                'exactly match existing skills:\n%(collisions)s',
                collisions='\n'.join(errors),
            )
            raise ValidationError(error_msg)

    def _get_overlapping_individual_skill(self, vals_list):
        """≙ ``_get_overlapping_individual_skill`` (``:111-195``).

        Una sola búsqueda con el ``OR`` de las condiciones de cada alta; cada
        coincidencia se empareja con las altas de su misma clave para separar
        el solapamiento real del falso positivo del ``OR``.
        """
        can_edit_certification_validity_period = (
            self._can_edit_certification_validity_period())
        linked = self._linked_field_name()
        matching_skill_domain = fields.Domain.FALSE
        overlapping_dict = defaultdict(list)
        certification_dict = defaultdict(list)
        regular_dict = defaultdict(list)
        for individual_skill_vals in vals_list:
            ind_domain = fields.Domain.AND([
                fields.Domain(
                    f'{linked}.id', '=', individual_skill_vals[linked]),
                fields.Domain(
                    'skill_id.id', '=', individual_skill_vals['skill_id']),
                fields.Domain('id', '!=', individual_skill_vals['id']),
            ])
            if (can_edit_certification_validity_period
                    and individual_skill_vals['is_certification']):
                ind_domain = fields.Domain.AND([
                    ind_domain,
                    fields.Domain('skill_level_id.id', '=',
                                  individual_skill_vals['skill_level_id']),
                    fields.Domain('valid_from', '=',
                                  individual_skill_vals['valid_from']),
                    fields.Domain('valid_to', '=',
                                  individual_skill_vals['valid_to']),
                ])
                key = (
                    individual_skill_vals[linked],
                    individual_skill_vals['skill_id'],
                    individual_skill_vals['skill_level_id'],
                    fields.Date.from_string(
                        individual_skill_vals['valid_from']),
                    fields.Date.from_string(
                        individual_skill_vals['valid_to']),
                )
                certification_dict[key].append(individual_skill_vals)
            else:
                valid_from = individual_skill_vals['valid_from']
                valid_to = individual_skill_vals['valid_to']
                ind_domain = fields.Domain.AND([
                    ind_domain,
                    fields.Domain.OR([
                        fields.Domain.AND([
                            fields.Domain('valid_from', '<=', valid_from),
                            fields.Domain.OR([
                                fields.Domain('valid_to', '=', False),
                                fields.Domain('valid_to', '>=', valid_from),
                            ]),
                        ]),
                        fields.Domain.AND([
                            fields.Domain('valid_from', '<=', valid_to),
                            fields.Domain.OR([
                                fields.Domain('valid_to', '=', False),
                                fields.Domain('valid_to', '>=', valid_to),
                            ]),
                        ]),
                    ]),
                ])
                key = (
                    individual_skill_vals[linked],
                    individual_skill_vals['skill_id'],
                )
                regular_dict[key].append(individual_skill_vals)
            matching_skill_domain = fields.Domain.OR(
                [matching_skill_domain, ind_domain])
        matching_individual_skills = self.env[self._name].search(
            matching_skill_domain)
        for matching_ind_skill in matching_individual_skills:
            if (can_edit_certification_validity_period
                    and matching_ind_skill.is_certification):
                similar_certifications = certification_dict.get((
                    matching_ind_skill[linked].id,
                    matching_ind_skill.skill.id,
                    matching_ind_skill.skill_level.id,
                    fields.Date.from_string(matching_ind_skill.valid_from),
                    fields.Date.from_string(matching_ind_skill.valid_to),
                ))
                if similar_certifications:
                    overlapping_dict[matching_ind_skill].extend(
                        similar_certifications)
            else:
                similar_regular_skills = regular_dict.get((
                    matching_ind_skill[linked].id,
                    matching_ind_skill.skill.id,
                ), [])
                for similar_regular_skill in similar_regular_skills:
                    if _overlaps(matching_ind_skill, similar_regular_skill):
                        overlapping_dict[matching_ind_skill].append(
                            similar_regular_skill)
        return overlapping_dict

    @api.constrains('valid_from', 'valid_to')
    def _check_date(self):
        """≙ ``_check_date`` (``:196-205``)."""
        error_ind_skill_msg = ''
        for ind_skill in self:
            if (ind_skill.valid_to
                    and ind_skill.valid_from > ind_skill.valid_to):
                error_ind_skill_msg += self.env._(
                    '• %(skill_name)s from %(valid_from)s to %(valid_to)s',
                    skill_name=ind_skill.display_name,
                    valid_from=ind_skill.valid_from,
                    valid_to=ind_skill.valid_to,
                )
        if error_ind_skill_msg:
            raise ValidationError(self.env._(
                'The following skills have their valid stop date prior to '
                'their valid start date:\n') + error_ind_skill_msg)

    @api.constrains('skill_id', 'skill_type_id')
    def _check_skill_type(self):
        """≙ ``_check_skill_type`` (``:207-212``)."""
        for record in self:
            if record.skill.skill_type_id != record.skill_type_id:
                raise ValidationError(self.env._(
                    "The skill %(name)s and skill type %(type)s don't match",
                    name=record.skill.name, type=record.skill_type.name))

    @api.constrains('skill_type_id', 'skill_level_id')
    def _check_skill_level(self):
        """≙ ``_check_skill_level`` (``:214-219``)."""
        for record in self:
            if record.skill_level.skill_type_id != record.skill_type_id:
                raise ValidationError(self.env._(
                    'The skill level %(level)s is not valid for skill type: '
                    '%(type)s',
                    level=record.skill_level.name,
                    type=record.skill_type.name))

    def _compute_certification_skill_type_count(self):
        """≙ ``_compute_certification_skill_type_count`` (``:220-225``)."""
        count = HrSkillType.objects.filter(
            is_certification=True).count()
        for record in self:
            record.certification_skill_type_count = count

    @api.onchange('is_certification')
    def _onchange_is_certification(self):
        """≙ ``_onchange_is_certification`` (``:226-231``)."""
        self.valid_from = date.today()
        if not self.is_certification:
            self.valid_to = None

    @api.depends('skill_type_id')
    def _compute_skill_id(self):
        """≙ ``_compute_skill_id`` (``:232-238``). ``skill_ids`` sigue el
        ``_order = 'sequence, name'`` de ``hr.skill``."""
        for record in self:
            if record.skill_type:
                record.skill = record.skill_type.skill_ids.first()
            else:
                record.skill = False

    @api.depends('skill_id')
    def _compute_skill_level_id(self):
        """≙ ``_compute_skill_level_id`` (``:240-247``): el nivel por
        defecto del tipo y, si no hay, el primero por ``level_progress``."""
        for record in self:
            if not record.skill:
                record.skill_level = False
            else:
                skill_levels = record.skill_type.skill_level_ids
                record.skill_level = (
                    skill_levels.filter(default_level=True).first()
                    or skill_levels.first())

    @api.depends('skill_id', 'skill_level_id')
    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:249-253``)."""
        for individual_skill in self:
            individual_skill.display_name = (
                f'{individual_skill.skill.name}: '
                f'{individual_skill.skill_level.name}')

    @api.onchange('valid_to', 'valid_from')
    def _onchange_valid_date(self):
        """≙ ``_onchange_valid_date`` (``:254-256``)."""
        self.display_warning_message = bool(
            self.valid_to
            and self.valid_from
            and self.valid_to < self.valid_from,
        )

    # ------------------------------------------------------------------
    # Transformadores de comandos — ≙ ``:257-537``
    # ------------------------------------------------------------------

    def _expire_individual_skills(self):
        """≙ ``_expire_individual_skills`` (``:257-294``).

        Archiva todo registro de ``self``: si no venció y archivarlo no choca
        con otro, ``valid_to`` pasa a ayer; si se creó desde ayer, ya venció
        o archivarlo chocaría, se borra. Devuelve comandos ``WRITE`` y
        ``UNLINK``.
        """
        yesterday = fields.Date.today() - timedelta(days=1)
        empty = self.env[self._name].browse(())
        to_remove = empty
        to_archive = empty
        for individual_skill in self:
            if (individual_skill.valid_from >= yesterday
                    or (individual_skill.valid_to
                        and individual_skill.valid_to <= yesterday)):
                to_remove += individual_skill
            else:
                to_archive += individual_skill
        if to_archive:
            linked = self._linked_field_name()
            overlapping_dict = self._get_overlapping_individual_skill([{
                linked: skill[linked].id,
                'skill_id': skill.skill.id,
                'id': skill.id,
                'valid_from': skill.valid_from,
                'valid_to': yesterday,
                'skill_level_id': skill.skill_level.id,
                'is_certification': skill.is_certification,
            } for skill in to_archive])
            new_overlapped_skill_ids = []
            for new_skills in overlapping_dict.values():
                for new_skill in new_skills:
                    new_overlapped_skill_ids.append(new_skill['id'])
            changed_to_remove = to_archive.filtered(
                lambda ind_skill: ind_skill.id in new_overlapped_skill_ids)
            to_archive -= changed_to_remove
            to_remove += changed_to_remove
        return ([[2, skill.id] for skill in to_remove]
                + [[1, skill.id, {'valid_to': yesterday}]
                   for skill in to_archive])

    def _create_individual_skills(self, vals_list):
        """≙ ``_create_individual_skills`` (``:296-415``).

        Traduce comandos ``CREATE`` en ``CREATE``, ``WRITE`` y ``UNLINK``
        para conservar el historial y respetar las restricciones: un valor
        repetido en el lote se crea una vez, una certificación idéntica ya
        existente se omite y una habilidad regular vigente del mismo
        individuo se archiva.
        """
        can_edit_certification_validity_period = (
            self._can_edit_certification_validity_period())
        linked = self._linked_field_name()
        seen_skills = set()
        skills_to_archive = self.env[self._name].browse(())
        vals_to_return = []

        validity_domain = fields.Domain.OR([
            fields.Domain('valid_to', '=', False),
            fields.Domain('valid_to', '>=', fields.Date.today()),
        ])
        if can_edit_certification_validity_period:
            validity_domain = fields.Domain.OR([
                validity_domain,
                fields.Domain('is_certification', '=', True),
            ])
        existing_skills_domain = fields.Domain.AND([
            fields.Domain.OR([
                fields.Domain.AND([
                    fields.Domain(linked, '=', vals.get(linked, False)),
                    fields.Domain(
                        'skill_id', '=', vals.get('skill_id', False)),
                ])
                for vals in vals_list
            ]),
            validity_domain,
        ])
        existing_skills = self.env[self._name].search(existing_skills_domain)
        existing_skills_grouped = existing_skills.grouped(
            lambda skill: (skill[linked].id, skill.skill.id))

        if can_edit_certification_validity_period:
            certification_set = {}
            for cert in existing_skills.filtered(lambda s: s.is_certification):
                key = (
                    cert[linked].id,
                    cert.skill.id,
                    cert.skill_level.id,
                    fields.Date.from_string(cert.valid_from),
                    fields.Date.from_string(cert.valid_to),
                )
                certification_set[key] = cert
            certification_types = set(
                HrSkillType.objects.filter(
                    pk__in=[vals['skill_type_id'] for vals in vals_list],
                    is_certification=True,
                ).values_list('pk', flat=True))
        for vals in vals_list:
            individual_skill_id = vals.get(linked, False)
            skill_id = vals['skill_id']
            skill_type_id = vals['skill_type_id']
            skill_level_id = vals['skill_level_id']
            valid_from = fields.Date.from_string(vals.get('valid_from'))
            valid_to = fields.Date.from_string(vals.get('valid_to'))

            if can_edit_certification_validity_period:
                is_certificate = skill_type_id in certification_types
            else:
                is_certificate = False

            skill_key = (individual_skill_id, skill_id, valid_from, valid_to)
            # Remove duplicate skills
            if skill_key in seen_skills:
                continue
            seen_skills.add(skill_key)

            if is_certificate:
                key = (individual_skill_id, skill_id, skill_level_id,
                       valid_from, valid_to)
                # Remove duplicate certification
                if certification_set.get(key):
                    continue
            else:
                # Archive existing regular skill if the person already have
                # one with the same skill
                existing_skill = existing_skills_grouped.get(
                    (individual_skill_id, skill_id))
                if existing_skill:
                    skills_to_archive += existing_skill

            vals_to_return.append(vals)

        return (skills_to_archive._expire_individual_skills()
                + [[0, 0, new_create_val]
                   for new_create_val in vals_to_return])

    def _write_individual_skills(self, commands):
        """≙ ``_write_individual_skills`` (``:417-479``).

        Un ``write`` que no toca ``skill_type_id``, ``skill_id``,
        ``skill_level_id`` ni el campo ligado pasa igual; uno que los toca
        archiva el registro y crea otro con los valores del registro, los de
        ``vals`` (que mandan) y los campos pasivos. Las fechas sólo se
        conservan en una certificación.
        """
        linked = self._linked_field_name()
        self_dict = self.grouped('id')
        result_command = []
        create_vals = []
        remove_from_expire = self.env[self._name].browse(())

        def _get_passive_field_value(field, skill):
            """El valor de ``field`` listo para un ``vals``: el id de un
            ``Many2one``, los ids de un x2many, el valor tal cual si no."""
            field_type = self._fields[field].type
            if field_type == 'many2one':
                return skill[field].id
            if field_type in ('many2many', 'one2many'):
                return skill[field].ids
            return skill[field]

        for command in commands:
            ind_skill = self_dict.get(command[1])
            vals = command[2]
            if not any(key in vals for key in
                       ['skill_type_id', 'skill_id', 'skill_level_id',
                        linked]):
                result_command.append([1, ind_skill.id, vals])
                remove_from_expire += ind_skill
                continue

            passive_vals = {
                field: vals.get(field, _get_passive_field_value(
                    field, ind_skill))
                for field in self._get_passive_fields()
            }
            new_vals = {
                linked: vals.get(linked, ind_skill[linked].id),
                'skill_id': vals.get('skill_id', ind_skill.skill.id),
                'skill_level_id': vals.get(
                    'skill_level_id', ind_skill.skill_level.id),
                'skill_type_id': vals.get(
                    'skill_type_id', ind_skill.skill_type.id),
                **passive_vals,
            }
            skill_type = HrSkillType.objects.get(
                pk=new_vals['skill_type_id'])
            valid_from = vals.get(
                'valid_from',
                ind_skill.valid_from if skill_type.is_certification
                else fields.Date.today())
            valid_to = vals.get(
                'valid_to',
                ind_skill.valid_to if skill_type.is_certification else False)
            new_vals.update({'valid_from': valid_from, 'valid_to': valid_to})
            create_vals.append(new_vals)
        return (result_command
                + (self - remove_from_expire)._expire_individual_skills()
                + self.env[self._name].browse(())._create_individual_skills(
                    create_vals))

    def _get_transformed_commands(self, commands, individuals):
        """≙ ``_get_transformed_commands`` (``:481-537``).

        Reparte los comandos ``1``, ``2`` y ``0`` (copiando el ``0`` por cada
        individuo cuando los hay), descarta el ``1`` de un id que también se
        borra y devuelve ``expire(borrados) + write(escritos) +
        create(creados)``.

        DIVERGENCIA de defecto, declarada: en la rama del id mixto la fuente
        reinicia ``updated_ids = set()`` y después llama a
        ``updated_ids.append(...)``, que lanzaría ``AttributeError``. Se porta
        la intención —conservar los ``1`` no mixtos— con un ``set.add``.
        """
        if not commands:
            return None
        linked = self._linked_field_name()
        updated_ids = set()
        updated_commands = []
        created_values = []
        unlinked_ids = set()
        for command in commands:
            if command[0] == 1:
                updated_ids.add(command[1])
                updated_commands.append(command)
            elif command[0] == 2:
                unlinked_ids.add(command[1])
            elif command[0] == 0:
                if individuals:
                    for individual in individuals:
                        individual_command = command[2]
                        individual_command[linked] = individual.id
                        created_values.append(individual_command)
                else:
                    created_values.append(command[2])
        mixed_command_ids = list(updated_ids & unlinked_ids)
        if mixed_command_ids:
            # reset updated values
            updated_ids = set()
            updated_commands = []
            for command in commands:
                if command[1] not in mixed_command_ids and command[0] == 1:
                    updated_commands.append(command)
                    updated_ids.add(command[1])
        model = self.env[self._name]
        unlinked_commands = model.browse(
            list(unlinked_ids))._expire_individual_skills()
        updated_commands = model.browse(
            list(updated_ids))._write_individual_skills(updated_commands)
        created_commands = model.browse(())._create_individual_skills(
            created_values)
        return unlinked_commands + updated_commands + created_commands
