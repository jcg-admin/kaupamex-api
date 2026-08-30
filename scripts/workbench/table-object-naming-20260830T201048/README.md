# El nombrado por atributo de clase: se dispara en Django?

Sonda previa al porte de `odoo/orm/table_objects.py`, cuyo mecanismo de
nombrado cuelga entero del protocolo `__set_name__`: el objeto de tabla toma su
nombre del atributo de clase que lo aloja
(`odoo19c: odoo/orm/table_objects.py:39-50`).

La pregunta no era retorica. `ModelBase` de Django no construye la clase con el
namespace completo: separa los atributos que declaran `contribute_to_class` y
los reincorpora despues con `add_to_class`. Si el protocolo no se disparara, el
nombrado habria que construirlo de otra forma.

## Lo medido

```
clase Python normal:
  fired=True name='_probe' owner='_Plain'
modelo de Django:
  fired=True name='_probe' owner='_DjangoModel'
  el atributo sobrevive en la clase: True
  Meta.constraints por defecto: []
```

Y la segunda sonda, sobre que hay disponible en el owner en ese instante:

```
_probe: {'tiene__meta': False, 'tiene_pool': False, 'bases': ['Model', 'AltersData']}
tras construir la clase, _meta existe: True
```

## Los dos veredictos

1. **El protocolo se dispara, con el nombre correcto, y el atributo sobrevive.**
   El nombrado de la fuente se porta verbatim.
2. **`_meta` NO existe cuando corre `__set_name__`.** El registro no puede ir a
   `Meta.constraints` desde ahi: va a `_table_object_definitions`, una lista de
   clase, que es exactamente donde la fuente lo pone.

El segundo cierra tambien la divergencia. La fuente discrimina la clase de
definicion de la de registro con `getattr(owner, 'pool', None) is None`; aqui no
hay clases de registro y `_meta` nunca esta presente en ese instante, asi que la
guarda no tiene contraparte y se declara en el docstring del puerto.

*Metrica:* si el protocolo se dispara, con que nombre y sobre que owner; y que
atributos existen en el owner en ese instante.
*Ciega a:* el orden relativo entre `__set_name__` y el resto del arranque de
`ModelBase` — la sonda mide presencia, no secuencia; y a los modelos abstractos
y proxy, que no se midieron.
