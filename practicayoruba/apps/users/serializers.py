"""
Serializers de Users — UC-AUTH-01, UC-AUTH-02
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()

AMBIGUOUS_MSG = 'Los datos ingresados no estan disponibles. Prueba con otros.'


class RegisterSerializer(serializers.Serializer):
    """
    UC-AUTH-01: Registro de comprador.
    FR-AUTH-01.02: validar formato
    FR-AUTH-01.03: unicidad con mensaje ambiguo
    FR-AUTH-01.04: is_active=False
    """
    username         = serializers.CharField(min_length=3, max_length=150)
    email            = serializers.EmailField()
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(AMBIGUOUS_MSG)
        return value

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(AMBIGUOUS_MSG)
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Las contrasenas no coinciden.'}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username   = validated_data['username'],
            email      = validated_data['email'],
            password   = validated_data['password'],
            is_active  = False,   # FR-AUTH-01.04 — pendiente verificacion de email
        )
        return user
