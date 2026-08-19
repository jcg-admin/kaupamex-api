r"""``account.document.import.mixin`` — importar facturas desde adjuntos (PDF/XML).

Adaptación de ``addons/account/models/account_document_import_mixin.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 568 líneas, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). Modelo **nuevo** de ``account``
(``_name``, no ``_inherit``) — no cuelga sobre otro addon.

Clase Python, no ``AbstractModel`` — mismo criterio que ``product.catalog.mixin``
====================================================================================

La referencia declara ``models.AbstractModel`` con ``_name`` propio y
**ningún campo** (medido: ``grep -n "= fields\." account_document_import_
mixin.py`` → 0 hits). Mismo criterio que ``product/models/product_catalog_
mixin.py`` ya fija: *"mixin sólo de comportamiento → clase"*. Se preservan
``_name``/``_description`` como atributos de clase Python (no de un modelo
Django registrado) — cumplen el mismo rol de identidad y trazabilidad que
tendrían en un modelo real, sin fabricar un ``Meta``/tabla que no existe.

Lo que SÍ está disponible en este árbol — corrección de una suposición inicial
==================================================================================

Antes de escribir este archivo se midió disponibilidad real (no de memoria,
``react-verification-gate.md``):

.. code-block:: text

   uv run python3 -c "import lxml; print(lxml.__version__)"   → 6.1.1  (SÍ)
   uv run python3 -c "import pypdf"                            → ModuleNotFoundError
   uv run python3 -c "import PyPDF2"                            → ModuleNotFoundError
   uv run python3 -c "import fitz"                              → ModuleNotFoundError

``lxml`` **SÍ** está declarado (``pyproject.toml``) e instalado en el
entorno del proyecto (``uv run``, no el ``python3`` de sistema — la primera
medición con el intérprete equivocado habría dado un falso bloqueo). Por
tanto el árbol XML **SÍ se porta**: ``_get_xml_tree``,
``split_etree_on_tag``, ``_split_xml_into_new_attachments``.

Lo que sigue bloqueado — una sola pieza concreta, no dos
============================================================

Ninguna librería de PDF está instalada (``pypdf``/``PyPDF2``/``fitz``, las
tres medidas arriba). Sólo ``extract_pdf_embedded_files`` y la rama PDF de
``_unwrap_attachment`` quedan bloqueadas — el resto del archivo no depende
de ellas. Sucesor: declarar ``pypdf`` (sucesor de ``PyPDF2``, que
``OdooPdfFileReader`` de la referencia envuelve) en ``pyproject.toml``.

``@api.model`` → classmethod; el resto, instancia sobre el mixin
====================================================================

La mayoría de los métodos de la referencia son de instancia (operan sobre
``self`` como el documento que se está creando/extendiendo); los marcados
``@api.model`` en la fuente (``_to_files_data``, ``_from_files_data``,
``_get_import_file_type``, ``_get_xml_tree``, ``_unwrap_attachments``,
``_unwrap_attachment``, ``_split_xml_into_new_attachments``,
``_create_records_from_attachments``) se portan como ``@classmethod`` —
ninguno lee estado de una instancia concreta, coherente con la anotación de
la fuente.

``env.cr`` / commit intermedio → ``django.db.transaction``
==============================================================

``rollbackable_transaction(cr)`` hace un COMMIT explícito a mitad de
petición para poder revertir sólo el bloque que decodifica — un patrón
propio del ciclo de transacción por-request de Odoo. Django/psycopg no
comparten ese ciclo (una vista DRF corre dentro de UNA transacción, o
ninguna, según middleware) — el equivalente idiomático es
``transaction.atomic()`` como **savepoint**: revierte el bloque interno sin
tocar lo que la vista ya haya comiteado antes. Documentado como divergencia
de mecanismo, no como bloqueo: cumple el mismo propósito (aislar el fallo de
un decoder) con la primitiva que este stack sí tiene.

``self.env._`` → sin motor de traducción; texto literal en español (mismo
criterio que el resto del proyecto, ``redaccion-tecnica-es.md``).

``self.message_post(...)`` → GAP declarado, no relleno
==========================================================

Ningún consumidor de este mixin (``AccountMove``) declara ``message_post``
todavía (medido: ``grep -n "message_post" addons/account/models/account_move
.py`` → 0 hits; ``mail.thread`` no está entre sus bases). Las llamadas a
``message_post`` de la referencia se preservan como llamadas a
``getattr(self, 'message_post', None)`` — si el consumidor las gana en el
futuro (cableando el mixin ``mail.thread``), funcionan sin tocar este
archivo; hoy son no-op silencioso **documentado**, no ausente.
"""
import difflib
import itertools
import logging
import mimetypes
import sys
from contextlib import contextmanager
from copy import deepcopy

from django.core.files.base import ContentFile
from django.db import transaction
# DIVERGENCIA declarada: la referencia usa ``markupsafe.Markup``; ese paquete
# NO es dependencia de este árbol (0 hits en pyproject.toml/uv.lock). El
# marcador de «HTML ya seguro» nativo del stack es
# ``django.utils.safestring`` — misma sustitución que website.py:2290 e
# ir_qweb_fields.py ya declaran. ``format_html`` escapa los interpolados,
# que es exactamente lo que hace ``Markup(...) % args`` en la referencia.
# Medido contra los binarios instalados (2026-08-19): el resultado es
# ``SafeString`` (subclase de ``str``); DRF lo serializa como string plano
# (``JSONRenderer`` y ``CharField.to_representation`` idénticos a ``str``) —
# la capa de serializers/urls futura no necesita tratamiento especial.
from django.utils.html import format_html
from lxml import etree

from addons.base.models.ir_attachment import IrAttachment
from exceptions import RedirectWarning
from tools.translate import _

_logger = logging.getLogger(__name__)


def _can_commit():
    """≙ ``_can_commit`` (``odoo19c: account_document_import_mixin.py:20-25``).

    Sustituye ``not modules.module.current_test`` (bandera de test de Odoo)
    por la detección estándar de pytest en este stack: ``sys.modules``
    contiene ``pytest`` sólo durante una corrida de test.
    """
    return 'pytest' not in sys.modules


@contextmanager
def rollbackable_transaction(cr=None):
    """≙ ``rollbackable_transaction`` (``odoo19c: :29-63``).

    ``cr`` se acepta por compatibilidad de firma con la referencia y NO se
    usa — el savepoint lo abre ``transaction.atomic()`` sobre la conexión
    activa de Django. Ver "``env.cr``/commit intermedio..." en el docstring
    del módulo para la divergencia completa.
    """
    if not _can_commit():
        yield
        return
    with transaction.atomic():
        yield


def split_etree_on_tag(tree, tag):
    """≙ ``split_etree_on_tag`` (``odoo19c: :66-99``). Transcrito fiel — ver
    "Lo que SÍ está disponible..." en el docstring del módulo: ``lxml`` está
    disponible en este árbol.
    """
    tree = deepcopy(tree)
    nodes_to_split = tree.findall(f'.//{tag}')

    parent_node = nodes_to_split[0].getparent()
    for node in nodes_to_split:
        parent_node.remove(node)

    trees = []
    for node in nodes_to_split:
        parent_node.append(node)
        trees.append(deepcopy(tree))
        parent_node.remove(node)
    return trees


def extract_pdf_embedded_files(filename, content):
    """≙ ``extract_pdf_embedded_files`` (``odoo19c: :110-125``) —
    **bloqueado**: ninguna librería de PDF instalada (ver el docstring del
    módulo). Devuelve lista vacía —mismo neutro que un PDF sin adjuntos
    embebidos en la referencia— en vez de levantar, porque el llamador
    (``_unwrap_attachment``) trata "sin embebidos" como caso normal, no
    como error.
    """
    _logger.info(
        'extract_pdf_embedded_files("%s"): bloqueado, ninguna librería de '
        'PDF instalada (pypdf/PyPDF2/fitz). Ver docstring del módulo.',
        filename,
    )
    return []


class AccountDocumentImportMixin:
    """≙ ``account.document.import.mixin`` (``odoo19c: :126-128``).

    Clase Python de comportamiento — ver "Clase Python, no ``AbstractModel``"
    en el docstring del módulo.
    """

    _name = 'account.document.import.mixin'
    _description = 'Business document import mixin'

    @classmethod
    def _create_records_from_attachments(cls, self, attachments, grouping_method=None):
        """≙ ``_create_records_from_attachments`` (``odoo19c: :131-176``).

        :param self: el documento base sobre el que crear los registros
            (en la referencia, ``@api.model`` lo recibe implícito como el
            recordset vacío del modelo consumidor — aquí explícito porque
            es ``@classmethod`` de un mixin sin modelo Django propio).
        """
        if grouping_method is None:
            grouping_method = cls._group_files_data_by_origin_attachment

        files_data = cls._to_files_data(attachments)
        files_data = files_data + cls._unwrap_attachments(files_data)
        file_data_groups = grouping_method(files_data)

        records = []
        model = type(self)
        for _group in file_data_groups:
            records.append(model.objects.create())
        for record, file_data_group in zip(records, file_data_groups):
            attachment_records = cls._from_files_data(file_data_group)
            for attachment in attachment_records:
                attachment.res_model = type(record).__module__ + '.' + type(record).__name__
                attachment.res_id = record.pk
                attachment.save()
            post = getattr(record, 'message_post', None)
            if post is not None:
                post(body=_('Este documento se creó a partir del/de los '
                            'siguiente(s) adjunto(s).'),
                     attachment_ids=[a.pk for a in attachment_records])

        for record, file_data_group in zip(records, file_data_groups):
            record_extended = cls._extend_with_attachments(record, file_data_group, new=True)
            if not record_extended:
                post = getattr(record, 'message_post', None)
                if post is not None:
                    post(body=_(
                        'Ocurrió un error al importar la factura, se '
                        'adjunta el XML entrante.'))

        return records

    # --------------------------------------------------------
    # Agrupamiento de adjuntos
    # --------------------------------------------------------

    @staticmethod
    def _group_files_data_by_origin_attachment(files_data):
        """≙ ``_group_files_data_by_origin_attachment`` (``odoo19c: :182-192``)."""
        groups = {}
        order = []
        for file_data in files_data:
            key = id(file_data['origin_attachment'])
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(file_data)
        return [groups[key] for key in order]

    @classmethod
    def _group_files_data_into_groups_of_mixed_types(cls, files_data):
        """≙ ``_group_files_data_into_groups_of_mixed_types`` (``odoo19c: :194-224``)."""
        files_data_with_origin_attachment = []
        files_data_without_origin_attachment = []
        for file_data in files_data:
            if 'decoder_info' not in file_data:
                file_data['decoder_info'] = cls._get_edi_decoder(file_data, new=True)
            if file_data['origin_attachment'] == file_data['attachment']:
                files_data_without_origin_attachment.append(file_data)
            else:
                files_data_with_origin_attachment.append(file_data)

        groups = []
        sorted_files_data = sorted(
            files_data_without_origin_attachment,
            key=lambda fd: (fd['decoder_info'] or {}).get('priority', 0),
            reverse=True,
        )
        for file_data in sorted_files_data:
            cls._assign_attachment_to_group_of_different_type(file_data, groups)
        for file_data in files_data_with_origin_attachment:
            cls._assign_attachment_to_group_with_same_origin_attachment(file_data, groups)
        return groups

    @classmethod
    def _assign_attachment_to_group_of_different_type(cls, incoming_file_data, groups):
        """≙ ``_assign_attachment_to_group_of_different_type`` (``odoo19c: :229-253``)."""
        incoming_type = incoming_file_data['import_file_type']
        groups_with_different_type = [
            group for group in groups
            if not incoming_type
            or incoming_type not in (fd['import_file_type'] for fd in group)
        ]
        if groups_with_different_type:
            sorted_by_similarity = sorted(
                groups_with_different_type,
                key=lambda group: max(
                    cls._get_similarity_score(incoming_file_data['name'], fd['name'])
                    for fd in group
                ),
                reverse=True,
            )
            sorted_by_similarity[0].append(incoming_file_data)
            return
        groups.append([incoming_file_data])

    @staticmethod
    def _assign_attachment_to_group_with_same_origin_attachment(incoming_file_data, groups):
        """≙ ``_assign_attachment_to_group_with_same_origin_attachment`` (``odoo19c: :256-265``)."""
        for group in groups:
            if any(
                incoming_file_data['origin_attachment'] == fd['origin_attachment']
                for fd in group
            ):
                group.append(incoming_file_data)
                return
        groups.append([incoming_file_data])

    @staticmethod
    def _get_similarity_score(filename1, filename2):
        """≙ ``_get_similarity_score`` (``odoo19c: :267-280``)."""
        matcher = difflib.SequenceMatcher(a=filename1, b=filename2, autojunk=False)
        return matcher.find_longest_match().size

    # --------------------------------------------------------
    # Marco de decoders
    # --------------------------------------------------------

    @classmethod
    def _extend_with_attachments(cls, self, files_data, new=False):
        """≙ ``_extend_with_attachments`` (``odoo19c: :282-370``).

        :param self: el registro que se extiende (ver el mismo criterio que
            ``_create_records_from_attachments``).
        """
        for file_data in files_data:
            if 'decoder_info' not in file_data:
                file_data['decoder_info'] = cls._get_edi_decoder(file_data, new=new)

        sorted_files_data = sorted(
            files_data,
            key=lambda fd: (
                fd['decoder_info'] is not None,
                (fd['decoder_info'] or {}).get('priority', 0),
            ),
            reverse=True,
        )
        file_data = sorted_files_data[0]

        if file_data['decoder_info'] is None or file_data['decoder_info'].get('priority', 0) == 0:
            _logger.info(
                'Adjunto(s) %s no importado(s): sin decoder aplicable.',
                [fd['name'] for fd in files_data],
            )
            return None

        post = getattr(self, 'message_post', None)
        sudo_post = getattr(getattr(self, 'sudo', lambda: self)(), 'message_post', post)
        try:
            with rollbackable_transaction():
                reason_cannot_decode = file_data['decoder_info']['decoder'](self, file_data, new)
                if reason_cannot_decode:
                    if post is not None:
                        post(body=_('Adjunto %(filename)s no importado: %(reason)s') % {
                            'filename': file_data['name'], 'reason': reason_cannot_decode,
                        })
                    return None
        except RedirectWarning:
            raise
        except Exception as error:  # noqa: BLE001 -- mismo alcance amplio que la referencia
            _logger.exception(
                'Error importando el adjunto %s en el registro %s',
                file_data['name'], self)
            if sudo_post is not None:
                sudo_post(body=format_html(
                    '{}<br/><br/>{}<br/>{}',
                    _('Error importando el adjunto %(filename)s:') % {
                        'filename': file_data['name']},
                    _('Este error específico ocurrió durante la importación:'),
                    str(error),
                ))
            return None
        return True

    def _get_edi_decoder(self, file_data, new=False):
        """≙ ``_get_edi_decoder`` (``odoo19c: :372-385``, terminal — sobreescribir).

        Sin registro de decoders EDI en este árbol (ningún addon
        ``l10n_*_edi``/``account_edi_*`` portado todavía) — ``None`` es el
        neutro correcto, no una ausencia silenciosa: es lo que la referencia
        también devuelve por defecto.
        """
        return None

    # --------------------------------------------------------------
    # Adjuntar/desadjuntar de forma consistente
    # --------------------------------------------------------------

    def _attachment_fields_to_clear(self):
        """≙ ``_attachment_fields_to_clear`` (``odoo19c: :388-390``, terminal — sobreescribir)."""
        return []

    def _fix_attachments_on_record(self, attachments):
        """≙ ``_fix_attachments_on_record`` (``odoo19c: :392-410``, marcado
        "Deprecated, removed in master" en la propia fuente)."""
        attachments_to_attach = [a for a in attachments if self._should_attach_to_record(a)]
        model_label = type(self).__module__ + '.' + type(self).__name__
        if attachments_to_attach:
            for attachment in attachments_to_attach:
                if attachment.res_model != model_label or attachment.res_id != self.pk:
                    attachment.res_model = model_label
                    attachment.res_id = self.pk
                    attachment.save()
        attachments_to_unattach = [
            a for a in attachments if a not in attachments_to_attach
            and a.res_model == model_label and not a.res_field
        ]
        if attachments_to_unattach:
            for field_name in self._attachment_fields_to_clear():
                manager = getattr(self, field_name, None)
                if manager is not None:
                    manager.remove(*attachments_to_unattach)
            for attachment in attachments_to_unattach:
                attachment.res_model = ''
                attachment.res_id = None
                attachment.save()

    def _fix_attachments_on_record_from_files_data(self, valid_files_data, extra_files_data):
        """≙ ``_fix_attachments_on_record_from_files_data`` (``odoo19c: :415-421``)."""
        model_label = type(self).__module__ + '.' + type(self).__name__
        valid_attachments = [
            a for a in type(self)._from_files_data(valid_files_data)
            if a.res_model != model_label or a.res_id != self.pk
        ]
        extra_attachments = [
            a for a in type(self)._from_files_data(extra_files_data)
            if a.res_model == model_label and not a.res_field
        ]
        for attachment in valid_attachments:
            attachment.res_model = model_label
            attachment.res_id = self.pk
            attachment.save()
        for attachment in extra_attachments:
            attachment.res_model = ''
            attachment.res_id = None
            attachment.save()

    @staticmethod
    def _should_attach_to_record(attachment):
        """≙ ``_should_attach_to_record`` (``odoo19c: :422-441``)."""
        return bool(attachment) and not attachment.res_field and attachment.mimetype in {
            'text/csv',
            'application/pdf',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.oasis.opendocument.spreadsheet',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.oasis.opendocument.presentation',
        }

    # -------------------------------------------------------------------------
    # ``ir.attachment`` ↔ ``file_data``
    # -------------------------------------------------------------------------

    @classmethod
    def _to_files_data(cls, attachments):
        """≙ ``_to_files_data`` (``odoo19c: :444-463``)."""
        files_data = []
        for attachment in attachments:
            raw = attachment.datas.read() if attachment.datas else b''
            if attachment.datas:
                attachment.datas.seek(0)
            file_data = {
                'name': attachment.name,
                'raw': raw,
                'mimetype': attachment.mimetype or '',
                'origin_attachment': attachment,
                'attachment': attachment,
            }
            file_data['xml_tree'] = cls._get_xml_tree(file_data)
            file_data['import_file_type'] = cls._get_import_file_type(file_data)
            file_data['origin_import_file_type'] = file_data['import_file_type']
            files_data.append(file_data)
        return files_data

    @classmethod
    def _from_files_data(cls, files_data):
        """≙ ``_from_files_data`` (``odoo19c: :465-472``)."""
        seen = set()
        result = []
        for file_data in files_data:
            attachment = file_data.get('attachment')
            if attachment is not None and attachment.pk not in seen:
                seen.add(attachment.pk)
                result.append(attachment)
        return result

    @staticmethod
    def _get_import_file_type(file_data):
        """≙ ``_get_import_file_type`` (``odoo19c: :475-479``, terminal — sobreescribir)."""
        if 'pdf' in (file_data['mimetype'] or '') or file_data['name'].endswith('.pdf'):
            return 'pdf'
        return None

    @staticmethod
    def _get_xml_tree(file_data):
        """≙ ``_get_xml_tree`` (``odoo19c: :481-493``). Portado — ``lxml``
        está disponible (ver el docstring del módulo). ``guess_mimetype`` de
        la referencia (sniff de contenido) se sustituye por
        ``mimetypes.guess_type`` sobre el nombre (mismo patrón ya usado en
        ``ir_binary.py:156`` de este árbol) — divergencia declarada: no hay
        sniff de contenido, sólo de extensión.
        """
        mimetype = file_data['mimetype'] or ''
        guessed, _enc = mimetypes.guess_type(file_data['name'] or '')
        is_xml = (
            ('text/plain' in mimetype and (
                (guessed or '').endswith('/xml') or file_data['name'].endswith('.xml')))
            or mimetype.endswith('/xml')
        )
        if not is_xml:
            return None
        try:
            return etree.fromstring(
                file_data['raw'],
                parser=etree.XMLParser(remove_comments=True, resolve_entities=False),
            )
        except etree.ParseError as error:
            _logger.info('Error leyendo el archivo xml "%s": %s', file_data['name'], error)
            return None

    @classmethod
    def _unwrap_attachments(cls, files_data, recurse=True):
        """≙ ``_unwrap_attachments`` (``odoo19c: :496-503``)."""
        return list(itertools.chain(*(
            cls._unwrap_attachment(file_data, recurse=recurse) for file_data in files_data
        )))

    @classmethod
    def _unwrap_attachment(cls, file_data, recurse=True):
        """≙ ``_unwrap_attachment`` (``odoo19c: :505-524``). La rama PDF
        delega en ``extract_pdf_embedded_files`` — bloqueada (ver el
        docstring del módulo); esta función funciona igual, simplemente no
        encuentra embebidos hasta que la librería de PDF aterrice.
        """
        embedded = []
        if file_data['import_file_type'] == 'pdf' and file_data['raw']:
            for filename, content in extract_pdf_embedded_files(file_data['name'], file_data['raw']):
                embedded_file_data = {
                    'name': filename,
                    'raw': content,
                    'mimetype': mimetypes.guess_type(filename)[0] or 'application/octet-stream',
                    'attachment': None,
                    'origin_attachment': file_data['origin_attachment'],
                    'origin_import_file_type': file_data['origin_import_file_type'],
                }
                embedded_file_data['xml_tree'] = cls._get_xml_tree(embedded_file_data)
                embedded_file_data['import_file_type'] = cls._get_import_file_type(embedded_file_data)
                embedded.append(embedded_file_data)

        if embedded and recurse:
            embedded.extend(cls._unwrap_attachments(embedded))
        return embedded

    @classmethod
    def _split_xml_into_new_attachments(cls, file_data, tag):
        """≙ ``_split_xml_into_new_attachments`` (``odoo19c: :527-568``).
        Portado — ``lxml`` disponible (ver el docstring del módulo).
        """
        new_files_data = []
        if len(file_data['xml_tree'].findall(f'.//{tag}')) > 1:
            trees = split_etree_on_tag(file_data['xml_tree'], tag)
            filename_without_extension, _dummy, extension = file_data['name'].rpartition('.')
            created_attachments = []
            for filename_index, tree in enumerate(trees[1:], start=2):
                attachment = IrAttachment.objects.create(
                    name=f'{filename_without_extension}_{filename_index}.{extension}',
                )
                attachment.datas.save(attachment.name, ContentFile(etree.tostring(tree)))
                created_attachments.append(attachment)
            new_files_data.extend(cls._to_files_data(created_attachments))
        return new_files_data


def apply_account_extensions():
    """No aplica — ``AccountDocumentImportMixin`` es un modelo NUEVO
    (``_name``, no ``_inherit``), no cuelga sobre otro addon.

    Se define por uniformidad con el resto del pase, pero no hay clase
    ajena que extender: el consumidor (``AccountMove``) debe declarar
    ``AccountDocumentImportMixin`` como una de sus bases — fuera del
    alcance de este porte (``account_move.py`` no está en la lista de
    archivos a escribir). Ver "Consumidor todavía sin cablear" en
    ``product_catalog_mixin.py`` de este mismo pase (mismo GAP).
    """
    return None
