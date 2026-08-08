"""Serializers — addons.authz_ldap.

Contrato del CRUD de configuraciones LDAP (superficie que en la referencia
pinta ``views/ldap_installer_views.xml`` + ``res_config_settings_views.xml``).
``ldap_password`` es ``write_only``: se escribe al configurar y no vuelve en
ninguna respuesta (misma disciplina que el resto de secretos del árbol).
"""
from rest_framework import serializers

from addons.authz_ldap.models import CompanyLdap


class CompanyLdapSerializer(serializers.ModelSerializer):

    ldap_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default='',
        style={'input_type': 'password'},
    )

    class Meta:
        model = CompanyLdap
        fields = [
            'id', 'sequence', 'company', 'ldap_server', 'ldap_server_port',
            'ldap_binddn', 'ldap_password', 'ldap_filter', 'ldap_base',
            'user', 'create_user', 'ldap_tls', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
