<!-- Extraído de 6b46f724-EarlySoftwareSizingwithCOSMICPractitionersGuideEspa_ol..pdf (18 págs) por pypdf — 2026-06-03T03:37:21Z. Fuente COSMIC oficial. -->
# COSMIC — Early Software Sizing (Guía del Profesional / Practitioners Guide)



<!-- pág 1/18 -->

Medición Temprana de 
Software  
con COSMIC:  
Guía de Practicantes 
 
 
 
27 de febrero, 2020 
(actualización menor mayo 2020)


<!-- pág 2/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 2 
Copyright © 2020 
 
Tabla de Contenidos 
 
1. PRINCIPIOS GENERALES DEL TAMAÑO APROXIMADO.  ............................................................ 4 
1.1  ¿Cuándo se necesita un tamaño COSMIC aproximado? ............................................................. 4 
1.2 Problemas en la aproximación de tamaño funcional. . ................................................................. 5 
1.3 Descripción general de las técnicas descritas para la etapa de requisitos. ................................. 5 
1.4 Descripción general de las técnicas descritas para la etapa de viabilidad. .................................. 6 
2. TAMAÑO PROMEDIO DE LOS PROCESOS FUNCIONALES. ......................................................... 6 
3. CLASIFICACIÓN DE TAMAÑO FIJO. ................................................................................................ 7 
4. BANDAS DE IGUAL TAMAÑO. .......................................................................................................... 8 
5. TAMAÑO PROMEDIO DE LOS CASOS DE USO. ............................................................................. 9 
6. APROXIMACIÓN COSMIC RAPIDA Y TEMPRANA (E&Q) ............................................................... 9 
7. APROXIMACIÓN DE SOFTWARE ICEBERG. .................................................................................11 
8. APROXIMACIÓN DE PUNTOS DE FUNCIÓN EASY (EARLY & SPEEDY). ...................................13 
9. TAMAÑO APROXIMADO DE CAMBIOS DE FUNCIONALIDAD Y ALCANCE NO CONTROLADO.
 ……………………………………………………………………………………………………………. 14 
9.1 Tamaño aproximado de los cambios de funcionalidad. ............................................................. 14 
9.2 Tamaño aproximado y alcance no controlado. ........................................................................... 14 
9.3 Aplicando aproximación en proyectos de mejora. ..................................................................... 15 
10. LISTA DE VERIFICACIÓN. .............................................................................................................15 
11. GLOSARIO DE TERMINOS ............................................................................................................16 
12. REFERENCIAS. ...............................................................................................................................18 
 
Agradecimientos: Editor y revisores 2020 (orden alfabético).  
Alain Abran 
École de Technologie 
Supérieure, Canadá 
Arlan Lesterhuis 
COSMIC 
Los Paises Bajos 
Bruce Reynolds 
Tecolote Research 
Estados Unidos 
Asma Sellami 
University of Sfax 
Tunez 
Hassan Soubra 
German University of 
Cairo 
Egipto 
Sylvie Trudel 
Université du Québec 
à Montréal, Canadá 
Francisco Valdés 
Souto 
Spingere 
México 
Frank Vogelezang * 
METRI 
Los Paises Bajos 
* Editor 
 
Equipo de traducción de Medición Temprana del Software con COSMIC: Guía de 
Practicantes 
Francisco Valdés 
Souto 
Spingere 
México 
Ricardo Cardenas 
Estrada 
Coppel 
México


<!-- pág 3/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 3 
Copyright © 2020 
 
Copyright 2020. Todos los derechos reservados. El Consorcio Internacional de la Comunidad de Medición de 
Software (COSMIC). Se concede permiso para copiar todo o parte de este material siempre que las copias no se 
realicen o distribuyan con fines comerciales y que se cite el título de la publicación, su número de v ersión y su 
fecha y se notifique que la copia se realiza con permiso de Consorcio Internacional de Medición de Software Común 
(COSMIC). Copiar lo contrario requiere un permiso específico.


<!-- pág 4/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 4 
Copyright © 2020 
 
1. PRINCIPIOS GENERALES DEL TAMAÑO APROXIMADO 
El método COSMIC proporciona una forma estandarizada de medir un tamaño funcional de 
software. 
En la práctica, a veces es suficiente o necesario aproximar un tamaño funcional1: 
• cuando se necesita un tamaño, pero no hay suficiente tiempo o recursos para medir 
utilizando el método estándar; 
• temprano en la vida de un proyecto, antes de que los Requisitos del Usuario Funcional 
(FUR) se hayan especificado hasta el nivel de detalle donde es posible la medición precisa 
del tamaño; 
• cuando la calidad de la documentación de los requisitos reales no es lo suficientemente 
buena para una medición precisa. 
La audiencia prevista para este documento es para aquellos que necesitan establecer el 
tamaño de una pieza de software sin tiempo o detalles disponibles para usar el métod o 
COSMIC estándar.  
Para aquellos que están interesados en una visión más profunda de la s técnicas de 
aproximación COSMIC, consulte la Guía de Expertos [1]que analiza sus pros y sus contras, y 
sus áreas de aplicación recomendadas. 
Este documento describe las razones por las cuales puede ser necesario aproximar, cómo los 
requisitos reales a menudo  se expresan en diferentes niveles de documentación y algunos 
principios generales de cómo reconocer y aplicar técnicas de aproximación.  
El resto de la guía describe: 
• Técnicas para la Etapa de Requisitos (secciones 2-5). 
• Técnicas para la Etapa de Viabilidad (secciones 6-8). 
• Una lista de verificación con elementos para tener en cuenta al usar la aproximación. 
Puede utilizar el foro sobre cosmic-sizing.org/forums para publicar sus preguntas y respuestas 
de la comunidad  mundial de COSMIC. La calidad de cualquier respuesta dependerá del 
conocimiento y la experiencia del miembro de la comunidad que escribe la respuesta.  
Existen organizaciones comerciales que pueden proporcionar capacitación y consultoría o 
soporte de herramientas; consulte https://cosmic-sizing.org/organization/commercial-support/ 
1.1  ¿Cuándo se necesita un tamaño COSMIC aproximado? 
Hay tres circunstancias principales en las que un tamaño funcional COSMIC aproximado 
puede ser valioso: 
1. cuando se necesita una medición de tamaño rápidamente y un tamaño aproximado es 
aceptable si se puede medir mucho más rápido que con el método estándar. Esto se 
conoce como "aproximación rápida"; 
2. temprano en la vida de un proyecto antes de que los requisitos reales hayan sido 
especificados con cierto detalle, pero insuficientes para una medición precisa del tamaño. 
Esto se conoce como "medición temprano"; 
 
1 En lugar de describir este tema como técnicas para "aproximar el tamaño", podría ser más preciso describirlo como técnicas 
para "estimar tamaños". Sin embargo, la palabra "estimación" está fuertemente asociada con los métodos de estimación de 
costos, esfuerzo o duración del proyecto, etc. Para evitar confusiones, por lo tanto, preferimos referirnos a ella como "tamaño 
aproximado".


<!-- pág 5/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 5 
Copyright © 2020 
 
3. en general, cuando la calidad de la documentación de  los requisitos reales no es lo 
suficientemente buena para una medición precisa del tamaño. 
La aproximación rápida puede ser valiosa cuando se necesita medir una pieza de software 
muy grande o, por ejemplo, una cartera de software completa, pero tomaría demasiado tiempo 
y dinero medir con precisión, y los tamaños aproximados son aceptables. 
Ya sea que midan con precisión o aproximadamente, los medidores siempre deben tratar de 
obtener tanta información y detalles sobre la descripción de los requisitos reale s. Las 
suposiciones se pueden utilizar para que la medición del tamaño funcional sea lo más precisa 
posible. 
1.2 Problemas en la aproximación de tamaño funcional. 
1.2.1 Localización (calibración). 
Las técnicas  de tamaño aproximado se basan en hechos de  artefactos que no están 
estandarizados y pueden variar en sus niveles de detalles funcionales dentro de las 
organizaciones y entre organizaciones.  Esto implica que los factores de escala deben 
calibrarse localmente. En este documento, "localmente" implica  que el entorno en el que se 
han definido los factores de escala para la técnica de aproximación es representativo del entorno 
en el que se debe utilizar la técnica de   aproximación.  
1.2.2 Tamaño aproximado por clasificación y escala. 
Clasificación: clasificar cada requisito real y asignarle un tamaño (es decir, aplicarle un factor 
de escala) que represente el tamaño funcional COSMIC para ese requisito. 
El enfoque general de la clasificación es que cada parte de los requisitos reales que se va a 
medir aproximadamente se asigna a una clase predefinida (o pieza de referencia) de 
requisitos cuyo tamaño se ha calibrado en CFP, es decir, cada clase tiene su propio factor de 
escala. Por lo tanto, se asigna un tamaño a cada parte de las necesidades reales, en función 
de su clasificación. 
Es altamente deseable que una técnica de aproximación que utiliza la clasificación 
proporcione reglas o criterios objetivos, o ejemplos típicos para ayudar a la clasificación 
correcta. 
1.2.3 Certeza del tamaño aproximado. 
Cualquier técnica para aproximar el tamaño es el resultado de un equilibrio entre la facilidad 
y la velocidad de medición frente a la  pérdida de la certeza. Por lo tanto, se debe establecer 
e informar la cantidad estimada de error de cada técnica. Consulte la Guía [1]para obtener 
más orientación. 
1.3 Descripción general de las técnicas descritas para la etapa de 
requisitos. 
Técnica Fortaleza Debilidad Área de aplicación 
Tamaño Promedio 
de PF. 
Fácil de usar. Dependiente del dominio.  
 Requiere muestreo. La misma que la 
muestra. 
Clasificación de 
Tamaño Fijo. * 
Fácil de usar. Depende del dominio.  
Se documentan los 
factores de escala. 
Asignar una clase a un PF 
es subjetivo. 
La clasificación de 
tamaño debe ajustarse 
al software. 
Bandas de igual 
tamaño. 
Fácil de usar. Los PF deben clasificarse 
correctamente. 
Negocio y tiempo real 
embebido. 
Más bandas conducen a 
una aproximación más 
precisa. 
Las bandas deben estar 
significativamente 
separadas. 
Distribución sesgada 
de los PF


<!-- pág 6/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 6 
Copyright © 2020 
 
Requiere conjunto de 
datos de muestra. 
Tamaño promedio 
de los casos de 
uso. * 
Fácil de usar cuando los 
Casos de Uso están 
estandarizados. 
La funcionalidad asignada 
a un caso de uso puede 
variar. 
CU estandarizados. 
El factor de escala es un 
producto de dos factores 
que contienen estimación. 
 
Requiere conjunto de 
datos de muestra. 
Igual que el conjunto 
de datos de muestra. 
Tabla 1.1 – Resumen de las técnicas de aproximación para la etapa de requisitos. 
* NOTA Esta técnica funciona mejor con un conjunto de datos simétricos y una desviación 
estándar (valor σ) que es significativamente menor que el tamaño promedio del  proceso 
funcional. 
1.4 Descripción general de las técnicas descritas para la etapa de 
viabilidad. 
Técnica Fortaleza Debilidad Área de aplicación 
Rápida y 
Temprana 
COSMIC 
Aplicable cuando parte de los 
requisitos aún no se detallan. 
Asignar una clase a un 
PF es subjetivo. 
Más adecuado 
cuando una parte de 
los requisitos no 
está lo 
suficientemente 
detallada como para 
identificar PF. 
Puede manejar diferentes 
niveles de documentación. 
No diseñado para 
mejoras. 
Analogía de 
iceberg de 
software 
Se puede mezclar con 
medidas estándar. 
Mediciones históricas 
necesarias para la 
calibración. 
Válido a lo largo de 
la obtención de los 
primeros requisitos 
en requisitos reales. Se puede escalar a diferentes 
niveles de documentación. 
 
Se puede alinear con ISO-
IEEE 29148 en Ingeniería de 
Requisitos. 
 
FACIL por 
Puntos de 
Función 
 
Se puede mezclar con 
medidas estándar. 
La calibración 
consume mucho 
tiempo. 
Válido a lo largo de 
la obtención de los 
primeros requisitos 
en requisitos reales. Se puede escalar a diferentes 
niveles de documentación. 
Mapear los requisitos 
es subjetivo. 
También se puede usar para 
medir mejoras. 
 
Tabla 1.2 – Resumen de las técnicas de aproximación para la etapa de viabilidad. 
2. TAMAÑO PROMEDIO DE LOS PROCESOS FUNCIONALES. 
La técnica del tamaño promedio de los procesos funcionales se puede usar cuando los 
requisitos reales de una pieza de software se conocen solo por el nivel de los procesos 
funcionales, pero no por el nivel de los movimientos de datos. 
A Determinar el factor de escala. 
1. Identificar una muestra de los requisitos reales cuyos procesos funcionales y movimientos 
de datos se han definido en detalle,  con características similares a los  requisitos reales 
del software a medir.


<!-- pág 7/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 7 
Copyright © 2020 
 
2. Identificar los procesos funcionales de estos requisitos de muestra. 
3. Mida los tamaños de los procesos funcionales de estos requisitos de muestra utilizando 
con precisión el método COSMIC estándar. 
4. Determinar el tamaño promedio, en CFP, de los procesos funcionales de estos requisitos 
muestreados (por ejemplo, tamaño medio = 8 CFP).  '8' es entonces el factor de escala 
para esta técnica. 
5. Identificar la desviación estándar. 
 
B   Aproximación utilizando el factor de escala. 
1. Identificar y contar todos los procesos funcionales de los requisitos reales del software a 
medir (por ejemplo, = 40 procesos funcionales). 
2. Para un conjunto de requisitos: El tamaño funcional aproximado del conjunto si se estima 
que los requisitos reales del software a medir son (número de procesos funcionales x 
factor de escala) = 40 x 8 CFP = 320 CFP. 
3. Para un requisito específico: determine el rango de  tamaño aproximado utilizando la 
desviación estándar de tamaño promedio +/- 1. Desde arriba: si el promedio es 8 CFP, y 
la desviación estándar es 2 CFP, el rango de un proceso funcional específico es: [6,10 
CFP]. 
3. CLASIFICACIÓN DE TAMAÑO FIJO. 
La técnica depende de definir una clasificación de tamaño típica de los procesos funcionales 
en la pieza de software a medir. A  continuación, se asigna un tamaño o factor de escala 
correspondiente a cada clase, para todos sus procesos funcionales. 
Se debe analizar una  declaración de  los requisitos reales para identificar l os procesos 
funcionales y clasificar cada uno de ellos según su tamaño en una de las tres o más clases 
de tamaño llamadas, por ejemplo, Pequeña, Mediana y Grande.  
La Tabla 3.1 muestra un ejemplo de un conjunto de clases de tamaño que está en uso real en 
una organización comercial específica. Las filas muestran las tres clases de tamaño posibles 
para esta organización y el número total de CFP que debe asignarse a un proceso funcional 
en cada grupo (por ejemplo, si se identifica un pequeño proceso funcional,  se le asigna un 
factor de escala de 5, por lo que su tamaño es de 5 CFP). Para obligar al Medidor a elegir 
deliberadamente el tamaño, se considera que el tamaño del paso entre las clases es bastante 
amplio, a 5 CFP. 
Las cuatro columnas #E, #X, #R y #W explican por qué se asigna el número de CFP al proceso 
funcional de un tamaño determinado.  Por ejemplo, se supone que un proceso funcional 
pequeño consta de 1 movimiento de datos de Entrada, 1 Lectura, 1 Escritura y 1 Salida. Para 
procesos funcionales medianos o grandes se asumen más movimientos de datos de cada 
tipo. La quinta columna 'Mensajes de error' se agrega en una salida para mensajes de 
error/confirmación 
Clasificación Tamaño 
(CFP) 
#E #X #R #W Mensaje Error 
Pequeño 5 1 1 1 1 1 
Mediano 10 2 2 3 2 1 
Grande 15 3 3 4 4 1 
…       
Tabla 3.1 – Clasificación de tamaño fijo a partir de [2].


<!-- pág 8/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 8 
Copyright © 2020 
 
Si el tamaño funcional de algunos requisitos reales debe aproximarse al principio del proceso 
de desarrollo, a cada requisito real se le asignan uno o más procesos  funcionales, junto con 
su clasificación de tamaño adecuada y la aproximación de tamaño correspondiente.  
El uso de una tabla como 3.1 ayuda al medidor a tomar una decisión más rápida sobre la 
asignación de la clase de tamaño para cada proceso funcional. Si es necesario, la tabla puede 
ampliarse para acomodar uno o más tamaños adicionales, como "muy grandes" de 20 CFP.   
4. BANDAS DE IGUAL TAMAÑO. 
En la técnica de "Bandas de igual tamaño", los procesos funcionales se clasifican en un 
pequeño número de bandas de tamaño. Los límites de las bandas se eligen en el proceso de 
calibración para que el tamaño total de todos los procesos funcionales en cada banda sea el 
mismo para cada banda. 
A   Determinar el factor de escalas. 
1. Identificar una muestra de requisitos reales cuyos procesos funcionales y movimientos de 
datos se han definido en detalle, con características similares a los requisitos reales del 
software a medir. 
2. Identificar los procesos funcionales de estos requisitos de muestra. 
3. Mida los tamaños de los procesos funcionale s de estos requisitos de muestra con 
precisión utilizando el método COSMIC estándar. 
4. Ordenar los procesos funcionales en orden ascendente y presentarlos gráficamente en 
orden ascendente junto con su tamaño acumulado. 
5. Utilizando la información de la distribución acumulativa, divida la muestra en varias bandas 
que tengan el mismo tamaño total (y que por lo tanto contengan una cantidad diferente de 
procesos funcionales). Entonces, si, por ejemplo, la opción es tener tres bandas, entonces 
el tamaño total de todos los procesos funcionales en cada banda contribuirá 33% al 
tamaño total del software que se está midiendo. 
6. Determinar el tamaño promedio, en CFP, de los procesos funcionales en cada banda. 
Estos son los factores de escala para cada banda. Estos factores de escala generalmente 
no son números enteros. 
B   Aproximación usando los factores de escala. 
1. Identificar para cada uno de los procesos funcionales que se aproximarán la banda de 
tamaño en la que pertenece. 
2. Asigne el factor de escala para esa banda de tamaño al proceso funcional. 
3. Sumar todos los procesos funcionales aproximados para obtener la aproximación del 
tamaño funcional de toda la pieza de software. 
 Ejemplos de uso reportado 
Banda Tamaño promedio de 
un Proceso 
Funcional 
% del Tamaño 
Funcional total 
% del número total de 
Procesos Funcionales 
Pequeño 4.8 25% 40% 
Mediano 7.7 25% 26% 
Grande 10.7 25% 19% 
Muy Grande 16.4 25% 15% 
Table 4.1 – Ejemplo de 4 bandas de igual tamaño de 37 aplicaciones empresariales en [2].


<!-- pág 9/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 9 
Copyright © 2020 
 
Banda Tamaño promedio de 
un Proceso 
Funcional 
% del Tamaño 
Funcional total 
% del número total de 
Procesos Funcionales 
Pequeño 5.5 25% 49% 
Mediano 10.8 25% 26% 
Grande 18.1 25% 16% 
Muy Grande 38.8 25% 7% 
Table 4.2 – Ejemplo de 4 bandas de tamaño igual de un componente principal de un sistema de aviación 
en [2]. 
Tenga en cuenta la similitud entre el número de procesos funcional es en cada una de las 
cuatro bandas a pesar de los diferentes tipos de software. Sin embargo, el tamaño promedio 
de los procesos funcionales en cada banda es bastante diferente, especialmente para las 
bandas grandes y muy grandes. Esto enfatiza la necesidad de calibrar el tamaño local. 
Para medir una nueva pieza de software:  
1. Se identifican los procesos funcionales de la nueva pieza.  
2. Se clasifican como "Pequeño", "Mediano", "Grande" o "Muy grande".  
3. Los tamaños promedio de cada banda (como se mencionan arriba pero 
preferiblemente calibrados localmente) se utilizan para multiplicar el número de 
procesos funcionales de la nueva pieza de software, en cada banda respectivamente 
para obtener el tamaño aproximado total estimado. 
 
5. TAMAÑO PROMEDIO DE LOS CASOS DE USO. 
El principio de la aproximación es similar a la aproximación promedio del proceso funcional 
de la sección 2, pero en un nivel más alto de documentación, a saber, el Caso de Uso. 
La calibración local podría determinar que un Caso de Uso (definido localmente) comprende, 
en promedio, 3.5 procesos funcionales, cada uno de tamaño promedio 8 CFP (como en el 
ejemplo en la Sección 2). Por lo tanto, el tamaño promedio de un caso de uso según esta 
definición local es 3.5 x 8 = 28 CFP por caso de uso. 
Para un nuevo proyecto con 12 Use Cases, el tamaño del software sería de 12 x 28 x 236 
CFP. 
Por lo tanto, con esta calibración, la identificación del número de casos de uso al principio de 
un proyecto de desarrollo proporcionará una base para hacer una estimación preliminar del 
tamaño del software en unidades de CFP.   
6. APROXIMACIÓN COSMIC RÁPIDA Y TEMPRANA (EARLY 
&QUICK) 
La técnica de aproximación COSMIC Temprana y Rápida (E&Q) se basa en la capacidad del 
medidor para clasificar una parte de los requisitos reales como pertenecientes a una categoría 
funcional particular. Una tabla de referencia apropiada le permite al medidor asignar un valor 
promedio de CFP para ese elemento (esto se aplica para el software en cada capa identificada 
de la arquitectura de software por separado, según el método COSMIC estándar).


<!-- pág 10/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 10 
Copyright © 2020 
 
Cada función se puede clasificar, en orden de magnitud creciente y número decreciente de 
elementos de composición, como un Proceso Funcional, Proceso Típico, Proceso General o 
Macroproceso.  
 
a) En la técnica Temprana y Rápida, un Proceso Funcional2 (PF) es el proceso más pequeño. 
Un Proceso Funcional puede ser Pequeño, Mediano, Grande o Extragrande, dependiendo 
de su número estimado de movimientos de datos. Esta categorización es similar a la 
técnica de 'Aproximación a la Clasificación de Tamaño Fijo' discutida en la Sección 3. 
b) Un Proceso Típico ( PT) es un conjunto de las cuatro operaciones básicas del usuario: 
Crear, Recuperar, Actualizar y Eliminar (CRUD , por siglas en ingles ) en datos que 
describen un objeto de interés en particular. Estos Procesos Típicos se encuentran con 
frecuencia en el software de aplicación empresarial. 
c) Un Proceso General (PG) es un conjunto de Procesos Funcionales promedio y puede ser 
considerado como un subsistema operativo de la aplicación. Un PG puede ser Pequeño, 
Medio o Grande, basado en el número estimado de Procesos Funcionales que contiene. 
d) Un Macroproceso (MP) es un conjunto de Procesos Generales promedios y puede ser 
considerado como un subsistema relevante del Sistema de Información general de la 
organización del usuario. Un MP puede ser Pequeño, Medio o Grande, basado en el 
número estimado de Procesos Generales que contiene. 
Cada nivel se construye sobre la base del inferior. Una tabla de referencia apropiada le permite 
al medidor asignar un valor promedio de CFP para ese artículo.  
 
Para realizar una estimación, el medidor (después de haber realizado los pasos preliminares 
del método estándar: definir los límites de las aplicaciones, las capas y el alcance de la 
medición) debe clasificar cada parte de los requisitos reales como pertenecientes a un nive l 
de las categorías propuestas. Una tabla de asignación dará la medida de tamaño relacionada 
de ese requisito. De esta manera, no solo las hojas del árbol de funcionalidad pueden 
cuantificarse directamente, sino también las ramas intermedias. 
Tabla de Referencia:  
La técnica de aproximación COSMIC Temprana y Rápida se basa en la capacidad del Medidor 
para clasificar una parte de los requisitos reales como pertenecientes a una categoría 
funcional particular. Cada parte de los requisitos reales debe clasifica rse, en orden de 
magnitud creciente y número de elementos de composición en uno de los cuatro niveles, como 
un Proceso Funcional, Proceso Típico, Proceso General o Macroproceso. La tabla de 
referencia 6.1 le permite al medidor asignar un valor de CFP para esa parte de los requisitos 
reales (esto se aplica para cada nivel identificado por separado). 
Tipo Nivel Rangos / Equivalencias COSMIC CFP 
min 
más 
probable 
CFP 
max 
Proceso 
funcional 
Pequeño 1 - 5 Movimientos de datos 2.0 3.9 5.0 
Mediano 5 - 8  Movimientos de datos 5.0 6.9 8.0 
Grande 8 - 14 Movimientos de datos 8.0 10.5 14.0 
 Muy 
Grande 
14+ Movimientos de datos 14.0 23.7 30.0 
Proceso 
típico Pequeño CRUD (Procesos pequeños/medianos) 
CRUD + Lista (Proceso pequeño) 15.6 20.4 27.6 
Mediano CRUD (Procesos medianos/grandes) 
CRUD + Lista (Procesos medianos) 27.6 32.3 42.0 
 
2 La definición de un proceso funcional en la técnica E&Q difiere de la definición estándar del método COSMIC. 
En una versión f utura, se adoptará la definición estándar COSMIC. La funcionalidad identificada por las dos 
definiciones pretende ser exactamente la misma.


<!-- pág 11/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 11 
Copyright © 2020 
 
CRUD + List a + Report e (Procesos 
pequeños) 
Grande 
CRUD (Procesos grandes) 
CRUD + List a (Procesos 
medianos/grandes) 
CRUD +  Lista + Report e (Procesos 
medianos.) 
42.0 48.5 63.0 
Proceso 
general 
Pequeño 6 -10 PF’s genéricos 20.0 60.0 110.0 
Mediano 10 - 15 PF’s genéricos 40.0 95.0 160.0 
Grande 15 - 20 PF’s genéricos 60.0 130.0 220.0 
Proceso 
Macro 
Pequeño 2 - 4 PF’s genéricos 120.0 285.0 520.0 
Mediano 4 - 6 PF’s genéricos 240.0 475.0 780.0 
 Grande 6 - 10 PF’s genéricos 360.0 760.0 1,300 
Tabla 6.1 – Valores de estimación para las categorías funcionales de la técnica temprana y rápida. 
 
7. APROXIMACIÓN DE SOFTWARE ICEBERG. 
La aproximación de software iceberg [5] se basa en el estándar ISO/IEC/IEEE 29148: 2018 
[7] en Ingeniería de Requisitos y la analogía de iceberg. En esta analogía (Fig. 7.1), la parte 
visible del iceberg por encima de la línea de flotación (izquierda) corresponde a la descripción 
inicial de los requisitos de software, cuyos requisitos se describen progresivamente con más 
detalles, hasta los detalles finales completamente descritos de estos requisitos de software 
(la visibilidad progresiva de la parte del iceberg que está bajo la línea de flota). 
 
Fig. 7.1. La analogía Software-Iceberg: desde funciones inicialmente visibles (izquierda) a vista completa 
(derecha) [5]. 
En física, existe una relación bien conocida entre la masa de arriba y la masa debajo del agua 
para un iceberg flotante, basada en una serie de mediciones empíricas y observaciones 
científicas. Esta relación es una constante. 
En el desarrollo de software no se conoce una relación constante, pero utilizando 
observaciones empíricas y mediciones de estudios de casos COSMIC, se pueden elaborar 
algunos procedimientos de aproximación para obtener relaciones para contextos locales.  
En todos los proyectos de software, la visibilidad funcional variará a lo largo del ciclo de vida 
del desarrollo y, por lo tanto, la documentación funcional del software en las fases del ciclo de 
vida variará. 
La norma ISO/IEC/IEEE 29148 sobre ingeniería de requisitos presenta una serie de conceptos 
relacionados con las fuentes, los tipos y los niveles de detalle de los requisitos en todo el ciclo 
de vida del sistema y del software. 
El conjunto inicial de requisitos se origina en dos conjuntos de fuentes, las partes interesadas 
del negocio y otras partes interesadas, lo que conduce a los requisitos de los "sistemas". Estas 
fuentes proporcionan los requisitos contextuales del sistema, incluido el propósito del sistema,


<!-- pág 12/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 12 
Copyright © 2020 
 
el alcance del sistema y la descripción general del sistema. A partir de esta informaci ón 
contextual, se identifican los siguientes requisitos: 
• requisitos funcionales del sistema (algunos de los cuales se asignarán al software), 
• requisitos de calidad no funcionales del sistema (algunos de los cuales se asignarán al 
software). 
 
ISO 29148 también señala que, además de las funciones de software identificadas 
explícitamente, puede haber interfaces identificadas, pero aún no especificadas, así como 
requisitos de calidad, aún en un nivel alto. 
En la práctica se pueden observar cuatro niveles de detalle.: 
Level 1. Funciones de negocio. Una lista de las funciones del "sistema", que posiblemente 
incluyen la funcionalidad relacionada con las interfaces con otras aplicaciones de 
software. 
Level 2. Funciones de negocio detalladas. Una lista de funciones de "software": funciones 
de negocio asignadas a procesos funcionales de software, incluidas interfaces a 
otras aplicaciones de software. 
Level 3. Funciones operacionales. Implementación de los requisitos del negocio en 
procesos funcionales de software designados. 
Level 4. Funciones detalladas y funciones de calidad. Procesos funcionales del software 
que están completamente detallados e incluyen todos los requisitos de calidad que 
el software debe cumplir, incluidos los requisitos no funcionales asignados al 
software. 
En [5] los requisitos para el caso de estudio bien documentado del sistema de registro de 
cursos COSMIC se han desglosado en los cuatro niveles de requisitos. Esto condujo a los 
siguientes factores de escala: 
 
Fig. 7.2. Factores de escala en la aproximación Iceberg, derivados de [5]. 
El análisis de un segundo estudio de caso dio resultados similares. Las proporciones tipo 
iceberg se pueden usar como factores de escala en varias fases del ciclo de vida y niveles de 
documentación. 
Por ejemplo, si la medición COSMIC se realiza muy temprano e n el ciclo de vida donde solo 
se identifican las funciones del sistema y se pueden medir con COSMIC, el factor de escala 
para la funcionalidad de nivel 1 se puede usar para aproximar el tamaño funcional esperado 
al final del ciclo de vida de desarrollo de software. 
Por lo tanto, se esperaría razonablemente que 100 CFP en el nivel de las funciones de 
negocios crecieran a 490 CFP una vez que el software esté completamente desarrollado.  
En las primeras etapas del desarrollo de un nuevo software, como a nivel de sistema en ISO-
IEEEE 21948 antes de que se defina formalmente un proyecto, los requisitos probablemente 
solo se conocerán en el esquema más amplio. En esta etapa, es posible determinar un tamaño 
aproximado utilizando la aproximación Iceberg con los tamaños conocidos de otro software


<!-- pág 13/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 13 
Copyright © 2020 
 
existente (preferiblemente de su propio dominio), pero será demasiado pronto para aplicar 
cualquiera de las otras técnicas de tamaño aproximado descritas en este Guía. 
 
8. APROXIMACIÓN DE PUNTOS DE FUNCIÓN EASY (EARLY & 
SPEEDY). 
La técnica aproxima ción EASY (EArly  & SpeedY) proporciona las distribuciones de 
probabilidad más típicas para que el Medidor pueda elegir, y permite mezclar tamaños 
aproximados y tamaños precisos.  
Nota: Los tamaños precisos, es decir, los tamaños medidos de acuerdo con el método de 
medición estándar corresponden a tamaños donde se asigna un valor con una probabilidad 
cercana al 100%. 
Ejemplo: “Este informe tiene 'pro bablemente' 5 movimientos de datos (60%), pero 'podría 
tener' 2 movimientos de datos adicionales (30%), o incluso 4 movimientos de datos 
adicionales (por confirmar) (10%). " El valor aproximado para la función es la suma ponderada 
de todos los valores posibles (donde los pesos son las probabilidades correspondientes). En 
el ejemplo, esto significaría un tamaño aproximado de 5x0.6 + 7x0.3 + 9x0.10 = 6.0 CFP). 
(Todas las probabilidades de opciones para una función deben sumar 100%). 
Tenga en cuenta que el val or más probable no siempre es necesariamente el "medio". 
Depende del medidor asignar las probabilidades a los valores posibles. Esto es diferente de 
cualquier técnica de "promedio" en secciones anteriores, donde los valores promedio o medio 
se toman como "siempre" los valores más probables.  
Tabla 8.1 muestra distribuciones de probabilidad típicas de valores aproximados para casos 
comunes en el dominio de Negocios (PF significa "Proceso Funcional") [4]. 
Clasificación 
del PF 
Nivel de 
especificación 
CFP 
(min) 
CFP CFP 
(max) 
CFP 
Aproximado 
Probabilidad 
PF Pequeño Poco desconocido 2 
(10%) 
3 
(75%) 
5 
(15%) 3.2 >80% 
PF Pequeño Desconocido (Sin 
FUR) 
2 
(15%) 
4 
(50%) 
8 
(35%) 5.1 <50% 
PF Mediano Poco desconocido 5 
(10%) 
7 
(75%) 
10 
(15%) 7.25 >80% 
PF Mediano Desconocido (Sin 
FUR) 
5 
(15%) 
8 
(50%) 
12 
(35%) 8.95 <50% 
PF Grande Poco desconocido 8 
(10%) 
10 
(75%) 
12 
(15%) 10.1 >80% 
PF Grande Desconocido (Sin 
FUR) 
8 
(15%) 
10 
(50%) 
15 
(35%) 11.45 <50% 
PF Complejo Poco desconocido 10 
(10%) 
15 
(75%) 
20 
(15%) 15.25 >80% 
PF Complejo Desconocido (Sin 
FUR) 
10 
(15%) 
18 
(50%) 
30 
(35%) 21 <50% 
Tabla 8.1 - Distribuciones de probabilidad de valores aproximados en el dominio empresarial. [4] . 
Las diferentes opciones de distribuciones d e probabilidad, as í como los valores mínimos y 
máximos de CFP para los diversos casos de procesos funcionales anteriores, conduce a 
diferentes instancias de la técnica de aproximación EASY.


<!-- pág 14/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 14 
Copyright © 2020 
 
9. TAMAÑO APROXIMADO DE CAMBIOS DE FUNCIONALIDAD Y 
ALCANCE NO CONTROLADO. 
9.1 Tamaño aproximado de los cambios de funcionalidad. 
Si hay un catálogo existente de procesos funcionales y sus tamaños (o clasificación de 
tamaños), entonces se puede elegir uno de los dos enfoques siguientes. 
a) Si es posible, basándose en los Requisitos funcionales del usuario para los cambios, 
juzgue qué movimientos de datos de los procesos funcionales relevantes se verán 
afectados y cuente estos movimientos de datos; 
b) De lo contrario, calcule para cada proceso funcional el número o la proporción de 
movimientos de datos que deben cambiarse. Por ejemplo, si un proceso funcional a 
cambiar tiene un tamaño de 12 CFP y se estima que el cambio afecta al 25% de los 
movimientos de datos, entonces el tamaño del cambio es 3 CFP.   
Use estos números o proporciones en lugar de los tamaños totales de los procesos 
funcionales que se van a cambiar para complementar uno de los enfoques de aproximación 
descritos anteriormente. 
Si no hay un catálogo de procesos funcionales existentes, la primera tarea sería identificar los 
procesos funcionales afectados por los requisitos de cambio reales, y luego seguir uno de los 
enfoques aproximados anteriores. 
9.2 Tamaño aproximado y alcance no controlado (scope creep). 
La experiencia muestra que, al principio de la vida de un proyecto de desarrollo de software, 
el tamaño funcional del software tiende a aumentar a medida que el proyecto avanza de los 
requisitos reales resumidos a los requisitos reales detallados, a las especificaciones 
funcionales, etc. Este fenómeno, a menudo denominado "alcance no controlado", puede surgir 
porque: 
• el alcance se extiende más allá de lo planeado originalmente para incluir áreas adicionales 
de funcionalidad; 
• y/o, a medida que los detalles se vuelven más claros, la funcionalidad  requerida resulta 
ser más extensa (por ejemplo, requerir más movimientos de datos por proceso funcional) 
de lo que se había previsto originalmente y/o 
• Los requisitos no funcionales pueden resultar (parcialmente) implementados en el 
software. 
(También puede suceder, por supuesto, que el alcance se reduzca del alcance planificado 
originalmente, por ejemplo, debido a recortes presupuestarios). 
Las técnicas de tamaño aproximado descritas en esta Guía no tienen en cuenta 
explícitamente el alcance no controlado.  Por lo tanto, cuando se utilizan estas técnicas de 
aproximación para el dimensionamiento temprano, el alcance no controlado potencial debe 
considerarse como un factor adicional .  Si se ignora el posible cambio del alcance, existe el 
riesgo de subestimar el tamaño final del software y, por lo tanto, el esfuerzo del proyecto. 
Estimar un alcance no control ado potencial en un Proyecto en particular va más allá del 
alcance de esta Guía. Sin embargo, pude ser útil abordar las siguientes preguntas:


<!-- pág 15/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 15 
Copyright © 2020 
 
• ¿Son los requisitos reales de este proyecto particularmente inciertos desde el principio? 
Si es así, ¿qué corrección (o "contingencia") del tamaño aproximado se debe hacer para 
un posible cambio del alcance? 
• Si el alcance no controlado es endémico dentro de la organización, entonces podemos 
usar mediciones pasadas para ayudar a cuantificar este fenómeno. Por ejemplo, en una 
organización dada y usando un proceso de desarrollo dado para el cual existen muchas 
mediciones, puede ser posible encontrar un patrón recurrente como: “al final de la fase 3, 
los tamaños son típicamente 30% mayores que al final de la fase 1”. 
9.3 Aplicando aproximación en proyectos de mejora. 
A menudo, los proyectos no solo deben crear nuevos procesos funcionales, sino que también 
deben modificar los procesos funcionales existentes. En la práctica, se ha observado el 
siguiente enfoque: 
1. Al medir proyectos, cada proceso funcional se marca como 'Nuevo' o 'Modificado'. 
2. El tamaño promedio de un proceso funcional nuevo y modificado se estableció por 
separado. Los valores promedio obtenidos variaron según el dominio. Pero típicamente, 
el tamaño promedio de un proceso funcional modificado era aproximada mente la mitad 
del tamaño promedio de un nuevo proceso funcional. 
Al aproximar el tamaño de un proyecto en una etapa temprana, los procesos funcionales 
nuevos y modificados deben identificarse, contarse y multiplicarse por sus tamaños promedio 
respectivos.  
10. LISTA DE VERIFICACIÓN. 
Las técnicas de tamaño aproximado deben usarse con cuidado. Se recomienda encarecidamente no 
utilizar ninguna de las técnicas de aproximación descritas en esta Guía como simples "libros de 
recetas". Siempre: 
 Elija una técnica que sea óptima para el propósito de la medición, dado el tiempo disponible 
para la medición y la precisión requerida del tamaño aproximado y la disponibilidad de 
datos para la calibración. Se pueden encontrar otras técnicas en la guía de expertos. [1]. 
 Verifique la técnica de aproximación (comparando mediciones precisas y aproximadas) 
utilizando los requisitos y mediciones locales para garantizar que produzca tamaños 
razonablemente precisos en su entorno local y, si es necesario, calibre la técnica 
localmente antes de usarla para sus propias mediciones reales . Vea la guía de expertos 
para más detalles. [1]. 
 Intente obtener más detalles de los que se dan en los requisitos de un experto en el 
software. 
 Preste especial atención a identificar cualquier proceso funcional grande y a determinar 
buenos factores de escala para ellos: pueden hacer una gran contribución al tamaño total 
a pesar de que son pocos en número. 
 Cualquiera sea el propósito de usar una técnica de aproximación, cada vez que haya más 
información disponible que permita un dimensionamiento más certero y/o preciso, refine y 
actualice la medición. Esto es importante cuando se utilizan los resultados como entrada 
para la estimación. 
 Examine los requisitos para comprender los niveles de documentación, la integridad y la 
calidad de los requis itos antes de comenzar a utilizar una técnica. Consulte la guía de 
expertos para obtener información detallada sobre los niveles de documentación. [1]. 
 Considere si se debe hacer una contingencia para el " alcance no controlado " y por la 
contribución que la incorporación de requisitos no funcionales puede conducir a.


<!-- pág 16/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 16 
Copyright © 2020 
 
 Estime e informe la incertidumbre más o menos sobre el tamaño aproximado, mencionando 
cualquier contingencia que se haya hecho para el alcance del desplazamiento; estimar la 
incertidumbre sobre un tamaño aproximado es especialmente importante en situaciones 
contractuales. 
 Clasificar la calidad de las diversas partes de los requisitos reales mediante el esquema de 
la "Guía para garantizar la precisión de las mediciones" [6] puede ayudar a determinar la 
precisión de una medición de tamaño aproximado en situaciones contractuales. 
a) cuando se asignan suficientes recursos de medición y tiempo calendario para 
obtener resultados de medición precisos, se debe usar el estándar COSMIC. 
b) cuando no hay suficientes recursos de medición disponibles y cuando hay 
limitaciones de tiempo importantes, se podría utilizar un método aproximado de la 
guía de expertos, siempre que se deba respaldar un rango de resultados de 
medición (por ejemplo, + o -%) e identificarlo e indicarlo claramente en el Informes 
de medición. 
11. GLOSARIO DE TÉRMINOS 
Los términos en este Glosario son específicos de esta Guía. Para otros términos COSMIC, 
vea el Glosario principal en el Manual de Medición COSMIC. 
Certeza.   
La proximidad del acuerdo entre un valor de cantidad medida y un valor de cantidad real de 
una medida [Guía ISO 99] [8]. 
NOTA 1: El concepto "certeza de medición" no es una cantidad y no se le da un valor 
numérico de cantidad. Se dice que una medición es más precisa cuando ofrece un 
error de medición menor.  
NOTA 2: El término “certeza de medición” no debe usarse para la exactitud de la 
medición y el término “precisión de medición” no debe de usarse para “certeza de 
medición”, que, sin embargo, está relacionado con estos dos conceptos. 
NOTA 3: “Certeza de medición” a veces se entiende como una proximidad de 
acuerdo entre los valores de cantidad medidos que se atribuyen a la medida.  
Tamaño Aproximado.   
1. Medición aproximada de un tamaño.  
2. Medición de un tamaño por una técnica de aproximación. 
Calibración 
Determinar los factores de escala o los valores de clasificación que se utilizarán en el entorno 
local en el que se usa la técnica de aproximación en lugar de los factores de escala o los 
valores de clasificación publicados en documentos de referencia como esta Guía, con el 
objetivo de obtener el resultado más preciso posible de la aplicación del enfoque de 
aproximación. 
Clasificación 
Asignación de una parte de los requisitos reales a una clase definida (o pieza de referencia) 
de requisitos cuyo tamaño ha sido calibrado en CFP. 
Localización (ver también calibración) 
Calibrar los factores de escala o los valores de clasificación a un entorno que sea 
representativo del entorno en el que se utilizará la técnica de aproximación. 
Precisión.   
El grado de exactitud o discriminación con el que se establece una cantidad (ISO / IEC 24765: 
2010)


<!-- pág 17/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 17 
Copyright © 2020 
 
Ejemplo: una precisión de 2 decimales versus una precisión de 5 decimales. 
 
Factor de escala.    
Una constante que se utiliza para convertir un tamaño medido bajo un conjunto de condiciones 
(por ejemplo, un nivel de documentación de algunos requisitos reales) a un tamaño medido 
bajo otro conjunto de condiciones (por ejemplo, otro nivel de documentación de los mismos 
requisitos).


<!-- pág 18/18 -->

Medición Temprana del Software con COSMIC: Guía de Practicantes 18 
Copyright © 2020 
 
12. REFERENCES. 
[1] Vogelezang,  Grupo COSMIC, “ Early Software Sizing with COSMIC: Experts Guidelines’ 
https://cosmic-sizing.org/publications/guideline-for-early-or-rapid-cosmic-fsm/ 
[2] F.W. Vogelezang and T.G. Prins, "Approximate size measurement with the COSMIC meth od: 
Factors of influence", Foro Europeo de Medición de Software (SMEF 2007), Roma, Italia, 2007 
[3] L. Santillo, "Early & Quick COSMIC -FFP Analysis Using the Analytic Hierarc hy Process." 10th 
Taller Internacional de Medición de Software, Notas de Lectura en Ciencias de la Computación  
2006, (pp. 147-160), Berlin (Alemania), 2006. 
[4] L. Santillo, "EASY Function Points – ‘SMART’ Approximation Technique for the IFPUG and 
COSMIC Methods", 22ª Conferencia IWSM-MENSURA, Assisi (Italia), Noviembre 2012. 
[5] A. Abran and S. Vedadi, “Development of COSMIC Scaling Factors using Classification of 
Functional Requirements”, 29ª conferencia IWSM-MENSURA, Oct. 7-9, 2019, Haarlem, Holanda, 
CEUR Proceedings Vol-2476, 2019, pp. 31-46. 
[6] COSMIC Group, Guide for assuring the accuracy of measurements. 
[7] ISO 29148 Ingeniería de Sistemas y Software -Procesos del ciclo de vida - Ingeniería de 
Requisitos, Organización Internacionales de Estandarización (ISO), Ginebra, 2011. 
[8]  ISO Guide 99: Vocabulario internacional de términos básicos y generales en metrología (VIM), 
Organización Internacional de Normalización – ISO, 2019.