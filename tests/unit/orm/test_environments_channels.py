"""Los dos canales del entorno — dato vs elevación (DEC-AISL-04 §2-3).

Contrato fiel a la referencia, verificado idéntico en las dos poblaciones:

- ``env.companies``: ctx validado contra lo permitido, ``AccessError`` en el
  excedente, fallback al permitido completo (``odoo19c:
  odoo/orm/environments.py``, símbolo ``def companies``; en 18c vive en
  ``odoo/api.py``).
- ``env.su`` / ``sudo()``: no cambia al usuario, omite las reglas, y — verbatim
  del docstring de la fuente — *"No sanity checks applied in sudo mode!"*.
- La ausencia de dato DENIEGA (fail-closed); ya no existe el centinela
  ``company=None`` como elevación implícita.
"""
import pytest

from exceptions import AccessError
from orm.environments import (
    activate_companies,
    company_scope,
    get_current_companies,
    get_current_company,
    is_su,
    sudo,
)


@pytest.fixture(autouse=True)
def _clean_context():
    activate_companies((), ())
    yield
    activate_companies((), ())


class TestCanalDelDato:
    def test_fallback_al_permitido_completo(self):
        # "If not specified in the context, fallback on current user companies."
        assert activate_companies((), (7, 9)) == (7, 9)
        assert get_current_companies() == (7, 9)
        assert get_current_company() == 7  # env.company = la primera activada

    def test_pedido_valido_subconjunto(self):
        assert activate_companies((9,), (7, 9)) == (9,)
        assert get_current_company() == 9

    def test_excedente_no_autorizado_es_access_error(self):
        with pytest.raises(AccessError):
            activate_companies((7, 13), (7, 9))

    def test_sin_dato_deniega_no_eleva(self):
        activate_companies((), ())
        assert get_current_companies() == ()
        assert get_current_company() is None
        assert is_su() is False  # ausencia de dato ≠ elevación


class TestCanalDeElevacion:
    def test_sudo_es_bloque_explicito_y_se_restaura(self):
        assert is_su() is False
        with sudo():
            assert is_su() is True
        assert is_su() is False

    def test_sudo_omite_el_sanity_check(self):
        # "No sanity checks applied in sudo mode!" — habilita inter-company.
        with sudo():
            assert activate_companies((13,), (7, 9)) == (13,)

    def test_sudo_no_toca_el_canal_del_dato(self):
        activate_companies((), (7,))
        with sudo():
            assert get_current_companies() == (7,)  # el dato no cambia
        assert get_current_companies() == (7,)

    def test_company_scope_sigue_siendo_dato_no_elevacion(self):
        with company_scope(5):
            assert get_current_company() == 5
            assert is_su() is False
        assert get_current_company() is None
