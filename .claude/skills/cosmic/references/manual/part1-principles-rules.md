<!-- Extraído de 1837f91e-Part1MMRulesv5.0bENESPA_OL1.pdf (24 págs) por pypdf — 2026-06-03T03:35:05Z. Fuente oficial COSMIC v5.0 / ISO 19761. -->
# COSMIC v5.0 — Parte 1: Principios, Definiciones y Reglas



<!-- pág 1/24 -->

Manual de medición DE COSMIC 
para ISO 19761 
 
Parte 1: 
Principios, Definiciones y Reglas 
 
Versión 5.0 
31 de marzo de 2020


<!-- pág 2/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 2 
 
 
Prólogo 
El s oftware es un componente importante de muchos presupuestos corporativos. Las 
organizaciones reconocen la importancia de estimar proyectos de software, controlar los 
gastos de software y analizar el rendimiento de los presupuestos asignados al desarrollo y 
mantenimiento de software. Para ello, se necesitan medidas y modelos que usen estas 
medidas, incluida la medición del tamaño funcional del software para la estimación de  
software, planificación y benchmarking. 
La versión 5.0 del Manual de Medición COSMIC para la ISO 19761 consta de tres Partes: 
Parte 1: Principios, Definiciones y Reglas 
Parte 2: Directrices 
Parte 3: Ejemplos 
El manual de medición de COSMIC se basa en la norma ISO-IEC 19761:2011, reconfirmada 
en 2019. 
Esta versión 5.0 del Manual de Medición DE COSMIC sustituye a la versión 4.0.2: acota la 
versión 4.0.2 sin modificar su contenido en términos de definiciones de medición, reglas y 
orientación. 
Puede encontrar una versión de dominio público del Manual de Medición de COSMIC y otros 
informes técnicos, incluidas las traducciones a otros idiomas, en la base de conocimientos de  
www.cosmic-sizing.org. 
 
Editores: 
Alain Abran, Escuela de Tecnología Avanzada - Universidad de Quebec (Canadá), 
Peter Fagg, Pentad (Reino Unido), 
Arlan Lestherhuis (Países Bajos). 
Otros miembros del Comité de Prácticas de Medición DE COSMIC: 
Diana Baklizky, (Brasil), 
Jean-Marc Desharnais, Ecole de technologie supérieure – Universidad de Quebec (Canadá), 
Cigdem Gencel, Universidad Libre de Bozen-Bolzano (Italia), 
Dylan Ren, Measures Technology LLC (China),


<!-- pág 3/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 3 
 
 
Bruce Reynolds, Telecote Research (EE.UU.), 
Hassan Soubra, Universidad Alemana en El Cairo (Egipto), 
Sylvie Trudel, Universidad de Quebec en Montreal - UQAM (Canadá), 
Frank Vogeleliang, Países Bajos. 
Francisco Valdés Souto, SPINGERE, UNAM, Mexico 
 
 
 
Copyright 2020. Todos los derechos reservados. El Common Software Measurement International Consortium 
(COSMIC).  Se concede permiso para copiar todo o parte de este material siempre que las copias no se hagan o 
distribuyan con fines comerciales y que se c iten el título de la publicación, su número de versión y su fecha y se 
notifique que la copia es por permiso del Common Software Measurement International Consortium (COSMIC). 
Para copiar de lo contrario se requiere un permiso específico.


<!-- pág 4/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 4 
 
 
Tabla de contenidos 
 
1. INTRODUCCION. ................................ ................................ ................................ ............... 5 
1.1 Propósito. ................................ ................................ ................................ ...................... 5 
1.2Información general. ................................ ................................ ................................ .......... 5 
1.3 Los  modelos y  principios del  método COSMIC . ................................ ......................... 5 
1.4 Definiciones. ................................ ................................ ................................ .................. 7 
2. PROCESO DE MEDICIÓN COSMIC. ................................ ................................ ............... 12 
3. FASE DE ESTRATEGIA DE MEDICIÓN................................. ................................ ......... 13 
3.1 Derivar la estrategia de medición del modelo contexto de software. ............................ 13 
3.2 Determinación de la finalidad y el alcance del FSM. ................................ .................... 14 
3.3 Identificación de los FUR. ................................ ................................ ...............................  15 
3.4 Identificación de las capas. ................................ ................................ ............................. 15 
3.4.1 El alcance del FSM y las capas ................................ ................................ .......... 15 
3.4.2 Características de las capas ................................ ................................ ............... 15 
3.5  Identificación de los usuarios funcionales. ................................ ................................ .. 16 
3.6 Identificación de los límites del software ................................ ................................ ......... 16 
4. FASE DE MAPEO. ................................ ................................ ................................ ........... 16 
4.1   General – Asignación de la FUR al modelo genérico de software. ............................. 16 
4.2 Identificación de procesos funcionales. ................................ ................................ ....... 17 
4.3 Identificación de grupos de  datos. ................................ ................................ .............. 18 
4.4 Identificación de movimientos de datos. ................................ ................................ ...... 19 
4.5 Clasificación de  los movimientos de datos. ................................ ................................ . 20 
5. FASE DE MEDICIÓN. ................................ ................................ ................................ ...... 21 
5.1 Proceso de fase de medición. ................................ ................................ ..................... 21 
5.2 Cálculo del tamaño funcional. ................................ ................................ ...................... 22 
6. INFORMES DE MEDICIÓN. ................................ ................................ ............................. 23 
REFERENCIAS. ................................ ................................ ................................ ................... 24


<!-- pág 5/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 5 
 
 
1. INTRODUCCION. 
1.1 Propósito. 
El propósito de este documento es indicar los Principios, Definiciones y Reglas del método de 
Medición del Tamaño Funcional COSMIC (el ‘ Método COSMIC '),así como el proceso de 
medición COSMIC. 
Esta Parte 1 del documento del Manual de Medición DE COSMIC contiene únicamente 
material de refe rencia, es decir,  qué hacer, como se describe en ISO 19761. Para obtener 
orientación elaborada por el Grupo COSMIC sobre cómo aplicar COSMIC a  diferentes 
situaciones, consulte  la Parte 2, y para  ejemplos, consulte la Parte 3. El Grupo COSMIC 
también ha publicado documentos adicionales para ilustrar su uso en diversos contextos 
(Agile, Aplicaciones Empresariales, Tiempo Real, etc.) y tecnologías (SOA, Móvil, etc.) 
1.2Información general.  
El método COSMIC consiste en aplicar un conjunto de modelos, principios, reglas y procesos 
para medir los Requisitos Funcionales del Usuario (o 'FUR') de una determinada pieza  de 
‘software.   
El resultado es un 'valor de una cantidad' numérico (según lo definido por ISO) que representa 
el tamaño funcional de la pieza de software según el método  COSMIC. El valor numérico es 
en una escala de relación : por lo tanto, las operaciones matemáticas válidas se pueden 
realizar utilizando los valores. 
El método COSMIC adopta la definición ISO de Requisitos Funcionales del Usuario  (FUR).. 
1.3 Los modelos y  principios del  método COSMIC . 
El método COSMIC se basa en 17principios de ingeniería de software categorizados en dos 
modelos: 
El Modelo de Contexto de Software COSMIC:  contiene los principios que se refieren a la 
identificación de la naturaleza y estructura del Software que se medirá según lo requerido por 
el método COSMIC, dando lugar a la identificación de su FUR. 
El modelo de software genérico:  contiene los principales que se aplicarán al FUR con el fin 
de extraer y medir los elementos que contribuyen al tamaño funcional utilizando el método 
COSMIC.


<!-- pág 6/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 6 
 
 
PRINCIPIOS - El modelo de contexto de software COSMIC.   
1. Una aplicación de software normalmente se estructura en capas. 
2. Una capa puede contener una o más piezas de software separadas. 
3. Una pieza de software se describe mediante sus Requisitos Funcionales del Usuario 
(FUR). 
4. El FUR se expresa en un nivel de granularidad que expone sus procesos funcionales. 
5. Una pieza de software ofrece funcionalidad a sus usuarios funcionales como se identifica 
en el FUR. 
6. Una pieza de s oftware que se debe medir se define por el  alcance de la medición de 
tamaño funcional (FSM), que se limita totalmente dentro de una sola capa.   
7. El alcance del FSM define los procesos funcionales a medir, y depende del propósito  de 
la medición. 
El siguiente modelo de software genérico identifica los componentes de la funcionalidad que 
aportan el tamaño funcional medido por el método COSMIC. 
PRINCIPIOS - El modelo de software genérico COSMIC. 
1. Una pieza de software interactúa con sus usuarios funcionales a través de un límite con 
almacenamiento persistente dentro de este límite. 
2. Un proceso funcional consiste en subprocesos denominados movimientos de datos. 
3. Hay cuatro subtipos de movimiento de datos:  Entrada, Salida, Escritura y Lectura. Un 
subtipo de movimiento de datos incluye cualquier manipulación de datos asociada. 
4. Un movimiento de datos mueve un único grupo de datos. 
5. Un grupo de datos consta de un conjunto único de atributos de datos que describen un 
único objeto de interés. 
6. Cada pro ceso funcional es iniciado por  un evento desencadenante , detectada por un 
usuario funcional y que a su vez inicia un movimiento de datos llamado Entrada 
Desencadenante. 
7. El tamaño funcional se basa en los tipos de los movimientos utilizados para la medición, 
no en el número de ocurrencias.   
8. El tamaño de un proceso funcional es igual al número de sus movimientos de datos donde 
un movimiento de datos tiene un tamaño de 1 punto de función COSMIC (CFP). 
9. El tamaño de una pieza de software es la suma de los tamaños de los procesos funcionales 
dentro del alcance del FUR.


<!-- pág 7/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 7 
 
 
10. El tamaño de una pieza de software modificada es la suma de los tamaños de los procesos 
funcionales modificados, agregados y eliminados. 
NOTA:  Los principios se escriben utilizando la terminología del método COSMIC. 
1.4 Definiciones. 
En esta subsección: 
• las definiciones de los documentos ISO se reproducen "tal cual", pero sin las NOTAS  
ISO que se han transferido al cuerpo principal del texto; 
• textos subrayados se refieren a los términos definidos en esta subsección. 
 
aplicación. 
software para la recopilación, el almacenamiento, el procesamiento y la presentación de datos a través 
de un ordenador. [Adaptado de ISO 24570] 
Componente funcional base. (BFC). 
unidad elemental de Requisitos Funcionales del Usuario definida y utilizada por un método FSM para 
fines de medición. [ISO 14143-1] 
Tipo de componente funcional base. Tipo BFC. 
categoría definida de Componente funcional base. [ISO 14143-1] 
Frontera. 
interfaz conceptual entre el software que se está midiendo y sus usuarios funcionales. 
Componente. 
cualquier parte de un sistema de software que sea independiente por razones de la arquitectura de 
software, y que se especificó, diseñó o desarrolló por separado. 
 
comando de control. 
comando que permite a los usuarios funcionales humanos controlar su uso del software, pero que no 
implica ningún movimiento de datos sobre un objeto de interés de los FUR del software que se está 
midiendo. 
Unidad de medida COSMIC. 
1 CFP (Punto de función COSMIC), que se define como el tamaño de un movimiento de datos. 
atributo de datos.


<!-- pág 8/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 8 
 
 
paquete de información más pequeño, dentro de un grupo de datos identificado, que lleva un significado 
desde la perspectiva de los Requisitos Funcionales del Usuario del software. [ISO 19761] 
grupo de datos. 
tipo de grupo de datos. 
conjunto de atributos de datos distintos, no vacíos, no ordenados y no redundantes donde cada atributo 
de datos incluido describe un aspecto complementario del mismo objeto de interés. [ISO 19761] 
manipulación de datos. 
cualquier tratamiento de los datos que no sea un movimiento de los datos dentro o fuera de un proceso 
funcional, o entre un proceso funcional y el almacenamiento persistente. [ISO 19761] 
movimiento de datos. 
tipo de movimiento de datos. 
Componente funcional base que mueve un único grupo de datos. [ISO 19761] 
E - Abreviatura para Tipo de entrada.   
Entrada. 
Tipo de entrada. 
movimiento de datos  que mueve un grupo de datos de un usuario funcional a través de la frontera 
hacia el proceso funcional donde se requiere. [ISO 19761] 
mensaje de error/confirmación. 
Salida emitida por un proceso funcional a un usuario humano que confirma sólo que se han 
aceptado los datos introducidos, o solo que hay un error en los datos introducidos. 
Salida. 
Tipo de salida. 
movimiento de datos que mueve un grupo de datos de un proceso funcional a través de la frontera al 
usuario funcional que lo requiere. [ISO 19761] 
Evento. 
algo que sucede. 
proceso funcional. 
tipo de proceso funcional. 
componente elemental de un conjunto de  requisitos funcionales del usuario, que comprende un 
conjunto único, cohesivo e independiente ejecutable de movimientos de datos. [ISO 19761] 
nivel de granularidad de proceso funcional  
nivel de granularidad de la descripción de una pieza de software en la que


<!-- pág 9/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 9 
 
 
• el usuario funcional ( -tipos) son humanos individuales o dispositivos de ingeniería o piezas de 
software (y no ningún grupo de estos) y 
• evento único (tipos) que la pieza de software debe responder  a (y no cualquier nivel de 
granularidad en el que se definen grupos de eventos).   
tamaño funcional. 
tamaño del software derivado mediante la cuantificación de los Requisitos Funcionales del Usuario . 
[14143-1] 
Medición del tamaño funcional 
FSM. 
proceso de medición del tamaño funcional. [14143-1] 
Método de medición de tamaño funcional.   
Método FSM 
implementación específica del FSM definida por un conjunto de normas, que se ajusta a las 
características obligatorias de ISO/IEC 14143-1:2007. [14143-1] 
usuario funcional. 
remitente y/o destinatario previsto de datos en los Requisitos funcionales del usuario de una pieza de 
software. [ISO 19761] 
Requisitos funcionales del usuario. 
subconjunto de los requisitos del usuario que describan lo que el software debe hacer, en térmi nos de 
tareas y servicios. [ISO 14143-1] 
entrada.   
datos movidos por todas las Entradas de un proceso funcional determinado. 
Capa. 
partición resultante de la división funcional de un sistema de software. [ISO 19761] 
nivel de descomposición. 
un nivel  resultante de dividir una pieza de software en componentes (denominados 'Nivel 1', por 
ejemplo), luego dividir los componentes en subcomponentes ('Nivel 2'), luego dividir subcomponentes 
en subcomponentes (Nivel 3'), etc.   
nivel de granularidad. 
cualquier nivel de expansión de la descripción de cualquier parte de una sola pieza de software (por 
ejemplo, una declaración de sus requisitos, o una descripción de la estructura de la pieza de software) 
de tal forma que, en cada mayor nivel de expansión,  la descripción de la funcionalidad de la pieza de 
software está en un nivel de detalle mayor y uniforme. 
método de medición


<!-- pág 10/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 10 
 
 
secuencia lógica de operaciones, describir genéricamente, utilizada en el rendimiento de las 
mediciones. [Guía ISO 99] 
procedimiento de medición. 
conjunto de operaciones, descrito específicamente, utilizado en el rendimiento de mediciones 
particulares de acuerdo con un método determinado. [Guía ISO 99] 
proceso de medición. 
proceso de establecimiento, planificación, realización y evalu ación de la medición del software dentro 
de un proyecto global o estructura de medición organizativa. [ISO 19761 - adaptado de ISO 15939] 
patrones de medición (estrategia). 
plantilla estándar que se puede aplicar al medir una pieza de software de un dominio funcional de 
software determinado, que define los tipos de usuario funcional que puede interactuar con el software, 
el nivel de descomposición del software y los tipos de movimientos de datos que el software puede 
manejar. 
modelo.   
descripción o analogía utilizada para ayudar a visualizar un concepto que no se puede observar 
directamente. 
 
OOI - Abreviatura de objeto de interés 
objeto de interés. 
Tipo de objeto de interés 
 
cualquier "cosa" que se identifique desde el punto de vista de los Requisitos Funcionales del Usuario 
sobre los cuales se requiere el software para procesar y o almacenar datos. [ISO 19761] 
Requisitos no funcionales (de software). 
NFR. 
un requisito para la parte de software de un sistema de hardware / software o producto de software, 
incluyendo cómo se debe desarrollar y mantener, y cómo debe funcionar en funcionamiento, 
excepto un requisito funcional del usuario para el software. 
salidas.   
datos movidos por todas las salidas de un proceso funcional determinado. 
software semejante. 
pieza de software que residen en la misma capa que, e intercambia datos con, otra pieza de software.  
[ISO 19761] 
almacenamiento persistente.


<!-- pág 11/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 11 
 
 
almacenamiento que permite a un proceso funcional almacenar datos más allá de la vida  útil del 
proceso funcional y/o que permite a un proceso funcional recuperar datos almacenados por otro 
proceso funcional, o almacenados por una aparición anterior del mis mo proceso funcional, o   
almacenados por algún otro proceso. [ISO 19761] 
propósito de medición. 
declaración que define por qué se está realizando una medición y para qué se utilizará el resultado.  
R – Abreviatura de tipo de lectura. 
Leer. 
Tipo de lectura. 
movimiento de datos  que mueve un grupo de datos del almacenamiento persistente al alcance del 
proceso funcional que lo requiere. [ISO 19761] 
Alcance. 
alcance del FSM. 
conjunto de Requisitos de usuario funcionales que se incluirán en una instancia de medición de tamaño 
funcional específica. [ISO 19761] 
Software 
conjunto de instrucciones informáticas, datos, procedimientos y tal vez documentación que funcione en 
su conjunto, para cumplir un conjunto específico de propósitos, todos los cuales se pueden describir 
desde una perspectiva funcional a través de un conjunto finito de Requisitos Funcionales del Usuario, 
requisitos técnicos y de calidad. 
sistema de software.   
sistema que consiste únicamente en software. 
tipo de subproceso.   
parte de un proceso funcional que mueve datos (al software de un usuario funcional o fuera del 
software a un usuario funcional, o hacia o desde almacenamiento persistente) o que manipula los 
datos.   
sistema.   
combinación de hardware, software y procedimientos manuales organizados para lograr los propósitos 
indicados. [adaptado de ISO 15288] 
Entrada desencadenante 
el movimiento de datos de entrada de un proceso funcional que mueve un grupo de datos generado 
por un usuario funcional que el proceso funcional necesita para iniciar el procesamiento. 
Evento desencadenante


<!-- pág 12/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 12 
 
 
(algo que sucede) que hace que un usuario funcional de la pieza de software inicie ('disparador') uno 
o más procesos funcionales. [ISO 19761] 
unidad de medida.   
cantidad particular, definida y adoptada por convenio, con la que se comparan otras cantidades del 
mismo tipo para expresar sus magnitudes con respecto a esa cantidad. [Guía ISO 99] 
Usuario 
cualquier persona o cosa que se comunique o interactúe con el software en cualquier momento. [ISO 
19761] 
valor (de una cantidad) 
magnitud de una cantidad determinada, generalmente expresada como una unidad de medida 
multiplicada por un número. 
W - Abreviatura para tipo de escritura. 
Escritura 
movimiento de datos que mueve un grupo de datos del almacenamiento persistente dentro alcance 
al proceso funcional que lo requiere. [ISO 19761] 
X – Abreviatura para Tipo de salida. 
Consulte Salida. 
2. PROCESO DE MEDICIÓN COSMIC. 
El proceso de medición COSMIC consta de tres fases – ver Figura 2.1: 
• la Fase de Estrategia de medición, en la que se definen el propósito y el alcance del FSM. 
A continuación, se aplica el modelo de contexto de software para que el software que se 
va a medir y la medición requerida se definan inequívocamente– consulte la Sección 3. 
• la Fase de Representación en la que el Modelo de Software Genérico se aplica al FUR del 
software que se va a medir para producir el modelo COSMIC del software que se puede 
medir – ver Sección 4. 
• la Fase de Medición, en la que se asignan tamaños reales - ver Sección 5. 
Las reglas sobre cómo deben registrarse las mediciones se indican en la Sección 6. 
La relación de las tres fases del método COSMIC se muestra en la Figura 2.1.


<!-- pág 13/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 13 
 
 
 
Figura 2.1 – El proceso de medición del método COSMIC. 
3. FASE DE ESTRATEGIA DE MEDICIÓN. 
3.1 Derivar la estrategia de medición del modelo contexto de software. 
En esta sección se describen los parámetros clave que deben tenerse en cuenta en la  fase 
de estrategia de medición antes de empezar a medir. Las subsecciones dan las reglas para 
ayudar al medidor a través del proceso de determinación de una estrategia de medición, como 
se muestra en Figure 3.1.


<!-- pág 14/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 14 
 
 
 
Figura 3.1 - El proceso de determinación de una estrategia de medición. 
REGLA 1:  Actividades de medición. 
La determinación del tamaño funcional de COSMIC implicará todas las actividades y reglas 
descritas en las secciones  3.2 a 3.6. 
3.2 Determinación de la finalidad y el alcance del FSM. 
REGLA 2:  Propósito y Alcance. 
El propósito y el alcance del FSM se determinarán antes de que se presente un ejercicio de 
medición determinado. 
NOTA: Una vez que se ha determinado el propósito del FSM, el proceso de determinar el 
alcance del FSM, los usuarios funcionales, las capas y los límites puede  requerir algunas 
iteraciones.


<!-- pág 15/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 15 
 
 
 3.3 Identificación de los FUR. 
REGLA 3:  Identificación de los FUR. 
Los FUR identificados para estar dentro del ámbito de aplicación del FSM se utilizará como 
fuente exclusiva a partir de la cual se medirá el tamaño funcional del software. 
 
NOTA: El término 'FUR' se refiere a los requisitos funcionales del usuario que están 
completamente definidos para que sea posible una medición  del tamaño funcional DE 
COSMIC. 
 
  
 3.4 Identificación de las capas. 
3.4.1 El alcance del FSM y las capas 
El software puede tener componentes de su funcionalidad que existen en diferentes capas del 
entorno operativo del software. 
REGLA 4: Si es necesario para el ejercicio  de medición, se identificará cada capa de este 
tipo. 
REGLA 5: - Un solo alcance de software a  medir no tendrá su alcance definido para 
extenderse a más de una capa. 
NOTA 1: FUR puede indicar explícitamente, puede implicar, o la medida puede inferir, que el 
FUR se aplica al software en diferentes capas o a diferentes partes cuyo tamaño debe medirse 
por separado. Alternativamente, el analista de medición puede enfrentarse al tamañ o del 
software existente que parece estar en diferentes capas o a consistir en elementos del mismo 
nivel separados. En ambos casos, se necesita orientación para ayudar a decidir si el FUR del 
software comprende una o más capas o elementos del mismo nivel. 
NOTA 2: La identificación de capas es una actividad iterativa. La identificación exacta de las 
capas se puede refinar a medida que avanza la actividad de la planificación. 
3.4.2 Características de las capas 
REGLA 6:  Características de las capas.


<!-- pág 16/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 16 
 
 
Las capas  identificadas en el ámbito de aplicación del FSM tendrán las siguientes 
características: 
a) El software de cada capa proporcionará funcionalidad a sus usuarios funcionales. 
b) El software en una capa subordinada proporcionará servicios funcionales al software 
en una capa utilizando sus servicios. 
c) El software que comparte datos con otro software no se considerará en diferentes 
capas si interpretan de forma idéntica los atributos de datos que comparten. 
3.5  Identificación de los usuarios funcionales. 
REGLA 7:  Usuarios funcionales. 
Se identificarán todos  los usuarios funcionales que envíen información , o reciban información de 
procesos funcionales en el FUR del software dentro del ámbito de la medición.  
NOTA 1: Esta regla anterior corrige una omisión en ISO 19761. Se está preparando una modificación 
de la norma. 
NOTA 2: Como el  almacenamiento persistente se encuentra dentro de la frontera del software , no se 
considera un usuario funcional del software que se está midiendo. 
 3.6 Identificación de los límites del software 
REGLA – Identificación de la frontera. 
REGLA 8: Se identificará la frontera de cada pieza de software dentro de cada capa y en el 
ámbito del FSM.   
REGLA 9:  Una vez identificad as las fronteras , cada FUR dentro del ámbito del FSM se 
asignará a una pieza de software. 
4. FASE DE MAPEO. 
4.1   General – Asignación de la FUR al modelo genérico de software. 
La Figura 4.1 muestra los pasos del proceso para asignar el FUR como en los artefactos de 
software disponibles a la forma requerida por el modelo de software genérico COSMIC.


<!-- pág 17/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 17 
 
 
 
Figura 4.1 – Método general de la fase de mapeo COSMIC. 
4.2 Identificación de procesos funcionales. 
REGLA 10:  Identificación de procesos funcionales. 
Cada proceso funcional identificado en el ámbito de aplicación del FSM deberá: 
a) derivan de al menos un FUR identificable, 
b) iniciarse mediante un movimiento de datos de Entrada  de un usuario funcional 
informando al proceso funcional de que ha detectado un evento desencadenante, 
c) comprenden al menos dos movimientos de datos siempre una entrada más una salida 
o una escritura. 
d) pertenece a una, y sólo una capa


<!-- pág 18/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 18 
 
 
e) ser completado cuando se requiere un punto de sincronización asín crona para ser 
alcanzado de acuerdo con su FUR. 
NOTA 1: el Grupo COSMIC ha aclarado posteriormente la su cláusula e) anterior como el 
equivalente de la siguiente declaración: «el  conjunto de todos los movimientos de datos 
necesarios para cumplir su FUR para todas las    posibles respuestas a su entrada 
desencadenante». 
NOTA 2:   El modelo de software genérico es un modelo  lógico. Una ocurrencia de  
proceso funcional puede comenzar a procesarse antes de que se hayan introducido los 
datos, por ejemplo, cuando un usuario humano hace clic en un menú para mostrar un a 
pantalla en blanco para la entrada de datos. 
NOTA 3: En un conjunto  de FUR, cada evento que hace que un usuario funcional activ a 
un proceso funcional 
- no se puede subdividir para ese conjunto de FUR, 
- ha sucedido o no ha sucedido. 
4.3 Identificación de grupos de datos. 
REGLA 11:  Identificación de grupos de datos. 
Cada grupo de datos identificado en el ámbito de aplicación del FSM deberá: 
a) ser único y distinguible a través de su colección única de atributos de datos, 
b) ser directamente relacionado con un objeto de interés descrito en el FUR del software. 
NOTA 1: Un objeto de interés puede  ser cualquier cosa  física, así como cualquier cosa 
conceptual o parte de una cosa conceptual en el mundo de un usuario funcional. 
NOTA 2: Los ejemplos de "cosa" incluyen, pero no se limitan a, aplicaciones de software, 
seres humanos, sensores u otro hardware. 
NOTA 3: El término objeto de interés se utiliza con el  fin de evitar términos relacionados con 
métodos de ingeniería de software específicos. El término no implica objetos en el sentido 
utilizado en los métodos orientados a objetos. Del mismo modo, se evita la palabra Entidad 
debido a su uso en modelado de datos. 
NOTA 4: Las constantes o variables que son internas al proceso funcional, o resultados 
intermedios en un cálculo, o datos almacenados por un proceso funcional que resulta sólo 
forman la implementación, en lugar de la FUR, no serán grupos de datos.


<!-- pág 19/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 19 
 
 
4.4 Identificación de movimientos de datos. 
Este paso consiste en identificar los movimientos de datos (Entrada, Sali da, Le ctura y 
Escritura) de cada proceso funcional. La Figura 4.2 ilustra la relación general entre los cuatro 
tipos de movimiento de datos, el proceso funcional al que pertenecen y la frontera del software 
medido. 
REGLA 12:  Identificación de movimientos de datos. 
Cada proceso funcional identificado en el punto 4.2 se  compondrá de sus movimientos de 
datos. 
NOTA: El método COSMIC define un tipo de movimiento de datos como BFC. 
 
Figura 4.2 – Los cuatro tipos de movimiento de datos y su relación con un proceso funcional. 
REGLA 13:  Proceso funcional – Entrada única. 
Para cualquier proceso funcional, se identificará un único movimiento de datos de entrada y 
se contará para la entrada de todos los datos que describan un único objeto de interés que la 
FUR requiera introducir, a menos que la FUR exija explícitamente que se introduzcan datos 
que describan el mismo objeto de interés en más de una vez en el mismo proceso funcional. 
REGLA 14:  Proceso funcional – Salida única, Lectura o escritura. 
Del mismo modo, se identificará un único movimiento de datos Salida, Lectura o Escritura 
para el movimiento de todos los datos que describan un único objeto de interés que el FUR


<!-- pág 20/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 20 
 
 
requiere de ese tipo (por ejemplo, Salida, Lectura o Escritura, respectivamente), a menos que 
el FUR requiera explícitamente que los datos que describan el mismo objeto de interés se 
muevan más de una vez en el mismo proceso funcional por un movimiento de datos del mismo 
tipo (por ejemplo, Salida, Lectura o Escritura, respectivamente). 
REGLA 15:  Proceso funcional – Ocurrencias. 
Si un movimiento de datos de un tipo determinado ( Entrada, Salida, Lectura o Escritura ) se 
produce varias veces con valores de datos diferentes cuando se ha ejecutado un proceso 
funcional, solo se identificará y contará un movimiento de datos de ese tipo en ese proceso 
funcional. 
4.5 Clasificación de  los movimientos de datos. 
REGLA 16:  Entrada. 
Una Entrada deberá: 
a) recibe un único grupo de datos que se origina en el lado de la frontera del usuario 
funcional 
b) incluye todas las manipulaciones de formato y presentación necesarias junto con todas 
las validaciones asociadas de los atributos de datos introducidos, en la medida en que 
estas manipulaciones de datos no implican otro tipo de movimiento de datos. 
NOTA: Una entrada representa todas las manipulaciones que podrían ser necesarias 
para validar algunos códigos introducidos u obtener algunas descripciones asociadas. 
Sin embargo, si se requiere una de las lectu ras más como parte del proceso de 
validación, se identifican y se cuentan como movimientos de datos de lectura 
independientes. 
c) incluye cualquier 'solicitud para recibir la funcionalidad de datos de entrada ‘, donde no 
es necesario especificar qué datos deben introducirse. 
REGLA 17:  Salida 
Una salida deberá: 
a) enviar atributos de datos de un único grupo de datos hacia el usuario funcional a través 
de la frontera, 
b) tiene en cuenta todas las manipulaciones de presentación y formato de datos 
requeridas, incluido el procesamiento  necesario para enviar los atributos de datos al


<!-- pág 21/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 21 
 
 
usuario funcional, en la medida en que estas manipulaciones no impliquen otro tipo de 
movimiento de datos. 
REGLA 18:  Lectura 
Una lectura deberá: 
a) Leer un único grupo de datos del almacenamiento persistente. 
b) incluye todo el procesamiento lógico y  la necesidad de cálculo matemático para leer 
los datos, en la medida en que  estas manipulaciones no implican otro tipo de 
movimiento de datos, 
c) incluye cualquier funcionalidad de solicitar lectura. 
REGLA 19:  Escritura 
Una escritura deberá: 
a) mover atributos de datos de un único grupo de datos al almacenamiento persistente. 
b) Incluye todo el procesamiento lógico y el cálculo matemático para crear los atributos 
de datos que se van a escribir, en la medida en que estas manipulaciones no implican 
otro tipo de movimiento de datos. 
REGLA 20:  Escritura – Eliminar. 
Un requisito para eliminar un grupo de datos del almacenamiento persistente será un único 
movimiento de escribir datos. 
5. FASE DE MEDICIÓN. 
5.1 Proceso de fase de medición. 
El método general para medir una pieza de software cuando su FUR se ha expresado en 
términos del modelo de software genérico COSMIC se resume en la Figura 5.1.


<!-- pág 22/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 22 
 
 
 
Figura 5.1 – Proceso general para la Fase de Medición COSMIC. 
5.2 Cálculo del tamaño funcional. 
REGLA 21:  Tamaño de un movimiento de datos. 
Se asignará una unidad de  medida, 1 CFP, a cada movimiento de datos (Entrada, Salida, 
Lectura o Escritura) identificado en cada proceso funcional. 
REGLA 22: Tamaño de un proceso funcional. 
Los resultados del punto 5.2, aplicados a todos los movimientos de datos identificados dentro 
del proceso funcional identificado, se agregarán en un valor de tamaño funcional para dicho 
proceso funcional mediante: 
a) multiplicando el número de datos de cada tipo por su tamaño de unidad, 
b) totalizar los tamaños desde el paso a) para cada uno de los tipos  de movimiento de 
datos en el proceso funcional. 
Tamaño (proceso funcional)  =    tamaño (entradas) + tamaño (salidas) + tamaño (lecturas) + 
tamaño (escrituras).


<!-- pág 23/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 23 
 
 
REGLA 23:  Tamaño Funcional de los FUR identificados de cada pieza de software a 
medir 
El tamaño de cada pieza de software que se mida dentro de una capa se obtendrá agregando 
el tamaño de los procesos funcionales dentro de l os FUR identificados para cada pieza de 
software. 
NOTA: Dentro de cada capa identificada, la función de agregación es totalmente escalable. 
Por lo tanto, se puede generar un subtotal para procesos funcionales individuales, piezas de 
software individuales o para toda la capa, dependiendo del propósito y alcance del FSM. 
REGLA 24:  Tamaño Funcional de los cambios en los FUR. 
Dentro de cada capa identificada, el tamaño funcional de los cambios en el FUR dentro de 
cada pieza de software dentro del alcance del FSM se calculará agregando los tamaños del 
movimiento de datos de correspondiente de acuerdo con la siguiente fórmula: 
Tamaño (Cambiars a una pieza de software) = tamaño (movimientos de datos añadidos) + 
Tamaño (movimientos de datos modificados) + Tamaño (movimientos de datos eliminados)  
 
sumando todos los procesos funcionales para la pieza de software. 
NOTA: Se considera que se cambia un movimiento de datos si se cambia alguno de los 
atributos del grupo de datos o si se necesitan cambios en la manipulación de datos asociada 
con el movimiento de datos. 
6. INFORMES DE MEDICIÓN. 
El resultado debe notificarse y  registrarse datos sobre la medición  para garantizar que el 
resultado siempre sea inequívoco interpretable. 
REGLA 25:  Etiquetado. 
Un resultado de medición COSMIC en el FUR para una pieza de software que se ajuste a las 
normas obligatorias de ISO 19761 se etiquetará de acuerdo con el siguiente convenio: 
 CFP (ISO-IEC 19761:2011). 
REGLA 26:  Documentación de los resultados de la medición. 
La documentación de los resultados de la medición COSMIC incluirá la siguiente información: 
a) Identificación de cada pieza de software en el ámbito del FSM (nombre, identificación 
de versión o identificación de configuración).


<!-- pág 24/24 -->

Manual de Medición COSMIC- versión 5.0 – Parte 1: Principios, Definiciones y Reglas                     Derechos de autor © 2020
 24 
 
 
b) Una descripción del propósito y el alcance de la medición. 
c) Una descripción de la relación de cada pieza de software dentro del alcance del FSM 
con sus usuarios funcionales, tanto punto a punto como entre capas. 
d) El tamaño funcional de cada pieza de software dentro del ámbito del FSM, calculado 
según 5.2 e informe según 6. 
NOTA: Se requiere documentación para cada pieza de software medida dentro de cada
 capa. 
 
REFERENCIAS. 
[ISO 14143-1] ISO/IEC 14143-1: 2007 Tecnología de la información – Medición de software – 
Medición del tamaño funcional – Parte 1: Definición de conceptos, Organización Internacional 
de Normalización – ISO, Ginebra, 2017. 
[ISO 15288] ISO/IEC  15288: 2008 Ingeniería de Sistemas y Software – Procesos del Ciclo de 
Vida del Sistema, Organización Internacional de Normalización – ISO, Ginebra, 2008. 
[ISO 19761] ISO/IEC 19761: 2011 Ingeniería de software – COSMIC: un método de medición 
de tamaño funcional, Organización Internacional de Normalización – ISO, Ginebra, 2011. 
[ISO 24570] ISO/IEC 24570:2005 Ingeniería de software -- NESMA método de medición de 
tamaño funcional versión 2.1, Organización Internacional de Normalización – ISO, Ginebra, 
2010. 
[Guía ISO 99] Guía ISO 99: 1993, Vocabulario internacional de términos básicos y generales 
en metrología (VIM), Organización Internacional de Normalización – ISO, Ginebra, 2019.