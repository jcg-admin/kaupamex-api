"""Seed canonical PracticaYoruba category tree.

Run via:

    python manage.py shell < scripts/seed-data/seed_categories.py

Idempotent: existing categories are left untouched.
"""
from apps.modules.catalogue.models import Category

CATEGORIES = [
    ('Collares y Elekes', 'collares', 'Collares ceremoniales y elekes Lukumí.'),
    ('Pulseras e Idés',   'pulseras', 'Pulseras consagradas e idés de orishas.'),
    ('Ofrendas y Adimú',  'ofrendas', 'Ofrendas y adimú tradicionales para orishas.'),
    ('Sahumerios',        'sahumerios', 'Sahumerios y sahumadores rituales.'),
    ('Aceites Rituales',  'aceites',  'Aceites rituales bajo invocación de orisha.'),
    ('Jabones Rituales',  'jabones',  'Jabones artesanales para baños rituales.'),
    ('Polvos Rituales',   'polvos',   'Polvos rituales y cascarillas consagradas.'),
    ('Semillas y Plantas Sagradas', 'semillas', 'Semillas y plantas sagradas Yoruba.'),
]

created, existing = 0, 0
for name, slug, description in CATEGORIES:
    cat, was_created = Category.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'description': description, 'is_active': True},
    )
    if was_created:
        created += 1
    else:
        existing += 1
print(f'Categorías creadas: {created}, ya existentes: {existing}')
