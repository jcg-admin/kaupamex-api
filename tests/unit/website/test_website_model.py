"""Contrato del modelo ``website`` — bloque B1 del porte (tarea **#534**).

Adaptación de ``odoo19c: addons/website/models/website.py``
(``odoo-tools@622ddc2a``, LGPL-3). El archivo de la referencia declara **1
clase, 111 métodos, 44 campos y 4 atributos de clase** en 2430 líneas; B1 cubre
la cabecera, los 44 campos y 33 métodos. Los otros 78 métodos viven en las
tareas #535-#539, y la partición está verificada completa (33+15+10+15+6+32 =
111).

**Por qué este modelo es el ancla.** Antes de este pase el árbol tenía un addon
``website`` con 8 modelos y **ninguno declaraba el modelo ``website`` mismo**:
``grep "_name = 'website'"`` daba 0 hits sobre todo el árbol. Cuatro tareas
(#101, #104, #105, #258) esperan una FK a este modelo que no existía.

Los casos cubren, en este orden:

1. **La cabecera entera** — los 4 atributos de clase que la fuente declara, no
   una parte. Es lo que ``atributos-de-clase-de-modelo.md`` v2.0.0 exige tras
   :ref:`h-api-580`, y lo que los 8 modelos preexistentes de este addon
   incumplen: 0 atributos de clase entre los ocho.
2. **Los 44 campos, por nombre** — un porte parcial de campos pasa la suite
   igual que uno completo, porque los tests se escriben sobre lo portado. El
   conteo contra la fuente es lo único que lo distingue.
3. **``_normalize_domain_url``** — el único de los 33 métodos de B1 que es
   función pura, así que se puede ejercitar sin base de datos. Sus dos reglas
   (prefijar ``https://`` si no empieza con ``http``; recortar la barra final)
   salen de ``odoo19c: website.py:406-415``.
4. **La restricción de dominio único** — ``_domain_unique`` es un objeto de
   tabla en la fuente (``models.Constraint``); su hogar aquí es
   ``Meta.constraints`` con el nombre conservado.
"""

import pytest

from addons.website.models.website import Website

pytestmark = [pytest.mark.django_db]


#: Los 44 campos que ``odoo19c: addons/website/models/website.py`` declara,
#: en el orden de la fuente. Derivados por AST, no a mano.
REFERENCE_FIELDS = [
    'name', 'sequence', 'domain', 'domain_punycode', 'company_id',
    'language_ids', 'language_count', 'default_lang_id', 'auto_redirect_lang',
    'cookies_bar', 'configurator_done', 'block_third_party_domains',
    'custom_blocked_third_party_domains', 'blocked_third_party_domains',
    'logo', 'social_twitter', 'social_facebook', 'social_github',
    'social_linkedin', 'social_youtube', 'social_instagram', 'social_tiktok',
    'social_discord', 'social_default_image', 'has_social_default_image',
    'google_analytics_key', 'google_search_console', 'google_maps_api_key',
    'plausible_shared_key', 'plausible_site', 'user_id', 'cdn_activated',
    'cdn_url', 'cdn_filters', 'partner_id', 'menu_id', 'homepage_url',
    'custom_code_head', 'custom_code_footer', 'robots_txt', 'favicon',
    'theme_id', 'specific_user_account', 'auth_signup_uninvited',
]

#: Traducción de los nombres de la fuente a los de aquí. Un FK se llama
#: ``company`` y no ``company_id`` porque Django ya expone ``company_id`` como
#: la columna; conservar el sufijo produciría ``company_id_id``.
EQUIVALENCE = {
    'company_id': 'company', 'language_ids': 'languages',
    'default_lang_id': 'default_lang', 'user_id': 'user',
    'partner_id': 'partner', 'menu_id': 'menu', 'theme_id': 'theme',
}


def test_header_declares_the_four_source_attributes():
    """Los 4 atributos de clase, no un subconjunto.

    ``odoo19c: website.py:99-103`` declara ``_name``, ``_description`` y
    ``_order``; ``:216-219`` declara el objeto de tabla ``_domain_unique``.
    """
    assert Website._name == 'website'
    assert Website._description == "Website"
    assert Website._order == 'sequence, id'
    names = {c.name for c in Website._meta.constraints}
    assert 'domain_unique' in names


def test_the_forty_four_source_fields_are_declared():
    """Ningún campo de la fuente queda fuera en silencio.

    Es el conteo que ``porte-completo-no-parcial.md`` exige: un porte de 30 de
    44 campos pasa cualquier test escrito sobre esos 30.

    **Se mide por DOS canales, y la primera versión de este test sólo miraba
    uno.** Preguntando sólo a ``_meta.get_fields()`` daban por ausentes cinco
    campos que sí estaban portados — ``domain_punycode``, ``language_count``,
    ``blocked_third_party_domains``, ``partner_id`` y ``menu_id``—, porque los
    cinco son ``compute`` **sin** ``store=True`` en la fuente y aquí van con
    ``fields.NonStored``, que es un descriptor y no una columna. El
    instrumento era ciego justo al fenómeno sobre el que concluía
    (``metrica-decide-la-conclusion.md``).

    *Métrica:* el nombre aparece como columna en ``_meta`` **o** como atributo
    declarado en la clase.
    *Ciega a:* un atributo heredado de ``TimeStampedModel`` que por casualidad
    se llame como un campo de la fuente — ninguno de los 44 colisiona
    (``created_at``/``updated_at`` no están en la lista).
    """
    columns = {f.name for f in Website._meta.get_fields()}
    missing = []
    for field in REFERENCE_FIELDS:
        here = EQUIVALENCE.get(field, field)
        if here not in columns and not hasattr(Website, here):
            missing.append(field)
    assert not missing, f'campos de la referencia sin portar: {missing}'


@pytest.mark.parametrize('given,expected', [
    ('www.midominio.com', 'https://www.midominio.com'),
    ('https://www.midominio.com/', 'https://www.midominio.com'),
    ('http://localhost:8000', 'http://localhost:8000'),
    ('https://x.com///', 'https://x.com'),
])
def test_normalize_domain_url_prefixes_and_trims(given, expected):
    """≙ ``_normalize_domain_url`` (``odoo19c: website.py:406-415``).

    Dos reglas: prefijar ``https://`` si no empieza por ``http``, y recortar
    toda barra final. El caso ``http://`` comprueba que el prefijo NO se
    duplica — la fuente compara contra ``'http'``, no contra ``'https'``.
    """
    assert Website()._normalize_domain_url(given) == expected
