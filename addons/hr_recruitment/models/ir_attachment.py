"""``ir.attachment`` — índice de búsqueda de texto sobre adjuntos de
candidatos (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/ir_attachment.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 19 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 1 símbolo
====================================

``init`` (``:11-19``) crea, al instalar el módulo, un índice GIN trigram
**parcial** (``WHERE res_model = 'hr.applicant'``) sobre
``index_content`` — acelera la búsqueda de texto libre en el contenido
indexado de los CVs adjuntos.

Bloqueado por dos piezas medidas:

1. **El mecanismo de disparo.** ``init()`` es un hook de Odoo que corre al
   instalar/actualizar el módulo — este árbol no tiene ese ciclo de vida;
   un índice condicional (``self.env.registry.has_trigram``/
   ``has_unaccent``) es responsabilidad de una **migración** (``python
   manage.py makemigrations``), que el orquestador genera, no este addon
   (regla del pase: "no creas migraciones").
2. **Las banderas de capacidad.** ``registry.has_trigram``/
   ``has_unaccent`` (``FunctionStatus``) no existen en este ORM (medido:
   0 hits de ambos símbolos en ``src/``) — la comprobación de si
   ``pg_trgm``/``unaccent`` están instaladas en la base activa no está
   portada.

El SQL en sí no cambia entre motores — se deja citado para que la
migración que #278-adyacente decida lo escriba verbatim::

    CREATE INDEX IF NOT EXISTS ir_attachment_index_content_applicant_trgm_idx
        ON ir_attachment USING gin (index_content gin_trgm_ops)
     WHERE res_model = 'hr.applicant';

Sucesor: tarea de migración cuando el pipeline de indexación de adjuntos
(``attachment_indexation``, addon completo ausente de este árbol — medido:
0 hits) se porte.
"""


def apply_hr_recruitment_ir_attachment_extensions():
    """No-op declarado — ver el docstring del módulo (bloqueo de migración)."""
    return None


__all__ = ['apply_hr_recruitment_ir_attachment_extensions']
