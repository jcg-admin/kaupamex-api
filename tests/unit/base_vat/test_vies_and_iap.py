"""La mitad VIES de ``base_vat``: la casilla de empresa, el par IAP y el cron.

Los símbolos que consultan al proxy están **bloqueados** por
``tools.hash_sign`` (sucesor #461) y sus casos viven en
``test_extension_wiring.py``. Aquí se ejerce todo lo que **sí** se porta: el
predicado que decide si hay que preguntar, el par de credenciales, la elección
de endpoint y el guardado del estado.
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_company import ResCompany
from addons.base.models.res_country import ResCountry
from addons.base.models.res_partner import ResPartner
from addons.base_vat.models import res_partner as vat
from exceptions import ValidationError
from orm.environments import context_scope, set_current_company

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    """Una empresa activada, y desactivada al salir.

    El ``finally`` no es adorno: ``set_current_company`` escribe en un
    ``ContextVar`` que sobrevive al caso, y sin restaurar el siguiente test
    heredaría la empresa de éste.
    """
    creada = ResCompany.objects.create(name='Kaupamex QA VIES')
    set_current_company(creada.pk)
    try:
        yield creada
    finally:
        set_current_company(None)


# --- _companies_with_vies_check ------------------------------------------

def test_companies_with_vies_check_only_counts_the_ones_with_the_box_on(company):
    """≙ el ``search_count`` de ``_compute_vies_valid`` (``odoo19c: :200``).

    El par discrimina: con la casilla apagada la consulta debe estar vacía, y
    encenderla debe hacerla aparecer. Un predicado que ignorase el campo
    devolvería la empresa en los dos casos.
    """
    assert not vat._companies_with_vies_check().filter(pk=company.pk).exists()
    company.vat_check_vies = True
    company.save(update_fields=['vat_check_vies'])
    assert vat._companies_with_vies_check().filter(pk=company.pk).exists()


# --- perform_vies_validation ---------------------------------------------

def test_perform_vies_validation_is_false_without_the_company_box(company):
    """≙ ``_compute_perform_vies_validation`` (``odoo19c: :186-197``).

    Con la casilla apagada no hay nada que preguntar, aunque el partner traiga
    un identificador intracomunitario.
    """
    partner = ResPartner.objects.create(name='Socio BE', vat='BE0477472701')
    assert partner.perform_vies_validation is False


def test_perform_vies_validation_skips_a_number_from_the_company_country(company):
    """El prefijo igual al país de la empresa **no** se consulta a VIES.

    ≙ ``not to_check[:2].upper() == company_code`` (``odoo19c: :193``). El par
    es lo que discrimina el predicado del país: el mismo partner sale ``True``
    cuando la empresa es de otro país y ``False`` cuando es del suyo. Sin esa
    condición, un número doméstico saldría a preguntar a la base
    intracomunitaria en los dos casos.
    """
    company.vat_check_vies = True
    company.save(update_fields=['vat_check_vies'])
    partner = ResPartner.objects.create(name='Socio BE', vat='BE0477472701')

    # Los países vienen sembrados por ``base``; crearlos aquí choca con la
    # unicidad de ``code`` (medido: IntegrityError sobre res_country_code_key).
    belgica = ResCountry.objects.get(code='BE')
    otro = ResCountry.objects.exclude(code='BE').first()

    company.country = otro
    company.save()
    assert partner.perform_vies_validation is True, (
        'con la empresa en otro país, BE es intracomunitario y se pregunta')

    company.country = belgica
    company.save()
    assert partner.perform_vies_validation is False, (
        'con la empresa en BE, el número es doméstico y no se pregunta')


def test_perform_vies_validation_is_false_without_vat(company):
    """Sin identificador no hay nada que validar — ≙ ``to_check and …``."""
    company.vat_check_vies = True
    company.save(update_fields=['vat_check_vies'])
    partner = ResPartner.objects.create(name='Socio sin VAT')
    assert partner.perform_vies_validation is False


# --- _compute_vies_valid: las dos ramas que NO consultan ------------------

def test_compute_vies_valid_is_false_when_no_company_asks_for_it(company):
    """≙ ``_compute_vies_valid`` (``odoo19c: :198-213``), rama sin empresas.

    Ninguna empresa con la casilla encendida ⇒ ``vies_valid = False`` sin
    salir a la red. Es una de las dos ramas que este porte cubre entero.
    """
    partner = ResPartner.objects.create(name='Socio', vat='BE0477472701')
    assert vat._compute_vies_valid(partner) is False
    assert partner.vies_valid is False


def test_compute_vies_valid_inherits_from_the_parent_with_the_same_vat(company):
    """≙ la rama ``self.parent_id.vat == self.vat`` (``odoo19c: :207-209``).

    El contacto que comparte identificador con su matriz hereda su veredicto
    en vez de volver a preguntar. Discrimina: si el porte no mirase al padre,
    el contacto saldría ``False`` y no ``True``.
    """
    company.vat_check_vies = True
    company.save(update_fields=['vat_check_vies'])
    matriz = ResPartner.objects.create(
        name='Matriz', vat='BE0477472701', vies_valid=True)
    contacto = ResPartner.objects.create(
        name='Contacto', vat='BE0477472701', parent=matriz)
    assert vat._compute_vies_valid(contacto) is True


# --- _get_iap_vies_credentials -------------------------------------------

def test_iap_credentials_are_created_once_and_then_reused():
    """≙ ``_get_iap_vies_credentials`` (``odoo19c: :221-256``).

    La segunda llamada debe devolver **el mismo par**: la fuente sólo da de
    alta credenciales cuando no existen, porque el proxy sólo acepta consultas
    de actualización de quien hizo la consulta original. Un porte que las
    regenerara en cada llamada pasaría un caso que sólo mirase «devuelve algo».
    """
    primero = vat._get_iap_vies_credentials(object())
    segundo = vat._get_iap_vies_credentials(object())
    assert primero == segundo
    assert all(primero), 'ninguno de los dos puede venir vacío'
    assert SystemParameter.get_param(vat.IAP_CLIENT_IDENTIFIER_PARAM) == primero[0]


# --- _get_iap_vies_endpoint ----------------------------------------------

def test_iap_endpoint_defaults_to_production_without_demo_data():
    """≙ ``_get_iap_vies_endpoint`` (``odoo19c: :259-265``)."""
    production, _testing = vat.IAP_VIES_ENDPOINTS
    assert vat._get_iap_vies_endpoint(object()) == production


def test_iap_endpoint_rejects_a_third_party_host():
    """El ``ValidationError`` de la fuente protege contra apuntar a cualquiera.

    Es el control que discrimina de verdad: sin esa guarda, el parámetro haría
    que las consultas de VAT salieran al host que alguien escribiera ahí.
    """
    SystemParameter.set_param(vat.IAP_ENDPOINT_PARAM, 'https://ejemplo.invalid')
    with pytest.raises(ValidationError):
        vat._get_iap_vies_endpoint(object())


# --- _update_vies_status --------------------------------------------------

@pytest.mark.parametrize('status, expected', [('valid', True), ('invalid', False)])
def test_update_vies_status_persists_the_verdict(status, expected):
    """≙ ``_update_vies_status`` (``odoo19c: :328-340``).

    Sólo ``"valid"`` da ``True``; cualquier otro estado del proxy da ``False``.
    La nota en el hilo del partner que la fuente además escribe está bloqueada
    por ``mail.thread._message_log_batch`` (sucesor **#462**); la escritura del
    estado —el trabajo del método— sí se hace, y es lo que este caso mide.
    """
    partner = ResPartner.objects.create(name='Socio estado', vat='BE0477472701')
    vat._update_vies_status(partner, status)
    assert ResPartner.objects.get(pk=partner.pk).vies_valid is expected


# --- _no_vat_validation ---------------------------------------------------

def test_no_vat_validation_reads_the_context():
    """≙ ``self.env.context.get('no_vat_validation')`` (``odoo19c: :138``)."""
    assert vat._no_vat_validation() is False
    with context_scope(no_vat_validation=True):
        assert vat._no_vat_validation() is True
    assert vat._no_vat_validation() is False
