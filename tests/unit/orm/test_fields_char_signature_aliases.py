"""``fields.Char`` — los alias de firma que hacen legible la declaración.

La fachada existe para que el sitio de declaración se lea **contra el de la
fuente sin traducir nada**: donde la referencia escribe
``fields.Char('Name', required=True, size=64)``, aquí se escribe igual y el
campo resultante es un ``models.CharField`` de Django con los nombres que
Django espera.

==============  =====================================================
De la fuente    Aquí
==============  =====================================================
``required=``   ``blank=False``/``blank=True`` — el vacío de formulario
``help=``       ``help_text=``
``size=``       ``max_length=`` — la longitud de la columna ``varchar``
``translate=``  ``translate`` — el mismo nombre en los dos lados
==============  =====================================================

El veredicto por símbolo, con el criterio de las dos categorías:

===========================  ==============================================
El stack lo trae hecho       ``models.CharField`` y sus cuatro parámetros —
                             ``blank``, ``help_text``, ``max_length``,
                             ``verbose_name``. La traducción es de **nombre**,
                             no de mecanismo.
El stack tiene con qué       la anotación ``translate``: Django no tiene
construirlo                  columna por idioma, así que la bandera se
                             conserva en el campo —con el nombre que la fuente
                             le da (``odoo19c: odoo/orm/fields.py:288``)— para
                             que la declaración sea fiel y greppeable mientras
                             se construye el almacenamiento ``jsonb``
                             (tarea **#333**).
===========================  ==============================================

Qué haría fallar a estos casos
==============================

``size=`` cerraba el **viaje de ida** de una traducción que ya existía en la
vuelta: ``_char_column_type`` (``src/orm/fields.py:1332``) emite
``('varchar', pg_varchar(self.max_length))`` desde hace tiempo, y la firma no
aceptaba el nombre de la fuente. El caso que lo mide es
``test_the_size_alias_becomes_max_length``: sin el alias, la construcción
levanta ``TypeError`` y el caso cae — que es exactamente lo que le pasó a la
sonda de ``test_environments_cache`` al declarar ``size=64``.

``test_the_column_type_reads_the_translated_length`` es el que discrimina de
verdad: comprueba que la longitud llega hasta el tipo de columna, así que un
alias que aceptara ``size=`` y lo tirara —el ``**kwargs`` que se lo traga—
seguiría rojo aquí y verde en el anterior.
"""
import pytest
from django.db import models as django_models

import fields


class TestTheSignatureAliasesTranslateNamesNotMechanisms:
    """Los cuatro nombres de la fuente y su destino en Django."""

    def test_the_size_alias_becomes_max_length(self):
        """El alias que cerró el viaje de ida (33 declaraciones en la fuente)."""
        field = fields.Char('Label', size=64)
        assert isinstance(field, django_models.CharField)
        assert field.max_length == 64

    def test_the_column_type_reads_the_translated_length(self):
        """Y la longitud llega hasta el tipo de columna.

        ``_char_column_type`` emite ``('varchar', pg_varchar(max_length))``:
        es el otro extremo de la misma traducción, y sólo este caso comprueba
        que los dos extremos se hablan.
        """
        assert fields.Char('Label', size=64).column_type == ('varchar', 'VARCHAR(64)')

    def test_max_length_still_works_by_its_django_name(self):
        """El nombre de Django sigue admitido: el alias suma, no sustituye."""
        assert fields.Char('Label', max_length=32).max_length == 32

    def test_the_required_alias_becomes_blank(self):
        """``required=True`` es ``blank=False`` — el vacío de formulario."""
        assert fields.Char('Label', required=True, size=8).blank is False
        assert fields.Char('Label', required=False, size=8).blank is True

    def test_the_help_alias_becomes_help_text(self):
        field = fields.Char('Label', help='La etiqueta', size=8)
        assert field.help_text == 'La etiqueta'

    def test_the_first_positional_is_the_label_on_both_sides(self):
        """El único que no hace falta traducir: ``verbose_name`` en Django es
        la etiqueta de la fuente."""
        assert fields.Char('Label', size=8).verbose_name == 'Label'

    def test_the_translate_flag_is_annotated_not_swallowed(self):
        """``translate=True`` no traduce **todavía** — y por eso se anota.

        Un ``**kwargs`` que se tragara la bandera dejaría al árbol sin forma de
        medir cuántos campos esperan traducción. Con la anotación, el barrido
        que la tarea **#333** necesita es un ``grep``.
        """
        assert fields.Char('Label', translate=True, size=8).translate is True

    def test_the_untranslated_field_says_so(self):
        """El control de la anotación: sin la bandera, la marca es falsa."""
        assert fields.Char('Label', size=8).translate is False


class TestTheAliasesComposeAsTheSourceDeclaresThem:
    """La forma real que la referencia escribe, entera."""

    def test_the_source_declaration_reads_the_same_here(self):
        """``fields.Char('Name', required=True, translate=True, size=64)``."""
        field = fields.Char('Name', required=True, translate=True, size=64)
        assert field.verbose_name == 'Name'
        assert field.blank is False
        assert field.translate is True
        assert field.max_length == 64

    def test_size_and_store_false_do_not_meet(self):
        """Un campo sin columna no tiene ``varchar`` que dimensionar.

        No es una prohibición inventada: ``store=False`` devuelve un
        :class:`~orm.fields_nonstored.NonStored`, que no declara columna. El
        caso fija que el ``size=`` no se pierda en silencio ahí — se ignora
        porque no hay dónde aplicarlo, y el campo sigue siendo el sin columna.
        """
        field = fields.Char('Label', store=False, size=64)
        assert not isinstance(field, django_models.CharField)
