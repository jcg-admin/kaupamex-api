"""Tests unitarios — CookieGovernanceMiddleware (LFPDPPP).

Verifican que el middleware:
  - audita las cookies emitidas contra COOKIE_REGISTER,
  - en modo auditoria (Fase 1) NO borra ninguna cookie,
  - en modo enforce (Fase 2) borra las no registradas y las que requieren
    consentimiento no otorgado, respetando el registro de consentimiento.

No toca DB: opera sobre request/response en memoria.
"""
import json
from urllib.parse import quote

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from core.middleware.cookie_governance import (
    CONSENT_COOKIE,
    COOKIE_REGISTER,
    CookieGovernanceMiddleware,
)

pytestmark = pytest.mark.unit


def _consent_cookie(**choices):
    record = {'version': 1, 'ts': '2026-07-01T00:00:00Z', 'choices': choices}
    return quote(json.dumps(record))


def _run(request, cookies):
    def get_response(_req):
        resp = HttpResponse('ok')
        for name, value in cookies.items():
            resp.set_cookie(name, value)
        return resp
    return CookieGovernanceMiddleware(get_response)(request)


def test_audit_mode_keeps_all_cookies(settings):
    settings.COOKIE_GOVERNANCE_ENFORCE = False
    request = RequestFactory().get('/')
    response = _run(request, {'sessionid': 'x', 'analytics_id': 'y'})
    # Fase 1: no borra nada, solo audita.
    assert 'sessionid' in response.cookies
    assert 'analytics_id' in response.cookies


def test_enforce_drops_unregistered_cookie(settings):
    settings.COOKIE_GOVERNANCE_ENFORCE = True
    request = RequestFactory().get('/')
    response = _run(request, {'sessionid': 'x', 'analytics_id': 'y'})
    # Necesaria registrada permanece; no registrada se suprime.
    assert 'sessionid' in response.cookies
    assert 'analytics_id' not in response.cookies


def test_necessary_cookies_always_allowed(settings):
    settings.COOKIE_GOVERNANCE_ENFORCE = True
    request = RequestFactory().get('/')
    response = _run(request, {'csrftoken': 'x', CONSENT_COOKIE: 'z'})
    assert 'csrftoken' in response.cookies
    assert CONSENT_COOKIE in response.cookies


def test_consent_cookie_is_read_from_request(settings):
    # Registrar analytics_id como categoria que requiere consentimiento.
    COOKIE_REGISTER['analytics_id'] = {'category': 'analytics'}
    try:
        settings.COOKIE_GOVERNANCE_ENFORCE = True
        rf = RequestFactory()

        # Sin consentimiento -> se bloquea.
        req_no = rf.get('/')
        resp_no = _run(req_no, {'analytics_id': 'y'})
        assert 'analytics_id' not in resp_no.cookies

        # Con consentimiento analytics=True -> se permite.
        req_yes = rf.get('/')
        req_yes.COOKIES[CONSENT_COOKIE] = _consent_cookie(analytics=True)
        resp_yes = _run(req_yes, {'analytics_id': 'y'})
        assert 'analytics_id' in resp_yes.cookies
    finally:
        COOKIE_REGISTER.pop('analytics_id', None)
