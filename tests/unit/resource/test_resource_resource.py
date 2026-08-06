"""``resource.resource`` + ``resource.calendar.leaves`` + ``resource.mixin``
(addon ``resource``, cierre parcial — ver ``resource_resource.py``/
``resource_mixin.py`` para lo DEFERIDO).

Adaptación fiel de Odoo resource/models/{resource_resource,
resource_calendar_leaves,resource_mixin,res_users}.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import IntegrityError, transaction

from addons.base.models import ResCompany, ResUsers
from addons.resource.models import (
    ResourceCalendar, ResourceCalendarLeaves, ResourceMixin, ResourceResource,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-resource-2', name='ACME')


@pytest.fixture
def calendar(company):
    calendar = ResourceCalendar.objects.create(
        name='Horario estándar', company=company, is_default=True, tz='UTC',
    )
    calendar.create_default_attendances()
    return calendar


class TestResourceResourceDefaults:
    def test_save_inherits_calendar_from_company(self, company, calendar):
        resource = ResourceResource.objects.create(name='Ana', company=company)
        assert resource.calendar_id == calendar.pk

    def test_save_does_not_override_explicit_calendar(self, company, calendar):
        other = ResourceCalendar.objects.create(name='Otro', company=company, tz='UTC')
        resource = ResourceResource.objects.create(
            name='Ana', company=company, calendar=other,
        )
        assert resource.calendar_id == other.pk

    def test_save_inherits_tz_from_calendar_when_no_user(self, company, calendar):
        resource = ResourceResource.objects.create(name='Máquina', company=company)
        assert resource.tz == 'UTC'

    def test_save_falls_back_to_calendar_tz_when_user_has_no_tz(
            self, company, calendar):
        """La precedencia usuario > calendario de la referencia está inerte.

        ``ResUsers`` no expone ``tz``: en la referencia lo hereda de
        ``res.partner`` por ``_inherits``, y nuestro ``base`` no portó ese
        campo (ver H-API-300). El test fija el comportamiento **real** de
        hoy —cae al calendario— y sirve de centinela: cuando ``tz`` aterrice
        en ``base``, este test empieza a fallar y ahí se restituye la
        precedencia de la referencia.
        """
        assert not hasattr(ResUsers, 'tz'), (
            'ResUsers ya expone tz: restituir la precedencia usuario > '
            'calendario en ResourceResource.save y actualizar H-API-300'
        )
        user = ResUsers.objects.create_user(login='ana@practicayoruba.mx')
        resource = ResourceResource.objects.create(
            name='Ana', company=company, user=user,
        )
        assert resource.tz == calendar.tz

    def test_time_efficiency_must_be_positive(self, company):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResourceResource.objects.create(
                    name='Inválido', company=company, tz='UTC', time_efficiency=0,
                )


class TestResourceResourceFlexibility:
    def test_is_fully_flexible_without_calendar(self, company):
        resource = ResourceResource.objects.create(name='Libre', company=company, tz='UTC')
        assert resource.is_fully_flexible is True
        assert resource.is_flexible is True

    def test_is_flexible_when_calendar_is_flexible(self, company, calendar):
        calendar.flexible_hours = True
        calendar.save()
        resource = ResourceResource.objects.create(
            name='Ana', company=company, calendar=calendar, tz='UTC',
        )
        assert resource.is_fully_flexible is False
        assert resource.is_flexible is True

    def test_is_flexible_false_with_fixed_calendar(self, company, calendar):
        resource = ResourceResource.objects.create(
            name='Ana', company=company, calendar=calendar, tz='UTC',
        )
        assert resource.is_flexible is False


class TestResourceUserExtension:
    def test_resource_resources_reverse_accessor(self, company, calendar):
        user = ResUsers.objects.create_user(login='beto@practicayoruba.mx')
        resource = ResourceResource.objects.create(
            name='Beto', company=company, calendar=calendar, user=user, tz='UTC',
        )
        assert list(user.resource_resources.all()) == [resource]
        assert user.resource_calendar.pk == calendar.pk

    def test_resource_calendar_property_none_without_resource(self):
        user = ResUsers.objects.create_user(login='sinrecurso@practicayoruba.mx')
        assert user.resource_calendar is None


class TestResourceCalendarLeaves:
    def test_save_syncs_calendar_and_company_from_resource(self, company, calendar):
        resource = ResourceResource.objects.create(
            name='Ana', company=company, calendar=calendar, tz='UTC',
        )
        leave = ResourceCalendarLeaves.objects.create(
            resource=resource,
            date_from=datetime(2026, 3, 10, tzinfo=dt_timezone.utc),
        )
        assert leave.calendar_id == calendar.pk
        assert leave.company_id == company.pk

    def test_save_defaults_date_to_end_of_day_from_date_from(self, calendar):
        leave = ResourceCalendarLeaves.objects.create(
            calendar=calendar,
            date_from=datetime(2026, 3, 10, 9, 0, tzinfo=dt_timezone.utc),
        )
        assert leave.date_to.date() == leave.date_from.date()
        assert leave.date_to.hour == 23

    def test_clean_rejects_date_to_before_date_from(self, calendar):
        leave = ResourceCalendarLeaves(
            calendar=calendar,
            date_from=datetime(2026, 3, 10, tzinfo=dt_timezone.utc),
            date_to=datetime(2026, 3, 9, tzinfo=dt_timezone.utc),
        )
        with pytest.raises(Exception):
            leave.clean()


class TestResourceMixinShape:
    """``resource.mixin`` es abstracto y hoy no tiene consumidor concreto
    (ver el docstring de ``resource_mixin.py``) — se verifica su FORMA
    (abstracto, campos declarados), no un flujo save() end-to-end, que
    requeriría una subclase concreta con tabla propia todavía inexistente.
    """

    def test_is_abstract(self):
        assert ResourceMixin._meta.abstract is True

    def test_declares_expected_fields(self):
        field_names = {f.name for f in ResourceMixin._meta.get_fields()}
        assert {'resource', 'company', 'resource_calendar'} <= field_names
