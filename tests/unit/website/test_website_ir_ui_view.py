"""Contrato de la extensión que ``website`` cuelga sobre ``ir.ui.view``.

Tarea **#565**. Adaptación de
``odoo19c: addons/website/models/ir_ui_view.py`` (``odoo-tools@622ddc2a``,
LGPL-3, 542 líneas). Contrato medido por AST sobre su única clase
``IrUiView``: **10 atributos de clase (2 de ORM + 8 campos) y 36 métodos**;
**12 portados, 24 bloqueados**.

Los casos cubren cuatro cosas, y la segunda es la que un porte silencioso
perdería:

1. **Lo portado existe** — los 12 métodos y los campos, colgados sobre el
   ``ir.ui.view`` de ``base``.
2. **Lo bloqueado NO existe como stub** — 23 de los 24 no portados no pueden
   aparecer con el nombre de la fuente y un cuerpo vacío: eso convertiría una
   arista honesta en una mentira. El vigésimo cuarto (``save``) se excluye
   porque el nombre lo ocupa ``django.db.models.Model.save``, que no es el
   símbolo de la fuente.
3. **El comportamiento**, contra PostgreSQL real — la fila lateral, sus
   defectos, el par contraseña/hash, el invariante de ``visibility`` y el
   control de acceso.
4. **Los cuatro ganchos encadenados** — que el delta del sitio se suma al de
   ``base`` en vez de reemplazarlo, que es lo que un ``chain_method`` mal
   compuesto haría en silencio.
"""

import pytest
from django.contrib.auth import hashers

from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_company import ResCompany
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.website.models.ir_ui_view import (
    VISIBILITY_CHOICES,
    WebsiteViewInfo,
)
from addons.website.models.website import Website
from addons.website.models.website_page import WebsitePage
from exceptions import AccessError
from orm.environments import context_scope

#: Los 12 métodos que #565 porta, en el orden en que la fuente los declara.
PORTED_METHODS = [
    '_get_pwd',
    '_set_pwd',
    '_compute_first_page_id',
    'get_view_hierarchy',
    '_build_hierarchy_datastructure',
    'filter_duplicate',
    '_get_cached_template_prefetched_keys',
    '_get_template_domain',
    '_get_template_order',
    '_fetch_template_views',
    '_get_cached_visibility',
    '_handle_visibility',
]

#: Los 23 bloqueados cuyo nombre NO debe existir sobre ``ir.ui.view``.
#: ``save`` queda fuera: lo ocupa ``Model.save`` de Django, que no es el
#: ``save`` del editor de la fuente (``odoo19c: :484-507``).
BLOCKED_METHODS = [
    'create', 'write', 'unlink', '_load_records_write_on_cow',
    '_create_all_specific_views', '_create_website_specific_pages_for_view',
    '_compute_display_name', 'get_related_views',
    '_view_get_inherited_children', '_get_inheriting_views_domain',
    '_get_inheriting_views', '_get_template_minimal_cache_keys',
    'render_public_asset', '_render_template', 'get_default_lang_code',
    '_read_template_keys', '_update_field_translations', '_get_base_lang',
    '_save_oe_structure_hook', '_snippet_save_view_values_hook',
    '_get_allowed_root_attrs', '_set_noupdate', '_get_filter_xmlid_query',
]

#: Los cuatro campos de la fuente que aquí viven en la fila lateral (D-1).
SIDE_TABLE_FIELDS = ['website', 'track', 'visibility', 'visibility_password']


class TestPortedSurface:
    """Lo portado está colgado sobre ``ir.ui.view``, sin base de datos."""

    def test_the_twelve_methods_are_installed(self):
        missing = [name for name in PORTED_METHODS
                   if not hasattr(IrUiView, name)]
        assert missing == []

    def test_the_underscore_prefix_is_preserved(self):
        # H-API-581: quitar el guion bajo publica lo que la fuente reservó.
        # Diez de los doce son privados allá y tienen que serlo aquí.
        private = [name for name in PORTED_METHODS if name.startswith('_')]
        assert len(private) == 10
        for name in private:
            assert not hasattr(IrUiView, name[1:]), (
                'existe la forma pública de %s' % name)

    def test_the_side_table_fields_are_readable_from_the_view(self):
        for name in SIDE_TABLE_FIELDS:
            assert isinstance(getattr(IrUiView, name), property), (
                '%s debería ser propiedad de lectura (D-1)' % name)

    def test_the_password_display_is_a_read_write_property(self):
        # ``visibility_password_display`` es el par compute/inverse de la
        # fuente (``:35``): tiene lectura y escritura, no sólo lectura.
        prop = IrUiView.visibility_password_display
        assert isinstance(prop, property)
        assert prop.fget is not None and prop.fset is not None

    def test_the_first_page_is_a_non_stored_field(self):
        # ``compute`` sin ``store`` (``:23``): no genera columna.
        assert hasattr(IrUiView, 'first_page_id')
        columns = {f.name for f in IrUiView._meta.get_fields()}
        assert 'first_page_id' not in columns

    def test_the_visibility_choices_come_from_the_source(self):
        assert VISIBILITY_CHOICES == [
            ('', 'Public'),
            ('connected', 'Signed In'),
            ('restricted_group', 'Restricted Group'),
            ('password', 'With Password'),
        ]


class TestBlockedSurface:
    """Lo bloqueado no aparece como stub — si apareciera, la arista miente."""

    def test_the_blocked_methods_are_absent(self):
        """Ausentes **como símbolo de la fuente**, no como nombre.

        El control era ``hasattr`` y dejó de discriminar cuando
        ``TimeStampedModel`` adoptó ``orm.models.RecordLoaderMixin`` (tarea
        #115): desde entonces todo modelo hereda un ``write`` genérico —el que
        el cargador de datos necesita— y ``hasattr(IrUiView, 'write')`` pasó a
        ser cierto sin que nadie hubiera stubbeado el ``write`` de COW de la
        fuente (``odoo19c: website/models/ir_ui_view.py``). Un verde de
        ``hasattr`` ya no distinguía "no hay stub" de "lo hereda del
        framework": sub-patrón D de ``metrica-decide-la-conclusion.md``.

        El discriminador es **quién declara** el nombre. Si lo declara una
        clase de ``orm.`` es un mecanismo del framework, que allá vive en
        ``BaseModel`` y aquí viaja por mixin — no es el símbolo de
        ``website``. Si lo declara una clase de ``addons.``, es un stub y el
        caso cae, nombrando dónde.

        *Métrica:* la primera clase del MRO que declara el nombre en su
        ``__dict__``.
        *Ciega a:* un stub instalado en tiempo de ejecución sobre una clase de
        ``orm.`` — que sería, además, un defecto peor y de otro instrumento.
        """
        stubbed = []
        for name in BLOCKED_METHODS:
            if not hasattr(IrUiView, name):
                continue
            owner = next(klass for klass in IrUiView.__mro__
                         if name in vars(klass))
            if not owner.__module__.startswith('orm.'):
                stubbed.append('%s (declarado en %s.%s)' % (
                    name, owner.__module__, owner.__name__))
        assert stubbed == []

    def test_the_count_matches_the_measured_contract(self):
        # 12 portados + 23 aquí + ``save`` (nombre ocupado por Django) = 36,
        # que es el conteo AST de la fuente.
        assert len(PORTED_METHODS) + len(BLOCKED_METHODS) + 1 == 36

    def test_the_controller_page_field_is_not_stubbed(self):
        # ``controller_page_ids`` (``:22``) queda bloqueado por la ausencia
        # de ``website.controller.page``; declararlo vacío sería fingir.
        assert not hasattr(IrUiView, 'controller_page_ids')

    def test_the_page_ids_relation_already_existed(self):
        # ``page_ids`` (``:21``) NO lo aporta #565: es el reverso de
        # ``website.page.view``, portado por #104. Un segundo One2many
        # duplicaría la relación.
        assert hasattr(IrUiView, 'page_ids')
        related = {f.get_accessor_name()
                   for f in IrUiView._meta.get_fields()
                   if f.auto_created and not f.concrete}
        assert 'page_ids' in related


class TestChainedTemplateHooks:
    """Los cuatro ganchos suman su delta al de ``base``, no lo reemplazan."""

    def test_the_prefetched_keys_keep_the_base_ones(self):
        keys = IrUiView._get_cached_template_prefetched_keys()
        # Primero lo de ``base``, después lo del addon — el orden del
        # ``super() + [...]`` de la fuente.
        assert keys[:3] == ['id', 'key', 'active']
        assert keys[3:] == ['active', 'visibility', 'track']

    def test_the_duplicate_active_is_faithful(self):
        # ``base`` ya publica ``active`` y la fuente vuelve a añadirlo
        # (``odoo19c: odoo/addons/base/models/ir_ui_view.py:1122`` frente a
        # ``addons/website/models/ir_ui_view.py:364``). Deduplicar sería
        # divergir.
        keys = IrUiView._get_cached_template_prefetched_keys()
        assert keys.count('active') == 2

    def test_the_order_puts_the_website_first(self):
        # ≙ ``f"website_id asc, {super()}"``: el sitio delante del orden base.
        assert IrUiView._get_template_order() == (
            'website_info__website_id', 'priority', 'id')

    def test_the_template_domain_narrows_to_the_generic_without_context(self):
        query = str(IrUiView._get_template_domain(['website.algo']))
        assert 'key__in' in query
        assert 'website_info__isnull' in query

    def test_the_template_domain_admits_the_context_website(self):
        with context_scope(website_id=7):
            query = str(IrUiView._get_template_domain(['website.algo']))
        assert 'website_info__website_id' in query
        # La genérica sigue admitida — el ``(False, ctx)`` de la fuente.
        assert 'website_info__isnull' in query


def _make_website(slug='p565'):
    """Sitio mínimo — ``company`` y ``user`` son NOT NULL (B1 de website.py)."""
    company = ResCompany.objects.create(name='Kaupamex %s QA' % slug)
    login = '%s@kaupamex.test' % slug
    user = (ResUsers.objects.filter(login=login).first()
            or ResUsers.objects.create_user(login=login))
    website = Website(name=slug.upper(),
                      domain='https://%s.example.test' % slug,
                      company=company, user=user)
    website.save()
    return website


def _make_view(key='website.vista-565', **overrides):
    values = {
        'name': 'Vista 565',
        'type': 'qweb',
        'key': key,
        'arch_db': '<t><div id="wrap"/></t>',
    }
    values.update(overrides)
    return IrUiView.objects.create(**values)


@pytest.mark.django_db
class TestSideTableDefaults:
    """La fila lateral y su ausencia — el vacío de la fuente (D-1)."""

    def test_a_view_without_the_side_row_is_generic_and_public(self):
        view = _make_view()
        assert view.website is None
        assert view.track is False
        assert view.visibility == ''
        assert view.visibility_password == ''

    def test_the_side_row_carries_the_four_fields(self):
        view = _make_view()
        website = _make_website('p565a')
        info = WebsiteViewInfo.objects.create(
            view=view, website=website, track=True, visibility='connected')
        assert info.view_id == view.pk
        # La vista los lee por sus propiedades.
        view.refresh_from_db()
        assert view.website == website
        assert view.track is True
        assert view.visibility == 'connected'

    def test_the_side_row_dies_with_its_view(self):
        view = _make_view()
        WebsiteViewInfo.objects.create(view=view)
        view.delete()
        assert not WebsiteViewInfo.objects.filter(pk=view.pk).exists()


@pytest.mark.django_db
class TestVisibilityPassword:
    """El par ``_get_pwd`` / ``_set_pwd`` — compute e inverse de la fuente."""

    def test_the_display_masks_a_stored_password(self):
        view = _make_view()
        view._set_pwd('secreto-565')
        assert view._get_pwd() == '********'
        assert view.visibility_password_display == '********'

    def test_the_stored_value_is_a_hash_not_the_password(self):
        view = _make_view()
        view.visibility_password_display = 'secreto-565'
        stored = WebsiteViewInfo.objects.get(view=view).visibility_password
        assert stored != 'secreto-565'
        assert hashers.check_password('secreto-565', stored)

    def test_an_empty_value_clears_the_hash(self):
        view = _make_view()
        view._set_pwd('secreto-565')
        view._set_pwd('')
        assert WebsiteViewInfo.objects.get(view=view).visibility_password == ''
        assert view._get_pwd() == ''

    def test_only_qweb_views_take_a_password(self):
        # ≙ ``if r.type == 'qweb'`` (``odoo19c: :44``).
        view = _make_view(key='website.form-565', type='form')
        view._set_pwd('secreto-565')
        assert not WebsiteViewInfo.objects.filter(view=view).exists()

    def test_the_display_of_a_view_without_password_is_empty(self):
        assert _make_view()._get_pwd() == ''


@pytest.mark.django_db
class TestVisibilityInvariant:
    """El invariante que la fuente aplica al escribir ``visibility``."""

    def test_leaving_restricted_group_clears_the_view_groups(self):
        view = _make_view()
        group = ResGroups.objects.create(name='Grupo 565')
        view.groups.add(group)
        info = WebsiteViewInfo.objects.create(
            view=view, visibility='restricted_group')
        assert view.groups.count() == 1

        info.visibility = ''
        info.save()
        assert view.groups.count() == 0

    def test_restricted_group_keeps_the_view_groups(self):
        view = _make_view()
        view.groups.add(ResGroups.objects.create(name='Grupo 565 bis'))
        info = WebsiteViewInfo.objects.create(view=view)
        info.visibility = 'restricted_group'
        info.save()
        assert view.groups.count() == 1


@pytest.mark.django_db
class TestHandleVisibility:
    """``_handle_visibility`` — el 403 del control de acceso de la fuente."""

    def test_a_public_view_is_served(self):
        view = _make_view()
        assert view._get_cached_visibility() == ''
        assert view._handle_visibility() is True

    def test_a_password_view_without_password_is_refused(self):
        view = _make_view()
        WebsiteViewInfo.objects.create(view=view, visibility='password')
        assert view._handle_visibility(do_raise=False) is False

    def test_the_refusal_carries_the_discriminant_of_the_source(self):
        # La cadena la lee el frontal para pedir la contraseña; se conserva
        # verbatim (D-6).
        view = _make_view()
        WebsiteViewInfo.objects.create(view=view, visibility='password')
        with pytest.raises(AccessError) as raised:
            view._handle_visibility()
        assert 'website_visibility_password_required' in str(raised.value)


@pytest.mark.django_db
class TestFilterDuplicate:
    """``filter_duplicate`` — la más específica por ``key`` (D-3)."""

    def test_without_a_website_only_the_generic_views_survive(self):
        website = _make_website('p565b')
        generic = _make_view(key='website.dup-565')
        specific = _make_view(key='website.dup-565', name='Específica')
        WebsiteViewInfo.objects.create(view=specific, website=website)

        kept = IrUiView.filter_duplicate([generic, specific])
        assert kept == [generic]

    def test_inside_a_website_its_view_wins_over_the_generic(self):
        website = _make_website('p565c')
        generic = _make_view(key='website.dup-565b')
        specific = _make_view(key='website.dup-565b', name='Específica')
        WebsiteViewInfo.objects.create(view=specific, website=website)

        with context_scope(website_id=website.pk):
            kept = IrUiView.filter_duplicate([generic, specific])
        assert kept == [specific]

    def test_a_generic_without_specific_counterpart_survives(self):
        website = _make_website('p565d')
        alone = _make_view(key='website.dup-565c')
        with context_scope(website_id=website.pk):
            kept = IrUiView.filter_duplicate([alone])
        assert kept == [alone]

    def test_a_view_of_another_website_is_dropped(self):
        mine = _make_website('p565e')
        other = _make_website('p565f')
        foreign = _make_view(key='website.dup-565d')
        WebsiteViewInfo.objects.create(view=foreign, website=other)

        with context_scope(website_id=mine.pk):
            kept = IrUiView.filter_duplicate([foreign])
        assert kept == []


@pytest.mark.django_db
class TestHierarchyAndFirstPage:
    """El árbol de herencia y la primera página de la vista."""

    def test_the_hierarchy_climbs_to_the_root(self):
        root = _make_view(key='website.raiz-565')
        child = _make_view(key='website.hija-565', inherit_id=root)

        tree = child.get_view_hierarchy()
        assert tree['hierarchy']['id'] == root.pk
        children = tree['hierarchy']['inherit_children']
        assert [node['id'] for node in children] == [child.pk]

    def test_the_datastructure_carries_the_seven_keys_of_the_source(self):
        node = _make_view(key='website.nodo-565')._build_hierarchy_datastructure()
        assert set(node) == {
            'id', 'name', 'inherit_children', 'arch_updated',
            'website_name', 'active', 'key',
        }

    def test_a_generic_view_reports_no_website_name(self):
        node = _make_view(key='website.nodo-565b')._build_hierarchy_datastructure()
        assert node['website_name'] is False

    def test_a_specific_view_reports_its_website_name(self):
        website = _make_website('p565g')
        view = _make_view(key='website.nodo-565c')
        WebsiteViewInfo.objects.create(view=view, website=website)
        node = view._build_hierarchy_datastructure()
        assert node['website_name'] == website.name

    def test_the_first_page_is_the_one_that_uses_the_view(self):
        website = _make_website('p565h')
        view = _make_view(key='website.pagina-565')
        assert view._compute_first_page_id() is None

        page = WebsitePage.objects.create(
            url='/pagina-565', view=view, website=website)
        assert view._compute_first_page_id() == page


@pytest.mark.django_db
class TestFetchTemplateViews:
    """``_fetch_template_views`` — el sitio en el mensaje del ausente."""

    def test_a_missing_template_names_the_context_website(self):
        with context_scope(website_id=99):
            data = IrUiView._fetch_template_views(['website.no-existe-565'])
        error = data['website.no-existe-565']
        assert isinstance(error, Exception)
        assert '(website: 99)' in str(error)

    def test_an_existing_template_still_resolves(self):
        view = _make_view(key='website.existe-565')
        data = IrUiView._fetch_template_views(['website.existe-565'])
        assert data['website.existe-565'] == view
