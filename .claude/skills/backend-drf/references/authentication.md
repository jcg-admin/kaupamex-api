```yml
type: Reference (lazy-load on-demand)
applies_when: Se razona sobre quién es request.user, el contrato 401 vs 403, o se toca la config de autenticación
created_at: 2026-07-18 03:04:21
status: Aprobado
version: 1.0.0
source: DRF api-guide/authentication
```

# DRF Authentication — identidad de la petición

> La autenticación **identifica** la petición (`request.user`/`request.auth`);
> **no** autoriza — eso lo hace `HasCapability` (ver `SKILL.md` Phase 10). Corre
> al inicio de la vista, antes de permisos y throttling.

## Default del proyecto — sesión de servidor, ÚNICA auth (ADR-018)

`DEFAULT_AUTHENTICATION_CLASSES` tiene **una sola** clase (PROVEN 2026-07-18,
`src/config/settings/base.py:249-262`)::

    'DEFAULT_AUTHENTICATION_CLASSES': [
        'addons.users.authentication.CsrfExemptSessionAuthentication',
    ],

Es la migración completa a **sesión de servidor** para la web (ADR-018): la única
auth por default es la **cookie de sesión HttpOnly** (`__Host-sessionid;
SameSite=Strict`). Con `SessionAuthentication`, `request.user` es el usuario
Django (`IdentityUser`, `USERNAME_FIELD='email'`) y **`request.auth` es `None`**
(no hay token).

## JWT (SimpleJWT) — instalado pero DORMIDO, fuera del default

SimpleJWT está en `INSTALLED_APPS` (`rest_framework_simplejwt` +
`token_blacklist`, `base.py:37-38`) y el login **aún emite tokens** (dormidos),
pero `JWTAuthentication` **no** está en `DEFAULT_AUTHENTICATION_CLASSES` (PROVEN
2026-07-18: su única mención es un comentario, `base.py:260`). Para una futura app
móvil basta re-añadir `rest_framework_simplejwt.authentication.JWTAuthentication`
a la lista. **Hoy la auth web activa es la sesión, no el JWT.**

> Nota de deriva de deps: si se re-activa JWT bajo Apache+mod_wsgi, hay que pasar
> el header `Authorization` a la app (`WSGIPassAuthorization On`) — mod_wsgi no lo
> propaga por default. No aplica hoy (la sesión viaja por cookie, no por
> `Authorization`).

## CSRF — no se usa token; la defensa es la cookie

`CsrfExemptSessionAuthentication` (subclase de `SessionAuthentication`,
`addons/users/authentication.py:19`) vuelve **no-op** `enforce_csrf`: no se pide
`X-CSRFToken`. La defensa CSRF es `SameSite=Strict` + prefijo `__Host-` (la cookie
no viaja cross-site, que es el vector de CSRF). Origen: el incidente en que las
mutaciones por sesión pedían `X-CSRFToken` y el SPA, tras recargar, no lo tenía →
403 → logout. **No** re-introducir plumbing de token CSRF.

## Contrato 401 vs 403 — clave para el SPA y los tests

- **401 Unauthorized** = sesión ausente/expirada (anónimo a endpoint protegido).
  `CsrfExemptSessionAuthentication` implementa `authenticate_header()` → devuelve
  `'Session'` justamente para forzar **401** (DRF sólo da 401 si algún
  authenticator aporta `WWW-Authenticate`; `SessionAuthentication` base no lo
  hace y daría 403). El SPA (`apiService`) y los tests dependen de este contrato:
  **401 = "reautenticar"**.
- **403 Forbidden** = autenticado **pero sin capacidad** (`HasCapability`
  fail-closed; ver `SKILL.md`). La distinción es firme: 401 lo maneja el login,
  403 lo maneja el modelo de capacidades.

## Config por vista — no se overridea

Estado del repo (PROVEN 2026-07-18): **0** `authentication_classes` en
`src/addons`. La auth de sesión aplica **global**; ninguna vista la overridea. Si
hiciera falta (una vista que acepte JWT), el decorador FBV es
`@authentication_classes([...])` (bajo `@api_view`; ver `views.md`), o el atributo
`authentication_classes` en CBV — pero hoy no ocurre.

## Auth a medida — 1 en el repo

Una auth a medida subclasea `BaseAuthentication` (o una concreta) y overridea
`authenticate(self, request)` → `(user, auth)` o `None`; y opcionalmente
`authenticate_header()` para el `WWW-Authenticate` (→ 401 en vez de 403). PROVEN
2026-07-18: **1** subclase — `CsrfExemptSessionAuthentication` (arriba). No se usa
`Knox`, `django-oauth-toolkit`, `djoser`, `dj-rest-auth` ni OIDC; SimpleJWT es la
única dep de token, y está dormida.

## Checklist al razonar sobre autenticación

1. ¿Quién es `request.user`? → el usuario de la **sesión** (cookie
   `__Host-sessionid`); `request.auth` es `None`.
2. ¿Anónimo a endpoint protegido? → **401** (contrato del proyecto), no 403.
3. ¿Autenticado sin permiso? → **403** vía `HasCapability`, no una cuestión de
   auth.
4. **Nunca** pedir token CSRF ni reintroducir su plumbing (SameSite+`__Host-` es
   la defensa).
5. ¿App móvil futura? → re-añadir `JWTAuthentication` al default (+ `WSGIPassAuthorization`
   si Apache); no hoy.

## Referencias cruzadas

- `request-object.md` — `request.user`/`request.auth` desde el handler.
- `views.md` — `authentication_classes` como policy attribute + decorador FBV.
- `SKILL.md` Phase 10 — autorización por capacidad (el 403); la auth es sólo
  identidad.
- Código: `addons/users/authentication.py:19`
  (`CsrfExemptSessionAuthentication`), `config/settings/base.py:249-262` (default),
  `:339` (`SIMPLE_JWT`, dormido).
```
