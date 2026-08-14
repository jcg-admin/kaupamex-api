"""URLs — addons.authz_signup (alta, set-password y reset por token)."""
from django.urls import path

from addons.authz_signup.controllers.main import (
    request_reset,
    signup,
    signup_info,
    verify_email,
)

app_name = 'authz_signup'

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('signup-info/', signup_info, name='signup-info'),
    path('request-reset/', request_reset, name='request-reset'),
    path('verify-email/', verify_email, name='verify-email'),
]
