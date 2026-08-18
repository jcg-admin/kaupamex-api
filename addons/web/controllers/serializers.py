"""Serializers — addons.web.

``CredentialSerializer`` es la forma del ``credential`` de la referencia
(``odoo19c: odoo/http.py:1246`` — ``{'login', 'password', 'type': 'password'}``).
El ``type`` no se acepta desde el cliente: aquí sólo existe el tipo
``password``, y admitirlo como entrada sugeriría que hay otros.
"""
from rest_framework import serializers


class CredentialSerializer(serializers.Serializer):
    """Credencial de apertura de sesión."""

    login = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True,
                                     style={'input_type': 'password'})


class SessionInfoSerializer(serializers.Serializer):
    """≙ el retorno de ``ir.http.session_info()``, recortado a lo publicado."""

    uid = serializers.IntegerField(read_only=True)
    login = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_system = serializers.BooleanField(read_only=True)


class LangSerializer(serializers.Serializer):
    """Un idioma activo — ≙ la tupla ``(code, name)`` que la referencia
    devuelve desde ``/web/session/get_lang_list`` (``odoo19c:
    addons/web/controllers/session.py:57-62``, vía ``exp_list_lang``).

    Aquí se lee ``base.ResLang`` en vez de escanear los ``.po`` del árbol
    (``scan_languages()`` de la referencia): el catálogo de idiomas es un
    modelo de datos propio, no un directorio de traducciones.
    """

    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class GetFieldsRequestSerializer(serializers.Serializer):
    """Payload de ``POST /web/export/get_fields`` (``Export.get_fields`` de
    ``odoo19c: addons/web/controllers/export.py``). ``model`` usa la
    convención ``app_label.ModelName`` del proyecto (≙ ``ir.model.model``),
    no el ``dominio.punto`` de Odoo.
    """

    model = serializers.CharField()
    domain = serializers.JSONField(default=list)
    prefix = serializers.CharField(default='', allow_blank=True)
    parent_name = serializers.CharField(default='', allow_blank=True)
    import_compat = serializers.BooleanField(default=True)
    parent_field_type = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    exclude = serializers.ListField(
        child=serializers.CharField(), required=False, allow_null=True)


class ExportFieldTreeNodeSerializer(serializers.Serializer):
    """Un nodo del árbol devuelto por ``get_fields``/``namelist``."""

    id = serializers.CharField(read_only=True)
    string = serializers.CharField(read_only=True)
    value = serializers.CharField(read_only=True)
    children = serializers.BooleanField(read_only=True)
    field_type = serializers.CharField(read_only=True, allow_null=True)
    required = serializers.BooleanField(read_only=True, allow_null=True)
    relation_field = serializers.CharField(read_only=True, allow_null=True)
    default_export = serializers.BooleanField(read_only=True, allow_null=True)


class NamelistRequestSerializer(serializers.Serializer):
    """Payload de ``POST /web/export/namelist`` — ``model`` + el ``id`` de un
    ``ir.exports`` guardado (``IrExports``, ``addons.base``)."""

    model = serializers.CharField()
    export_id = serializers.IntegerField()


class ExportFormatSerializer(serializers.Serializer):
    """Un formato de exportación disponible (≙ ``Export.formats``)."""

    tag = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    error = serializers.CharField(read_only=True, allow_null=True)


class HealthCheckSerializer(serializers.Serializer):
    """≙ el retorno de ``Home.health`` (``home.py:174-188``)."""

    status = serializers.ChoiceField(choices=['pass', 'fail'], read_only=True)
    db_server_status = serializers.BooleanField(read_only=True, required=False)


class DomainValidateRequestSerializer(serializers.Serializer):
    """Payload de ``POST /web/domain/validate`` (``domain.py::validate``,
    ``odoo19c: addons/web/controllers/domain.py``). ``model`` usa la
    convención ``app_label.ModelName`` del proyecto (≙ ``dominio.punto`` de
    Odoo), la misma que ``GetFieldsRequestSerializer.model``.
    """

    model = serializers.CharField()
    domain = serializers.JSONField()


class DomainValidateResponseSerializer(serializers.Serializer):
    """≙ el booleano que devuelve ``Domain.validate`` de la referencia,
    envuelto en objeto — el campo lleva nombre en inglés
    (``identificadores-en-ingles.md``)."""

    valid = serializers.BooleanField(read_only=True)
