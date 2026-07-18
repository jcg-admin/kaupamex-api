"""authz_password_policy — política de contraseña configurable en caliente (L2).

Adaptación nativa de ``auth_password_policy`` de Odoo: la longitud mínima vive
en ``SystemParameter`` (``authz.password_minlength``), editable en runtime, y se
aplica vía la API nativa ``AUTH_PASSWORD_VALIDATORS`` (por lo que corre en el
registro y el cambio de contraseña, que ya llaman ``validate_password``).

Verifica:
- el valor NO está cableado: se lee de L2 (sembrado a 8 por la migración);
- cambiar el ``SystemParameter`` cambia el enforcement en caliente;
- si la clave se borra, la política se deshabilita (fallback 0, fiel a Odoo);
- integración con ``django.contrib.auth.password_validation.validate_password``.
"""
import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from addons.base.models import SystemParameter, _clear_cache
from addons.authz_password_policy.validators import (
    ConfigurablePasswordPolicyValidator,
    get_password_policy,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reset_param_cache():
    """El caché de ``SystemParameter`` es global de proceso (no transaccional);
    limpiarlo evita fugas entre tests cuando el rollback restaura la BD pero no
    el caché."""
    _clear_cache()
    yield
    _clear_cache()


def test_policy_seeded_to_8_not_hardcoded():
    """La política se lee de L2 (sembrada por la migración), no del código."""
    assert get_password_policy()['minlength'] == 8
    assert SystemParameter.get_param('authz.password_minlength') == '8'


def test_validator_rejects_below_configured_minlength():
    v = ConfigurablePasswordPolicyValidator()
    with pytest.raises(ValidationError) as exc:
        v.validate('Ab3!x')  # 5 < 8
    assert exc.value.error_list[0].code == 'password_too_short'


def test_validator_accepts_at_or_above_minlength():
    v = ConfigurablePasswordPolicyValidator()
    # 8 caracteres exactos: no lanza (la cota es "< minlength").
    assert v.validate('Abcd3fg!') is None


def test_policy_is_hot_editable_via_systemparameter():
    """Subir la cota a 12 en L2 rechaza una contraseña de 8 sin redeploy."""
    SystemParameter.set_param('authz.password_minlength', '12')
    v = ConfigurablePasswordPolicyValidator()
    with pytest.raises(ValidationError):
        v.validate('Abcd3fg!')  # 8 < 12
    assert get_password_policy()['minlength'] == 12


def test_absent_param_disables_policy_like_odoo():
    """Borrar la clave L2 deshabilita el enforcement (fallback 0, fiel a Odoo)."""
    SystemParameter.set_param('authz.password_minlength', None)  # delete
    v = ConfigurablePasswordPolicyValidator()
    assert v.validate('a') is None  # 1 char pasa: política off
    assert get_password_policy()['minlength'] == 0


def test_integration_with_django_validate_password():
    """El validador corre dentro de ``validate_password`` (registro/cambio).

    Contraseña que pasa los otros validadores (no común, no numérica pura) pero
    falla la longitud cuando la cota L2 sube a 20.
    """
    SystemParameter.set_param('authz.password_minlength', '20')
    with pytest.raises(ValidationError):
        validate_password('Abcd3fg!x')  # 9 < 20, pero no común/numérica
