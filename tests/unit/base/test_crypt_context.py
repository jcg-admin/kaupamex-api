"""``CryptContext`` y ``_crypt_context`` (``:33-76``, ``:1193-1212``).

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3). Es el
cifrador de contraseñas del modelo: la referencia envuelve ``passlib`` y
expone ocho símbolos —``__init__``, ``copy``, ``hash``, ``identify``,
``verify``, ``verify_and_update``, ``schemes``, ``update``— más el método
``_crypt_context`` que lo construye con las rondas de configuración.

``passlib`` no está en este árbol (medido: 0 en ``pyproject.toml``), así que
el motor se construye sobre ``django.contrib.auth.hashers``, que es la
biblioteca de cifrado del stack. Lo que NO cambia es la superficie: mismo
archivo, misma clase, mismos métodos, mismas firmas — incluidos los nombres
de esquema ``pbkdf2_sha512`` y ``plaintext``, que son valores de
configuración de la fuente y no identificadores nuestros.

El control que puede fallar
---------------------------

Cada caso apunta a un método distinto de la clase. Si ``identify`` dejara de
distinguir el texto plano, caen el caso de identidad **y** el de
``verify_and_update`` que exige reemplazo; si ``copy`` devolviera el mismo
objeto, cae el caso de independencia; si ``update`` no validara el tipo de
``schemes``, cae su aserción. Ninguno pasa por ausencia del fenómeno: todos
los hashes que se les pasan existen y están construidos por la propia clase.

*Métrica:* métodos de ``CryptContext`` con al menos un caso que los ejerce.
*Ciega a:* que el coste en rondas sea el que la configuración pide — se
comprueba que el ajuste llegue al hash, no cuánto tarda.
"""

import pytest

from addons.base.models.res_users import MIN_ROUNDS, CryptContext, ResUsers


@pytest.fixture
def context():
    """El contexto tal como lo arma ``_crypt_context`` en la fuente."""
    return CryptContext(
        ['pbkdf2_sha512', 'plaintext'],
        deprecated=['auto'],
        pbkdf2_sha512__rounds=MIN_ROUNDS,
    )


def test_schemes_come_out_in_the_declared_order(context):
    assert context.schemes() == ('pbkdf2_sha512', 'plaintext')


def test_hash_uses_the_first_scheme_of_the_list(context):
    assert context.identify(context.hash('secreto')) == 'pbkdf2_sha512'


def test_identify_names_plaintext_when_no_scheme_recognises_it(context):
    assert context.identify('secreto') == 'plaintext'


def test_verify_accepts_the_secret_and_rejects_another(context):
    encoded = context.hash('secreto')
    assert context.verify('secreto', encoded) is True
    assert context.verify('otro', encoded) is False


def test_verify_and_update_leaves_a_current_hash_alone(context):
    valid, replacement = context.verify_and_update('secreto', context.hash('secreto'))
    assert valid is True
    assert replacement is None


def test_verify_and_update_replaces_a_deprecated_scheme(context):
    """``deprecated=['auto']``: todo esquema que no sea el primero se reemplaza."""
    valid, replacement = context.verify_and_update('secreto', 'secreto')
    assert valid is True
    assert context.identify(replacement) == 'pbkdf2_sha512'


def test_verify_and_update_gives_no_replacement_when_the_secret_is_wrong(context):
    valid, replacement = context.verify_and_update('otro', 'secreto')
    assert valid is False
    assert replacement is None


def test_copy_returns_an_independent_instance_with_the_same_configuration(context):
    other = context.copy()
    assert other is not context
    assert other.schemes() == context.schemes()
    other.update(schemes=['plaintext'])
    assert context.schemes() == ('pbkdf2_sha512', 'plaintext')


def test_update_rejects_a_scheme_that_is_not_a_string(context):
    with pytest.raises(AssertionError):
        context.update(schemes=[object()])


def test_update_accepts_a_single_scheme_as_a_string(context):
    context.update(schemes='plaintext')
    assert context.schemes() == ('plaintext',)


def test_the_rounds_setting_reaches_the_hash(context):
    context.update(pbkdf2_sha512__rounds=1000)
    # MCF de passlib: ``$pbkdf2-sha512$<rondas>$<sal>$<hash>``.
    assert context.hash('secreto').split('$')[2] == '1000'


@pytest.mark.django_db
def test_crypt_context_of_res_users_declares_the_two_schemes():
    context = ResUsers._crypt_context()
    assert context.schemes() == ('pbkdf2_sha512', 'plaintext')
    assert context.identify(context.hash('secreto')) == 'pbkdf2_sha512'
