"""Contrato del addon ``utm`` — porte fiel de Odoo Community 19 (LGPL-3).

Cubre los 25 símbolos de la referencia (``odoo-tools@622ddc2a``, ``odoo19c:
addons/utm/``), agrupados por el archivo que los declara:

- ``utm_mixin.py`` (7): ``_split_name_and_count``, ``_get_unique_names``,
  ``_find_or_create_record``, ``find_or_create_record``, ``tracking_fields``,
  ``_tracking_models``, ``default_get``.
- ``utm_medium.py`` (4): ``save`` (≙ ``create``),
  ``SELF_REQUIRED_UTM_MEDIUMS_REF``, ``_unlink_except_utm_medium_record``,
  ``_fetch_or_create_utm_medium``.
- ``utm_source.py`` (7): ``_unlink_except_referral``, ``save`` (≙ ``create``),
  ``_generate_name`` · y los 4 de ``utm.source.mixin`` — ver la nota sobre su
  cobertura al final de este docstring.
- ``utm_campaign.py`` (3): ``_compute_name``, ``save`` (≙ ``create``),
  ``_group_expand_stage_ids``.
- ``utm_tag.py`` (1): ``_default_color``.
- ``ir_http.py`` (3): ``get_utm_domain_cookies``, ``_set_utm``,
  ``_post_dispatch``.

**``utm.source.mixin`` se ejercita por sus piezas, no por un consumidor.**
Ningún addon de este árbol lo hereda todavía — igual que ``analytic.mixin``
cuando se portó. Sus cuatro métodos exigen un modelo concreto que declare
``_rec_name``, y fabricar uno sólo para el test añadiría una tabla al esquema
de producción. Se cubre ``_generate_name`` (el núcleo, que es donde vive la
lógica) y queda registrado el resto como sucesor: tarea **#415**.
"""
import pytest
from django.test import RequestFactory
from django.utils import timezone

from addons.base.models import IrModelData, ResUsers
from addons.utm.models import (
    IrHttp,
    UtmCampaign,
    UtmCookieMiddleware,
    UtmMedium,
    UtmMixin,
    UtmSource,
    UtmStage,
    UtmTag,
)
from addons.utm.models.utm_medium import SELF_REQUIRED_UTM_MEDIUMS_REF
from addons.utm.models.utm_tag import _default_color
from exceptions import UserError, ValidationError

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- utm.mixin --


class TestSplitNameAndCount:
    """≙ ``_split_name_and_count`` — los dos casos del docstring de la fuente."""

    def test_plain_name_counts_as_one(self):
        assert UtmMixin._split_name_and_count('Medium') == ('Medium', 1)

    def test_bracketed_counter_is_extracted(self):
        assert UtmMixin._split_name_and_count('Medium [1234]') == ('Medium', 1234)

    def test_empty_name_is_tolerated(self):
        assert UtmMixin._split_name_and_count(None) == ('', 1)


class TestGetUniqueNames:
    """≙ ``_get_unique_names`` — el ejemplo verbatim del docstring de la fuente."""

    def test_reference_example(self):
        # "El nombre 'test' ya existe en la base"
        UtmSource.objects.create(name='test')

        result = UtmMixin._get_unique_names(
            'utm.source', ['test', 'test [3]', 'bob', 'test', 'test'])

        assert result == ['test [2]', 'test [3]', 'bob', 'test [4]', 'test [5]']

    def test_empty_name_yields_none(self):
        assert UtmMixin._get_unique_names('utm.source', [None, '']) == [None, None]

    def test_skip_record_ids_excludes_the_record_from_its_own_collision(self):
        source = UtmSource.objects.create(name='promo')

        # Sin excluirse, 'promo' colisionaría consigo mismo y saldría 'promo [2]'.
        assert UtmMixin._get_unique_names('utm.source', ['promo'])[0] == 'promo [2]'
        assert UtmMixin._get_unique_names(
            'utm.source', ['promo'], skip_record_ids=[source.pk])[0] == 'promo'

    def test_unknown_model_is_reported(self):
        with pytest.raises(LookupError):
            UtmMixin._get_unique_names('utm.nope', ['x'])


class TestFindOrCreateRecord:
    """≙ ``_find_or_create_record`` / ``find_or_create_record``."""

    def test_existing_record_is_found_case_insensitively(self):
        source = UtmSource.objects.create(name='Affiliate Ring')

        found = UtmMixin._find_or_create_record('utm.source', '  affiliate ring ')

        assert found.pk == source.pk

    def test_seeded_source_is_found_not_duplicated(self):
        """La semilla de ``utm_source_data.xml`` ya está: no se recrea."""
        found = UtmMixin._find_or_create_record('utm.source', 'search engine')

        assert found.name == 'Search engine'
        assert UtmSource.objects.filter(name__iexact='search engine').count() == 1

    def test_missing_record_is_created(self):
        record = UtmMixin._find_or_create_record('utm.source', 'Partner Blog')

        assert record.pk is not None
        assert record.name == 'Partner Blog'

    def test_created_campaign_is_flagged_as_auto(self):
        """La fuente marca ``is_auto_campaign`` cuando el modelo lo declara."""
        campaign = UtmMixin._find_or_create_record('utm.campaign', 'Autumn push')

        assert campaign.is_auto_campaign is True

    def test_frontend_wrapper_returns_id_and_name(self):
        payload = UtmMixin.find_or_create_record('utm.medium', 'Podcast')

        assert set(payload) == {'id', 'name'}
        assert payload['name'] == 'Podcast'
        assert UtmMedium.objects.filter(pk=payload['id']).exists()


class TestTrackingFields:
    """≙ ``tracking_fields`` / ``_tracking_models`` — el contrato de los 3 ejes."""

    def test_three_axes_in_reference_order(self):
        assert UtmMixin.tracking_fields() == [
            ('utm_campaign', 'campaign_id', 'kaupamex_utm_campaign'),
            ('utm_source', 'source_id', 'kaupamex_utm_source'),
            ('utm_medium', 'medium_id', 'kaupamex_utm_medium'),
        ]

    def test_tracking_models_are_the_three_utm_models(self):
        assert UtmMixin._tracking_models() == {
            'utm.campaign', 'utm.source', 'utm.medium'}


class TestDefaultGet:
    """≙ ``default_get`` — los tres ejes salen de la cookie."""

    def test_cookie_value_is_resolved_to_a_record(self):
        request = RequestFactory().get('/')
        request.COOKIES['kaupamex_utm_source'] = 'Search Engine'

        values = UtmMixin.default_get(['source_id'], request=request)

        # Resuelve contra la fuente sembrada (``utm.utm_source_search_engine``),
        # que se llama 'Search engine' — la búsqueda no distingue mayúsculas.
        source = UtmSource.objects.get(pk=values['source_id'])
        assert source.name == 'Search engine'

    def test_without_request_nothing_is_filled(self):
        assert UtmMixin.default_get(['source_id']) == {}

    def test_fields_not_asked_for_are_ignored(self):
        request = RequestFactory().get('/')
        request.COOKIES['kaupamex_utm_source'] = 'Search Engine'

        assert UtmMixin.default_get(['medium_id'], request=request) == {}


# --------------------------------------------------------------- utm.medium --


class TestUtmMedium:

    def test_save_numbers_a_colliding_name(self):
        UtmMedium.objects.create(name='Kiosk')
        second = UtmMedium.objects.create(name='Kiosk')

        assert second.name == 'Kiosk [2]'

    def test_seeded_medium_pushes_the_counter(self):
        """'Email' viene de la semilla, así que el nuevo sale numerado."""
        assert UtmMedium.objects.create(name='Email').name == 'Email [2]'

    def test_update_does_not_renumber(self):
        """La fuente numera en ``create``, no en ``write``."""
        medium = UtmMedium.objects.create(name='Sponsorship')
        medium.active = False
        medium.save()
        medium.refresh_from_db()

        assert medium.name == 'Sponsorship'

    def test_self_required_mediums_reference(self):
        medium = UtmMedium.objects.create(name='Whatever')

        assert medium.SELF_REQUIRED_UTM_MEDIUMS_REF == SELF_REQUIRED_UTM_MEDIUMS_REF
        assert medium.SELF_REQUIRED_UTM_MEDIUMS_REF['utm.utm_medium_twitter'] == 'X'

    def test_protected_medium_cannot_be_deleted(self):
        medium = UtmMedium.objects.create(name='Direct')
        IrModelData.set_xmlid(medium, 'utm.utm_medium_direct')

        with pytest.raises(UserError):
            medium.delete()

    def test_unprotected_medium_can_be_deleted(self):
        medium = UtmMedium.objects.create(name='Flyer')
        medium.delete()

        assert not UtmMedium.objects.filter(name='Flyer').exists()

    def test_fetch_or_create_registers_its_external_id(self):
        created = UtmMedium._fetch_or_create_utm_medium('Direct')

        assert created.name == 'Direct'
        assert IrModelData.objects.filter(
            module='utm', name='utm_medium_direct', res_id=created.pk).exists()

    def test_fetch_or_create_is_idempotent(self):
        first = UtmMedium._fetch_or_create_utm_medium('Website')
        second = UtmMedium._fetch_or_create_utm_medium('Website')

        assert first.pk == second.pk
        assert UtmMedium.objects.filter(name='Website').count() == 1

    def test_name_is_normalised_for_the_external_id(self):
        """Espacios y puntos pasan a guion bajo — ≙ ``re.sub(r"[\\s|.]", "_", …)``."""
        medium = UtmMedium._fetch_or_create_utm_medium('Paid Social')

        assert IrModelData.objects.filter(
            module='utm', name='utm_medium_paid_social', res_id=medium.pk).exists()


# --------------------------------------------------------------- utm.source --


class TestUtmSource:

    def test_save_numbers_a_colliding_name(self):
        UtmSource.objects.create(name='Blog')
        second = UtmSource.objects.create(name='Blog')

        assert second.name == 'Blog [2]'

    def test_referral_source_cannot_be_deleted(self):
        source = UtmSource.objects.create(name='Referral')
        IrModelData.set_xmlid(source, 'utm.utm_source_referral')

        with pytest.raises(ValidationError):
            source.delete()

    def test_generate_name_composes_content_model_and_date(self):
        stage = UtmStage.objects.create(name='Ideas')

        generated = UtmSource._generate_name(stage, 'Spring sale')

        assert 'Spring sale' in generated
        assert 'Campaign Stage' in generated          # ≙ ``_description``
        assert stage.created_at.date().isoformat() in generated

    def test_generate_name_truncates_long_content(self):
        stage = UtmStage.objects.create(name='Ideas')

        generated = UtmSource._generate_name(stage, 'x' * 40)

        assert 'x' * 20 + '...' in generated

    def test_generate_name_flattens_newlines(self):
        stage = UtmStage.objects.create(name='Ideas')

        assert '\n' not in UtmSource._generate_name(stage, 'one\ntwo')

    def test_generate_name_without_content_is_none(self):
        stage = UtmStage.objects.create(name='Ideas')

        assert UtmSource._generate_name(stage, '') is None


# ------------------------------------------------------------- utm.campaign --


@pytest.fixture
def responsible(db):
    return ResUsers.objects.create_user(
        username='utm-owner', email='utm-owner@example.com', password='x')


class TestUtmCampaign:

    def test_title_falls_back_to_the_identifier(self):
        stage = UtmStage.objects.create(name='Nuevas')
        campaign = UtmCampaign.objects.create(
            name='autumn_drive', user_id=None, stage_id=stage)

        assert campaign.title == 'autumn_drive'

    def test_identifier_is_numbered_on_collision(self):
        stage = UtmStage.objects.create(name='Nuevas')
        UtmCampaign.objects.create(name='drive', stage_id=stage)
        second = UtmCampaign.objects.create(name='drive', stage_id=stage)

        assert second.name == 'drive [2]'

    def test_first_stage_is_the_default(self):
        first = UtmStage.objects.create(name='Nuevas', sequence=1)
        UtmStage.objects.create(name='Cerradas', sequence=9)

        campaign = UtmCampaign.objects.create(title='Verano')

        assert campaign.stage_id_id == first.pk

    def test_compute_name_excludes_the_record_itself(self):
        """≙ ``utm_check_skip_record_ids`` — recalcular no incrementa."""
        stage = UtmStage.objects.create(name='Nuevas')
        campaign = UtmCampaign.objects.create(title='Navidad', stage_id=stage)

        assert campaign._compute_name() == 'Navidad'

    def test_str_uses_the_rec_name(self):
        stage = UtmStage.objects.create(name='Nuevas')
        campaign = UtmCampaign.objects.create(
            name='xmas_2026', title='Navidad 2026', stage_id=stage)

        assert str(campaign) == 'Navidad 2026'

    def test_group_expand_returns_every_stage(self):
        UtmStage.objects.create(name='Cerradas', sequence=9)
        UtmStage.objects.create(name='Nuevas', sequence=1)

        stages = list(UtmCampaign._group_expand_stage_ids())

        # También las etapas sin ninguna campaña, y en el orden de ``_order``.
        # 'New' (secuencia 10) la aporta la semilla de ``utm_stage_data.xml``.
        assert [stage.name for stage in stages] == ['Nuevas', 'Cerradas', 'New']

    def test_tags_are_many_to_many(self):
        stage = UtmStage.objects.create(name='Nuevas')
        campaign = UtmCampaign.objects.create(title='Verano', stage_id=stage)
        tag = UtmTag.objects.create(name='newsletter')
        campaign.tag_ids.add(tag)

        assert list(tag.campaign_ids.all()) == [campaign]


# ------------------------------------------------------------ utm.tag/stage --


class TestUtmTagAndStage:

    def test_default_color_is_within_the_reference_range(self):
        assert all(1 <= _default_color() <= 11 for _ in range(50))

    def test_tag_gets_a_colour_without_being_asked(self):
        tag = UtmTag.objects.create(name='promo')

        assert 1 <= tag.color <= 11

    def test_stage_orders_by_sequence(self):
        UtmStage.objects.create(name='Cerradas', sequence=9)
        UtmStage.objects.create(name='Nuevas', sequence=1)

        assert [s.name for s in UtmStage.objects.all()] == [
            'Nuevas', 'Cerradas', 'New']


# ----------------------------------------------------------------- ir.http --


class TestIrHttpUtmCapture:

    def test_domain_comes_from_the_request_host(self):
        request = RequestFactory().get('/')

        # ``testserver`` es el host que ``RequestFactory`` fija por defecto.
        assert IrHttp.get_utm_domain_cookies(request) == 'testserver'

    def test_url_parameters_land_in_cookies(self):
        request = RequestFactory().get(
            '/?utm_campaign=verano&utm_source=buscador&utm_medium=banner')
        response = UtmCookieMiddleware(lambda _req: _Response())(request)

        assert response.cookies['kaupamex_utm_campaign'].value == 'verano'
        assert response.cookies['kaupamex_utm_source'].value == 'buscador'
        assert response.cookies['kaupamex_utm_medium'].value == 'banner'

    def test_cookie_lives_for_thirty_one_days(self):
        request = RequestFactory().get('/?utm_source=buscador')
        response = UtmCookieMiddleware(lambda _req: _Response())(request)

        assert response.cookies['kaupamex_utm_source']['max-age'] == 31 * 24 * 3600

    def test_unchanged_value_is_not_rewritten(self):
        """La guarda de la fuente: sin cambio, no se reemite la cookie."""
        request = RequestFactory().get('/?utm_source=buscador')
        request.COOKIES['kaupamex_utm_source'] = 'buscador'
        response = UtmCookieMiddleware(lambda _req: _Response())(request)

        assert 'kaupamex_utm_source' not in response.cookies

    def test_a_request_without_parameters_sets_nothing(self):
        request = RequestFactory().get('/')
        response = UtmCookieMiddleware(lambda _req: _Response())(request)

        assert response.cookies == {}

    def test_post_parameters_are_captured_too(self):
        """``request.params`` de la fuente cubre GET y POST."""
        request = RequestFactory().post('/', {'utm_medium': 'correo'})
        response = UtmCookieMiddleware(lambda _req: _Response())(request)

        assert response.cookies['kaupamex_utm_medium'].value == 'correo'


class _Response:
    """Respuesta mínima con la superficie de cookies que el middleware usa."""

    def __init__(self):
        self.cookies = {}

    def set_cookie(self, key, value, max_age=None, domain=None):
        self.cookies[key] = _Cookie(value, max_age, domain)


class _Cookie:

    def __init__(self, value, max_age, domain):
        self.value = value
        self._attrs = {'max-age': max_age, 'domain': domain}

    def __getitem__(self, item):
        return self._attrs[item]
