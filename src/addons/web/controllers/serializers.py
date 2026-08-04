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
