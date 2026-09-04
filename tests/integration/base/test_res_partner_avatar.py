"""Tests — el avatar de ``res.partner`` y su relleno por tipo de dirección.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_compute_avatar_1920`` … ``_compute_avatar_128`` (``:334-353``),
``_compute_avatar`` (``:355``) y ``_avatar_get_placeholder_path`` (``:367``).

Qué añade ``ResPartner`` sobre el mixin
========================================

``avatar.mixin`` ya resuelve «imagen si la hay, si no una inicial sobre
color». ``ResPartner`` **reenruta** esa decisión, y el motivo es de producto:
una dirección de entrega no es una persona, así que ponerle la inicial «B» de
«Bodega Norte» sobre un color aleatorio no comunica nada. La fuente le pone un
**camión**; a una de facturación, una **factura**; a una empresa, un
**edificio**; a «otra», una **pieza de rompecabezas**.

El reenrutado es una partición en tres, y cada rama se mide abajo:

1. **Con usuario interno, o de tipo ``contact``** → lo del mixin (es una
   persona: su inicial sirve).
2. **Sin usuario interno y sin imagen** → el relleno **de su tipo**.
3. **Sin usuario interno pero con imagen** → su propia imagen.

Los cinco ``_compute_avatar_NNNN`` NO se portan
================================================

En la fuente los cinco sobreescriben al mixin para **no hacer nada más que
llamar a ``super()``**: existen sólo para redeclarar ``@api.depends`` con
``name``, ``user_ids.share``, ``is_company`` y ``type``, porque su ORM
necesita saber de qué depende el cómputo para invalidarlo.

Aquí los cinco ``avatar_NNNN`` son ``property``: se calculan al leer, así que
no hay grafo de dependencias que declarar y el mecanismo que justifica los
cinco no tiene receptor. Divergencia declarada, no omisión.

*Métrica:* el cuerpo de los cinco en ``odoo19c: res_partner.py:334-353`` — una
sola línea, ``super()._compute_avatar_NNNN()``.
*Ciega a:* un addon que sobreescriba uno de los cinco para hacer algo más que
delegar. Medido en la referencia: ninguno lo hace en ``base``.

Los PNG no están desplegados, y eso no invalida los casos
==========================================================

El árbol tiene **0** PNG en ``static`` (medido con ``find src -name '*.png'``:
1 archivo, y es un adjunto de prueba). ``_avatar_get_placeholder`` ya declara
esa divergencia y devuelve ``b''`` cuando el archivo falta. Por eso los casos
miden **la RUTA que se elige**, que es la decisión portada, y no los bytes
—que dependen de un despliegue de assets que este repo no hace.
"""
from base64 import b64decode

import pytest

from addons.base.models.res_partner import ResPartner


def es_svg_generado(avatar):
    """¿El avatar es el SVG de la inicial que genera el mixin?

    El mixin devuelve el SVG **en base64**, asi que buscar ``b'svg'`` en
    crudo da siempre falso — y un control que afirme «NO es el SVG» pasaria
    por la razon equivocada. Se decodifica antes de mirar.
    """
    try:
        return b'<svg' in b64decode(avatar, validate=True)
    except Exception:
        return False

pytestmark = pytest.mark.integration


class TestPlaceholderPath:
    """≙ ``_avatar_get_placeholder_path`` (``:367``) — qué dibujo le toca."""

    def test_a_company_gets_the_building(self, db):
        who = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        assert who._avatar_get_placeholder_path().endswith('company_image.png')

    def test_a_delivery_address_gets_the_truck(self, db):
        who = ResPartner.objects.create(name='Bodega Norte',
                                        type=ResPartner.TYPE_DELIVERY)
        assert who._avatar_get_placeholder_path().endswith('truck.png')

    def test_an_invoice_address_gets_the_bill(self, db):
        who = ResPartner.objects.create(name='Facturacion',
                                        type=ResPartner.TYPE_INVOICE)
        assert who._avatar_get_placeholder_path().endswith('bill.png')

    def test_an_other_address_gets_the_puzzle_piece(self, db):
        who = ResPartner.objects.create(name='Otra',
                                        type=ResPartner.TYPE_OTHER)
        assert who._avatar_get_placeholder_path().endswith('puzzle.png')

    def test_a_plain_contact_falls_back_to_the_mixin(self, db):
        """CONTROL — ``contact`` no está en la cascada de la fuente, así que
        cae al ``super()``. Sin esa caída el método no tendría rama por
        defecto y una persona quedaría sin relleno."""
        who = ResPartner.objects.create(name='Ana Ruiz')
        assert who._avatar_get_placeholder_path().endswith('avatar_grey.png')

    def test_a_company_wins_over_its_type(self, db):
        """CONTROL del ORDEN de la cascada: la fuente pregunta ``is_company``
        ANTES que el tipo. Una empresa marcada como dirección de entrega es un
        edificio, no un camión. Sin el orden, saldría el camión."""
        who = ResPartner.objects.create(name='Filial SA', is_company=True,
                                        type=ResPartner.TYPE_DELIVERY)
        assert who._avatar_get_placeholder_path().endswith('company_image.png')


class TestAvatarRouting:
    """≙ ``_compute_avatar`` (``:355``) — la partición en tres."""

    def test_a_contact_takes_the_generated_initial(self, db):
        """Rama 1 — una persona sin imagen: su inicial sobre color."""
        who = ResPartner.objects.create(name='Ana Ruiz')
        assert es_svg_generado(who._compute_avatar('image_1920'))

    def test_a_delivery_address_takes_the_placeholder_not_the_initial(self, db):
        """Rama 2, y es el eje del bloque — sin este reenrutado una bodega
        saldría con una «B» sobre un color aleatorio, que no dice nada.

        Los bytes son ``b''`` porque el PNG no está desplegado; lo que se mide
        es que NO es el SVG generado — y se mide **decodificando**, porque el
        mixin lo devuelve en base64 y un ``b'svg' not in`` en crudo pasaría
        siempre, midiendo la codificación en vez de la rama.
        """
        who = ResPartner.objects.create(name='Bodega Norte',
                                        type=ResPartner.TYPE_DELIVERY)
        assert not es_svg_generado(who._compute_avatar('image_1920')), (
            'una direccion de entrega no toma la inicial del mixin')

    def test_an_address_with_its_own_image_keeps_it(self, db):
        """Rama 3 — con imagen propia, la imagen gana al relleno."""
        who = ResPartner.objects.create(name='Bodega Norte',
                                        type=ResPartner.TYPE_DELIVERY)
        who.image_1920 = b'PNGFALSO'
        assert who._compute_avatar('image_1920') == b'PNGFALSO'

    def test_a_contact_type_is_routed_to_the_mixin_even_without_user(self, db):
        """CONTROL de la segunda mitad de la condición: la fuente enruta al
        mixin si hay usuario interno **o** si el tipo es ``contact``. Sin ese
        ``or``, una persona sin cuenta caería al relleno gris en vez de a su
        inicial."""
        who = ResPartner.objects.create(name='Ana Ruiz',
                                        type=ResPartner.TYPE_CONTACT)
        assert es_svg_generado(who._compute_avatar('image_1920'))
