"""Tests — el vendedor, el usuario principal y el idioma de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_default_category`` (``:197-198``), ``_compute_lang`` (``:398-405``),
``_compute_user_id`` (``:419-423``) y ``_compute_main_user_id`` (``:426-441``).

Los dos campos de usuario NO son el mismo, y la fuente lo avisa en un
comentario propio (``:230``): *"Warning: user_id is a Salesperson, not the
inverse of partner_id in res.users. For the latter, see user_ids and
main_user_id."*

- **el vendedor** (``user``) es quien atiende a este contacto. Es una columna
  con cómputo: se hereda del padre al crear y se puede reescribir a mano.
- **el usuario principal** (``main_user``) es el inverso: de entre las cuentas
  que apuntan a este partner, la más apropiada. No es columna — se deriva.

Confundirlos hace que asignar un vendedor cambie de quién es la cuenta, que es
la clase de error que un contacto compartido entre dos comerciales destapa
tarde.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from django.contrib.auth import get_user_model

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner, ResPartnerCategory
from orm.environments import context_scope, user_scope
from orm.utils import SUPERUSER_ID

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'VendedorYPrincipal123!'


def _user(login, internal=True, active=True):
    """Una cuenta que apunta a su own partner, interna o compartida."""
    account = User.objects.create_user(login=login, password=PASSWORD)
    if internal:
        group = ResGroups.objects.create(name=f'grupo-{login}',
                                         user_type='internal')
        account.group_ids.add(group)
    if not active:
        account.active = False
        account.save()
    return account


class TestComputeLang:
    """≙ ``_compute_lang`` (``:398-405``).

    Docstring de la fuente, verbatim: *"While creating / updating child
    contact, take the parent lang by default if any. 0therwise, fallback to
    default context / DB lang"*.
    """

    def test_a_child_takes_the_language_of_its_parent(self, db):
        """El eje. Qué lo haría fallar: no mirar al padre."""
        parent = ResPartner.objects.create(name='Matriz', is_company=True,
                                           lang='ja-jp')
        child = ResPartner.objects.create(name='Contacto', parent=parent)
        assert child.lang == 'ja-jp'

    def test_a_child_overrides_its_own_language_with_the_parents(self, db):
        """CONTROL de la asimetría del ``if``/``elif``.

        Con padre, el idioma del padre **gana** sobre el que el hijo ya tenía.
        Qué lo haría fallar: anteponer ``if not partner.lang``, que es la
        lectura cómoda y deja al hijo con el suyo.
        """
        parent = ResPartner.objects.create(name='Matriz', is_company=True,
                                           lang='ja-jp')
        child = ResPartner.objects.create(name='Contacto', lang='es-mx')
        child.parent = parent
        child.save()
        assert child.lang == 'ja-jp'

    def test_a_child_of_a_parent_without_language_falls_back(self, db):
        """CONTROL del ``or`` de la fuente — el padre mudo no borra el idioma.

        Qué lo haría fallar: asignar ``parent.lang`` a secas. El hijo quedaría
        con la cadena vacía, que no es «hereda del padre» sino «sin idioma».
        """
        parent = ResPartner.objects.create(name='Matriz muda', is_company=True)
        child = ResPartner.objects.create(name='Contacto', parent=parent)
        assert child.lang

    def test_a_loose_partner_with_its_own_language_keeps_it(self, db):
        """CONTROL de la guarda ``elif not partner.lang``.

        Sin padre y con idioma propio, nadie lo toca. Qué lo haría fallar:
        asignar el idioma por defecto sin comprobar que ya había uno.
        """
        who = ResPartner.objects.create(name='Suelto', lang='ja-jp')
        who.city = 'Osaka'
        who.save()
        assert who.lang == 'ja-jp'


class TestComputeUserId:
    """≙ ``_compute_user_id`` (``:419-423``).

    Docstring de la fuente, verbatim: *"Synchronize sales rep with parent if
    partner is a person"*.
    """

    def test_a_person_takes_the_salesperson_of_its_parent(self, db):
        """El eje."""
        seller = _user('vendedor.eje@practicayoruba.mx')
        parent = ResPartner.objects.create(name='Matriz', is_company=True,
                                           user=seller)
        who = ResPartner.objects.create(name='Persona', parent=parent)
        assert who.user_id == seller.pk

    def test_a_company_does_not_take_it(self, db):
        """CONTROL de ``company_type == 'person'``.

        Una filial es una entidad comercial propia: su vendedor no se hereda.
        Qué lo haría fallar: quitar la comprobación del tipo.
        """
        seller = _user('vendedor.filial@practicayoruba.mx')
        parent = ResPartner.objects.create(name='Matriz', is_company=True,
                                           user=seller)
        who = ResPartner.objects.create(name='Filial', is_company=True,
                                        parent=parent)
        assert who.user_id is None

    def test_a_partner_that_already_has_one_keeps_it(self, db):
        """CONTROL de ``not partner.user_id`` — el cómputo no pisa lo puesto.

        Qué lo haría fallar: asignar el del padre siempre. El comercial que
        reasigna una cuenta a mano la perdería en la siguiente escritura.
        """
        from_parent = _user('vendedor.padre@practicayoruba.mx')
        own = _user('vendedor.own@practicayoruba.mx')
        parent = ResPartner.objects.create(name='Matriz', is_company=True,
                                           user=from_parent)
        who = ResPartner.objects.create(name='Persona', parent=parent,
                                        user=own)
        assert who.user_id == own.pk

    def test_without_a_parent_nothing_is_assigned(self, db):
        """CONTROL de ``partner.parent_id.user_id``."""
        who = ResPartner.objects.create(name='Suelto')
        assert who.user_id is None


class TestComputeMainUser:
    """≙ ``_compute_main_user_id`` (``:426-441``)."""

    def test_the_only_active_user_is_the_main_one(self, db):
        """El eje."""
        account = _user('principal.unico@practicayoruba.mx')
        assert account.partner.main_user == account.pk

    def test_an_internal_user_beats_a_shared_one(self, db):
        """CONTROL del término ``not u.share`` del orden.

        Qué lo haría fallar: ordenar sólo por id. El compartido se creó
        primero, así que con el id solo ganaría él.
        """
        shared = _user('principal.shared@practicayoruba.mx',
                           internal=False)
        internal = _user('principal.internal@practicayoruba.mx')
        who = shared.partner
        internal.partner = who
        internal.save()
        assert who.main_user == internal.pk

    def test_among_internal_users_the_lowest_id_wins(self, db):
        """CONTROL del término ``-u.id`` del orden.

        Qué lo haría fallar: quedarse con el último. La fuente prefiere la
        cuenta **más antigua**, que es la que lleva el histórico.
        """
        first = _user('principal.first@practicayoruba.mx')
        second = _user('principal.second@practicayoruba.mx')
        who = first.partner
        second.partner = who
        second.save()
        assert who.main_user == first.pk

    def test_an_archived_user_is_not_chosen(self, db):
        """CONTROL de ``user_ids.filtered('active')``.

        Qué lo haría fallar: no filtrar. Una cuenta archivada seguiría siendo
        la principal y el correo iría a quien ya no está.
        """
        archived = _user('principal.archived@practicayoruba.mx')
        alive = _user('principal.alive@practicayoruba.mx')
        who = archived.partner
        alive.partner = who
        alive.save()
        archived.active = False
        archived.save()
        assert who.main_user == alive.pk

    def test_the_partner_of_the_current_user_is_that_user(self, db):
        """CONTROL de la primera rama, que cortocircuita el orden.

        La fuente reserva ``env.user.partner_id`` antes de ordenar nada: para
        el partner de quien mira, el principal es él mismo aunque haya otra
        cuenta más antigua apuntando ahí.

        Qué lo haría fallar: caer directo al orden, que elegiría al primero.
        """
        first = _user('principal.otro@practicayoruba.mx')
        viewer = _user('principal.yo@practicayoruba.mx')
        who = first.partner
        viewer.partner = who
        viewer.save()
        with user_scope(viewer.pk):
            assert who.main_user == viewer.pk

    def test_a_partner_without_users_has_no_main_user(self, db):
        """CONTROL del caso vacío — ni excepción ni un id inventado."""
        who = ResPartner.objects.create(name='Sin cuentas')
        assert who.main_user is None

    def test_the_superuser_partner_falls_back_to_the_superuser(self, db):
        """CONTROL de la rama especial de la fuente.

        Su comentario, verbatim: *"Special case for OdooBot as its user might
        be archived."* Con la cuenta raíz archivada, su partner sigue teniendo
        usuario principal. Qué lo haría fallar: quitar el caso especial.
        """
        root = User.objects.filter(pk=SUPERUSER_ID).first()
        if root is None:
            # La base de QA no siembra la cuenta raiz, asi que el caso la
            # construye. Saltarlo dejaria la rama sin control ninguno, que es
            # justo lo que el sub-patron D prohibe.
            root = User.objects.create_user(
                login='raiz@practicayoruba.mx', password=PASSWORD)
            User.objects.filter(pk=root.pk).update(id=SUPERUSER_ID)
            root = User.objects.get(pk=SUPERUSER_ID)
        assert root.partner_id is not None, 'la cuenta raiz tiene partner'
        root.active = False
        root.save()
        assert root.partner.main_user == SUPERUSER_ID


class TestDefaultCategory:
    """≙ ``_default_category`` (``:197-198``)."""

    def test_it_reads_the_category_from_the_context(self, db):
        """El eje: la categoría inicial la pone quien abre el formulario."""
        tag = ResPartnerCategory.objects.create(name='Mayorista')
        with context_scope(category_id=tag.pk):
            assert [c.pk for c in ResPartner._default_category()] == [tag.pk]

    def test_without_context_it_is_empty(self, db):
        """CONTROL — qué lo haría fallar: devolver todas las categorías.

        La fuente hace ``browse(None)``, que es un recordset vacío, no el
        conjunto entero.
        """
        ResPartnerCategory.objects.create(name='Minorista')
        assert list(ResPartner._default_category()) == []
