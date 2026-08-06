"""Modelos del addon ``onboarding`` (estructura Odoo: un archivo por modelo).

Orden de import: el mismo que ``odoo19c: onboarding/models/__init__.py``
(onboarding, onboarding_step, progress, progress_step) — cada módulo resuelve
sus propias dependencias internas top-level (ver docstrings de
``onboarding_onboarding.py``/``onboarding_onboarding_step.py`` sobre el orden
real de imports para evitar ciclos: progress -> progress_step ->
onboarding_step -> onboarding).
"""
from .onboarding_onboarding import OnboardingOnboarding
from .onboarding_onboarding_step import OnboardingOnboardingStep
from .onboarding_progress import OnboardingProgress
from .onboarding_progress_step import OnboardingProgressStep

__all__ = [
    'OnboardingOnboarding', 'OnboardingOnboardingStep',
    'OnboardingProgress', 'OnboardingProgressStep',
]
