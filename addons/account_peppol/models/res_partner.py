"""``res.partner`` extendido por ``account_peppol`` — ¿está en la red?

Adaptación de Odoo ``account_peppol/models/res_partner.py``
(``odoo19c: addons/account_peppol/models/res_partner.py``, 314 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el contacto visto desde Peppol. Su campo central es
``peppol_verification_state`` —si el contacto existe en la red y puede recibir
el formato elegido— y la maquinaria que lo averigua consultando el **SMP**
(*Service Metadata Publisher*) de la red o el proxy de Odoo.

Medido por AST en la fuente: 1 clase (``_inherit``), **5 campos** y
**15 métodos**.

Porte símbolo por símbolo — 20 símbolos: 6 portados, 14 bloqueados
====================================================================

Campos — 5
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``peppol_verification_state`` (``:29-39``)
     - **portado** — los cuatro valores verbatim. Su ``company_dependent=True``
       cae: este árbol no tiene propiedades por empresa sobre un campo
       (``ir.property``), así que el valor es único por contacto. Divergencia
       declarada, y es la que hace que ``_update_peppol_state_per_company``
       pierda su razón de ser (ver abajo).
   * - ``invoice_sending_method`` ``selection_add`` (``:23-25``)
     - BLOQUEADO por ``account`` — el campo lo declara
       ``odoo19c: account/models/partner.py:575`` y **no está en este árbol**
       (medido: 0 hits de ``invoice_sending_method``).
   * - ``peppol_eas`` ``selection_add`` (``:26``)
     - BLOQUEADO por ``account_edi_ubl_cii``
       (``odoo19c: account_edi_ubl_cii/models/res_partner.py:51``).
   * - ``available_peppol_sending_methods`` (``:27``) /
       ``available_peppol_edi_formats`` (``:28``)
     - BLOQUEADOS — dependen de los dos anteriores y de ``PEPPOL_LIST``
       (``odoo19c: account/models/company.py``, 0 hits aquí).

Métodos — 15
--------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``_get_participant_info`` (``:110-124``)
     - **portado** — la consulta directa al SMP por DNS/CNAME. La fuente la
       marca *DEPRECATED* (Peppol pasó de CNAME a NAPTR); se porta igual
       porque el porte es completo o declara su cobertura, y porque
       ``_check_peppol_participant_exists`` todavía acepta su forma XML.
   * - ``_check_peppol_participant_exists`` (``:126-147``)
     - **portado** — las dos formas de respuesta (JSON del proxy y XML del
       SMP) y la salvedad de ``hermes-belgium``, verbatim. Sin
       ``@handle_demo`` (ver ``tools/demo_utils.py``).
   * - ``_peppol_lookup_participant`` (``:149-182``)
     - **portado** — la consulta NAPTR a través del proxy de Odoo, con sus
       cuatro salidas por error (excepción de red, JSON inválido, error
       lógico, respuesta no-ok).
   * - ``_get_peppol_proxy_identification_info`` (``:309-314``)
     - **portado** verbatim — es una función pura sobre sus dos argumentos.
   * - ``_get_partners_to_skip_peppol_computation`` (``:304-307``)
     - **portado** — los contactos de las empresas que ya pueden enviar.
   * - ``_get_frontend_writable_fields`` (``:298-302``)
     - **portado** — devuelve sólo su aporte (``{'peppol_eas',
       'peppol_endpoint'}``), y ``chain_method`` lo funde con lo previo. Hoy
       no hay implementación previa (0 hits en el árbol): la cadena se arma
       sola cuando ``portal`` la porte.
   * - ``_onchange_verify_peppol_status`` (``:40-45``)
     - no portado — ``@api.onchange`` es un gancho del formulario del cliente
       web de Odoo, capa que este árbol no tiene (mismo criterio que la
       exclusión de ``views/``).
   * - ``_compute_available_peppol_sending_methods`` (``:51-57``) /
       ``_compute_available_peppol_edi_formats`` (``:59-66``) /
       ``_compute_available_peppol_eas`` (``:68-75``)
     - BLOQUEADOS — alimentan widgets y dependen de campos de ``account`` /
       ``account_edi_ubl_cii`` (arriba).
   * - ``_log_verification_state_update`` (``:80-108``)
     - BLOQUEADO por ``_message_log`` — el registro en el hilo de mensajes del
       contacto (``mail.thread``); medido, 0 hits de ``def _message_log`` en
       este árbol. Su cuerpo es además ``Markup`` de HTML para el cliente web.
   * - ``_check_document_type_support`` (``:184-197``)
     - BLOQUEADO por ``account_edi_ubl_cii`` — llama a ``_get_edi_builder`` y
       a ``_get_customization_id``, ambos de ese addon.
   * - ``_update_peppol_state_per_company`` (``:199-225``)
     - BLOQUEADO — su razón de existir es que ``peppol_verification_state`` es
       ``company_dependent``: recorre empresas para escribir el valor de cada
       una. Sin esa dimensión (ver la divergencia del campo), no hay nada que
       recorrer.
   * - ``create`` (``:227-231``)
     - BLOQUEADO — su cuerpo llama a ``_update_peppol_state_per_company``.
   * - ``_compute_peppol_endpoint`` (``:233-237``) /
       ``_compute_peppol_eas`` (``:239-247``)
     - BLOQUEADOS por ``account_edi_ubl_cii`` — calculan los dos campos que
       ese addon declara.
   * - ``button_account_peppol_check_partner_endpoint`` (``:249-277``)
     - BLOQUEADO — orquesta ``_get_peppol_verification_state`` (abajo) y
       escribe ``peppol_verification_state`` por empresa.
   * - ``_get_peppol_verification_state`` (``:279-296``)
     - BLOQUEADO por ``_check_document_type_support`` y por
       ``invoice_edi_format``, los dos de ``account_edi_ubl_cii``. Es el
       método que decide entre los cuatro valores del estado.

Divergencias declaradas
=========================

1. **``self.env.company`` → argumento explícito.** ``_get_participant_info`` y
   ``_peppol_lookup_participant`` leen la empresa activa para saber el modo
   (``test``/``prod``/``demo``) y el tipo de proxy. Aquí no hay «empresa
   activa» de sesión en el modelo, así que la reciben como parámetro
   ``company`` — que es como la tienen sus dos llamadores
   (``ResCompany._get_company_info_on_peppol``).
2. **``@api.model`` → ``@classmethod``**, y cada ``cls.X(...)`` de este archivo
   apunta a un ``classmethod`` (coherencia de ``H-API-738``).
3. **``company_dependent=True`` cae** en ``peppol_verification_state`` — ver la
   fila del campo.
"""
import logging
from hashlib import md5
from urllib import parse

import fields
import requests
from lxml import etree

from addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyUser,
)
from addons.base.models.res_company import ResCompany
from addons.base.models.res_partner import ResPartner
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'

_logger = logging.getLogger(__name__)

TIMEOUT = 10

#: ≙ el ``selection`` de ``peppol_verification_state`` (``odoo19c: :30-38``).
#: ``not_valid`` = no existe en Peppol; ``not_valid_format`` = existe pero no
#: puede recibir el tipo de documento elegido.
PEPPOL_VERIFICATION_STATES = [
    ('not_verified', 'Sin verificar'),
    ('not_valid', 'El contacto no está en Peppol'),
    ('not_valid_format', 'El contacto no puede recibir el formato'),
    ('valid', 'El contacto está en Peppol'),
]


def _campos():
    """El campo que este addon cuelga sobre ``base.ResPartner``."""
    return {
        'peppol_verification_state': fields.Selection(
            max_length=20, choices=PEPPOL_VERIFICATION_STATES,
            blank=True, default='not_verified',
            verbose_name='Estado Peppol',
            help_text='Si el contacto existe en la red Peppol y puede recibir el '
                      'formato elegido (Odoo peppol_verification_state; su '
                      'company_dependent=True no tiene contraparte aquí).',
        ),
    }


def _get_participant_info(cls, edi_identification, company):
    """≙ ``_get_participant_info`` (``odoo19c: :110-124``).

    Consulta directa al SMP por el nombre DNS derivado del identificador. La
    fuente la marca *DEPRECATED* —la red pasó de registros CNAME a NAPTR— pero
    su formato de respuesta (XML) lo sigue aceptando
    ``_check_peppol_participant_exists``.

    :param edi_identification: el identificador Peppol, ``{eas}:{endpoint}``.
    :param company: la empresa cuyo modo decide la zona del SML
        (divergencia 1).
    :return: el árbol XML de la respuesta, o ``None`` si no hubo respuesta.
    """
    hash_participant = md5(edi_identification.lower().encode()).hexdigest()
    endpoint_participant = parse.quote_plus(f'iso6523-actorid-upis::{edi_identification}')
    edi_mode = company._get_peppol_edi_mode()
    sml_zone = 'acc.edelivery' if edi_mode == 'test' else 'edelivery'
    smp_url = (f'http://B-{hash_participant}.iso6523-actorid-upis.{sml_zone}'
               f'.tech.ec.europa.eu/{endpoint_participant}')

    try:
        response = requests.get(smp_url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        _logger.debug(e)
        return None
    return etree.fromstring(response.content)


def _check_peppol_participant_exists(cls, participant_info, edi_identification):
    """≙ ``_check_peppol_participant_exists`` (``odoo19c: :126-147``).

    Acepta las dos formas de respuesta: el JSON del proxy de Odoo y el XML del
    SMP (esta última, *DEPRECATED* en la fuente).

    Conserva verbatim la salvedad belga: *todas* las empresas belgas están
    pre-registradas en ``hermes-belgium``, así que técnicamente tienen SMP sin
    ser participantes reales. Y la comparación del identificador es
    **insensible a mayúsculas**, como la fuente exige.

    Sin ``@handle_demo`` — ver ``tools/demo_utils.py``.
    """
    service_href = ''
    if isinstance(participant_info, dict):
        participant_identifier = participant_info.get('identifier', '')
        if services := participant_info.get('services', []):
            service_href = services[0].get('href', '')
    else:
        participant_identifier = participant_info.findtext('{*}ParticipantIdentifier') or ''
        service_metadata = participant_info.find('.//{*}ServiceMetadataReference')
        if service_metadata is not None:
            service_href = service_metadata.attrib.get('href', '')

    return (edi_identification.lower() == participant_identifier.lower()
            and 'hermes-belgium' not in service_href)


def _peppol_lookup_participant(cls, edi_identification, company):
    """≙ ``_peppol_lookup_participant`` (``odoo19c: :149-182``).

    Consulta NAPTR del participante a través del proxy Peppol de Odoo.
    Devuelve el ``result`` de la respuesta, o ``None`` — nunca levanta: es
    consulta informativa y sus cuatro salidas por error se registran en el log,
    igual que en la fuente.

    :param company: la empresa cuyo modo y tipo de proxy deciden el destino
        (divergencia 1).
    """
    if (edi_mode := company._get_peppol_edi_mode()) == 'demo':
        return None

    proxy_type = company._get_peppol_proxy_type()
    origin = AccountEdiProxyUser()._get_proxy_urls()[proxy_type][edi_mode]
    query = parse.urlencode({'peppol_identifier': edi_identification.lower()})
    api_endpoint = AccountEdiProxyUser()._get_peppol_proxy_endpoint(
        '1/lookup', proxy_type=proxy_type,
    )
    endpoint = f'{origin}{api_endpoint}?{query}'

    try:
        response = requests.get(endpoint, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        _logger.debug('falló la consulta del participante peppol %s: %s', edi_identification, e)
        return None

    try:
        decoded_response = response.json()
    except ValueError:
        _logger.error(
            'respuesta JSON inválida %s al consultar el participante peppol %s',
            response.status_code, edi_identification,
        )
        return None

    if error := decoded_response.get('error'):
        if error.get('code') != 'NOT_FOUND':
            _logger.error(
                'error al consultar el participante peppol %s: %s',
                edi_identification, error.get('message', 'error desconocido'),
            )
        return None

    if not response.ok:
        _logger.error(
            'respuesta no exitosa %s al consultar el participante peppol %s',
            response.status_code, edi_identification,
        )
        return None

    return decoded_response.get('result')


def _get_peppol_proxy_identification_info(cls, peppol_eas, peppol_endpoint):
    """≙ ``_get_peppol_proxy_identification_info`` (``odoo19c: :309-314``).

    :return: la tupla ``(proxy_type, peppol_identifier)``, donde el
        identificador tiene la forma ``{scheme}:{identifier}``.
    """
    if not peppol_eas or not peppol_endpoint:
        return None, ''
    return 'peppol', f'{peppol_eas}:{peppol_endpoint}'


def _get_partners_to_skip_peppol_computation(cls):
    """≙ ``_get_partners_to_skip_peppol_computation`` (``odoo19c: :304-307``) —
    los contactos de las empresas que ya pueden enviar; su estado no se
    recalcula."""
    company_ids = ResCompany.objects.filter(
        account_peppol_proxy_state__in=AccountEdiProxyUser._get_can_send_domain(),
    ).values_list('partner_id', flat=True)
    return ResPartner.objects.filter(pk__in=[pk for pk in company_ids if pk])


def _get_frontend_writable_fields(self):
    """≙ ``_get_frontend_writable_fields`` (``odoo19c: :298-302``).

    Devuelve SOLO su aporte; ``chain_method`` lo funde con lo previo (hoy no
    hay previo: 0 hits del método en este árbol).
    """
    return {'peppol_eas', 'peppol_endpoint'}


def _merge_sets(new, previous):
    """``combine`` para hooks que acumulan en un conjunto — ≙
    ``fields = super(); fields.update({...})``."""
    return set(previous or set()) | set(new or set())


def apply_account_peppol_res_partner_extensions():
    """Cuelga sobre ``base.ResPartner`` el estado Peppol del contacto — ≙
    ``_inherit = 'res.partner'``. La llama ``AccountPeppolConfig.ready()``."""
    for name, field in _campos().items():
        add_field_if_absent(ResPartner, name, field)

    chain_method(
        ResPartner, '_get_frontend_writable_fields',
        _get_frontend_writable_fields, combine=_merge_sets,
    )

    for name, function in (
        ('_get_participant_info', classmethod(_get_participant_info)),
        ('_check_peppol_participant_exists', classmethod(_check_peppol_participant_exists)),
        ('_peppol_lookup_participant', classmethod(_peppol_lookup_participant)),
        ('_get_peppol_proxy_identification_info',
         classmethod(_get_peppol_proxy_identification_info)),
        ('_get_partners_to_skip_peppol_computation',
         classmethod(_get_partners_to_skip_peppol_computation)),
    ):
        chain_method(ResPartner, name, function)


__all__ = [
    'PEPPOL_VERIFICATION_STATES',
    'apply_account_peppol_res_partner_extensions',
]
