"""Contract for the seeded module dependency graph (SOL-085 S3).

``seed_authz`` populates ``Module.depends`` so the S3 activation guard has a
real graph to enforce (without a seed the graph is dead capability). The graph
is conservative and functional: e.g. orders needs catalogue + inventory,
payments/invoices/logistics/returns need orders, inventory needs catalogue.
"""
import pytest
from django.core.management import call_command

from apps.authz.models import Module

pytestmark = pytest.mark.django_db


def _deps(code):
    return set(Module.objects.get(code=code).depends.values_list('code', flat=True))


class TestSeededModuleDepends:
    def test_seed_sets_the_dependency_graph(self):
        call_command('seed_authz')
        assert _deps('inventory') == {'catalogue'}
        assert _deps('orders') == {'catalogue', 'inventory'}
        assert _deps('payments') == {'orders'}
        assert _deps('invoices') == {'orders'}
        assert _deps('logistics') == {'orders'}
        assert _deps('returns') == {'orders'}

    def test_standalone_modules_have_no_deps(self):
        call_command('seed_authz')
        # catalogue is a root; banners/newsletter/seo are independent surfaces
        assert _deps('catalogue') == set()
        assert _deps('banners') == set()
        assert _deps('newsletter') == set()

    def test_seed_is_idempotent_on_depends(self):
        call_command('seed_authz')
        call_command('seed_authz')  # second run must not duplicate/clear deps
        assert _deps('orders') == {'catalogue', 'inventory'}
