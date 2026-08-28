"""El identificador externo, de ida y de vuelta (:ref:`h-api-347`).

``ir.model.data`` existía como tabla desde el porte de ``base``: cinco campos,
sus restricciones, y **ningún modo de recuperar un registro por su nombre**.
Estos tests fijan el mecanismo completo — escribir el identificador, resolverlo,
y qué pasa cuando lo que nombraba ya no está.

Por qué importa: la referencia siembra por identificador externo. El impuesto
por defecto de una empresa se elige así (``odoo19c: l10n_mx/…/template_mx.py``
apunta a ``tax12``), no buscando "el primero que aparezca". Sin este mecanismo
esa siembra no se puede portar fiel.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from addons.uom.models import Uom
from exceptions import UserError

pytestmark = [pytest.mark.unit]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.mark.django_db
class TestIdaYVuelta:
    def test_se_resuelve_el_registro_sembrado(self, company):
        IrModelData.set_xmlid(company, 'l10n_mx.company_acme')
        assert IrModelData.ref('l10n_mx.company_acme') == company

    def test_la_pareja_lleva_la_etiqueta_de_django(self, company):
        """``model`` guarda ``app.Modelo`` — la llave que ``apps.get_model`` lee.

        La referencia guarda su nombre punteado (``res.company``); nuestros
        modelos no tienen ``_name``, y el único lector previo de la tabla ya
        consultaba con ``_meta.label``.
        """
        IrModelData.set_xmlid(company, 'l10n_mx.company_acme')
        assert IrModelData._xmlid_to_res_model_res_id('l10n_mx.company_acme') == (
            'base.ResCompany', company.pk)

    def test_el_nombre_puede_llevar_puntos(self, company):
        """El corte es por el **primer** punto: el módulo es sólo lo de antes."""
        IrModelData.set_xmlid(company, 'account.1_tax_group_16')
        fila = IrModelData.objects.get(name='1_tax_group_16')
        assert fila.module == 'account'
        assert IrModelData.ref('account.1_tax_group_16') == company

    def test_resembrar_repunta_en_vez_de_duplicar(self, company):
        otra = ResCompany.objects.create(code='beta', name='BETA')
        IrModelData.set_xmlid(company, 'l10n_mx.la_empresa')
        IrModelData.set_xmlid(otra, 'l10n_mx.la_empresa')
        assert IrModelData.objects.filter(name='la_empresa').count() == 1
        assert IrModelData.ref('l10n_mx.la_empresa') == otra


@pytest.mark.django_db
class TestCuandoNoEsta:
    def test_desconocido_es_None_por_defecto(self, db):
        assert IrModelData.ref('l10n_mx.no_existe', raise_if_not_found=False) is None
        assert IrModelData._xmlid_to_res_id('l10n_mx.no_existe') is None

    def test_desconocido_levanta_si_se_pide(self, db):
        with pytest.raises(ValueError):
            IrModelData.ref('l10n_mx.no_existe')

    def test_sin_modulo_es_un_error_de_forma(self, db):
        """``'tax12'`` a secas no es un identificador externo, es medio.

        Se distingue de "no encontrado" porque el arreglo es distinto: uno se
        siembra, el otro se escribe bien.
        """
        with pytest.raises(ValueError):
            IrModelData._xmlid_lookup('tax12')

    def test_un_identificador_puede_sobrevivir_a_su_registro(self, company):
        """La fila no se borra en cascada — la referencia también lo contempla.

        Su ``record.exists()`` existe justamente para este caso; devolvemos
        ``None`` en vez de un registro fantasma.
        """
        IrModelData.set_xmlid(company, 'l10n_mx.company_acme')
        company.delete()
        assert IrModelData.ref('l10n_mx.company_acme', raise_if_not_found=False) is None
        with pytest.raises(ValueError):
            IrModelData.ref('l10n_mx.company_acme')


@pytest.mark.django_db
class TestElLectorQueEstabaInerte:
    """``uom.filter_protected_uoms`` ya consultaba esta tabla y nunca acertaba.

    Su docstring lo admitía —"hoy queda inerte"— porque nadie sembraba filas.
    Con el escritor puesto, el lector funciona **sin tocarlo**: es la prueba de
    que la llave elegida para ``model`` es la que ese consumidor ya esperaba.
    """

    def test_una_unidad_con_identificador_del_modulo_uom_queda_protegida(self, db):
        gram = Uom.objects.create(name='g', relative_factor=1.0)
        libre = Uom.objects.create(name='h', relative_factor=1.0)
        IrModelData.set_xmlid(gram, 'uom.product_uom_gram')
        IrModelData.set_xmlid(libre, 'uom.product_uom_hour')  # liberada a propósito

        protegidas = Uom.filter_protected_uoms([gram, libre])

        assert protegidas == [gram]
        with pytest.raises(UserError):
            gram.check_can_delete()
        assert libre.check_can_delete() is None
