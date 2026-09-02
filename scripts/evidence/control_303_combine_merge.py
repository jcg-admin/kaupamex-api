"""Control de #303 — el ``combine=merge_dict`` de los conversores discrimina.

Los ocho ``chain_method`` sobre ``attributes`` de
``addons/html_editor/models/ir_qweb_fields.py`` empiezan su cuerpo con
``attrs = {}``; la fuente empieza con ``attrs = super().attributes(...)``
(``odoo19c: html_editor/models/ir_qweb_fields.py``). Sin ``combine=`` el relevo
por defecto sólo invoca al eslabón previo cuando el nuevo devuelve ``None``, y
un diccionario vacío **no** es ``None``: lo que aporta la clase base se
descarta en silencio.

Este control lo mide. Sustituye el ``combine=`` en memoria, corre la sonda en
un proceso aparte y restaura desde la copia — nunca ``git checkout`` (#177),
cerrando con el sha256 del archivo.

*Métrica:* keys que ``IrFieldConverterMany2one.attributes`` devuelve para un
campo con ``placeholder`` en las opciones, que es lo que aporta el eslabón base.
*Ciega a:* si el resto de los siete conversores combinan igual — sólo se mide
el derivado de Many2one, que es el que la fuente documenta con ``super()`` en
su primera línea.
"""
import hashlib
import os
import pathlib
import subprocess
import sys

PATH = pathlib.Path('addons/html_editor/models/ir_qweb_fields.py')

PROBE = r'''
import django
django.setup()
from django.apps import apps
from addons.base.models.ir_field_converters import IrFieldConverterMany2one

Partner = apps.get_model('base', 'ResPartner')
partner = Partner(name='sonda 303')
keys = IrFieldConverterMany2one.attributes(
    partner, 'parent', {'placeholder': 'nombre del padre'}, None)
print('CLAVES', sorted(keys))
'''


def run_probe(label):
    output = subprocess.run(
        [sys.executable, '-c', PROBE], capture_output=True, text=True,
        env={**os.environ,
             'DJANGO_SETTINGS_MODULE': 'config.settings.testing',
             'PYTHONPATH': 'src'})
    line = [l for l in output.stdout.splitlines() if l.startswith('CLAVES')]
    print(f'{label}: {line[0] if line else output.stderr.strip()[-400:]}')


def main():
    original = PATH.read_text()
    sha_before = hashlib.sha256(original.encode()).hexdigest()
    run_probe('con combine= ')
    try:
        PATH.write_text(original.replace(', combine=merge_dict', ''))
        run_probe('sin combine= ')
    finally:
        PATH.write_text(original)
    sha_after = hashlib.sha256(PATH.read_text().encode()).hexdigest()
    print(f'sha256 antes   {sha_before}')
    print(f'sha256 despues {sha_after}')
    print('RESTAURADO' if sha_before == sha_after else 'DIVERGE')


if __name__ == '__main__':
    main()
