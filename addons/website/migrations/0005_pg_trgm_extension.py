"""Instala ``pg_trgm`` — la extensión que la búsqueda difusa del sitio exige.

``Website._trigram_enumerate_words`` (B3, #536) preselecciona candidatos con
``word_similarity()`` y el operador ``<%``, ambos de ``pg_trgm``. La fuente
asume la extensión presente (su ``registry.has_trigram`` sólo la sondea); aquí
se instala por migración para que una base recién creada la traiga sin pasos
manuales — mismo criterio que ``django.contrib.postgres`` ya cableado (#94).

Medido antes de esta migración: ``kaupamex_core_qa`` sólo tenía ``plpgsql``,
y ``CREATE EXTENSION IF NOT EXISTS pg_trgm`` como ``django_user`` funciona en
este entorno (la extensión es *trusted* desde PostgreSQL 13). El despacho de
``_search_find_fuzzy_term`` degrada solo a ``_basic_enumerate_words`` si la
sonda ``has_trigram`` no la ve, así que un entorno sin permiso de CREATE
EXTENSION no rompe — pierde el fuzzy por trigramas, no la búsqueda.
"""
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0004_websitemenu_website_fk_parent_path_new_window'),
    ]

    operations = [
        TrigramExtension(),
    ]
