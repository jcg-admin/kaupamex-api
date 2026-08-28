"""Tests — el nombre completo y las etiquetas calculadas de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_get_complete_name`` (``:378``), ``_compute_complete_name`` (``:393``),
``_compute_active_lang_count`` (``:408``), ``_compute_tz_offset`` (``:414``),
``_compute_partner_share`` (``:443``), ``_compute_vat_label`` (``:490``),
``_compute_type_address_label`` (``:494``), ``_compute_company_registry``
(``:528``), ``_compute_company_registry_label`` (``:534``),
``_get_company_registry_labels`` (``:540``),
``_compute_company_registry_placeholder`` (``:543``),
``_compute_email_formatted`` (``:602``), ``_compute_company_type`` (``:635``),
``_write_company_type`` (``:639``) y ``onchange_company_type`` (``:644``).

Diez de trece campos NO son columnas
=====================================

La referencia declara diez de estos campos con ``compute=`` y **sin**
``store=True``: existen para leerse, no para consultarse. Aquí eso es
``fields.NonStored`` (``src/orm/fields_nonstored.py``), el mecanismo que este
árbol ya construyó para ``store=False``.

**Tres** llevan columna: ``complete_name`` (``:214``), ``company_registry``
(``:241``) y ``partner_share`` (``:295``), y son los tres que aparecen en la
migración.

*Métrica:* la declaración literal de los trece campos en
``odoo19c: base/models/res_partner.py``, extraída por expresión regular sobre
el bloque de cada uno.
*Ciega a:* un ``store=`` que un addon posterior cambie al extender el modelo.

.. note::

   Una versión anterior de este archivo decía «once de trece» y contaba dos
   columnas. Era falso: ``partner_share`` es ``store=True``. Lo destapó medir
   las trece declaraciones en vez de leerlas.

Qué haría fallar a cada control
--------------------------------

``TestCompleteName.test_a_child_is_prefixed_with_its_company``
    El eje del nombre completo: un contacto se muestra «Empresa, Persona»
    para que una lista de contactos de varias empresas sea legible.

``TestCompleteName.test_a_subsidiary_company_is_not_prefixed_with_its_parent``
    CONTROL — la fuente excluye ``is_company``; sin él una filial
    saldría «Matriz SA, Filial SA». Tiene que ser una empresa CON
    padre: una suelta no llega a la guarda y el control no
    discriminaría.

``TestCompanyType.test_writing_the_type_moves_is_company``
    CONTROL del inverso: sin él ``company_type`` sería de sólo lectura y el
    formulario que lo ofrece no cambiaría nada.
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country import ResCountry
from addons.base.models.res_lang import ResLang
from addons.base.models.res_partner import ResPartner
from orm.environments import set_current_company

pytestmark = pytest.mark.integration


class TestCompleteName:
    """≙ ``_get_complete_name`` — el nombre que se muestra en una lista."""

    def test_a_loose_partner_is_just_its_name(self, db):
        who = ResPartner.objects.create(name='Ana Ruiz')
        assert who._get_complete_name() == 'Ana Ruiz'

    def test_a_child_is_prefixed_with_its_company(self, db):
        """El eje — una lista de contactos de varias empresas es ilegible sin
        esto."""
        company = ResPartner.objects.create(name='Kaupamex SA',
                                            is_company=True)
        who = ResPartner.objects.create(name='Ana Ruiz', parent=company)
        assert who._get_complete_name() == 'Kaupamex SA, Ana Ruiz'

    def test_a_subsidiary_company_is_not_prefixed_with_its_parent(self, db):
        """CONTROL de la exclusión por ``is_company`` — y tiene que ser una
        empresa CON padre.

        Una empresa suelta no ejerce la guarda: el ``if`` externo
        (``self.company_name or self.parent_id``) es falso y el flujo nunca
        llega a la condición que se dice medir. Una **filial** sí: tiene
        padre, entra al bloque, y ahí ``is_company`` es lo único que decide.

        Sin la guarda saldría «Matriz SA, Filial SA» — una filial no se
        anuncia como contacto de su matriz.

        .. note::

           La versión anterior de este caso creaba una empresa sin padre y
           **pasaba con la guarda anulada**: medido, la mutación que quita
           ``not self.is_company`` daba 34 passed. Un control que no puede
           fallar es adorno, no red (sub-patrón D de
           ``metrica-decide-la-conclusion.md``).
        """
        matriz = ResPartner.objects.create(name='Matriz SA', is_company=True)
        filial = ResPartner.objects.create(name='Filial SA', is_company=True,
                                           parent=matriz)
        assert filial._get_complete_name() == 'Filial SA'

    def test_a_nameless_address_takes_its_type_as_name(self, db):
        """La fuente usa la etiqueta del tipo cuando no hay nombre — una
        dirección sin nombre saldría vacía en la lista."""
        company = ResPartner.objects.create(name='Kaupamex SA',
                                            is_company=True)
        bodega = ResPartner.objects.create(
            name='', parent=company, type=ResPartner.TYPE_DELIVERY)
        assert 'Kaupamex SA' in bodega._get_complete_name()
        assert bodega._get_complete_name() != 'Kaupamex SA, '

    def test_a_nameless_CONTACT_does_not_take_a_type_label(self, db):
        """CONTROL — ``contact`` no está en ``_complete_name_displayed_types``,
        así que la fuente NO le pone etiqueta."""
        assert 'contact' not in ResPartner._complete_name_displayed_types

    def test_it_lands_in_the_column_on_save(self, db):
        """``complete_name`` es ``store=True``: se escribe, no se calcula al
        leer. Qué lo haría fallar: no recalcularlo en ``save``."""
        company = ResPartner.objects.create(name='Kaupamex SA',
                                            is_company=True)
        who = ResPartner.objects.create(name='Ana Ruiz', parent=company)
        who.refresh_from_db()
        assert who.complete_name == 'Kaupamex SA, Ana Ruiz'


class TestTypeAddressLabel:
    """≙ ``_compute_type_address_label`` — cómo se llama esta dirección."""

    def test_an_invoice_address(self, db):
        who = ResPartner.objects.create(name='Fact',
                                        type=ResPartner.TYPE_INVOICE)
        assert who.type_address_label == 'Invoice Address'

    def test_a_delivery_address(self, db):
        who = ResPartner.objects.create(name='Bod',
                                        type=ResPartner.TYPE_DELIVERY)
        assert who.type_address_label == 'Delivery Address'

    def test_a_contact_with_a_parent_is_the_company_address(self, db):
        company = ResPartner.objects.create(name='Kaupamex SA',
                                            is_company=True)
        who = ResPartner.objects.create(name='Ana', parent=company)
        assert who.type_address_label == 'Company Address'

    def test_a_loose_contact_is_just_an_address(self, db):
        """CONTROL — sin padre no es la dirección de ninguna empresa."""
        who = ResPartner.objects.create(name='Ana')
        assert who.type_address_label == 'Address'


class TestEmailFormatted:
    """≙ ``_compute_email_formatted`` — lo que va en la cabecera ``To:``."""

    def test_it_joins_the_name_and_the_address(self, db):
        who = ResPartner.objects.create(name='Ana Ruiz',
                                        email='ana@kaupamex.mx')
        assert who.email_formatted == '"Ana Ruiz" <ana@kaupamex.mx>'

    def test_without_email_it_is_false(self, db):
        assert ResPartner.objects.create(name='Ana').email_formatted is False

    def test_an_already_formatted_email_is_not_double_wrapped(self, db):
        """El primer defensivo del docstring de la fuente: sin él saldría
        ``"Ana" <"Ana" <ana@x.mx>>``, que ningún servidor acepta."""
        who = ResPartner.objects.create(
            name='Ana Ruiz', email='Otra <ana@kaupamex.mx>')
        assert who.email_formatted == '"Ana Ruiz" <ana@kaupamex.mx>'

    def test_a_multi_email_keeps_both(self, db):
        """El segundo defensivo: el campo se usa a veces con dos buzones."""
        who = ResPartner.objects.create(
            name='Ana', email='a@kaupamex.mx, b@kaupamex.mx')
        assert 'a@kaupamex.mx,b@kaupamex.mx' in who.email_formatted

    def test_an_invalid_email_is_kept_as_is(self, db):
        """El tercer defensivo, y es deliberado: conservarlo facilita
        diagnosticar el fallo de envío en vez de esconderlo.

        **El ``@`` sobrante es de la fuente, no del puerto.** ``formataddr``
        parte con ``address.rpartition('@')`` y compone
        ``f'"{name}" <{local}@{domain}>'``
        (``odoo19c: odoo/tools/mail.py:980,1001``). Sobre una cadena sin
        ``@``, ``rpartition`` deja ``local=''`` y todo en ``domain``, así que
        el separador se emite igual. Una versión anterior de este caso
        afirmaba ``<no soy correo>`` sin el ``@`` — era lo que yo suponía, no
        lo que la fuente produce.
        """
        who = ResPartner.objects.create(name='Ana', email='no soy correo')
        assert who.email_formatted == '"Ana" <@no soy correo>'


class TestCompanyType:
    """≙ ``_compute_company_type`` / ``_write_company_type``."""

    def test_a_company_reads_as_company(self, db):
        who = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        assert who.company_type == 'company'

    def test_a_person_reads_as_person(self, db):
        assert ResPartner.objects.create(name='Ana').company_type == 'person'

    def test_writing_the_type_moves_is_company(self, db):
        """CONTROL del inverso — sin él el campo sería de sólo lectura y el
        formulario que lo ofrece no cambiaría nada."""
        who = ResPartner.objects.create(name='Ana')
        who.company_type = 'company'
        who._write_company_type()
        assert who.is_company is True

    def test_the_onchange_does_the_same(self, db):
        who = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        who.company_type = 'person'
        who.onchange_company_type()
        assert who.is_company is False


class TestVatLabel:
    """≙ ``_compute_vat_label`` — «RFC» en México, «Tax ID» donde no hay.

    **Es del país de la empresa ACTIVA, no del país del partner.** La fuente
    lee ``self.env.company.country_id.vat_label`` (``:491``), no
    ``partner.country_id``: un operador mexicano ve «RFC» en toda ficha, sea
    de quien sea el partner. Aquí ``env.company`` es
    ``get_current_company()``.

    .. note::

       Una versión anterior de esta clase medía el país del **partner** y
       ponía ``'RFC'`` en los dos casos. Medido: ``MX.vat_label == 'RFC'``,
       así que los dos controles daban la misma respuesta y el de respaldo
       no discriminaba nada — sub-patrón D de
       ``metrica-decide-la-conclusion.md``, en el propio test.
    """

    def test_without_an_active_company_it_falls_back(self, db):
        """Sin empresa activa no hay país del que sacar la etiqueta."""
        set_current_company(None)
        assert ResPartner.objects.create(name='Ana').vat_label == 'Tax ID'

    def test_it_takes_the_label_of_the_active_company_country(self, db):
        """El eje — con una empresa mexicana activa, la etiqueta es «RFC»."""
        mexico = ResCountry.objects.get(code='MX')
        company = ResCompany.objects.create(code='kx', name='Kaupamex')
        company.country = mexico
        company.save()
        set_current_company(company.pk)
        try:
            assert ResPartner.objects.create(name='Ana').vat_label == 'RFC'
        finally:
            set_current_company(None)

    def test_a_country_that_declares_no_label_falls_back(self, db):
        """CONTROL — discrimina del anterior: Japón está sembrado con
        ``vat_label`` vacío, así que cae al respaldo aunque SÍ haya empresa
        activa con país. Sin este caso, «tomó la etiqueta del país» y «cayó al
        respaldo» serían indistinguibles."""
        japon = ResCountry.objects.get(code='JP')
        assert japon.vat_label == '', 'la premisa del control: JP no declara'
        company = ResCompany.objects.create(code='kj', name='Kaupamex JP')
        company.country = japon
        company.save()
        set_current_company(company.pk)
        try:
            assert ResPartner.objects.create(name='Ana').vat_label == 'Tax ID'
        finally:
            set_current_company(None)


class TestCompanyRegistry:
    """≙ el bloque de ``company_registry`` — columna + dos etiquetas."""

    def test_it_is_a_writable_column(self, db):
        who = ResPartner.objects.create(name='Kaupamex SA', is_company=True,
                                        company_registry='RPC-12345')
        who.refresh_from_db()
        assert who.company_registry == 'RPC-12345'

    def test_the_label_falls_back_when_the_country_has_none(self, db):
        who = ResPartner.objects.create(name='Ana')
        assert who.company_registry_label == 'Company ID'

    def test_the_label_map_is_empty_by_design(self, db):
        """≙ ``_get_company_registry_labels`` — la fuente devuelve ``{}`` y lo
        pueblan las localizaciones. Qué lo haría fallar: inventar entradas que
        ninguna localización portada respalda."""
        assert ResPartner._get_company_registry_labels() == {}

    def test_the_placeholder_is_false_by_design(self, db):
        assert ResPartner.objects.create(
            name='Ana').company_registry_placeholder is False


class TestTzOffset:
    """≙ ``_compute_tz_offset`` — el desfase, en la forma ``+HHMM``."""

    def test_without_a_timezone_it_is_gmt(self, db):
        assert ResPartner.objects.create(name='Ana').tz_offset == '+0000'

    def test_with_one_it_is_its_offset(self, db):
        who = ResPartner.objects.create(name='Ana',
                                        tz='America/Mexico_City')
        assert who.tz_offset.startswith('-'), 'Mexico esta al oeste de GMT'
        assert len(who.tz_offset) == 5

    def test_an_unknown_timezone_falls_back_to_gmt(self, db):
        """DIVERGENCIA DE ESQUEMA declarada, no invención.

        La fuente NO cae a GMT: ``pytz.timezone('No/Existe')`` levanta. Puede
        permitírselo porque su ``tz`` es una ``Selection`` acotada a las zonas
        válidas (``:223``) y la basura no entra.

        **Corregido al cerrar #107.** Este docstring anunciaba que acotar
        ``tz`` retiraría el caso. Es falso, y la razón es medible: ``tz`` ya
        es una Selection (``choices=_tzs``), pero en Django ``choices`` es
        **validación, no DDL** —lo mismo que desbloqueó #118—, así que
        ``objects.create(tz='No/Existe')`` sigue escribiendo la fila y sólo
        ``full_clean()`` la rechaza. El caso se queda porque sigue siendo
        alcanzable: por un dato anterior al acotamiento, y por cualquier
        escritura que no pase por ``full_clean()``.
        """
        who = ResPartner.objects.create(name='Ana', tz='No/Existe')
        assert who.tz_offset == '+0000'


class TestPartnerShare:
    """≙ ``_compute_partner_share`` (``:443``) — ¿es un cliente sin acceso?

    ``partner_share`` es ``store=True``: columna, no cálculo al leer. La
    fuente lo define ``not partner.user_ids or not any(not user.share ...)``,
    y ``user.share`` es lo contrario de interno — aquí ``_is_internal()``.
    """

    def test_a_partner_without_users_shares(self, db):
        """Un cliente que nunca inició sesión: comparte, por definición."""
        who = ResPartner.objects.create(name='Ana')
        who.refresh_from_db()
        assert who.partner_share is True

    def test_it_lands_in_the_column(self, db):
        """CONTROL de que es columna y no cálculo: se lee desde la base."""
        who = ResPartner.objects.create(name='Ana')
        leido = ResPartner.objects.filter(partner_share=True, pk=who.pk)
        assert leido.exists(), 'si no fuera columna, no se podría filtrar'


class TestActiveLangCount:
    """≙ ``_compute_active_lang_count`` (``:408``)."""

    def test_it_counts_the_active_languages(self, db):
        """La fuente hace ``len(res.lang.get_installed())``;
        ``get_installed`` devuelve los ``active``, así que el número es el
        conteo directo. ``get_installed`` en sí es la tarea #104."""
        esperado = ResLang.objects.filter(active=True).count()
        assert ResPartner.objects.create(
            name='Ana').active_lang_count == esperado


class TestBlockedByDesign:
    """Los dos campos que devuelven ``None`` con divergencia declarada.

    ``None`` NO significa «no hay duplicado» — significa «no se puede
    responder». Faltan ``EU_EXTRA_VAT_CODES`` y ``partner.company_id``,
    medidos ausentes. Sucesor: tarea **#105**.
    """

    def test_the_vat_duplicate_is_blocked(self, db):
        assert ResPartner.objects.create(name='Ana').same_vat_partner_id is None

    def test_the_registry_duplicate_is_blocked(self, db):
        who = ResPartner.objects.create(name='Ana')
        assert who.same_company_registry_partner_id is None
