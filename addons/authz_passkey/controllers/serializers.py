"""Serializers — addons.authz_passkey.

``credential_identifier``/``public_key``/``sign_count`` llevan
``groups='base.group_system'`` en la referencia: NO salen por la API.
"""
from rest_framework import serializers

from addons.authz_passkey.models import PasskeyKey


class PasskeyKeySerializer(serializers.ModelSerializer):

    class Meta:
        model = PasskeyKey
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class PasskeyRegisterSerializer(serializers.Serializer):
    """≙ el wizard ``auth.passkey.key.create`` (name) + la respuesta de
    registro del navegador."""

    name = serializers.CharField(max_length=255)
    registration = serializers.DictField()


class PasskeySigninSerializer(serializers.Serializer):
    webauthn_response = serializers.DictField()
