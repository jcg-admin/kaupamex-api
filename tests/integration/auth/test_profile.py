"""
Tests de integracion — Perfil de usuario
UC-AUTH-05: Ver Perfil | UC-AUTH-06: Editar Perfil
"""
import io
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import Address

pytestmark = pytest.mark.integration

PROFILE_URL = '/api/v2/auth/profile/'


def make_image_bytes(fmt='PNG', size=(100, 100), color=(100, 149, 237)):
    """Genera bytes de imagen real para tests de avatar."""
    img = Image.new('RGB', size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ── GET /api/v2/auth/profile/ ─────────────────────────────────────────

class TestProfileGet:

    def test_perfil_retorna_200_autenticado(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert r.status_code == 200

    def test_perfil_retorna_401_sin_autenticar(self, api_client, db):
        r = api_client.get(PROFILE_URL)
        assert r.status_code == 401

    def test_perfil_contiene_campos_basicos(self, auth_client, user, db):
        r = auth_client.get(PROFILE_URL)
        data = r.json()
        assert data['username'] == user.username
        assert data['email'] == user.email
        assert 'first_name' in data
        assert 'last_name' in data
        assert 'phone' in data

    def test_perfil_contiene_completeness(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        data = r.json()
        assert 'profile_completeness' in data
        assert isinstance(data['profile_completeness'], int)
        assert 0 <= data['profile_completeness'] <= 100

    def test_perfil_contiene_pending_fields(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        data = r.json()
        assert 'pending_fields' in data
        assert isinstance(data['pending_fields'], list)

    def test_completeness_usuario_sin_opcionales(self, api_client, db):
        User = get_user_model()
        u = User.objects.create_user(
            username='empty', email='empty@test.mx', password='Pass123!',
            first_name='', last_name='', phone='',
        )
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(u).access_token}')
        r = api_client.get(PROFILE_URL)
        assert r.json()['profile_completeness'] == 0
        assert 'first_name' in r.json()['pending_fields']

    def test_completeness_usuario_completo(self, auth_client, user, db):
        user.first_name = 'Demo'
        user.last_name = 'Yoruba'
        user.phone = '5551234567'
        user.save()
        # Crear una direccion para el usuario
        Address.objects.create(
            user=user, alias='Casa', recipient_name='Demo Yoruba',
            street='Calle 1', city='CDMX', state='CDMX',
            zip_code='06600', country='MX', phone='5551234567',
        )
        r = auth_client.get(PROFILE_URL)
        data = r.json()
        # first_name(20) + last_name(20) + phone(20) + address(20) = 80 (sin avatar)
        assert data['profile_completeness'] == 80

    def test_completeness_multiplos_de_20(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert r.json()['profile_completeness'] % 20 == 0

    def test_aislamiento_datos(self, api_client, db):
        User = get_user_model()
        u1 = User.objects.create_user(username='u1', email='u1@test.mx', password='Pass123!')
        u2 = User.objects.create_user(username='u2', email='u2@test.mx', password='Pass123!')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(u1).access_token}')
        r = api_client.get(PROFILE_URL)
        assert r.json()['username'] == 'u1'
        assert r.json()['email'] == 'u1@test.mx'

    def test_avatar_url_es_none_sin_avatar(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert r.json()['avatar_url'] is None

    def test_is_staff_no_incluido_en_respuesta(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert 'is_staff' not in r.json()

    def test_is_superuser_no_incluido_en_respuesta(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert 'is_superuser' not in r.json()

    def test_password_no_incluido_en_respuesta(self, auth_client, db):
        r = auth_client.get(PROFILE_URL)
        assert 'password' not in r.json()


# ── PATCH /api/v2/auth/profile/ ───────────────────────────────────────

class TestProfileUpdate:

    def test_actualizar_nombre_retorna_200(self, auth_client, db):
        r = auth_client.patch(PROFILE_URL, {'first_name': 'Nuevo'}, format='json')
        assert r.status_code == 200

    def test_actualizar_nombre_persiste(self, auth_client, user, db):
        auth_client.patch(PROFILE_URL, {'first_name': 'Actualizado'}, format='json')
        user.refresh_from_db()
        assert user.first_name == 'Actualizado'

    def test_actualizar_telefono(self, auth_client, user, db):
        auth_client.patch(PROFILE_URL, {'phone': '5559876543'}, format='json')
        user.refresh_from_db()
        assert user.phone == '5559876543'

    def test_no_puede_cambiar_email(self, auth_client, user, db):
        original_email = user.email
        r = auth_client.patch(PROFILE_URL, {'email': 'nuevo@test.mx'}, format='json')
        user.refresh_from_db()
        assert user.email == original_email

    def test_no_puede_cambiar_username(self, auth_client, user, db):
        original_username = user.username
        auth_client.patch(PROFILE_URL, {'username': 'nuevouser'}, format='json')
        user.refresh_from_db()
        assert user.username == original_username

    def test_avatar_jpeg_valido_aceptado(self, auth_client, user, db, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        img_bytes = make_image_bytes('JPEG')
        avatar = SimpleUploadedFile('test.jpg', img_bytes, content_type='image/jpeg')
        r = auth_client.patch(PROFILE_URL, {'avatar': avatar}, format='multipart')
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.avatar

    def test_avatar_formato_invalido_retorna_400(self, auth_client, db):
        fake_file = SimpleUploadedFile('mal.jpg', b'not an image', content_type='image/jpeg')
        r = auth_client.patch(PROFILE_URL, {'avatar': fake_file}, format='multipart')
        assert r.status_code == 400

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.patch(PROFILE_URL, {'first_name': 'X'}, format='json')
        assert r.status_code == 401

    def test_eliminar_avatar_con_null(self, auth_client, user, db, settings, tmp_path):
        """PATCH con avatar='' elimina el avatar existente."""
        settings.MEDIA_ROOT = str(tmp_path)
        # Primero subir un avatar
        img_bytes = make_image_bytes('PNG')
        avatar = SimpleUploadedFile('test.png', img_bytes, content_type='image/png')
        auth_client.patch(PROFILE_URL, {'avatar': avatar}, format='multipart')
        # Luego eliminar
        r = auth_client.patch(PROFILE_URL, {'remove_avatar': True}, format='json')
        assert r.status_code == 200

    def test_completeness_aumenta_al_completar_campo(self, auth_client, user, db):
        user.first_name = ''
        user.save()
        r1 = auth_client.get(PROFILE_URL)
        completeness_antes = r1.json()['profile_completeness']
        auth_client.patch(PROFILE_URL, {'first_name': 'Nombre'}, format='json')
        r2 = auth_client.get(PROFILE_URL)
        assert r2.json()['profile_completeness'] > completeness_antes
