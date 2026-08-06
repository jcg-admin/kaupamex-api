"""Contrato de ``MailAlias`` y ``MailAliasDomain`` — portación fiel de Odoo
``mail.alias`` / ``mail.alias.domain`` (``odoo19c:``, ``odoo-tools@622ddc2a``).

Verifica:

- importables desde el hogar canónico ``addons.mail.models``,
- ``db_table`` fieles a Odoo (``mail_alias`` / ``mail_alias_domain``),
- ``sanitize_alias_name``: quita acentos, baja a minúsculas, corta en ``@``,
  no deja puntos al inicio/fin, sustituye lo no permitido por ``-``; con
  ``is_email=True`` conserva la parte derecha,
- los tres derivados del dominio (``bounce_email`` / ``catchall_email`` /
  ``default_from_email``) y el quirk de ``default_from``: si ya trae ``@``, NO
  se le concatena el dominio,
- ``display_name`` en sus tres ramas (con dominio, sin dominio, sin nombre),
- ``alias_full_name`` se recalcula al guardar y NO usa el texto de UI
  "Inactive Alias" (es columna de búsqueda),
- el nombre de dominio debe casar ``DOT_ATOM_TEXT`` (``clean()`` levanta),
- unicidad ``(alias_name, COALESCE(alias_domain_id, 0))``: el COALESCE es lo
  que hace colisionar dos aliases homónimos SIN dominio.

Toca DB → django_db.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from addons.base.models import IrModel
from addons.mail.models import (
    DOT_ATOM_TEXT,
    MailAlias,
    MailAliasDomain,
    sanitize_alias_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _modelo(name='orders.Order'):
    """El modelo reflejado al que apunta el alias (Odoo ``alias_model_id``)."""
    return IrModel.objects.create(model=name, name=name)


def _dominio(name='example.com', **kw):
    return MailAliasDomain.objects.create(name=name, **kw)


# --- Importables desde el hogar canónico ------------------------------------

def test_importables_desde_addons_mail_models():
    assert MailAlias.__module__ == 'addons.mail.models.mail_alias'
    assert MailAliasDomain.__module__ == 'addons.mail.models.mail_alias_domain'


def test_db_table_matches_reference():
    assert MailAlias._meta.db_table == 'mail_alias'
    assert MailAliasDomain._meta.db_table == 'mail_alias_domain'


# --- sanitize_alias_name (Odoo _sanitize_alias_name) ------------------------

@pytest.mark.parametrize('crudo,esperado', [
    ('Jobs', 'jobs'),
    ('  Josè Ñandú ', 'jose-nandu'),
    ('jobs@example.com', 'jobs'),        # sin is_email se corta en la arroba
    ('...jobs...', 'jobs'),              # ni empieza ni termina en punto
    ('a..b', 'a.b'),                     # puntos consecutivos colapsan
])
def test_sanitize_alias_name(crudo, esperado):
    assert sanitize_alias_name(crudo) == esperado


def test_sanitize_alias_name_vacio_devuelve_false():
    """Odoo devuelve ``False``, no ``''`` — quien llama distingue los casos."""
    assert sanitize_alias_name('   ') is False
    assert sanitize_alias_name(None) is False


def test_sanitize_alias_name_is_email_conserva_la_derecha():
    assert sanitize_alias_name('Notifications@Example.com', is_email=True) == \
        'notifications@example.com'


def test_sanitize_alias_name_is_email_sin_arroba_no_inventa_dominio():
    assert sanitize_alias_name('notifications', is_email=True) == 'notifications'


# --- Derivados del dominio (Odoo compute sin store) -------------------------

def test_dominio_derivados():
    d = _dominio('example.com', bounce_alias='bounce',
                 catchall_alias='catchall', default_from='notifications')
    assert d.bounce_email == 'bounce@example.com'
    assert d.catchall_email == 'catchall@example.com'
    assert d.default_from_email == 'notifications@example.com'


def test_default_from_completo_no_recibe_el_dominio():
    """Odoo ``_compute_default_from_email``: ``default_from`` admite un correo
    completo; sólo se le añade el dominio si NO trae arroba."""
    d = _dominio('example.com', default_from='avisos@otrodominio.com')
    assert d.default_from_email == 'avisos@otrodominio.com'


def test_dominio_sin_bounce_devuelve_cadena_vacia():
    d = MailAliasDomain(name='example.com', bounce_alias='')
    assert d.bounce_email == ''


# --- Nombre de dominio: DOT_ATOM_TEXT ---------------------------------------

def test_dot_atom_text_acepta_dominio_valido():
    assert DOT_ATOM_TEXT.match('mail.example.com')


def test_clean_rechaza_dominio_con_acentos():
    """Odoo ``_check_name``: NO sanea dinámicamente (confundiría) — levanta."""
    d = MailAliasDomain(name='exámple.com')
    with pytest.raises(ValidationError):
        d.clean()


def test_clean_rechaza_dominio_vacio():
    with pytest.raises(ValidationError):
        MailAliasDomain(name='').clean()


# --- display_name y alias_full_name -----------------------------------------

def test_display_name_con_dominio():
    a = MailAlias.objects.create(alias_name='jobs', alias_model=_modelo(),
                                 alias_domain=_dominio())
    assert a.display_name == 'jobs@example.com'


def test_display_name_sin_dominio():
    a = MailAlias.objects.create(alias_name='jobs', alias_model=_modelo())
    assert a.display_name == 'jobs'


def test_display_name_sin_nombre_es_inactive_alias():
    a = MailAlias.objects.create(alias_model=_modelo())
    assert a.display_name == 'Inactive Alias'


def test_alias_full_name_se_calcula_al_guardar():
    a = MailAlias.objects.create(alias_name='jobs', alias_model=_modelo(),
                                 alias_domain=_dominio())
    a.refresh_from_db()
    assert a.alias_full_name == 'jobs@example.com'


def test_alias_full_name_no_usa_el_texto_de_ui():
    """A diferencia de ``display_name``, es columna de búsqueda: sin nombre
    queda NULL, no la cadena "Inactive Alias"."""
    a = MailAlias.objects.create(alias_model=_modelo())
    a.refresh_from_db()
    assert a.alias_full_name is None
    assert a.display_name == 'Inactive Alias'


def test_alias_name_se_sanea_al_guardar():
    a = MailAlias.objects.create(alias_name='  Josè Ñandú ', alias_model=_modelo())
    a.refresh_from_db()
    assert a.alias_name == 'jose-nandu'


# --- Unicidad (alias_name, COALESCE(alias_domain_id, 0)) --------------------

def test_alias_duplicado_en_el_mismo_dominio_viola_unicidad():
    d = _dominio()
    MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('a.A'),
                             alias_domain=d)
    with pytest.raises(IntegrityError), transaction.atomic():
        MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('b.B'),
                                 alias_domain=d)


def test_mismo_alias_en_dominios_distintos_es_valido():
    MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('a.A'),
                             alias_domain=_dominio('uno.com'))
    MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('b.B'),
                             alias_domain=_dominio('dos.com'))
    assert MailAlias.objects.filter(alias_name='jobs').count() == 2


def test_coalesce_hace_colisionar_dos_alias_sin_dominio():
    """El ``COALESCE(alias_domain_id, 0)`` de Odoo existe justamente para esto:
    sin él, ``NULL != NULL`` dejaría pasar el duplicado."""
    MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('a.A'))
    with pytest.raises(IntegrityError), transaction.atomic():
        MailAlias.objects.create(alias_name='jobs', alias_model=_modelo('b.B'))


# --- Unicidad de bounce / catchall por dominio ------------------------------

def test_bounce_duplicado_en_dominio_homonimo_viola_unicidad():
    _dominio('example.com', bounce_alias='bounce')
    with pytest.raises(IntegrityError), transaction.atomic():
        _dominio('example.com', bounce_alias='bounce')


def test_check_bounce_catchall_detecta_alias_que_ya_ocupa_la_direccion():
    """Odoo ``_check_bounce_catchall_uniqueness`` (2ª mitad): si un
    ``mail.alias`` ya ocupa bounce@/catchall@, el correo entrante se rutearía
    al alias en vez de a la pasarela."""
    d = _dominio('example.com')
    MailAlias.objects.create(alias_name='bounce', alias_model=_modelo(),
                             alias_domain=d)
    otro = MailAliasDomain(name='example.com', bounce_alias='bounce')
    with pytest.raises(ValidationError):
        otro._check_bounce_catchall_uniqueness()
