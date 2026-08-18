"""Utilidades del addon ``website`` — espejo de ``odoo19c: addons/website/tools.py``.

La raíz ``addons/website/`` está espejada, así que este archivo va aquí y no en
``src/tools/``: la referencia lo declara **dentro del addon**, no en el núcleo
(``atributos-de-clase-de-modelo.md``, segunda cláusula — el sitio del archivo
se lee contra la referencia antes de crearlo).

**Cobertura declarada.** La fuente declara **6** símbolos de primer nivel en
**164** líneas (medido por AST sobre ``odoo-tools@622ddc2a``); este archivo
porta **5**. El sexto tiene su bloqueo medido y su dueño:

- ``create_image_attachment`` — llama ``Attachments.get_base_url()``, y ese
  método **no existe en el árbol**: medido, 0 declaraciones de ``get_base_url``
  en ``src/`` y ``addons/``. Portarlo hoy produciría un ``AttributeError`` en su
  primera llamada. Sucesor: tarea **#541**, que lo cierra junto con el porte de
  ``get_base_url`` en ``IrAttachment``.
"""
import re
from urllib.parse import urlsplit

from lxml import etree

from tools.misc import hmac


def distance(s1="", s2="", limit=4):
    """≙ ``distance`` (``odoo19c: addons/website/tools.py:10-45``).

    Distancia de Levenshtein **acotada** — inspirada en Apache Commons Text.
    Devuelve ``-1`` en cuanto la distancia supera ``limit``, que es lo que la
    hace barata: no calcula la matriz entera, sólo la banda diagonal de ancho
    ``limit`` alrededor de la diagonal principal.

    La fuente advierte —y se conserva la advertencia— que **no** ataja los
    casos triviales (cadena vacía, cadenas iguales): esos checks los hace el
    llamador antes de entrar al bucle.

    :param s1: primera cadena.
    :param s2: segunda cadena.
    :param limit: distancia máxima que se considera; por encima devuelve ``-1``.
    :returns: número de cambios de carácter para transformar ``s1`` en ``s2``,
        o ``-1`` si excede ``limit``.
    """
    BIG = 100000  # entero que el algoritmo nunca alcanza
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    l1 = len(s1)
    l2 = len(s2)
    if l2 - l1 > limit:
        return -1
    boundary = min(l1, limit) + 1
    p = [i if i < boundary else BIG for i in range(0, l1 + 1)]
    d = [BIG for _ in range(0, l1 + 1)]
    for j in range(1, l2 + 1):
        j2 = s2[j - 1]
        d[0] = j
        range_min = max(1, j - limit)
        range_max = min(l1, j + limit)
        if range_min > 1:
            d[range_min - 1] = BIG
        for i in range(range_min, range_max + 1):
            if s1[i - 1] == j2:
                d[i] = p[i - 1]
            else:
                d[i] = 1 + min(d[i - 1], p[i], p[i - 1])
        p, d = d, p
    return p[l1] if p[l1] <= limit else -1


def similarity_score(s1, s2):
    """≙ ``similarity_score`` (``odoo19c: addons/website/tools.py:48-65``).

    Cuánto se parecen dos cadenas. **No** está normalizada a ``[0, 1]``: es una
    puntuación relativa, y su único uso legítimo es comparar candidatos entre
    sí. Un par con puntuación ``<= 0`` se considera no parecido.

    Los tres términos que la componen, en el orden en que la fuente los aplica:

    1. la fracción de caracteres de ``s1`` que también están en ``s2`` (suma);
    2. la distancia acotada, relativa a la longitud de ``s1`` (resta);
    3. la diferencia simétrica de conjuntos, relativa a la longitud total
       (resta) — penaliza que ``s2`` traiga caracteres que ``s1`` no tiene.

    :param s1: primera cadena.
    :param s2: segunda cadena.
    :returns: la puntuación; a mayor valor, más parecidas.
    """
    dist = distance(s1, s2)
    if dist == -1:
        return -1
    set1 = set(s1)
    score = len(set1.intersection(s2)) / len(set1)
    score -= dist / len(s1)
    score -= len(set1.symmetric_difference(s2)) / (len(s1) + len(s2))
    return score


def text_from_html(html_fragment, collapse_whitespace=False):
    """≙ ``text_from_html`` (``odoo19c: addons/website/tools.py:68-93``).

    El texto plano de un fragmento HTML, sin etiquetas.

    Antes de extraer el texto **retira cuatro clases de nodo** que no son
    contenido: ``script``, ``style``, ``svg`` y lo marcado
    ``css_non_editable_mode_hidden``. Esa poda es la diferencia con el
    ``_search_text_from_html`` del modelo, que no la hace — dos funciones con
    nombre parecido y contrato distinto, como en la fuente.

    :param html_fragment: el documento del que extraer el texto.
    :param collapse_whitespace: si es cierto, colapsa espacios consecutivos.
    :returns: el texto extraído.
    """
    # lxml exige un único elemento raíz.
    tree = etree.fromstring('<p>%s</p>' % html_fragment, etree.XMLParser(recover=True))

    # Retirar los nodos técnicos que no deben convertirse en texto.
    xpath_filters = [
        '//script',
        '//style',
        '//svg',
        '//*[@class="css_non_editable_mode_hidden"]',
    ]
    for xpath_filter in xpath_filters:
        for element in tree.xpath(xpath_filter):
            element.getparent().remove(element)

    content = ' '.join(tree.itertext())
    if collapse_whitespace:
        content = re.sub(r'\s+', ' ', content).strip()
    return content


def get_base_domain(url, strip_www=False):
    """≙ ``get_base_domain`` (``odoo19c: addons/website/tools.py:96-112``).

    El dominio de una URL, sin esquema, sin barra final y —si se pide— sin el
    ``www.``.

    Lo consume ``Website._get_current_website_id`` para comparar el ``domain``
    configurado de cada sitio contra el ``Host`` de la petición. Por eso lo que
    devuelve es el ``netloc`` **con puerto**: el llamador decide si el puerto
    cuenta, y la fuente lo intenta primero con puerto y luego sin él.

    **Divergencia declarada:** la fuente usa ``werkzeug.urls.url_parse``; aquí
    ``urllib.parse.urlsplit`` de la biblioteca estándar. Sobre el ``netloc`` el
    resultado es el mismo, y evita atar el addon a werkzeug.

    Detalle que la fuente resuelve y no es obvio: una URL sin esquema
    (``midominio.com/x``) no tiene ``netloc`` para ningún parser — todo cae en
    ``path``. La fuente hereda ese comportamiento de ``url_parse`` y devuelve
    cadena vacía; se replica igual, porque el llamador ya trata la cadena vacía
    como «este sitio no declara dominio» y hace fallback.

    :param url: la URL de la que extraer el dominio.
    :param strip_www: si es cierto, quita el ``www.`` inicial.
    :returns: el dominio, o cadena vacía si la URL es falsy.
    """
    if not url:
        return ''

    url = urlsplit(url).netloc
    if strip_www and url.startswith('www.'):
        url = url[4:]
    return url


def add_form_signature(html_fragment, env_sudo):
    """≙ ``add_form_signature`` (``odoo19c: addons/website/tools.py:115-145``).

    Firma los formularios de contacto de un fragmento renderizado, para que el
    servidor pueda verificar a quién iba dirigido el correo sin confiar en lo
    que el navegador envíe.

    El mecanismo es exactamente el de la fuente: el HMAC cubre el destinatario
    (``email_to``), y le concatena ``:email_cc`` cuando el formulario declara
    copia — así una copia añadida por el cliente invalida la firma.

    El caso del correo de la empresa merece su renglón: cuando ``email_to`` no
    trae valor, o trae el placeholder ``info@yourcompany.example.com`` **y** el
    fragmento es el formulario de contacto por defecto, el destinatario real es
    el correo de la empresa. La fuente lo resuelve aquí y no en el renderizado,
    porque hasta este punto el ``data-for`` no está expandido.

    :param html_fragment: el árbol lxml del fragmento renderizado; se modifica
        en el sitio.
    :param env_sudo: entorno con privilegio, del que salen el secreto del HMAC
        y el correo de la empresa.
    """
    for form in html_fragment.iter('form'):
        if '/website/form/' not in form.attrib.get('action', ''):
            continue

        existing_hash_node = form.find(
            './/input[@type="hidden"][@name="website_form_signature"]')
        if existing_hash_node is not None:
            existing_hash_node.getparent().remove(existing_hash_node)
        input_nodes = form.xpath('.//input[contains(@name, "email_")]')
        form_values = {node.attrib['name']: node for node in input_nodes}
        # Si el formulario no envía correo, no hay nada que firmar. En este
        # punto ``email_to`` todavía puede venir sin valor (default pendiente).
        if 'email_to' not in form_values:
            continue

        email_to_value = form_values['email_to'].attrib.get('value')
        if (not email_to_value
                or (email_to_value == 'info@yourcompany.example.com'
                    and html_fragment.xpath('//span[@data-for="contactus_form"]')
                    and html_fragment.xpath('//form[@id="contactus_form"]'))):
            # El correo irá al valor del ``data-for``, que es el de la empresa.
            email_to_value = env_sudo.company.email or ''

        has_cc = {'email_cc', 'email_bcc'} & form_values.keys()
        value = email_to_value + (':email_cc' if has_cc else '')
        hash_value = hmac(env_sudo, 'website_form_signature', value)
        if has_cc:
            hash_value += ':email_cc'
        hash_node = etree.Element('input', attrib={
            'type': "hidden",
            'value': hash_value,
            'class': "form-control s_website_form_input s_website_form_custom",
            'name': "website_form_signature",
        })
        form_values['email_to'].addnext(hash_node)
