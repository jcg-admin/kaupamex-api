<!-- Extraído de 4ce0c586-Part2MMGuidelinesv5.0ESPA_OL1.pdf (26 págs) por pypdf — 2026-06-03T03:35:05Z. Fuente oficial COSMIC v5.0 / ISO 19761. -->
# COSMIC v5.0 — Parte 2: Guidelines (Guías de aplicación)



<!-- pág 1/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 1 
 
 
 
 
 
 
Manual de Medición COSMIC  
para ISO 19761  
 
Parte 2:  
Directrices 
 
 
versión 5.0  
31 de de marzo de 2020


<!-- pág 2/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 2


<!-- pág 3/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 3 
 
 
Prefacio. 
El Manual de COSMIC de medición para ISO/IEC 19761: 2011 consta de tres partes: 
Parte 1: Principios, Definiciones y Reglas. 
Parte 2: Directrices. 
Parte 3: Ejemplos de conceptos y mediciones. 
Esta Parte 2 del Manual de Medición COSMIC presenta el conjunto de directrices elaboradas 
por el Grupo COSMIC para facilitar la precisión, repetibilidad y reproducibilidad de los 
resultados de las mediciones COSMIC. 
 
Este manual de medición COSMIC se basa en ISO/IEC norma 19761: 2011, se volvió a 
confirmar en 2019. Esta versión 5.0 del manual de medición COSMIC sustituye al Ma nual 
versión 4.0.2: se acorta la versión 4.0.2 mientras no modifica su contenido en términos de 
definiciones de medición, normas y orientaciones. 
 
Una versión de dominio  publico de  informes técnicos de medición , manuales y otros, 
incluyendo las traducciones a otros idiomas se puede encontrar en la base de conocimiento 
www.cosmic-sizing.org. 
 
editores: 
Alain Abran, Escuela de Tecnología Superior - Universidad de Quebec (Canadá),  
Peter Fagg, Péntada (Reino Unido),  
Arlan Lestherhuis (Holanda). 
Otros miembros del Comité de Prácticas de medición COSMIC: 
Diana Baklizky, (Brasil),  
Jean-Marc Desharnais, Escuela de Tecnología Superior - Universidad de Quebec (Canadá),  
Cigdem Gencel, Universidad Libre de Bolzano (Italia),  
Dylan Ren, Medidas Technology LLC (China),  
Bruce Reynolds, Telecote Investigación (EE.UU.),  
Hassan Soubra, Universidad alemana en El Cairo (Egipto),  
Sylvie Trudel, Universidad de Quebec en Montreal - UQAM (Canadá),  
Frank Vogelezang, Metri (Holanda). 
Francisco Valdés Souto, SPINGERE, UNAM, Mexico


<!-- pág 4/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 4 
 
 
 
 
 
 
Derechos de autor 2020. Todos los derechos reservados. El Consorcio Medición Común Internacional de Software 
(COSMIC). Se permite copiar todos o se concede proporcionado parte de este material que las copias no se hacen 
ni distribuido para obtener una ventaja comercial y que el título de la publicación, su número de versión, y su fecha 
se citan y se da aviso que la copia es con permiso de Medición del Co nsorcio Internacional de Software Común 
(COSMIC). Para copiar exija otra cosa permiso específico.


<!-- pág 5/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 5 
 
 
Tabla de contenido 
 
1. INTRODUCCIÓN. ................................ ................................ ................................ .............. 6 
1.1  Propósito de este documento. ................................ ................................ ...................... 6 
1.2. El proceso de medición COSMIC. ................................ ................................ ................ 6 
2. FASE DE ESTRATEGIA DE LA MEDICIÓN. ................................ ................................ ..... 6 
2.1 Descripción general de la fase de estrategia de medición. ................................ ........... 6 
2.2 Determinar el propósito y el alcance de la FSM. ................................ .......................... 7 
2.3 Identificación de la FUR de artefactos software. ................................ ........................... 8 
2.4 Requerimientos no funcionales. ................................ ................................ ................... 9 
2.5 Identificación de las capas. ................................ ................................ .........................10 
2.6 La identificación de los usuarios funcionales. ................................ .............................. 12 
2.7 Niveles de descomposición. ................................ ................................ ........................12 
2.8 Diagramas de contexto. ................................ ................................ .............................. 12 
2.9 Identificacion de el nivel de granularidad. ................................ ................................ ....13 
3. LA FASE DE MAPEO ................................ ................................ ................................ ...... 13 
3.1 Mapeo de la FUR al Modelo Genérico de Software. ................................ ....................14 
3.2 La identificación de procesos funcionales. ................................ ................................ ..14 
3.3 Identificación de los grupos de datos................................. ................................ ..........16 
3.3.1 Identificación de los grupos de datos. ................................ ................................ .16 
3.3.2 Sobre la identificación de objetos de interés y grupos de datos. ........................17 
3.3.3  Datos o grupos de datos que no son candidatos para los datos grupos. ...........18 
3.3.4 identificación de los atributos de datos (opcional). ................................ .............18 
3.4 identificación de los movimientos de datos. ................................ ................................ .18 
3.5 La medición de los componentes de un sistema de software distribuido. ....................22 
3.6 La reutilización de software. ................................ ................................ ........................22 
3.7 Medida del tamaño de cambios en el software. ................................ ...........................22 
4. OTROS TEMAS. ................................ ................................ ................................ .............. 24 
4.1 Extendiendo el método de medición COSMIC - Extensión local. ................................ .24 
4.2 COSMIC en el ágil................................. ................................ ................................ ......24 
5. FASE DE MEDICIÓN. ................................ ................................ ................................ ...... 25 
6. INFORMES DE MEDICIÓN. ................................ ................................ ............................. 25


<!-- pág 6/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 6 
 
 
1. INTRODUCCIÓN. 
1.1  Propósito de este documento. 
El propósito de este documento es proporcionar una guía a los profesionales para la aplicación 
de la norma ISO 19761 COSMIC Puntos de Función presentado en la Parte 1. 
Esta Parte 2 es complementaria a la parte 1 y se complementa con la parte 3 que presenta 
un gran número de ejemplos. 
1.2. El proceso de medición COSMIC. 
El proceso de medición COSMIC presentado en la Parte 1 se reproduce en la Figura 1.1 
 
Figura 1.1 - El proceso de medición método COSMIC. 
2. FASE DE ESTRATEGIA DE LA MEDICIÓN. 
2.1 Descripción general de la fase de estrategia de medición. 
La figura 2.1 representa gráficamente la fase de estrategia de medición.


<!-- pág 7/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 7 
 
 
 
Figura 2.1 - El proceso de determinar una estrategia de medición. 
2.2 Determinar el propósito y el alcance de la FSM. 
El término 'propósito' se utiliza en su sentido normal de Inglés. El propósito ayuda a la persona 
que mide para determinar: 
• El alcance de la medición y por lo tanto los objetos que serán necesarios para la medición. 
• Los usuarios funcionales. 
• Los cambios funcionales. 
• El punto en el tiempo en el ciclo de vida del proyecto cuando la medición se llevará a cabo. 
• La precisión requerida de la medición, y por lo tanto si el método COSMIC estándar se 
debe utilizar, o si una técnica de aproximación se debe utilizar (por ejemplo, temprano en 
el ciclo de vida de un proyecto, antes de la FUR están completamente elaborados). 
Como una ayuda para la determinación de una estrategia de medición, con la Directriz de 
'Patrones de estrategia  de medición' describe, para cada uno de varios tipos diferentes de 
software, un conjunto estándar de parámetros para medir tamaños de software, llamados un 
'patrón estrategia de medición' (abreviado a 'patrón  de medición'), el uso consistente de los 
mismos patrones de medición debería ayudar medidores para garantizar que las mediciones 
realizadas para el mismo fin se hacen de una manera consistente, se puede comparar de 
manera segura con otras mediciones hechas usando el mismo patrón  y serán interpretados 
correctamente para todos los usos futuros. Un beneficio adicional de usar un patrón estándar 
es que el esfuerzo para determinar los parámetros de estrategia de medición se reduce 
mucho.


<!-- pág 8/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 8 
 
 
El Grupo COSMIC recomienda que estudiantes medidores y expertos en el método COSMIC, 
estudiar en especial los parámetros de estrategia de medición, antes de utilizar los patrones 
estándar. 
2.3 Identificación de la FUR de artefactos software. 
Por lo general, el medidor tendrá que extraer la FUR de los artefactos disponibles del software, 
antes de asignar a los conceptos de COSMIC 'modelos de software'. 
Como se ilustra en la Figura 2.2, los FUR se pueden derivar de artefactos de ingeniería de 
software que se producen antes de que exista el software. Por lo tanto, el tamaño funcional 
del software puede ser medida antes de su implementación en un sistema informático. 
 
Figura 2.2 - fuentes de Pre-aplicación de los requisitos funcionales de los usuarios. 
NOTA: Algunos software existentes pueden necesitar ser medidos sin que exista, o con sólo 
unos pocos elementos de la arquitectura o artefactos de diseño disponibles y los requisitos 
funcionales no pueden ser documentados (por ejemplo, para software heredado). En tales 
circunstancias, todavía es posible derivar el FUR de los artefactos del sistema de ordenador, 
incluso después de que se ha aplicado, como se ilustra en la Figura 2.3. 
 
Figura 2.3 - fuentes posterior a la aplicación de los requisitos de los usuarios funcionales 
(FUR).


<!-- pág 9/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 9 
 
 
El proceso que se utiliz ará y por lo tanto el esfuerzo necesario para extraer el FUR de 
diferentes tipos de artefactos de ingeniería de software o derivarlos  del software instalado 
variará, obviamente; estos procesos no pueden ser tratados en el Manual de Medición. El 
método COSMIC supone que el FUR del software a ser medido existen o que puedan ser 
extraídos o derivados de sus artefactos, a la luz de los fines de la medición. 
Si el medidor comprende estos dos modelos, siempre será posible derivar los FUR de una 
pieza de software que se mide a partir de sus artefactos disponibles, aunque el medidor puede 
tener que hacer algunos supuestos debido a la falta o información poco clara.  
2.4 Requerimientos no funcionales. 
Los NFR puede ser muy significativo para un proyecto de software. En casos extremos, una 
declaración de requisitos para un sistema de software intensivo puede requerir toda la 
documentación para la NFR en cuanto a los requisitos funcionales. El método COSMIC puede 
ser usado para medir algunos de los requisitos que pueden  expresarse primero como no 
funcional. Varios estudios han demostrado que algunos de los requisitos que aparecen 
inicialmente como  NFR evolucionan como una mezcla de requisitos que pueden ser 
implementadas en las funciones de software y otros requisitos o condiciones que son 
realmente 'no funcional'. Véase la Figura 2.4. 
 
Figura 2.4 - Muchos de los requisitos que aparecen inicialmente como NFR evolucionan en 
FUR con el progreso del proyecto. 
Esto es cierto para muchas limitaciones de calidad del sistema, tales como el tiempo de 
respuesta, facilidad de uso, facilidad de mantenimiento, etc. Una vez identificadas, estas 
funciones de software que han sido 'ocultos' en NFR al comienzo de un proyect o se pueden 
dimensionar utilizando el método COSMIC solo como cualesquiera otras funciones de


<!-- pág 10/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 10 
 
 
software. El no reconocer este tamaño funcional 'oculto' es una razón por tamaños de software 
pueden aparecer creciendo a medida que progresa un proyecto. 
Más discusiones en profundidad sobre el sistema y software requisitos no funcionales (NFR) 
se presentan en: 'Guideline on Non-Functional & Project Requirements'. 
2.5 Identificación de las capas. 
Las arquitecturas de software pueden ser muy complejos, sin embargo COSMIC emplea una 
visión muy simplificada de la arquitectura de software que es suficiente para el propósito de 
la medición. Es la tarea del medidor pa ra llevar a cabo dicho procedimiento. Esta sección 
proporciona una guía para el medidor. 
Dado que el alcance de una pieza de software a ser medido debe limitarse a una única capa 
de software, el proceso de definir el alcance (s) de FSM puede requerir que el medidor tenga 
primero para decidir cuáles son las capas de la arquitectura del software. Este sub -sección 
discute 'capas' de software como estos términos se utilizan en el método COSMIC porque: 
• el medidor puede enfrentarse con la medición de algún tipo de software en un entorno de 
'legado' de software que ha evolucionado durante muchos años sin haber sido diseñado 
de acuerdo a una arquitectura subyacente Por tanto, el medidor puede necesitar 
orientación sobre cómo distinguir capas según la terminología COSMIC; 
• las expresiones 'capa' y 'arquitectura en capas' se usan de manera habitual en la industria 
del software. Cuando el medidor debe medir algún tipo de software que se describe como 
estando en una 'arquitectura de capas', es recomendable comprobar que l as 'capas' en 
esta arquitectura se definen de una manera que sea compatible con el método COSMIC. 
Para hacer esto,  el medidor debe establecer la equivalencia entre los objetos 
arquitectónicos específicos en el paradigma de la arquitectura en capas y el concepto de 
capas como se define en este manual. 
En una arquitectura de software definido, cada capa puede tener las siguientes 
características: 
a) Software en una sola capa proporciona un conjunto de servicios que es coherente 
acuerdo con algún criterio definid o, y que el software en otras capas puede utilizar 
sin saber cómo se implementan estos servicios. 
b) La relación entre el software en cualquiera de las dos capas se define por una 'regla 
de correspondencia' que puede ser:


<!-- pág 11/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 11 
 
 
• 'jerárquico' se permite  que software en la capa A utilizar los servicios 
proporcionados por el software en la capa B pero no viceversa (comúnmente 
referido como cliente-servidor); 
• 'Bidireccional', es decir, software en la capa A se  le permite que el software de 
uso en la capa B, y viceversa (comúnmente referido como peer-to-peer (P2P)). 
c) Software intercambia grupos de datos con el software en otra capa a través de sus 
respectivos procesos funcionales. 
d) Software en una sola capa no necesariamente utiliza todos los servicios funcionales 
suministrados por el software en otra capa. 
e) Software en una capa de una arquitectura de software definido puede ser dividido en 
otras capas de acuerdo con una arquitectura de software definido diferente. 
Orientación sobre la Regla 4: Identificación de Capas 
Si el alcance general de la FSM se extiende a través de múltiples capas, el medidor debe 
proceder como sigue: 
• Si existe el software a ser medido dentro de una arquitectura establecida de capas que se 
pueden asignar a las característ icas de estratificación COSMIC como se define 
anteriormente, a continuación, que la arquitectura debe ser usado para identificar las 
capas para fines de medición.  
• Sin embargo, si el propósito requiere que algunos programas se mide que no está 
estructurado de acuerdo con las características de estratificación COSMIC, el medidor 
debe tratar de dividir el software en capas mediante la aplicación de los principios definidos 
anteriormente. 
• Convencionalmente, los paquetes de software de infraestructura, tales como los sistemas 
de gestión de bases de datos, sistemas operativos o controladores de dispositivo, que 
proporcionan servicios que pueden ser utilizados por otros programas en otras capas, 
cada una se encuentran en capas separadas. 
Normalmente, en las arquitecturas de software, la capa 'superior', es decir, la capa que no es 
un subordinado a cualquier otra capa en una jerarquía de capas, se refiere como la capa de 
'aplicación'. El software de este capa de aplicación se basa en los servicios de software en 
todas las otras capas para que éste se ejecute correctamente. Software en esta capa 'superior' 
puede ser él mismo en capas, por ejemplo, como en una 'arquitectura de tres capas' de 
interfaz de usuario, reglas de negocio y componentes de servicios de datos. 
Una vez identificados, cada capa puede estar registrada en el informe de medición, con la 
etiqueta correspondiente.


<!-- pág 12/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 12 
 
 
2.6 La identificación de los usuarios funcionales. 
 
Orientación sobre la Regla 7: Identificación de los usuarios funcionales. 
La identificación de usuario funcional (o usuarios) se determina por los FUR que se deben 
medir y por el propósito de la medición. 
 
2.7 Niveles de descomposición. 
Mediciones de tamaño de los componentes de una pieza de software sólo son directamente 
comparables para los componentes en el mismo nivel de descomposición. Esto es importante 
porque los tamaños de piezas de software en diferentes niveles de descomposición no se 
pueden añadir simplemente sin tener en cuenta las reglas de agregac ión del capítulo 5. 
Además, como consecuencia, el rendimiento (por ejemplo, la productividad = tamaño / 
esfuerzo) de los proyectos de desarrollar diferentes piezas de software sólo pueden 
compararse si todas las piezas de software están en el mismo nivel de descomposición. 
Diferentes niveles de descomposición de una pieza de software pueden corresponder a 
diferentes 'vistas' de las capas del software, por ejemplo como en la figura 2.4 en la Parte 3. 
Sin embargo, el software puede descomponerse en 'niveles' independientemente de si es o 
no diseñado usando una modelo de capas-arquitectura. 
2.8 Diagramas de contexto. 
Puede ser útil cuando se define un ámbito de FSM  y los usuarios funcionales para dibujar un 
'diagrama de contexto' para el software que se está m idiendo. Diagramas de contexto 
muestran los flujos de datos entre la pieza de software y sus usuarios funcionales (seres 
humanos, dispositivos de hardware u otro software) y también muestran los flujos de datos 
entre la pieza de software y almacenamiento persistente. 
Un diagrama de contexto es un ejemplo de un patrón de medición aplicada al software que se 
mide. Símbolos utilizados en los diagramas de contexto se presentan en la Figura 2.5. 
Símbolo Interpretación 
 
La pieza de software que va a medirse (caja con el espesor  grueso  en el borde ), es decir, la 
definición de un alcance de la medición. 
 
 
cualquier usuario funcional del software que se mide 
 
Las flechas representan todos los movimientos de los datos que cruzan una frontera (la línea 
de puntos) entre un usuario funcional y el software que se mide.


<!-- pág 13/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 13 
 
 
 
Las flechas representan todos los movimientos de datos entre el software que se está midiendo 
y 'almacenamiento persistente'. (El símbolo de diagrama de flujo para 'almacenamiento de 
datos' hace hincapié en que el almacenamiento persistente es un concepto abstracto. Este 
símbolo indica que el software no lo hace interactuar directamente con el alma cenamiento de 
hardware físico.) 
Figura 2.5 - Símbolos de diagramas de contexto. 
2.9 Identificacion de el nivel de granularidad. 
COSMIC requiere el FUR que se expresa a un nivel de detalle suficiente para crear los 
modelos de medición COSMIC: esto se llama el nivel de granularidad. 
Para derivar un tamaño funcional utilizando el COSMIC FSM usando las reglas de la norma 
ISO 19761, el nivel necesario de granularidad es aquel en la que los procesos funcionales 
individuales y sus movimientos de datos pueden  ser identificados y definidos. Cuando los 
detalles funcionales faltan en otros niveles de granularidad de los requisitos, las mediciones 
deben realizarse utilizando una de las técnicas de aproximación de tamaño descritos en “Early 
Software Sizing with COSMIC: Practitioners Guide” 
 
NOTA 1 En las etapas iniciales de un proyecto de desarrollo de software, requisitos reales 
son especificados 'en un alto nivel', que es, a grandes rasgos, o en el pequeño detalle. Como 
los progresos del proyecto, se refinan las n ecesidades reales, (por ejemplo, a través de las 
versiones 1, 2, 3 etc.), revelando más y más detalle 'en los niveles inferiores'. Estos diferentes 
grados de detalle de los requisitos reales se conocen como diferentes 'niveles de 
granularidad'. 
NOTA 2: Medidores deben ser conscientes de que cuando los requisitos están evolucionando 
temprano en la vida de un proyecto de software, en cualquier momento en diferentes partes 
de la funcionalidad del software requerido típicamente se han documentado en los diferentes 
niveles de granularidad. 
Para un ejemplo de medición a diferentes niveles de granularidad y de descomposición, ver 
el ejemplo de sistema de telecomunicaciones en el ‘Guideline for early or rapid COSMIC 
functional size measurement using approximation approaches’ 
3. LA FASE DE MAPEO 
procesos funcionales están compuestos de sub-procesos de mueven datos ( 'movimientos 
de datos') y, opcionalmente, puede manipular los datos ( 'manipulación de datos').


<!-- pág 14/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 14 
 
 
3.1 Mapeo de la FUR al Modelo Genérico de Software. 
La figura 3.1 muestra los pasos para la asignación del FUR en los artefactos de software 
disponibles en la forma requerida por el Software modelo COSMIC genérico. 
 
Figura 3.1 - Método general del proceso de mapeo COSMIC. 
Varias directrices están disponibles que describen cómo asignar de varios métodos de análisis 
de datos y los requisitos de determinación, utilizados en diferentes dominios a los conceptos 
del método COSMIC:  
• Guideline for Sizing Business Application Software, 
• Guideline for Sizing Data Warehouse Application Software,  
• Guideline for Sizing Service-Oriented Architecture Software, y 
• Guideline for Sizing Real-time Software.  
Para el negocio y tiempo real También existen Guías de referencia rápida disponibles que dan 
una visión general del proceso en unas pocas páginas. 
3.2 La identificación de procesos funcionales. 
El primer paso de la fase de medición es identificar el conjunto de procesos funcionales de la 
pieza de software que va a medirse, a partir de sus FUR. 
Las relaciones entre un evento desencadenante, el usuario funcional y el movimiento de los 
datos de entrada que activa un proceso funcional que se está midiendo se presentan en la 
Figura 3.2 donde: un evento desencadenante hace que un usuario funcional  genere un grupo


<!-- pág 15/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 15 
 
 
de datos que se desplaza por la entrada desencadenante de un proceso funcional para iniciar 
el proceso funcional. 
 
Figura 3.2 - Relaciones entre un evento desencadenante, un usuario funcional y un proceso 
funcional. 
NOTA 1: Para facilitar la lectura, se omite la referencia al grupo de datos al afirmar que un 
usuario funcional envia una entrada desencadenante que inicia un proceso funcional, o incluso 
más simplemente que un usuario funcional inicia un proceso funcional. 
NOTA 2: Todas las relaciones entre los conceptos de la figura 3.2 (el grupo de evento 
desencadenante / usuario funcional /  grupo de datos  / entrada desencadenante / proceso 
funcional) pueden ser de uno a muchos, muchos -a-uno, o muchos -a-muchos, con una 
excepción . La excepción es que el grupo de datos movido por cualquiera entrada 
desencadenante puede iniciar sólo el proceso funcional que del que es parte. 
Orientación sobre la Regla 10: Identificación de Procesos Funcionales 
El proceso de identificación de procesos funcionales, después de que los usuarios funcionales 
han sido identificadas, dado el FUR para el software que está siendo medido sigue la cadena 
de la Figura 3.2: 
1. Identificar los eventos separados en el mundo de los usuarios funcionales que el software 
que está siendo medido debe responder - los 'eventos desencadenantes'  
NOTA: eventos desencadenantes pueden ser identificados en los diagramas de estado 
y en los diagramas del ciclo de vida, ya que algunas transiciones de estados y 
transiciones del ciclo de vida corresponden a eventos de activación a l os que debe 
reaccionar el software. 
2. Identificar qué usuario funcional (s) del software puede responder a cada evento 
desencadenante; 
3. Identificar el grupo de datos (s) (es decir, la entrada desencadenante) que cada usuario 
funcional puede iniciar en respuesta al evento;


<!-- pág 16/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 16 
 
 
4. Identificar el proceso funcional iniciado por cada entrada desencadenante. 
Utilice los siguientes controles para garantizar que los procesos funcionales candidatos ( PF) 
han sido identificados correctamente: 
1. ¿Todos los Proceso Funcionales de la pieza de software residen medido en la misma capa? 
2. ¿Todos los Proceso Funcionales identificados se componen de una entrada y al menos 1 
Escritura o Salida? 
3.3 Identificación de los grupos de datos. 
3.3.1 Identificación de los grupos de datos. 
Una vez identificados los procesos funcionales, el siguiente paso es identificar sus 
movimientos de datos. Los siguientes orientaciones son de ayuda en la identificación de los 
grupos de datos y por lo tanto los objetos de interés en  
Orientación sobre la Regla 11: Identificación de los diferentes grupos de datos en el 
mismo proceso funcional. 
Para todos los atributos de datos que aparecen en una entrada-salida-lectura-escritura de un 
proceso funcional:  
a) conjuntos de atributos de datos que tienen diferentes frecuencias de ocurrencia describen 
diferentes objetos de interés; 
c) conjuntos de atributos de datos que tienen la misma frecuencia de aparición, pero diferente 
cantidad de atributo (s) describen diferentes objetos de interés; todos los atributos de datos 
en un conjunto resultante de aplicar las partes A) y B) de esta guía pertenecen al mismo 
grupo de datos, a menos que el FUR especifi que que puede haber más de un grupo de 
datos que describe el mismo objeto de interés (véase el Documento de orientación sobre 
las Reglas 13 y 14 - movimientos de datos únicos, los casos b) y c)). 
NOTA 1: Un usuario funcional del software que se mide puede ser el objeto de interés de un 
grupo de datos enviado o recibido por el usuario funcional. 
NOTA 2: En teoría, un grupo de datos podría contener atributo sólo un dato de si esto es todo 
lo que se requiere, desde la perspectiva de las FUR, para describir el objeto de interés. En la 
práctica, estos casos ocurren comúnmente en el software de aplicación en tiempo real (por 
ejemplo, el grupo de datos entrado para transmitir la señal de un reloj de tie mpo real o de la 
entrada del estado de un sensor); que son menos comunes en software de aplicación 
comercial. 
El origen de un grupo de datos puede ser de muchas formas, por ejemplo: 
a) Una estructura de registro físico en un dispositivo de almacenamiento de h ardware 
(archivo, tabla de base de datos, memoria ROM, etc.).


<!-- pág 17/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 17 
 
 
b) Una estructura física dentro de la memoria volátil del ordenador (estructura de datos 
asignada dinámicamente o a través de un bloque de pre -asignado de espacio de 
memoria). 
c) Una presentación agrupada de atributos de datos funcionalmente relacionadas en un 
dispositivo de entrada / salida (pantalla de visualización, informe impreso, de visualización 
de panel de control, etc.). 
d) Un mensaje en la transmisión entre un dispositivo y un ordenador, o sobre una red, etc. 
3.3.2 Sobre la identificación de objetos de interés y grupos de datos. 
La definición y principios de los objetos de interés y de los grupos de datos  son 
intencionalmente amplio con el fin de ser aplicables a la gama más amplia posible de software: 
A veces, esto da como resultado que sea difícil aplicar la definición y principios en la medición 
de una pieza específica de software. Véase la Parte 3 para ejemplos para ayudar en la 
aplicación de los principios a los casos concretos 
Cuando se enfrentan a la necesidad de analizar un conjunto de atributos de datos que se 
mueve en o fuera de un proceso funcional o se mueve mediante un proceso funcional hacia 
o desde el almacenamiento persistente, es críticamente importante para decidir si los atributos 
transmiten datos sobre un único 'objeto de interés', ya que es clave el determinar el número 
de grupos de datos separadas como se define por el método COSMIC que será movido por 
movimientos de datos.  
Por ejemplo, si los datos de atribut os para ser entrada a un proceso funcional son atributos 
de tres objetos de interés  separados, a continuación, tres movimientos de datos separad os 
de 'entrada' deben ser identificados. La decisión sobre el número de grupos de datos puede 
ser difícil cuando el análisis de la salida de un proceso funcional de una aplicación de negocio 
que pueden incluir: 
• múltiples grupos de datos, cada uno que describe un objeto de interés diferente, por 
ejemplo, un informe que muestra los totales en los distintos niveles de agregación; 
• los resultados de las investigaciones donde la salida variará dependiendo de la entrada; 
• grupos de datos que pueden incluso no estar relacionadas entre sí, por ejemplo, una 
factura que incluye un anuncio para un servicio no relacionado. 
Al analizar la producción compleja, por ejemplo, informes con datos que describen varios 
objetos de interés, consideran cada grupo de datos candidato independiente como si se 
tratara de salida por un proceso funcional separada. Cada uno de los tipos de grupos de datos 
identificados de esta manera también deben distinguirse y se contar an al medir el informe 
complejo.


<!-- pág 18/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 18 
 
 
3.3.3  Datos o grupos de datos que no son candidatos para los datos grupos. 
Los datos que aparecen en las pantallas de entrada o de salida o infor mes que no están 
relacionados con un objeto de interés a un usuario funcional no deben ser identificados como 
un grupo de datos.  
El modelo genérico de software de  COSMIC supone que toda la manipulación de los datos 
dentro de un proceso funcional está asoc iada con los cuatro tipos de movimiento de datos. 
Por lo tanto no hay grupos de datos pueden ser identificados derivados de la manipulación de 
datos dentro de un proceso funcional además de los grupos de datos movido por las entradas, 
salidas, lecturas y escrituras del proceso funcional. 
3.3.4 identificación de los atributos de datos (opcional). 
En el método COSMIC, no es obligatorio identificar los atributos de los datos. Sin embargo, 
entender el concepto de un 'atributo de datos' es necesario para entender cómo medir los 
cambios. Un requisito para cambiar un atributo de datos puede dar como resu ltado que el 
movimiento de datos a los que el atributo pertenece sea “cambiado” funcionalmente. 
Además, puede ser útil para analizar e identificar los atributos de datos en el proceso de 
distinguir grupos de datos y objetos de interés. 
3.4 identificación de los movimientos de datos. 
Este paso consiste en la identificación de los movimientos de datos (entrada, salida, lectura y 
escritura) de cada proceso funcional.  
Orientación sobre la Regla 12: Movimientos de Datos 
En general, el 'tipo' de una cosa es una clase abstracta de todas las cosas que comparten 
alguna característica común, por lo que las cosas están sujetas a la misma FUR. (Sinónimos 
de 'tipo': 'categoría', 'tipo'). 
Un 'ocurrencia' de una cosa es cuando se vuelve real mediante la asignación de valores a sus 
atributos. Conocido en el mundo orientado a objetos como 'instanciación' - la creación de una 
instancia. 
La siguiente guía ayuda a confirmar el estado de un movimiento de datos de entrada 
candidato: 
solUIDANCE en la Regla 16: Entrada (E). 
a) El grupo de datos de una entrada desencadenante puede consistir en sólo un atributo de 
datos que simplemente informa al software que 'ha ocurrido un evento Y'. 
b) Para eventos de reloj que desencadenan eventos identificar  una entrada de un usuario 
funcional, en este caso el reloj.


<!-- pág 19/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 19 
 
 
c) A menos que un proceso funcional específico es necesario, obtener la fecha y / u hora del 
reloj del sistema no se considera una entrada o cualquier otro movimiento de datos. 
NOTA:  Muy a menudo, sobre todo en software de aplicación c omercial, el grupo de 
datos de la entrada desencadenante  tiene varios atributos de los datos que informan al 
software que 'un evento Y ha ocurrido y aquí está la información sobre ese evento en 
particular'. 
Orientación sobre la Regla 17: Salida (X). 
a) Para una consulta que da salida a texto fijo, (en el que los medios 'fijos' el mensaje no 
contiene valores de datos variable), identificar una salida de texto fijo. 
b) En la identificación de las salidas, ignorar todos los campos y otras partidas que permiten 
a los usuarios humanos entender los datos de salida. 
 
Orientación sobre la Regla 18: Lectura (R). 
No se identifique una Lectura cuando el FUR del software que se está midiendo especifica un 
software o hardware usuario funcional como la fuente de un grupo de datos, o como los 
medios de recuperación de un grupo de datos almacenados persistentemente. 
 
Orientación sobre la Regla 19: Escritura (W). 
No identificar una escritura cuando el FUR del software que se está midiendo especifica un  
software o hardware usuario funcional como el destino del grupo de datos o como medio de 
almacenamiento de datos del grupo. 
NOTA: Cuando el FUR requiere datos a alm acenar o para ser recuperados de 
almacenamiento, el medidor debe investigar si los datos pueden ser almacenados o 
recuperados dentro de su propio límite, es decir, a / de 'almacenamiento persistente', o si se 
requiere datos a almacenar / recupera r con la a yuda de un usuario funcional del software 
medido (es decir, a través de alguna otra pieza de software, o directamente a o desde un 
dispositivo de hardware).  
Orientación sobre las Reglas 16 a 19 - Manipulación de datos asociado con los 
movimientos de datos. 
La manipulación de datos asociada con cualquiera de estos movimientos de datos no incluye 
ningún tipo de manipulación de datos que se necesita después de que el movimiento de datos 
se ha completado con éxito, ni tampoco incluye ningún tipo de manipulación de datos asociado 
con cualquier otro movimiento de datos.


<!-- pág 20/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 20 
 
 
La siguiente guía cubre la situación más común (orientación a)) y otros posibles casos válidos 
(orientación b) yc)): 
• En a) las ocurrencias del grupo de datos están sujetas a l os mismos FUR: así se  
identifica un grupo de datos y un movimiento de datos.  
• En b) y c) el mismo se aplica a cada grupo de datos diferente separado: así se 
identifica un grupo de datos y un movimiento de datos por diferentes grupos de datos. 
ORIENTACIÓN relativo a las normas 13 y 14 - Movimientos de datos únicos. 
a) A menos que el FUR s ean como se da en la orientación b) o c), todos los datos que 
describen cualquier objeto de interés que se requiere para ser introducido en un proceso 
funcional es identificado como un grupo de datos movido por una entrada. 
NOTA 1: Un proceso funcional puede, por supuesto, tener varias entradas, cada una en 
movimiento datos que describen un objeto de interés diferente. 
NOTA 2: La misma orientación equivalente es aplicable a cualquier movimiento de datos 
lectura, escribir o salida en cualquier proceso funcional. 
b) Si los FUR especifican que diferentes grupos de datos se deben introducir en un proceso 
funcional, cada uno desde un usuario funcional diferente, donde cada g rupo de datos 
describe el mismo objeto de interés, a continuación, una movimiento de datos  es 
identificado para cada uno de estos diferentes grupos de datos. 
NOTA 1: Se aplica la misma orientación equivalente para las salidas de datos a diferentes 
usuarios funcionales de cualquier proceso funcional. 
NOTA 2: Todo proceso funcional sólo una entrada desencadenante.  
c) Si los FUR especifica n que diferentes grupos de datos deben ser movidos de un 
almacenamiento persistente a un proceso funcional, cada uno que describe el mismo 
objeto de interés, entonces un a Lectura se identifica para cada uno de estos diferentes 
grupos de datos. 
NOTA 1: La misma orientación equivalente aplica a las escrituras en cualquier proceso 
funcional dada. 
NOTA 2: Esta guía es análoga a la regla b). En el caso de los FUR para lectura diferentes 
grupos de datos que describen el mismo objeto de interés, es probable que se han 
originado a partir de diferentes usuarios funcionales. En el caso de la FUR para escribir 
diferentes grupos de datos, que probablemente estarán disponibles para se r leídos por 
diferentes usuarios funcionales. 
 
Orientación sobre Reglas 16 -17: Cuando el proceso funcional requiere datos de un 
usuario funcional.


<!-- pág 21/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 21 
 
 
a) Cuando el proceso funcional no tiene que decirle al usuario funcional qué datos para 
enviar, una sola entrada es suficiente (por objeto de interés). 
b) Cuando las necesidades del proceso funcionales para indicar al usuario funcional qué 
datos enviar, una salida seguida de una entrada son necesarios. 
 
Orientación sobre Reglas 16-19: Comandos de control en aplicaciones con una interfaz 
humana. 
En una aplicación con 'comandos de control' una interfaz humana se ignoran, ya que no 
implican ningún movimiento de los datos acerca de un objeto de interés. 
 
Los mensajes de error y de confirmación son formas específicas de una salida y las reglas 
que rigen son las siguientes:   
 
Orientación sobre Reglas 16-19: mensajes de error / confirmación y otras indicaciones 
de condiciones de error. 
a) Una salida se identifica a la cuenta de todos los tipos de error / mensajes de confirmación 
emitidos por un único proceso funcional del software que se miden a partir de todas las 
causas posibles de acuerdo a su FUR. 
b) Si un mensaje a un usuario humano funci onal proporciona datos además de confirmar 
que los datos introducidos han sido aceptados, o que los datos introducidos es un error, 
a continuación, estos datos adicionales se identifica como un grupo de datos por separado 
movido por una salida en la forma normal. 
c) Todos los demás datos, emitidos o recibidos por el software que se mide, a / de sus 
usuarios funcionales de hardware o software deben ser analizados de acuerdo con el FUR 
como salidas o entradas, respectivamente, de acuerdo con las reglas COSMIC normales, 
independientemente de si los valores de datos indican una condición de error. 
d) Lecturas y Escrituras se consideran que contienen toda la  información asociada de 
condiciones de error. Por lo tanto no hay ninguna entrada para el proceso funcional que 
se está midiendo se identifica para cualquier indicación de error recibida como resultado 
de una lectura o escritura de datos persistentes. 
e) Ninguna entrada o de salida se identificar an para cualquier mensaje que indica una 
condición de error que podrían se r emitida, mientras que utilizando el software que está 
siendo medido, pero que no se requiere para ser procesado en cualquier forma por el FUR 
de que el software, por ejemplo, un mensaje de error emitido por el sistema operativo .


<!-- pág 22/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 22 
 
 
3.5 La medición de los componentes de un sistema de software distribuido. 
Cuando el propósito de una medición es medir por separado el tamaño de cada componente 
de un sistema de software distribuido, un ámbito de aplicación por separado de FSM debe 
definirse para cada componente. En tal caso el dimensionamiento de los procesos funcionales 
de cada componente sigue todas las reglas como ya se ha descrito. 
Desde el proceso para cada medición (... definir el alcance, entonces los usuarios funcionales 
y fronteras, etc ...) se deduce que si una pieza de software consta de dos o más componentes, 
no puede haber ningún solapamiento entre el alcance de EFM de cada componente. El 
alcance de la FSM para cada componente debe definir un conjunto de procesos funcionales 
completos. Por ejemplo, no  puede ser un proceso funcional con parte en un alcance y otra 
parte en otro. Asimismo, los procesos funcionales dentro del alcance de medición para uno 
de los componentes no tienen ninguna información acerca de los procesos funcionales dentro 
del alcance de otro componente, a pesar de que los dos componentes intercambian mensajes. 
El usuario (s) funcional (es) de cada componente es / son se determinan examinando donde 
los eventos se producen (Eventos desencadenantes sólo puede ocurrir en el mundo de un 
usuario funcional). 
 
3.6 La reutilización de software. 
Cualquiera de los dos o más procesos funcionales en el mismo software que se está midiendo 
puede tener alguna funcionalidad que es idéntico o muy similar en cada proceso y se describe 
por separado en otra  parte de los requisitos. Este fenómeno se conoce como 'comunalidad 
funcional', o 'similitud' funcional. 
Sin embargo, cada proceso funcional se define, modela y mide independientemente, es decir, 
sin referencia a ninguna otra FUR en el mismo software que se está midiendo.  
Por lo tanto, si el FUR para un proceso funcional dad o hace una referencia a FUR en otra 
parte de los requisitos a continuación, el tamaño de esa funcionalidad se hace referencia es 
para ser incluido en el tamaño del proceso funcional que se está midiendo. 
 
3.7 Medida del tamaño de cambios en el software. 
Un 'cambio funcional' para el software existente se interpreta en el método COSMIC como 
'cualquier combinación de adiciones de nuevos movimientos de datos o de modificaciones o 
eliminaciones de movimientos de datos existentes, incluyendo a la manipulación de datos


<!-- pág 23/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 23 
 
 
asociada'. Los términos 'mejora' y 'mantenimiento' 1 se utilizan a menudo para lo que aquí 
llamamos un 'cambio funcional'.  
La necesidad de un cambio en el software se pueda derivar de cualquiera de los dos: 
• un nuevo FUR (es decir, sólo adiciones a la funcionalidad existente), o  
• de un cambio en la FUR (tal vez con adiciones, modificaciones y supresiones) o  
• de la necesidad de 'mantenimiento' para corregir un defecto. 
Las reglas para el tamaño de cualquiera de estos cambios son los mismos pero el medidor se 
de la alerta para distinguir las diversas circunstancias cuando se hacen mediciones de 
rendimiento y estimaciones.  
 
 
 
Se considera que un movimiento de datos es modificado funcionalmente si: 
Orientación sobre los artículos 21 a 24: - Modificación de un movimiento de datos. 
a) Si un movimiento de datos debe ser modificado debido a un cambio de la manipulación 
de datos asociado con el movimiento de datos y / o debido a un cambio en el número o el 
tipo de los atributos en el grupo de datos m ovido, uno cambi o CFP se mide, 
independientemente de la número real de modificaciones en el movimiento de uno de 
datos. 
b) Si un grupo de datos debe ser modificado, los movimientos de datos cuya funcionalidad 
no se ve afectada por la modificación en el grupo de datos no es identificado como 
movimientos de datos modificados. 
NOTA: Una modificación de los datos que aparecen en las pantallas de entrada o de salida 
que no están relacionados a un objeto de interés para un usuario funcional no se identifica 
como un cambio CFP. 
c) Una convención de medición normal es que el tamaño funcional de una pieza de 
software no cambia si el software debe ser cambiado para corregir un defecto con el fin 
de llevar el software en línea con su FUR. El tamaño funcional del software es cambiado 
si el cambio es para corregir un defecto en el FUR.  
Movimientos de datos modificados no tienen influencia en el tamaño de la pieza de software 
tal como existen antes y después de las modificaciones se han hecho.


<!-- pág 24/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 24 
 
 
Cuando una pieza de software se sustituye completamente, por ejemplo mediante re -
escritura, con o sin extender y / o la omisión de la funcionalidad, el tamaño funcional de este 
cambio es el tamaño del software de reemplazo, medido de acuerdo con las reglas normales 
para el dimensionamiento nuevo software.  
NOTA Por lo general, el tamaño de un cambio funcional (discutido aquí) y el cambio en el 
tamaño funcional del software difieren. 
4. OTROS TEMAS. 
4.1 Extendiendo el método de medición COSMIC - Extensión local. 
El método COSMIC de la medición de un tamaño funcional no pretende medir todos los 
aspectos posibles del tamaño de un software . Así, el método no está actualmente diseñado 
para medir por separado y de forma explícita el tamaño de la FUR de manipulación de datos. 
La influencia del tamaño de la manipulación de datos se tiene en cuenta a través de una 
suposición simplificadora que es válida para una amplia gama de dominios de software. 
Sin embargo, la medida del tamaño COSMIC es considerada como una buena aproximación 
para el propósito y los dominios de aplicabilidad declarado del método. Sin embarg o, puede 
ser que en el medio ambiente local de una organización que utilice el método de medición 
COSMIC, se desea para dar cuenta de tal funcionalidad de una manera que es significativa 
como un estándar local. Cuando se usan tales extensiones locales, los resultados de medición 
deben ser reportados de acuerdo con la convención especial presentado en la sección 6. 
 
4.2 COSMIC en el ágil. 
El método COSMIC está siendo utilizado con éxito para medir el tamaño de las historias de 
los usuarios en los desarrollos de software ágiles, que pueden tener muy pocos movimientos 
de datos. Está bien establecida esta práctica, con muchos informes de los t amaños en CFP 
de iteraciones ágiles (o 'sprints'), agregados de los tamaños de historias de los usuarios 
individuales, que se correlacionan muy bien con el esfuerzo por desarrollar la iteración (y 
mucho mejor que el correlación con el esfuerzo de tamaños medidos usando History Points). 
Ver (https://cosmic-sizing.org/publications/guideline-for-sizing-agile-projects-with-cosmic/).


<!-- pág 25/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 25 
 
 
5. FASE DE MEDICIÓN. 
Orientación sobre la Regla 23: Agregación de tamaños funcionales. 
a) Los tamaños de las piezas de software o de los cambios en piezas de software se pueden 
sumar sólo si mide al mismo nivel de granularidad de su FUR. 
b) Los tamaños de las piezas de software y / o cambios en los tamaños de piezas de software 
dentro de cualquier capa o de diferentes capas se añaden juntos sólo si tiene sentido 
hacerlo, con el propósito de la medición. 
c) El tamaño de una pieza de software se obtiene mediante la suma de los t amaños de sus 
componentes (independientemente de cómo se descompone la pieza) y la eliminación de 
las contribuciones de tamaño de los movimientos de datos entre componentes. 
Dentro de cada capa identificado, la función de agregación es completamente escala ble. Un 
sub-total puede ser generado para procesos funcionales individuales o para todo el proceso 
funcional del software, dependiendo del propósito y alcance de la ejercicio de medición. 
6. INFORMES DE MEDICIÓN. 
El resultado debe ser informado y datos sobre la medición registrada con el fin de garantizar 
que el resultado es siempre inequívoc o interpretables. Resultados de la medición COSMIC 
deben ser reportados y archivados de acuerdo con las siguientes convenciones. 
 
Orientación sobre la Regla 25: etiquetado de medición COSMIC. 
Un resultado de la medición COSMIC se observa como 'x CFP (v)', donde: 
• 'X' representa el valor numérico del tamaño funcional, 
• 'V' representa la identificación de la versión del método COSMIC estándar utilizado para 
obtener el valor de tamaño funcional numérica 'x'. 
NOTA: Si se ha utilizado un método de aproximación local para obtener la medición, pero por 
lo demás se hizo la medición con las convenciones de una versión COSMIC estándar, se 
utiliza la convención de etiquetado anteriorm ente, pero el uso del método de aproximación 
debe señalarse en otros lugares. 
 
Orientación sobre la Regla 25: COSMIC etiquetado extensiones locales. 
Un resultado de la medición COSMIC usando extensiones locales se observa como: 
 'X CFP (v.) + Z FP Local', donde: 
• 'X' representa el valor numérico obtenido por agregación de todos los resultados de 
medición individual de acuerdo con el método COSMIC estándar, versión v,


<!-- pág 26/26 -->

COSMIC Medición Manual - Versión 5.0 - Parte 2: Directrices Copyright © 2020 26 
 
 
• 'V' representa la identificación de la versión del método COSMIC  estándar utilizado para 
obtener el valor de tamaño funcional numérica 'x'.  
• 'Z' representa el valor numérico obtenido mediante la agregación de todos los resultados 
de medición individuales obtenidos a partir de las extensiones locales para el método 
COSMIC.