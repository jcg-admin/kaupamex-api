<!-- Extraído de 0367d186-Part3MMRulesv5.0cENESPA_OL1.pdf (40 págs) por pypdf — 2026-06-03T03:35:05Z. Fuente oficial COSMIC v5.0 / ISO 19761. -->
# COSMIC v5.0 — Parte 3: Reglas (MM Rules)



<!-- pág 1/40 -->

Manual de Medición COSMIC  
para ISO 19761  
 
Parte 3:  
Ejemplos 
 
 
versión 5.0  
31 de marzo de 2020


<!-- pág 2/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 2 
 
 
 
Prefacio. 
El Manual de COSMIC de medición para ISO/IEC 19761: 2011 consta de tres partes: 
Parte 1: Principios, definiciones y reglas. 
Parte 2: Directrices. 
Parte 3: Ejemplos de conceptos COSMIC y mediciones. 
Esta parte 3 del Manual de Medición de COSMIC proporciona ejemplos de mediciones y 
conceptos del método Medida del tamaño funcional COSMIC (el 'Método COSMIC'). Los 
ejemplos se presentan por fase, con una introducción y caracterización de la intención de 
ejemplos en cursiva. 
 
 
Una versión de dominio público de los informes técnicos de medición , manuales y otros, 
incluyendo las traducciones a otros idiomas, se puede encontrar en l a base de 
conocimientowww.cosmic-sizing.org. 
 
 
 
Editores: 
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


<!-- pág 3/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 3 
 
 
 
 
 
 
Derechos de autor 2020. Todos los derechos reservados. El Consorcio Medición Común Internacional 
de Software ( COSMIC). Se permite copiar todos o se concede proporcionado parte de este material 
que las copias no se hacen ni para distribuir ni para obtener una ventaja comercial y que el título de la 
publicación, su número de versión, y su fecha se citan y se da aviso que la copia es con permiso de 
Consorcio Medición Común Internacional de Software (COSMIC). Para copiar otra exija cosa permiso 
específico.


<!-- pág 4/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 4 
 
 
 
Tabla de contenido. 
 
1 INTRODUCCIÓN A LA COSMIC. ................................ ................................ ................ 5 
1.1 Requisitos Funcionales de Usuario. ................................ ................................ ............. 5 
1.2 Requisitos no funcionales (NFR). ................................ ................................ ................. 5 
1.3 El contexto modelo COSMIC software. ................................ ................................ ........ 6 
1.4 El modelo de software genérico. ................................ ................................ .................. 6 
1.5 Tipos frente a las ocurrencias................................. ................................ ...................... 6 
1.6 El proceso de medición COSMIC. ................................ ................................ ................ 7 
2  LA MEDICIÓN ESTRATEGIA DE ELIMINACIÓN. ................................ ....................... 7 
2.1 Propósito de una medición. ................................ ................................ .......................... 7 
2.2 Ámbito de aplicación de una medición. ................................ ................................ ........ 8 
2.3  usuarios funcionales. ................................ ................................ ................................ .... 9 
2.4 Patrones estrategia de medición. ................................ ................................ ................10 
2.5 Capas. ................................ ................................ ................................ .........................10 
2.6 Niveles de descomposición. ................................ ................................ ........................14 
2.7 diagramas de contexto. ................................ ................................ ............................... 14 
2.8 Los niveles de granularidad. ................................ ................................ ........................15 
3  LA FASE DE PROYECCIÓN. ................................ ................................ .....................20 
3.1 procesos funcionales. ................................ ................................ ................................ ..20 
3.2 reata grupos y objetos de interés. ................................ ................................ ...............24 
3.3 Los atributos de datos. ................................ ................................ ................................ 26 
3.4 movimientos de datos. ................................ ................................ ................................ 26 
3.5 manipulaciones de datos asociadas con los movimientos de datos. ...........................35 
3.6  Comandos de control. ................................ ................................ ................................ .35 
3.7 Los mensajes de error / confirmación y otras indicaciones de condiciones de error. ...36 
3.8 La medición de los componentes de un sistema de software distribuido. ....................37 
3.9 La reutilización de software. ................................ ................................ ........................37 
3.10 Medida de la talla de cambios en el software. ................................ .............................39 
3.11 Extendiendo el método de medición COSMIC. ................................ ............................40


<!-- pág 5/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 5 
 
 
 
1 INTRODUCCIÓN A LA COSMIC. 
1.1 Requisitos Funcionales de Usuario. 
Un gran número de ejemplos de Requisitos Funcionales de Usuario (FUR) están 
documentados e n la COSMIC  Estudios de caso  (Disponible gratuitamente en cosmic -
sizing.org). 
1.2 Requerimientos no funcionales (NFR). 
El método COSMIC sólo se utiliza para medir el tamaño de FUR. Requisitos a menudo 
incluyen requisitos de los sistemas no funcionales que no pueden ser medidos por COSMIC. 
Sin embargo, los requisitos del sistema que aparecen inicialmente como NFR pueden 
evolucionar hacia FUR software como avances del proyecto. Por tan to, es importante 
distinguir los dos tipos de requisitos y la evolución de las necesidades. 
NEGOCIO Ejemplo: Los requisitos para un nuevo sistema de software incluye la declaración 
de las necesidades del usuario la opción de archivos seguros mediante la en criptación '. El 
proyecto para desarrollar el sistema se encuentra en la etapa de estimación de esfuerzo y 
costo. Se consideran dos opciones: 
• Desarrollar algún tipo de software de cifrado propietario. Para la estimación de los 
propósitos del proyecto, puede ser necesario para medir el tamaño de los FUR  del 
software de cifrado. 
• Comprar un paquete de programas comerciales off -the-shelf (COTS) exis tente. Para 
los propósitos estimación del proyecto, puede ser necesario medir sólo el tamaño de la 
funcionalidad del software necesario para integrar el paquete COTS. También 
necesitará el costo del paquete y el esfuerzo de integrar y probar el paquete de cifrado 
de archivos para ser considerado en el cálculo del coste del proyecto. 
TIEMPO REAL Ejemplo: Fiabilidad o requisitos de tolerancia a fallos para sistemas 
aeroespaciales se consiguen principalmente a través de una combinación de redundancia y 
de copia de seguridad de los sistemas físicos. Una función, como por ejemplo el control de 
motores, se lleva a cabo en dos o más ordenadores integrados separados. Esta función tiene 
una estricta limitación de tiempo indicado como NFR: 'cada respuesta obligada del equipo 
independiente dentro de un tiempo específico. Si cualquiera de los ordenadores responde en 
varias ocasiones después de la hora requerida, o sus resultados no están de acuerdo con los 
demás, tiene que ser desechado (por un mecanismo especificado com o un requisito 
funcional). Un requisito para la tolerancia a fallos que cuando se expresa inicialmente puede


<!-- pág 6/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 6 
 
 
 
aparecer como no funcional, por lo tanto, se convierte en FUR que se puede medir.  (Ver 
ejemplos en Guía para tamaño de un software en tiempo real, Sección 3.2). 
1.3 El modelo contextual de software de COSMIC. 
ver Estudios de caso en cosmic-sizing.org. 
1.4 El Modelo genérico de Software de COSMIC. 
ver Estudios de caso en cosmic-sizing.org. 
1.5 Tipos frente a las ocurrencias. 
El método COSMIC se refiere únicamente a los tipos de cosas, no con las apariciones de 
cosas que son del mismo tipo. Ya que tiene gran influencia en el tamaño, es de importancia 
crítica aplicar esto a tod as las cosas que se usan en la medición, como los usuarios 
funcionales, objetos de interés, grupos de datos, etc. 
Ejemplos del Modelo Contextual de Software. 
NEGOCIO Ejemplo 1: El sistema de soporte de un Call Center cuenta con 100 empleados 
que contestan preguntas de los clientes. A medida que los empleados están sujetos a los 
mismos requisitos (‘responder a las preguntas del cliente') un modelo contextual del sistema 
incluye el tipo de usuario funcional: 'Call Center' de los empleados de los cuales hay 100 
apariciones. 
EN TIEMPO REAL Ejemplo 1: El software incorporado de una radio digital envía su salida a 
un par de altavoces estéreo. El software envía señ ales separadas del mismo tipo para cada 
uno de los dos altavoces. Cada uno de ellos convierten la señal eléctrica recibida en sonido 
de la misma manera. Un modelo de contexto del software mostraría un tipo de usuario 
funcional 'altavoz' de los cuales hay dos ocurrencias. 
Ejemplos del Modelo genérico de Software. 
NEGOCIO Ejemplo 2: Supongamos que un proceso funcional que permite que a los datos ser 
introducidos y validados para un nuevo cliente. El movimiento de entrada de datos se 
ejecutará, es decir, se producirá una vez, cada vez que un usuario se registra humanos datos 
funcionales para un nuevo cliente. Durante su ejecución, el proceso funcional debe validar los 
datos introducidos mediante la búsqueda para comprobar si el cliente ya existe en la base de 
datos. De ahí que el movimiento lectura datos de esta validación se producirá una o más 
veces (dependiendo del diseño de base de datos). Sin embargo, uno de entrada y uno de 
lectura del cliente se cuenta cuando se mide este proceso funcional.


<!-- pág 7/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 7 
 
 
 
TIEMPO REAL Ej emplo 2: Supongamos  un proceso funcional que debe controlar la 
temperatura de un horno una vez cada segundo diez. El proceso funcional será ejecutado, es 
decir, se producirá una vez cada 10 segundos. Durante su ejecución, el movimiento de salida 
de datos del proceso para cambiar el calentador de encendido o apagado puede o no puede 
ser ejecutado, es decir, que puede o puede no producirse en absoluto en cualquier ciclo, 
dependiendo de si el calentador debe estar encendido o apagado, o dejado en su estado 
actual. El movimiento de salida de datos se cuenta una vez en el proceso funcional, 
independientemente de si se produce en una ejecución particular. 
1.6 El proceso de medición COSMIC 
ver el Estudios de caso en cosmic-sizing.org. 
2 LA FASE DE ESTRATEGIA DE MEDICIÓN 
2.1 Propósito de una medición. 
La medición se realiza para satisfacer las necesidades de información de los interesados. Es 
importante que el medidor entienda este propósito con el fin de que las necesidades de los 
interesados esten satisfechos. 
EJEMPLOS: Los siguientes son ejemplos típicos de propósitos. 
• Para medir el tamaño de la FUR a medida que evolucionan, como entrada a un proceso 
para estimar el esfuerzo de desarrollo. 
• Para medir el tamaño de los cambios a la FUR después de que hayan sido acordadas 
inicialmente, con el fin de gestionar el proyecto, causado por la adición de requisitos y 
cambios. 
• Para medir el tamaño del software entregado , como entrada para la medición del 
desempeño de la organización de desarrollo. 
• Para medir el tamaño del software total entregad o, y también el tamaño del software 
que fue desarrollado, con el fin de obtener una medida de re-uso funcional. 
• Para medir el tamaño del software existente como entrada para la medición de la 
actuación del grupo responsable del mantenimiento y soporte del software. 
• Para medir el tamaño de algunos cambios a un sistema de software existente como 
una medida del tamaño de la obra-salida de un equipo de proyecto de mejora. 
• Para medir el tamaño del subconjunto de la funcionalidad total del software que debe 
ser desarrollado, que se proporcionará a los usuarios humanos funcionales del 
software.


<!-- pág 8/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 8 
 
 
 
2.2 Alcance de una medición. 
El alcance de una medición puede ser la totalidad o parte del software, y depende del 
propósito de la medición. 
NEGOCIO ejemplo: Figura 2.1 muestra todas las piezas separadas de software - 'Alcance 
general' - entregado por un equipo de proyecto: 
• el cliente y los componentes de servidor de un paquete de software de aplicación 
práctica 
• un programa que proporciona una interfaz entre el componente de servidor del nuevo 
paquete y las aplicaciones existentes 
• un programa que se utiliza una vez para convertir los datos existentes al nuevo formato 
requerido por el paquete. Este programa ha sido desarrollado usando una serie de 
objetos reutilizables desarrollados por el equipo de proyecto 
• el software de controlador de dispositivo para el nuevo hardware en el que se ejecutará 
el componente de cliente paquete 
Cada pieza individual de software para el que se define un alcance de la medición se muestra 
como una caja rectangular sólida. 
 
Figura 2.1 - El alcance general de las prestaciones de un proyecto de software y la medición 
individual de alcances. 
Muestra el diagrama de que las piezas entregadas de software consistían en algunas que 
fueron de nuevo desarrollo y algunos que fueron impl ementadas por el equipo del proyecto. 
El propósito es medir los FUR de las piezas individuales de software entregado para ser 
añadido al tamaño de la cartera de software de la organización, teniendo en cuenta el paquete


<!-- pág 9/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 9 
 
 
 
de software en su conjunto, es decir, haciendo caso omiso de la estructura de componentes 
de cliente-servidor. 
El tamaño del paquete implementado se añadió a la del programa de interfaz para actualizar 
el tamaño total de la cartera de aplicaciones de la organización. El tamaño del programa d e 
conversión de datos no era de su interés, ya que se usa una vez y se tira. Pero el tamaño de 
cada uno de los objetos reutilizables se registró en el inventario de software de infraestructura 
de la organización, así como la del nuevo controlador de dispos itivo. Nuevamente, estas se 
clasifican por separado. 
Debido a la naturaleza diversa de los entregables no sería sensato al medir el rendimiento del 
equipo del proyecto en general sumar los tamaños de todo el software entregado. El 
rendimiento de los equipos que entregan cada pieza de software se debe medir por separado. 
Tenga en cuenta también que es normalmente sólo de interés medir el software resultante de 
la aplicación de un paquete, no el propio paquete. Este último es quizá sólo de interés para el 
proveedor del paquete. 
2.3 Usuarios Funcionales. 
Múltiples ocurrencias de un usuario funcional pueden ser responsables de la introducción de 
datos para el mismo proceso funcional. Sin embargo, el método COSMIC se refiere 
únicamente a tipos, no con ocurrencias (véase 1.5). 
NEGOCIO Ejemplo 1: En un sistema de orden es de un número de empleados (usuarios 
funcionales humanos) mantener los datos de las ordenes. Id de un empleado se añade a 
todos los grupos de datos que entran. Identificar el tipo de usuario funcional de un 'empleado' 
debido a que el sistema de órdenes de los FUR son los mismos para todos los empleados. 
TIEMPO REAL Ejemplo 1: Cada rueda de un coche tiene un sensor que obtiene la presión de 
su neumático. A intervalos regulares, un proceso funcional deb e obtener la presión de los 
cuatro neumáticos. Si la presión es demasiado baja o demasiado alta - la gama de presiones 
de seguridad está en el software – el software muestra que neumático tiene un problema de 
presión indicado en un diagrama de las cuatro r uedas en una pantalla de visualización en el 
tablero de instrumentos. Los usuarios funcionales son los cuatro sensores y los cuatro 
indicaciones en la pantalla de visualización. Sin embargo, los cuatro sensores están sujetos 
al mismo requisito (y idem para  las indicaciones en la pantalla), de manera de identificar un 
tipo de usuario  funcional 'sensor' y un tipo de usuario funcional para las indicaciones en la 
pantalla de visualización. 
Los diferentes usuarios funcionales que requieren una funcionalidad diferente.


<!-- pág 10/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 10 
 
 
 
NEGOCIO Ejemplo 2: Un sistema de software tiene la funcionalidad para mantener los datos 
personales básicos accesibles a todo el personal del Departamento de Personal, y los datos 
salariales más sensibles accesible sólo a un subconjunto de este personal. Por lo tanto, este 
software tiene dos tipos de usuarios funcionales. El propósito de una medida de este software 
debe definir si el alcance de la medición se aplica a la funcionalidad accesible a todo el 
personal o se limita a la funcionalidad disponible para uno de los dos tipos de personal. 
Los FUR están escritos desde el punto de vista de sus usuarios funcionales. A medida que 
cada usuario funcional puede percibir un sistema de diferentes maneras, los requisitos se 
expresarán en función de los usuarios funcionales. Es importante que todos los requisitos para 
ser medidos se expresan en el mismo punto de vista funcional para el usuario si sus tamaños 
se van a comparar. 
EN TIEMPO REAL Ejemplo 2: Considere el software incrustado de una copiadora. Usuarios 
funcionales del software podrían definirse en una de dos maneras. Podrían ser (a) el usuario 
humano que quiere hacer copias, o (b) los dispositivos de hardware de la copiadora, es decir, 
los botones de control, una pantalla en la que se muestran los  mensajes para el usuario 
humano, el mecanismo de transporte de papel, los sensores de atasco de papel, el controlador 
de tinta, luces indicadoras, etc., con el que interactúa el software directamente. Estos dos 
tipos de usuarios funcionales, las personas o el conjunto de dispositivos de hardware, ven una 
funcionalidad diferente. El usuario humano, por ejemplo, será consciente de solamente un 
sub-conjunto de la funcionalidad total del software de la copiadora. Los desarrolladores del 
software integrado que impulsa la copiadora tendrán que definir los dispositivos de hardware 
como sus usuarios funcionales. Alternativamente, 1. NO trate de mezclar los dos puntos de 
vista; una medida del tamaño de una visión humana / hardware 'mixta' sería muy difícil de 
interpretar. 
2.4 Patrones estrategia de medición. 
Ver también ejemplos en la Guía para la estrategia de patrones de medición. 
2.5 Capas. 
El software menudo tiene una arquitectura con lo que la funcionalidad se distribuye a través 
de varios componentes. Los componentes se comunican entre sí utilizando mensajes 
siguiendo normas establecidas en sus requisito s. Dentro de una capa, los componentes 
 
1 Toivonen, por ejemplo, se compara el tamaño de la funcionalidad de los teléfonos móviles disponibles sólo para usuarios humanos en 'Definición de medidas de eficiencia de la memoria del software en 
los terminales móviles, Taller Internacional de Software de medición, Magdeburg, Alemania, octubre de 2002.


<!-- pág 11/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 11 
 
 
 
pueden ser semejantes, clientes o servidores. En COSMIC sólo los tamaños de los 
componentes en la misma capa son comparables y pueden ser agregados. 
Ejemplo 1: Las piezas de software en la capa de aplicación de la figura 2.2 son todos 
semejantes entre sí. 
Ejemplo 2: Normalmente en arquitecturas de software, la capa 'superior', es decir, la capa que 
no es un subordinado a cualquier otra capa en una jerarquía de capas, se refiere como la 
capa de 'aplicación'. El software de este capa de aplicación se basa en los servicios de  
software en todas las otras capas para que éste realice correctamente  su función. Software 
en esta capa 'superior' puede ser en sí en capas, por ejemplo, como en una 'arquitectura de 
tres capas' de interfaz de usuario, reglas de negocio y componentes de s ervicios de datos 
(véase el Ejemplo de negocios 2 a continuación). 
NEGOCIO Ejemplo 1: La estructura física de un software típico capas arquitectura de software 
de soporte aplicaciones de negocios se da en la Figura 2.2: 
 
 
Figura 2.2- arquitectura de software en capas típica para un sistema de negocios / MIS.  
TIEMPO REAL Ejemplo 1: La estructura física de una arquitectura de software en capas típica 
de soporte una pieza de software embebido en tiempo real se da en la Figura 2.3. (Nota:. Una 
tarea sencilla en tiempo real de software embebido puede no necesitar un sistema operativo 
en tiempo real)


<!-- pág 12/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 12 
 
 
 
 
Figura 2.3 - arquitectura en capas típica para un sistema de software embebido en tiempo real.  
TIEMPO REAL Ejemplo 2: El modelo ISO de 7 capas (OSI) para las telecomunicaciones. Esto 
define una arquitectura en capas para las cuales las reglas de correspondencia jerárquic as 
para las capas del software de mensaje de recepción son la inversa de las reglas para las 
capas del software de mensaje de transmisión. 
TIEMPO REAL Ejemplo 3: El " AUTOSAR' arquitectura de la industria automotriz que exhibe 
todos los diferentes tipos de reglas de correspondencia entre las capas ahora descritas en los 
principios para una capa. 
 
Figura 2.4 - La estructura de la arquitectura AUTOSAR


<!-- pág 13/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 13 
 
 
 
Una arquitectura de software puede exhibir diferentes capas dependiendo de la 'vista' de la 
arquitectura.  
NEGOCIO Ejemplo 2: Considere una aplicación A situado en una arquitectura de software en 
capas, como en la figura 2.5 a continuación, que muestra tres posibles estructuras de capas 
a), b) y c) de acuerdo con diferentes vistas '' Arquitectura. 
 
 
Figura 2.5 - Tres puntos de vista de las capas de una aplicación. 
Propósito 1 es medir el tamaño funcional de aplicación A 'en su conjunto', como en la vista 
A). El alcance de la medición es el conjunto de aplicación A, que existe completamente dentro 
de la 'aplicación' capa uno 
Propósito 2. Aplicación A ha sido construido de acuerdo a una arquitectura 'de tres capas' 
que comprende una interfaz, reglas de negocio y servicios de datos de usuario componentes. 
Propósito 2 es medir los tres componentes por separado como en la vista B). Cada 
componente se encuentra en su propia capa de la arquitectura y el alcance de la medición se 
debe definir por separado para cada componente. 
Propósito 3. Componente de las reglas de negocio de la aplicación se ha construido utilizando 
componentes reutilizables de una arquitectura orientada a servicios, que tiene su propia 
estructura de capas. Propósito 3 es medir un componente SOA del componente de reglas de 
negocio como en la vista c). Cada componente SOA está situado en una capa de la 
arquitectura SOA y el alcance de la medición se debe definir por separado para cada


<!-- pág 14/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 14 
 
 
 
componente SOA. (Tenga en cuenta que la terminología SOA también utiliza 'capa de 
aplicación' dentro de su propia arquitectura.) 
2.6 Niveles de descomposición. 
El Software puede consistir en varios niveles de componentes, conocidos en COSMIC como 
los niveles de descomposición. Es importante medir a nivel de descomposición apropiado para 
la finalidad de la medida, como los tamaños de los componentes de una pieza de software 
sólo son directamente comparables para los componentes en el mismo nivel de 
descomposición. 
Ejemplo: La Guía para Patrones de 'estrategia de medición' reconoce tres niveles estándar de 
descomposición: 'Toda la aplicación', 'Componente Principal' y 'Componente minoritario'. 
Véase el ejemplo de negocios 2 de arriba, donde se muestran los tres niveles en la Figura 
2.5. 
2.7 Diagramas de Contexto. 
Un diagrama de contexto es útil para visualizar el software a ser medido en el contexto de sus 
usuarios funcionales y almacenamiento persistente. 
NEGOCIO Ejemplo: La figura 2.6 muestra el diagrama de contexto para el software de cliente 
/ servidor del paquete de aplicación implementado como en el ejemplo mostrado en la Figura 
2.1, que se mide como un 'todo', es decir, el hecho de que el paquete de aplicación tiene dos 
componentes (cliente y servidor) es para ser ignorado para esta medición del paquete. 
 
Figura 2.6 - diagrama de contexto para la aplicación cliente-servidor.


<!-- pág 15/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 15 
 
 
 
TIEMPO REAL ejemplo: Figura 2.7 muestra el diagrama de contexto para un sistema de  
intruso con alarma incorporada. 
 
Figura 2.7 - diagrama de contexto para el software embebido de un sistema de alarma de 
intrusión. 
2.8 Los niveles de granularidad. 
En las primeras etapas de desarrollo, los requisitos evolucionan a medida que la información 
se recopila y se aumenta la comprensión. En los procesos funcionales indiv iduales en las 
primeras etapas, y la información necesaria para identificar y medir ellos pueden no estar allí. 
En este caso, el tamaño puede ser  aproximado a través de una variedad de métodos, consulte 
el “Early Software Sizing with COSMIC: Guidelines”. Requisitos funcionales en un mayor nivel 
de granularidad describen por ejemplo, grupos de usuarios funcionales, en lugar de los seres 
humanos individuales o dispositivos de ingeniería individuales o piezas individuales de 
software. 
Cuando los requisitos para una medición COSMIC están presentes, los requisitos deben tener 
el llamado nivel de granularidad de proceso funcional. Por tanto, es importante asegurarse de 
que los requisitos estan a este nivel de granularidad antes de que comience la medición. 
Ejemplo: Un grupo de usuarios funcionales podría ser un 'departamento' cuyos miembros 
pueden manejar muchos tipos de procesos funcionales, o un 'panel de control' que tiene 
muchos tipos de instrumentos, o sistemas centrales. 
Un grupo de eventos podría ser indica do en un comunicado de requisitos funcionales a un 
alto nivel de granularidad por un flujo de entrada a un sistema de software de contabilidad con


<!-- pág 16/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 16 
 
 
 
la etiqueta ''operaciones de venta ” o mediante un flujo de entrada a un sistema de software 
de aviónica 'comandos'. 
EJEMPLO EN TIEMPO REAL: para ver un ejemplo de dimensionamiento en distintos niveles 
de granularidad y descomposición, consulte el ejemplo del sistema de telecomunicaciones en 
el Dimensionamiento temprano de software con COSMIC: Directrices para expertos. 
EJEMPLO EMPRESARIAL: El ejemplo, del dominio del software de aplicación empresarial, 
forma parte de un sistema bien conocido para ordenar productos por Internet, que llamaremos 
la "Aplicación de pedido Everest". El propósito de este ejemplo es ilustrar diferentes niveles 
de granularidad y que los procesos funcionales pueden revelarse en diferentes niveles ". La 
descripción a continuación está muy simplificada para los propósitos de esta ilustración de 
niveles de granularidad. 
Si quisiéramos medir esta aplicación, podríamos asumir que el propósito de la medición es 
determinar el tamaño funcional de la parte de la aplicación disponible para los usuarios 
humanos del cliente (como "usuarios funcionales"). Lue go definiríamos el alcance de la 
medición como "las partes de la aplicación Everest accesibles a los clientes para ordenar 
productos por Internet". Sin embargo, tenga en cuenta que el propósito de este ejemplo es 
ilustrar diferentes niveles de granularidad. Por lo tanto, exploraremos solo algunas partes de 
la funcionalidad total del sistema suficientes para comprender este concepto de niveles de 
granularidad. Este ejemplo trata sobre los niveles de granularidad del FUR; no dice nada sobre 
una posible descomposición del software subyacente. 
En el "Nivel 1 (Función principal)" más alto de esta parte de la solicitud, una declaración de 
los requisitos de la Solicitud de pedido de Everest sería una declaración resumida simple 
como la siguiente. 
"La solicitud de pedido de Everest debe permitir a los clientes consultar, seleccionar, ordenar, 
pagar y obtener la entrega de cualquier artículo de la gama de productos de Everest, incluidos 
los productos disponibles de terceros proveedores". 
Al acercarnos a esta declaraci ón de nivel más alto de los requisitos, encontramos que en el 
próximo nivel inferior 2, la Aplicación de pedido de Everest consta de cuatro subfunciones,  
como se muestra en la Figura 2.8 (a).


<!-- pág 17/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 17 
 
 
 
 
Figura 2.8 (a) - Análisis del sistema de pedidos Everest: los  dos primeros niveles de 
granularidad. 
Los requisitos de las cuatro subfunciones son: 
• La subfunción Consulta / Pedido, que permite al cliente encontrar cualquier producto 
en la base de datos de Everest, así como su precio y disponibilidad, y agregar cualquier 
producto seleccionado a una "cesta" para su compra. Esta subfunción también 
promueve las ventas al sugerir ofertas especiales, ofrecer revisiones de artículos 
seleccionados y permitir consultas generales tales como condiciones de entrega, etc. 
Es una subfunción muy compleja. Por lo tanto, no analizamos esta subfunción con más 
detalle por debajo del nivel 2 para los propósitos de este ejemplo. 
• La subfunción Pagar / Pagar, que permite al cliente comprometerse a ordenar y pagar 
los productos en la cesta. 
• La subfunción de seguimiento de pedidos que permite a un cliente preguntar cuánto ha 
progresado un pedido existente en el proceso de entrega, mantener su pedido (por 
ejemplo, cambiar la dirección de entrega) y devolver productos insatisfactorios. 
• La subfunción Mantenimiento de cuenta que permite a un cliente existente mantener 
varios detalles de su cuenta, como la dirección de su casa, los medios de pago, etc.  
 
 
Las Figuras 2.8 (b) y (c) muestran algunos detalles revelados cuando ampliamos los 
requisitos, reducimos un nivel adicional de granularidad en la subfunción Pago / Pago, la 
subfunción Seguimiento del pedido y la subfunción Mantenimiento de la cuenta. En este 
proceso de acercamiento es importante tener en cuenta que: 
• no hemos cambiado el alcance de la funcionalidad a medir, y


<!-- pág 18/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 18 
 
 
 
• todos los niveles de la descripción de la aplicación Everest muestran la funcionalidad 
disponible para los clientes (como usuarios funcionales). Un cliente puede "ver" la 
funcionalidad de la aplicación en todos estos niveles de granularidad. 
 
Figura 2.8 (b) - Análisis de la subfunción Pedido. 
 
 
Figura 2.8 (c) - Análisis de la Sub-función de Seguimiento de Orden y Mantenimiento de la 
cuenta. 
La Figura 2.8 (c) ahora revela que cuando nos acercamos al nivel 3 inferior de este análisis 
particular de la subfunción de Seguimiento de la Orden, encontramos dos procesos 
funcionales individuales en el nivel 3 (para dos consultas de la orden de seguimie nto- 
Subfunción). Se revelarían más procesos funcionales si continuamos el refinamiento de las 
sub-subfunciones de Nivel 3 a niveles más bajos. Este ejemplo demuestra, por lo tanto, que 
cuando alguna funcionalidad se refina en un enfoque 'de arriba hacia a bajo', no se puede 
suponer que la funcionalidad que se muestra en un 'nivel' particular en un diagrama siempre 
corresponderá al mismo 'nivel de granularidad' que Este concepto se define en el método 
COSMIC. (Esta definición requiere que en cualquier nivel de granularidad la funcionalidad esté 
"en un nivel de detalle comparable").


<!-- pág 19/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 19 
 
 
 
Además, otros analistas podrían muy bien dibujar los diagramas de forma diferente, 
mostrando otras agrupaciones de funcionalidad en cada nivel del diagrama. No hay una sola 
manera 'correcta' de hacer zoom sobre la funcionalidad de un sistema tan complejo. 
Teniendo en cuenta estas variaciones que inevitablemente se producen en la práctica, un 
medidor debe examinar cuidadosamente los diversos niveles de un diagrama de análisis para 
encontrar los procesos funcionales que se deben medir. Cuando en la práctica e sto no es 
posible, por ejemplo, porque el análisis aún no ha alcanzado el nivel en todos los procesos 
funcionales se han puesto de manifiesto, se debe aplicar un método de aproximación. Para 
ilustrar esto, examinemos el caso de la 'sub-sub-función Mantener detalles del cliente' (véase 
la figura 2.8 (c) anterior), en la rama de la sub-función de mantenimiento de cuentas. 
Para un Medidor experimentado, la palabra "mantener" sugiere casi invariablemente un grupo 
de eventos y, por lo tanto, un grupo de procesos funcionales. Por lo tanto, podemos suponer 
que esta subfunción "Mantener" debe comprender tres procesos funcionales, a saber, una 
"consulta sobre los detalles del cliente", "actualizar los detalles del cliente" y "eliminar los 
detalles del cliente". (El p roceso de "creación de detalles del cliente" también debe existir 
obviamente, pero esto ocurre en otra rama del sistema, cuando un cliente ordena productos 
por primera vez. Está fuera del alcance de este ejemplo simplificado). 
Un medidor experimentado debe ría ser capaz de 'estimar' un tamaño de esta subfunción 
secundaria en unidades de puntos de función COSMIC tomando la cantidad supuesta de 
procesos funcionales (tres en este caso) y multiplicando esta cantidad por el tamaño promedio 
de una función proceso. Este tamaño promedio se obtendría por calibración en otras partes 
de este sistema o en otros sistemas comparables. Se dan ejemplos de este proceso de 
calibración en el documento "Tamaño del software inicial con COSMIC: Guía de expertos", 
que también contiene otros ejemplos de otros enfoques para el tamaño aproximado. 
Claramente, tales métodos de aproximación tienen sus limitaciones. Si aplicamos este 
enfoque a la declaración de nivel 1 de los requisitos que se dieron anteriormente ( 'La 
aplicación Everest debe permitir a los clientes realizar la consulta y seleccion, el orden de 
pago y obtener la entrega de cualquier elemento de la gama de productos de Everest ....'), 
Que podría identificar algunos procesos funcionales. Sin embargo, un análisis más detallado 
revelaría que el número real de los procesos funcionales en esta aplicación compleja debe 
ser mucho mayor. Por eso tamaños funcionales suelen aparecer a aumentar a medida que se 
establecen más detalles de los requisitos, incluso sin cambios en el alcance . Por lo tanto, 
estos métodos de aproximación se deben utilizar con gran cuidado a altos niveles de 
granularidad, cuando muy pocos detalles están disponible.


<!-- pág 20/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 20 
 
 
 
3 LA FASE DE MAPEO. 
3.1 procesos funcionales. 
En el método COSMIC, la identificación de los procesos funcionales es esencial si una medida 
correcta de tamaño se ha de obtener. Los siguientes son ejemplos de cómo los procesos 
funcionales pueden ser identificados. 
Un usuario funcional humano introduce datos, que inician un proceso funcional. 
NEGOCIO EJEMPLO 1: en una empresa, se recibe un pedido (evento desencadenante), lo 
que hace que un empleado (usuario funcional) ingrese los datos del pedido (desencadenando 
datos de transmisión de entrada sobre el objeto 'orden' de interés), como el primer movimiento 
de datos del proceso funcional 'entrada de orden'. 
NEGOCIO Ejemplo 2: Un proceso funcional de un sistema de software personal puede ser 
iniciado por la entrada desencadenante que mueve un grupo de datos que describe un nuevo 
empleado. El grupo de datos se genera por un usuario humano funcional del software personal 
que introduce los datos. 
Un dispositivo funcional transmite datos de usuario, que se inicia un proceso funcional. 
TIEMPO REAL Ejemplo 1: Un proceso funcional de un sistema de software en  tiempo real 
puede ser iniciado por su entrada desencadenante informar al proceso funcional que un reloj 
(usuario funcional) ha marcado. El grupo de datos que se movió transmite (quizás a través de 
un solo bit) que sólo informa de que ha ocurrido un evento. 
TIEMPO REAL Ejemplo 2: Un proceso funcional de un sistema de software de detección de 
incendios en tiempo real industrial puede ser iniciado por su entrada desencadenante iniciada 
por un detector de humo específico (usuario funcional). El grupo de datos generada por el 
detector transmite la información 'humo detectado' (se ha producido un evento) e incluye el ID 
de detector (es decir, datos que pueden utilizarse para determinar dónde ocurrió el evento). 
TIEMPO REAL Ejemplo 3: Un lector de código de barras  (un usuario funcional) en una caja 
de un supermercado inicia un análisis cuando aparece un código de barras en la ventana (el 
evento desencadenante). El lector genera un grupo de datos, que comprende una imagen del 
código de barras que es introducida en el software de pago. La imagen de grupo de datos es 
movida por una entrada desencadenante en su proceso funcional. Este último se suma el 
costo del producto a la cuenta del cliente si el código es válido, suena un pitido para informar 
al cliente de que el producto ha sido aceptada, y registra la venta, etc. 
Identificar eventos desencadenantes por separado - y por lo tanto los procesos funcionales 
separados - cuando un usuario humano funcional toma decisiones fuera del software en 'qué


<!-- pág 21/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 21 
 
 
 
hacer a continuación' q ue son independientes en el tiempo y que requieren respuestas 
separadas de software. 
NEGOCIO Ejemplo 3: Un usuario funcional entra en un pedido de cliente para un elemento 
de equipo industrial complejo y más tarde confirma la aceptación del pedido al clien te. Entre 
entrar en el orden y aceptarla, el usuario puede realizar una consulta sobre si el nuevo pedido 
pueda ser entregado en la fecha de entrega solicitada, y sobre la solvencia del cliente, etc. A 
pesar de la aceptación de un pedido debe seguir entrada de una orden, en este caso el usuario 
debe tomar una decisión separada para aceptar el pedido. Esto indica procesos funcionales 
separados para la entrada de  la orden y para la aceptación del pedido (y para cada una de 
las consultas). 
Identificar eventos desencadenantes separados y separar procesos funcionales cuando se 
separan las responsabilidades para las actividades. 
NEGOCIO Ejemplo 4: En un sistema de personal donde la responsabilidad de mantener datos 
personales básicos se separa de la responsabilidad del mantenimiento de datos de la nómina 
indicando usuarios funcionales separad os, cada una con sus propios procesos funcionales 
separados. 
NEGOCIO Ejemplo 5: Supongamos que en el recibo de un pedido en el Ejemplo de negocios 
1, se requiere la aplicación de procesamiento de pedidos para enviar los detalles de cualquier 
nuevo cliente para una aplicación de registro de clientes central, que se está mid iendo. La 
aplicación de procesamiento de pedidos es, pues, un usuario funcional de la aplicación 
central. La aplicación de procesamiento de pedidos, tras haber recibido datos sobre un nuevo 
cliente, genera el grupo de datos de cliente que envía a la aplica ción de registro del cliente 
central que desencadena un proceso funcional para almacenar estos datos. 
Cuando se mide el tamaño de los procesos funcionales, no se debe hacer ninguna diferencia 
si se requiere que el proceso funcional para ser procesado en línea o en modo por lotes. 
NEGOCIO Ejemplo 6: Supongamos que las órdenes en el ejemplo de negocios 1 
anteriormente son introducidos por un proceso 'off -line' de alguna manera, por ejemplo, por 
exploración óptica de documentos en papel, y se almacenan temporalmente para el 
procesamiento automático por lotes. ¿Cómo es esto de entrada de pedidos , que proceso 
funcional analizó si se va a procesar por lotes? El usuari o funcional es el humano que hace 
los datos con el fin de ser introducido fuera de línea listo para ser procesado en modo por 
lotes; la entrada desencadenante del proceso funcional que va a procesar las órdenes en 
modo por lotes es el movimiento de datos q ue mueve el grupo de datos de orden en el 
proceso. El proceso fuera de línea, si se debe medir, implica otro, proceso funcional separado 
que carga la orden de almacenamiento temporal.


<!-- pág 22/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 22 
 
 
 
 
Figura 3.1 - El procesamiento por lotes del Ejemplo de negocios 4 
NEGOCIO Ejemplo 7: FUR Supongamos por fin de año  el objetivo de aplicación de lote 
procesado es dar a conocer el resultado del negocio para el año, y para restablecer las 
posiciones para el inicio del próximo año. Físicamente, un pulso de reloj de fin de año 
generada por el sistema operativo hace que la aplicación  inicie el procesamiento. 
Lógicamente, sin embargo, cada proceso funcional de la aplicación toma sus datos de entrada 
de la corriente de datos a ser lotes procesados. Esto debe ser analizada de la manera normal 
(por ejemplo, los datos de entrada para cualquier proceso funcional comprenden  una o más 
entradas, la primera de las cuales es la entrada desencadenante para ese proceso). 
Sin embargo, suponga que hay un proceso funcional particular de la aplicación de lote -
procesado que no requiere ningún dato de entrada para producir su conjunto de informes. 
Físicamente, el (human o) funcional para el usuario ha delegado en el sistema opera tivo la 
tarea de desencadenar este proceso funcional. Puesto que cada proceso funcional debe tener 
una entrada desencadenante, podemos considerar el ciclo de reloj de fin de año en el que 
comenzó la corriente de proceso por lotes para llenar este papel durante este proceso. Este 
proceso funcional puede entonces necesitar varias lecturas y muchas salidas para producir 
sus informes. Lógicamente, el análisis de este ejemplo no es diferente si el usuario funcional 
humano inicia la producción de uno o más inform es a través de un clic del ratón sobre un 
elemento de menú en línea, en lugar de delegar la activación de la producción de informes en 
el modo por lotes para la operación sistema. 
En el dominio de aplicaciones en tiempo real un sensor normalmente desencade na un 
proceso funcional. 
TIEMPO REAL Ejemplo 5: Cuando un sensor (usuario funcional) detecta que la temperatura 
alcanza un determinado valor (evento desencadenante), el sensor envía una señal para iniciar 
un movimiento de datos de entrada desencadenante de un proceso funcional para apagar un 
calentador (otro funcional usuario).


<!-- pág 23/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 23 
 
 
 
EN TIEMPO REAL Ejemplo 6: Un avión militar tiene un sensor que detecta el evento 'misil 
que se aproxima'. El sensor es un usuario funcional del software que debe responder a la 
amenaza. Para este programa, un evento ocurre sólo cuando el sensor detecta algo, y es que 
el sensor (el usuario funcional) que genera un grupo de datos para iniciar una entrada 
desencadenante diciendo, por ejemplo, 'el sensor 2 ha detectado un misil', además de quizás 
una corriente de datos acerca de la rapidez con que el misil se acerca y sus coordenadas. 
Identificar los procesos funcionales sobre la base de la organización de la entrada de datos o 
examinar los menús de algún tipo de software instalado. 
NEGOCIO Ejemplo 8: Supongamos que hay un requisito de usuario funcional para dos tipos 
de beneficios sociales, en primer lugar, para un niño adicional y el segundo un 'crédito fiscal' 
para los de bajos ingresos. Estos son los requisitos para el software responder a dos eventos 
que están separados en el mundo de los usuarios funcionales humanos. Por lo tanto, debe 
haber dos procesos funcionales, a pesar de que un único formulario de impuestos puede 
haber sido utilizado para capturar los datos para ambos casos. 
Identificar sólo los movimientos de datos de un proceso funcional; las diversas rutas de 
procesamiento en las que pueden ocurrir no conducen a separar procesos funcionales. 
NEGOCIO Ejemplo 9: Un proceso funcional que proporciona una capacidad de búsqueda 
general contra una base de datos puede ser obligado a aceptar hasta cuatro parámetros de 
búsqueda (atributos de su entrada desencadenante ). Pero el mismo proceso funcional 
funcionará si, se introducen dos o tres parámetros de búsqueda de los valores o una sola. 
NEGOCIO Ejemplo 10: Para un proceso funcional para registrar un nuevo cliente de una 
empresa de alquiler de coche, es obligatorio introducir datos para la mayoría de los atributos 
de datos, pero algunos (por ejemplo, algunos datos de contacto) son opcionales y puede estar 
en blanco. Independientemente de si se introducen todos o un subconjunto de estos atributos 
sólo hay un proceso funcional para el registro de un nuevo cliente. 
NEGOCIO Ejemplo 11: Continua del Ejemplo 10, para el proceso funcional para h acer una 
reserva de alquiler de coches en la misma empresa, hay varias opciones que puede o no 
puede ser recibido, por ejemplo, para un seguro adicional, conductores adicionales, las 
solicitudes de los asientos para niños, etc. Estas diferentes opciones co nducen a diferentes 
rutas de procesamiento dentro del proceso funcional alquiler de coches, pero todavía hay sólo 
un proceso funcional para reservar un alquiler de coches. 
EN TIEMPO REAL Ejemplo 12: Uno que facilitará la entrada (información de altitud de la 
aeronave enviado por el Sistema de Posicionamiento Geográfico) a un proceso funcional de 
un sistema de aviónica dará lugar a una de las dos rutas de procesamiento muy diferentes 
dentro del proceso funcional dependiendo del valor de la entrada, es decir,  si la altitud está


<!-- pág 24/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 24 
 
 
 
por encima o por debajo de una altura dada. Los diferentes caminos mostrarán diferentes 
grupos de datos en el mapa del piloto y, si la altura es demasiado baja, se emitirán 
advertencias adicionales. Sólo hay un proceso funcional. 
3.2 Grupos de Datos y Objetos de Interés. 
Grupos de Datos y Objetos de Interés se insertan en varias formas en el texto de los requisitos. 
Es responsabilidad de la persona que mide identificarlos dentro del contexto del proceso 
funcional que se está midiendo. 
Ejemplo 1: En la práctica, un grupo de datos puede tener muchos orígenes, por ejemplo: 
a) Una estructura de datos en un dispositivo de almacenamiento de hardware (archivo, tabla 
de base de datos, memoria ROM, etc.). 
b) Una estructura de datos dentro de la memoria volátil del ordenador (estructura de datos 
asignada dinámicamente o a tra vés de un bloque de pre -asignado de espacio de 
memoria). 
c) Una presentación agrupada de atributos de datos funcionalmente relacionadas en un 
dispositivo de entrada / salida (pantalla de visualización, informe impreso, de visualización 
de panel de control, etc.). 
d) Un mensaje en la transmisión entre un dispositivo y un ordenador, o sobre una red, etc. 
Ejemplo 2: Memoria de sólo lectura es el almacenamiento persistente si la recuperación de 
sus datos es requerida por el FUR. 
NEGOCIO Ejemplo 1: En el dominio de software de aplicación comercial, un objeto de interés 
podría ser 'empleado' (físico) u 'orden' (conceptual). En el caso de 'orden', se sigue 
comúnmente a partir de los FUR  de las órdenes de múltiples líneas que se identifican dos 
objetos de interés: 'orden' y 'orden online'. Los grupos de datos correspondientes podrían ser 
nombrados 'datos de la orden', y 'datos de pedido online'. 
NEGOCIO Ejemplo 2: Supongamos FUR para un proceso funcional especial de investigación 
en una base de datos personal para averiguar el número de empleados mayores de una 
determinada edad, que deben ser ingresados. El parámetro de entrada (el límite de edad) es 
un grupo de datos que define un objeto de interés 'el conjunto de empleados de más del límite 
dado'. El grupo de datos de salida, que comprende el recuento de los empleados de más del 
límite dado describe el mismo objeto de interés que la entrada. 
NEGOCIO Ejemplo 3: Supongamos que la misma consulta ad hoc contra una base de datos 
personal como en el Ejemplo de negocios 2, pero además de la salida del número total de los 
empleados sobre el límite de edad dada, la investigación también tiene que anotar los 
nombres de todos los empleados mayores del límite. El análisis es igual que para el Ejemplo


<!-- pág 25/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 25 
 
 
 
de negocios 2 pero el proceso funcional debe ahora mostrar dos grupos de datos: el recuento 
de los empleados y la lista de nombres de los empleados sobre el límite de edad dada 
(derivado de los datos persistente). Estos deben ser de dos grupos de datos separados porque 
tienen diferentes frecuencias de ocurrencia (un cargo de empleados de uno, uno o más 
nombres de los empleados). 
NEGOCIO Ejemplo 4: Una estructura de datos común representa objetos de interés que se 
mencionan en los FUR, que puede ser manejada por procesos funcionales, y que es accesible 
a la mayoría de los procesos funcionales que se encuentra en el software medido. 
Identificación de los grupos de datos y objetos de interés en el dominio de software en tiempo 
real. 
TIEMPO REAL Ejemplo 1: Un grupo de datos que ingresa software desde un dispositivo físico 
informa sobre el estado actual del dispositivo. En este caso, el dispositivo es el objeto de 
interés (y usuario funcional) y el grupo de datos transmite su estado, como que una válvula 
está abierta o cerrada, lo que lleva al inicio de un proceso funcional. El dispositivo físico es el 
objeto de interés. De manera similar, una salida de grupo de datos a un dispositivo, como 
encender o apagar una lámpara de advertencia, transmite datos de estado sobre el objeto de 
interés de la lámpara. 
Ejemplo 2 TIEMPO REAL-: Un sistema de software de cambio de mensajes puede recibir un 
grupo de datos de mensaje como entrada y enrutarlo hacia adelante sin cambios como salida, 
según el FUR de la pieza de software en particular. Los atributos del grupo de datos del 
mensaje podrían ser, por ejemplo, "ID del mensaje, ID del remitente, ID del destinatario, 
código de ruta y contenido del mensaje"; El objeto de interés del mensaje es "mensaje". 
TIEMPO REAL Ejemplo 3: Una estructura de datos de referencia representa objetos de interés 
cuyos valores de atributo se dan en tablas que se encuentran en el FUR, y que se mantienen 
en la memoria permanente (memoria ROM, por ejemplo) y accesibles a la mayoría de los 
procesos funcionales que se encuentran en el software medido. 
EN TIEMPO REAL Ejemplo: 4: Los archivos, comúnmente designados como "archivos 
planos", representan objetos de interés mencionados en el FUR, que se almacenan en un 
dispositivo de almacenamiento. 
Un usuario funcional puede ser un objeto de interés. 
NEGOCIO Ejemplo 5: Un usuario funcional humano entra un ID y una contraseña en un 
proceso de inicio de sesión para identificarse a sí mismo / ella misma a un sistema. El objeto 
de interés del grupo de datos introducido es el usuario humano.


<!-- pág 26/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 26 
 
 
 
TIEMPO REAL Ejemplo 5: Supongamos que un sensor de temperatura A envía una medida 
de la temperatura actual de un material para su procesamiento por un proceso funcional. El 
sensor proporciona información acerca de su propio estado y es  por tanto objeto de interés 
del grupo de datos de información. 
3.3 Los atributos de datos. 
El método COSMIC no requiere directamente identificación de los atributos  de datos 
asociados con un grupo de datos. Sin embargo, la orientación sobre las Normas 13 y 14 - los 
movimientos de datos de únicos en la sección 3.4 de la parte 2 requiere el examen de los 
atributos de datos. 
NEGOCIO Ejemplo: Un objeto de interés 'empleado' puede ser descrito por un grupo de datos 
denominada ' datos de empleado ', que contiene los atributos de datos 'ID de empleado', 
'Nombre', 'Dirección', 'Fecha de nacimiento', 'Sexo ', 'estado civil', 'número de seguridad 
social', 'grado', 'Profesión', etc.  
EJEMPLOS EN TIEMPO REAL: Un sensor de temperatura puede, previa solicitud, reportar el 
atributo 'Temperatura'. Un sensor de un sistema de seguridad puede detectar un intruso y 
enviar el atributo 'Movimiento detectado'. Un mensaje de la transmisión puede consistir en los 
atributos 'de (dirección), a (dirección), contenido'. 
 
 
3.4 Movimientos de datos. 
El movimiento de datos (s) y el tic de reloj. 
TIEMPO REAL Ejemplo 1: Para un evento de tic de reloj ocurre cada 3 segundos, identificar 
una entrada de mover un grupo de datos de un atributo de datos. El objeto de interés (y usuario 
funcional) es el reloj, el grupo de datos transmite el estado del reloj. 
El movimiento de datos (s) y la obtención de la fecha y / u hora del reloj del sistema. 
NEGOCIO Ejemplo 1: Cuando un proceso funcional añade una marca de tiempo a un registro 
que se hizo persistente o de salida  no se identifica ninguna entrada. Por convención, la 
obtención de valor del reloj del sistema es una funcionalidad que se pone a disposición por el 
sistema operativo a todos los procesos funcionales. 
El movimiento de datos (s) y cualquier dato que no están relacionados a un objeto de interés 
para un usuario funcional.


<!-- pág 27/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 27 
 
 
 
NEGOCIO Ejemplo 2: no se identifican los movimientos de datos para mover datos de 
aplicación general como los encabezados y pies de página (nombre de la empresa, nombre 
de la aplicación, fecha del sistema, etc.) que aparecen en todas las pantallas.  
NEGOCIO Ejemplo 3: no se identifican los movimientos de datos para mover los comandos 
de control (un concepto definido sólo en el dominio de aplicación de negocios) que permite a 
un usuario funcional para controlar su uso del software, en lugar de mover datos, por ejemplo, 
la página arriba / abajo comandos, al hacer clic en 'Aceptar' para confirmar un mensaje de 
error, etc., véase más adelante la sección 3.6). 
El movimiento de datos (s) para todos los datos que describen cualquier objeto de interés. 
NEGOCIO Ejemplo 4: El caso más común es que una escritura sería identificada que mueve 
un grupo de datos que contiene todos los atributos de datos de un objeto de interés que se  
ha hecho persistente en un proceso funcional dado.  
El movimiento de datos (s) cuando diferentes usuarios funcionales mueven diferentes grupos 
de datos que describen el mismo objeto de interés. 
TIEMPO REAL Ejemplo 2: Un proceso funcional se requiere para aceptar diferentes grupos 
de datos a partir de dos sensores diferentes (usuarios funcionale s) cada respondiendo al 
mismo evento, por ejemplo, una explosión. Identificar dos entradas. 
NEGOCIO Ejemplo 5: Existen FUR supongamos por un solo proceso funcional para producir 
dos o más salidas en movimiento de diferentes grupos de datos que describen el mismo objeto 
de interés, destinados a diferentes usuarios funcionales: por ejemplo, cuando un nuevo 
empleado se une a una empresa un informe se produce para ser pas ado al empleado para 
firmar sus datos personales como válido, y un mensaje se envía a la Seguridad para autorizar 
al empleado a entrar en el edificio. Identificar dos salidas. 
El movimiento de datos (s) para mover los diferentes grupos de datos que describen el mismo 
objeto de interés para / desde el almacenamiento persistente. 
NEGOCIO Ejemplo 6 : Supongamos por un solo proceso funcional A para almacenar dos 
grupos de datos derivados a partir de archivos de cuenta corriente de un banco para su uso 
posterior por programas separados. El primer grupo de datos es 'de la cuenta en descubierto' 
detalles (que incluye el atributo saldo negativo). El segundo grupo de datos es de 'alto valor 
de la cuenta detalles (que solo tiene el nombre y la dirección del titular de la cuenta, destinado 
a una comercialización de envió de correos). Proceso funcional A tendrá dos escrituras, uno 
para cada grupo de datos, a pesar de describir el mismo objeto de interés 'cuenta'.  
NEGOCIO Ejemplo 7: Supongamos un programa para combinar dos archivos de datos 
persistentes que describen el mismo objeto de interés, por ejemplo, un fichero de datos 
existentes sobre un objeto de interés 'X' y un archivo con atributos definidos recién describir


<!-- pág 28/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 28 
 
 
 
el mismo objeto de intereses 'X'. Identificar dos lecturas, una para cada archivo, para el 
proceso funcional. 
El movimiento de datos (s) para o currencias repetidas de cualquier movimiento datos que 
describen el mismo objeto de interés. 
NEGOCIO Ejemplo 8: Supongamos que un a lectura de un grupo de datos se requiere en el 
FUR, pero el desarrollador decide ponerlo en práctica por dos comandos para re cuperar 
diferentes sub-conjuntos de atributos de datos para el mismo objeto de interés por parte de 
almacenamiento persistente en diferentes puntos de la proceso funcional. Identificar un  
movimiento de lectura. 
NEGOCIO Ejemplo 9: Supongamos que una lectura se requiere en el FUR que en la práctica 
requiere muchas ocurrencias de recuperación, como en una búsqueda a través de un archivo. 
Identificar una lectura. 
TIEMPO REAL Ejemplo 3: Supongamos que, en un proceso funcional en tiempo real, la FUR 
requiere que el mismo grupo de datos idénticos debe introducirse de un usuario funcional 
dado, por ejemplo, un dispositivo de hardware, dos veces en un intervalo de tiempo fijo con el 
fin de medir una tasa de cambio durante el proceso. En COSMIC los dos movimi entos de 
datos se consideran como múltiples ocurrencias de la misma entrada. Sólo una entrada puede 
ser identificada para este grupo de datos para este proceso funcional . Tenga en cuenta que 
no hay manipulación de datos asociada con las dos apariciones de la entrada, el cálculo de la 
tasa de cambio está asociado con la salida que informa de la tasa. 
TIEMPO REAL Ejemplo 4: Supongamos que un sistema de control de proceso para una 
máquina que produce un producto plano tal como papel o una película de plástico. La máquina 
tiene un conjunto de 100 sensores idénticos a través de la dirección de movimiento del 
producto para detectar roturas o agujeros en el producto. El proceso funcional que debe 
comprobar si hay roturas o agujeros recibe los mismos datos de cada sensor. La posición de, 
por ejemplo, un agujero en el producto puede ser determinada a partir de la posición en la 
cadena de valores de datos enviado desde el conjunto de sensores, el procesamiento de los 
datos de todos los sensores de la matriz es idéntico. Identificar un usuario funcional para todos 
los sensores y una entrada para los datos obtenidos de todos los sensores por el proceso 
funcional. 
El movimiento de datos cuando se muestra un mensaje de texto fijo. 
NEGOCIO Ejemplo 10: Para el resultado de pulsar un botón de 'Términos y Condiciones' (por 
ejemplo, en un sitio web comercial) identificar una salida para la salida de texto fijo. 
El movimiento de datos (s) cuando se requiere un proceso funcional para mover un grupo de 
datos del almacenamiento persistente.


<!-- pág 29/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 29 
 
 
 
Ejemplo 1: Este ejemplo se refiere a una pieza de software A que se requiere para recuperar 
un grupo de datos almacenados en la que el FUR del software A no tienen que ver con la 
forma en que esos accesos de datos son manejados por cualquier otro software en la misma 
o diferentes capas.  
Los usuarios funcionales del software A podría ser, por ejemplo, usuarios humanos si el 
software A es tá en la capa de aplicación realizando una consulta en un grupo de datos 
almacenado. La figura 3.2 muestra los movimientos de datos COSMIC durante esta 
investigación. La investigación se desencadena por una entrada, seguido de una Lectura del 
grupo de dato s del almacenamiento persistente y luego una salida con el resultado de la 
investigación. PF A no tiene que ver con la que los datos se recupera, sólo que es los datos 
persistentes. 
 
Figura 3.2 - Solución para una lectura emitida por software A en la capa de aplicación. 
Un modelo exactamente análogo se aplicaría si el proceso funcional A se requiere para hacer 
un grupo de datos persistente a través de un movimiento de datos de escritura. Según la regla 
d) las condiciones de error en la parte 1, la lectura y los movimientos de escritura de datos se 
consideran que incluye cualquier notificación de una condición de error. 
La figura 3.2 muestra un posible mensaje de error de aplicación específica que podría ser 
emitido por PF A si, por ejemplo, no se encuen tra el registro solicitado. Sin embargo, una 
condición de error no es específico de la aplicación, por ejemplo, 'fallo de disco' no se cuenta 
como una salida para PF A. Véase también la sección 4.9 en la Parte 1 en los mensajes de 
error / confirmación. 
El movimiento de datos (s) cuando se requiere un proceso funcional para obtener algunos 
datos de otra pieza de software.


<!-- pág 30/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 30 
 
 
 
Ejemplo 2: Las piezas de software a medir se supone que tienen una relación cliente - servidor, 
es decir, donde una sola pieza, el cliente, obtiene los servicios y / o datos de la otra pieza, el 
servidor, en la misma o una capa diferente. Figura 3.3 muestra un ejemplo de tal relación, en 
el que las dos piezas son los componentes principales de la misma aplicación. En cualquiera 
de tales relaciones cliente / servidor, el FUR del componente de cliente C1 sería identificar el 
servidor C2 componente como un o de sus usuarios funcionales, y viceversa. La misma 
relación existiría y el mismo diagrama se apl icaría si las dos piezas eran aplicaciones 
separadas, o si una de las piezas eran un componente de una aplicación separada. 
 
Figura 3.3 - Los intercambios de datos entre los componentes de cliente y servidor.  
Físicamente, los dos componentes podrían ejecu tarse en procesadores separados; en tal 
caso intercambiarían datos a través de los sistemas operativos respectivos y cualesquiera 
otras capas intermedias de sus procesadores en una arquitectura de software tal como se 
muestra en la Figura 2.2. Pero lógicam ente, la aplicación de los modelos COSMIC, los dos 
componentes de intercambio de datos a través de una salida seguido de un movimiento de 
datos de entrada. Todo el software y el hardware que interviene se ignora en este modelo. 
La figura 3.3 muestra que un proceso funcional PF C1 del componente de cliente C1 se activa 
mediante una entrada de un usuario funcional (tal como un humano) que consiste, por 
ejemplo, de los parámetros de la consulta. Los FUR de C1 reconocerá que este componente 
debe pedir al servidor, componente C2, los datos requeridos, y debe decirle qué se requiere 
un grupo de datos. 
Para obtener el grupo de datos requerido, PF C1 emite una salida que contiene los parámetros 
de la petición de información para componente C2. Este movimiento de datos salida cruza la 
frontera entre C1 y C2 y así se convierte en la entrada desencadenante de un proceso 
funcional PF C2 en el componente C2. El proceso funcional PF C2 de C2 se asume para


<!-- pág 31/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 31 
 
 
 
obtener el grupo de datos requerida a través de una lectura de su pr opio almacenamiento 
persistente, y envía respuesta para C1 a través de una salida. Proceso funcional PF C1 de 
C1 recibe estos datos como una entrada. PF C1 pasa entonces el grupo de datos como una 
salida para satisfacer la consulta de su usuario funcional. 
Teniendo en cuenta el posible mensaje de error / confirmación emitida por el cliente, este 
Ejemplo 2, requiere 6 movimientos de datos (es decir, 6 CFP) para satisfacer la petición de 
consulta para C1 y 4 CFP para C2. Esto se compara con el 4 CFP (1 x E, 1 x R y 2 x X) que 
se habría requerido para C1 si hubiera sido capaz de recuperar el grupo de datos del 
almacenamiento persistente dentro de su propio lí mite a través de un a lectura como se 
muestra en Figura 3.3. 
Componente C2 probablemente utilizará los servicios de algún software de controlador de 
dispositivo de almacenamiento en otra capa de la arquitectura de software para recuperar los 
datos desde el hardware, como en el Ejemplo 4, la figura 3.5 (b).  
El movimiento de datos (s) y diferentes derechos de acceso a los datos almacenados. 
Ejemplo 3: Véase la Figura 3.4. Supongamos que una pieza de software A a medir se le 
permite recuperar ciertos datos alm acenados Z, pero no se permite para manejar (es decir, 
crear, actualizar o eliminar) estos mismos datos Z directamente. La pieza de software B se 
requiere para asegurar la integridad de los datos Z asegurando validación coherente, por lo 
que procesa todas las peticiones de administración de datos para Z. Datos cuando se requiere 
una para administrar los datos en Z, A debe pasar su petición a B a través de una salida 
seguido de una entrada. 
 
Figura 3.4 - Datos persistente Z dentro de la frontera de ambos softwares A y B para una 
lectura.


<!-- pág 32/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 32 
 
 
 
movimiento (s) de datos cuando los datos persistentes se obtienen por el software de 
controlador de dispositivo que interactúa con el dispositivo de almacenamiento físico. 
NEGOCIO Ejemplo: Este ejemplo se refiere a la pieza de software A del Ejemplo 1 que se 
requiere para recuperar un grupo de datos almacenado. Consider e una pieza separada del 
software de B que es el controlador de dispositivo para el almacenamiento de hardware 
inteligente que mantiene el grupo de datos que se requiere en el softwar e. (Ignorar la 
presencia probable de un sistema operativo para la simplicidad, el sistema operativo transmite 
eficazmente las solicitudes de aplicación al software controlador de dispositivo y devuelve los 
resultados de las solicitudes). 
Las dos piezas de software están en diferentes capas en una arquitectura tal como se muestra 
en la Figura 2.2. Software A está en, por ejemplo, la capa de aplicación, y el software de B 
está en una capa de controlador de dispositivo. Físicamente, es probable que haya una 
relación jerárquica entre las dos piezas y (ignorando el sistema operativo)  una interfaz física 
entre el software en las dos capas, como se muestra por ejemplo en la Figura 2.2. Sin 
embargo, los modelos de los procesos funcionales de software A y B son independientes de 
la naturaleza de la relación entre las capas, que puede ser jerárquica o bi-direccional. 
Los usuarios funcionales del software B en la capa de drivers son el software A (ignorando el 
sistema operativo) y el dispositivo de almacenamiento de hardware inteligente que contiene 
los datos requeridos. (Medios 'inteligente s' que el dispositivo debe decir qué datos son 
necesarios.) 
Supongamos que un proceso funcional PF A del software de A necesita recuperar un grupo 
de datos almacenados. Figura 3.5 (a) muestra el modelo COSMIC de esta investigación. 
Figura 3.5 (b) muestra el proceso funcional PF B del software B en la capa de controlador de 
dispositivo que se encarga de la recuperación física de los datos necesarios a partir de un 
dispositivo de almacenamiento de hardware (tal como un disco o memoria USB). 
 
Figuras 3.5 (a) y (b) - Solución para una lectura emitidos por el software de A en la capa de 
aplicación al software de B en la capa de controlador de dispositivo.


<!-- pág 33/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 33 
 
 
 
La figura 3.5 (b) muestra que la solicitud de lectura del software A se recibe como una entrada 
desencadenante para el proceso funcional PF B, que pasa la solicitud como una salida para 
el dispositivo de hardware. La respuesta de este último depende del dispositivo de hardware 
en particular. El dispositivo sólo puede devolver los datos solicitados, que se muestran como 
la entrada E2 en la figura 3.5 b). El dispositivo también puede emitir un mensaje de error 
separado que describe el éxito o la razón de la insuficiencia de la solicitud, por ejemplo, 'datos 
que no se encuentran', o “error de disco”, que se muestra como la entrada E1 * en la Figura 
3.5 b). PF B devuelve los datos al software de A como una salida. PF B también normalmente 
emite un 'código de retorno' que describe el éxito o el motivo del fallo de la solicitud. (Aunque 
el código de retorno puede estar unido físicamente a los datos devueltos, es lógicamente un 
grupo de datos diferente a la de los datos devueltos - se trata de datos sobre el resultado del 
proceso de solicitud). Para PF A ninguna entrada para estos mensajes se identifica, como 
representa el movimiento de datos de lectura de los datos retornados y mensajes de error, 
como se lee y escribe esto incluye c ualquier notificación asociada de condiciones de error. 
Para PF A, una salida se identifica por un mensaje de error / confirmación, si es necesario. 
Nota: en la práctica, puede haber más movimientos de datos entre el software del controlador 
del dispositivo y el dispositivo de hardware inteligente que se muestra en la Figura 3.5 b). Por 
ejemplo, esta figura no muestra el efecto del controlador de dispositivo de medición de un 
tiempo de espera para la falta de respuesta del hardware. 
El movimiento de datos ( s) cuando un proceso funcional no tiene que decirle al usuario 
funcional qué datos enviar. 
TIEMPO REAL Ejemplo 5: Supongamos que un proceso funcional de un sistema de software 
de control de procesos en tiempo real que se requiere para sondear un conjunto de sensores 
mudos idénticos. A nivel de aplicación, la solicitud de los datos por el proceso funcional y la 
recepción de los datos se explica por una entrada. (Dado que los sensores son idénticos se 
identifica una entrada) 
Supongamos, además, que la solicitud de la necesidad de datos en la práctica puede pasar a 
una pieza de software controlador de dispositivo en una capa inferior de la arquitectura de 
software, que obtiene físicamente los datos necesarios de la matriz de sensores como se 
ilustra en la arquitectura de capas de la figura 2.3. Los procesos funcionales del software de 
control de procesos y del software de controlador de dispositivo para los sensores mudos 
serían como se muestra en las Figuras 3.6 (a) y (b) a continuación.


<!-- pág 34/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 34 
 
 
 
 
Figura 3.6 (a) y (b) - Solución para una entrada de sensores mudos. 
La figura 3.6 muestra (a) que proceso funcional del software PF A es iniciado por una E1 
Entrada por ejemplo a partir de un pulso de reloj. Este proceso funcional a continuación 
obtiene los datos a través de la entrada E2 de la matriz de sensores para recibir las múltiples 
ocurrencias de las lecturas del sensor. Los sensores son también los usuarios funcionales del 
software de control de procesos. (El software de controlador de dispositivo está oculto en este 
nivel.) 
Figura 3.6 (b) muestra el modelo para el software que acciona los dispositivos sensores. Se 
recibe datos a través de una entrada desde el software de control de procesos (probablemente 
en la práctica a través de un sistema operativo) como el disparador de un proceso funcional 
PF B. Este proceso funcional obtiene los datos necesarios a través de una entrada E de su 
usuario funcional, la matriz de sensores. 
El grupo de datos se pasa de nuevo al software de control de procesos a través de una salida. 
Esta salida es recibida como la E2 entrada por el proceso funcional PF A. PF A continuación, 
continúa con su procesado de los datos de sensor. Una vez más, el hecho de que hay 
múltiples ocurrencias de este ciclo de recopilación de datos de cada uno de los se nsores 
idénticos es irrelevante. 
La aparente falta de coincidencia entre la  entrada  E2 desde un sensor para el software de 
control de procesos y la entrada seguid a por un movimiento de salida de datos del software 
de controlador de dispositivo es debido a la convención de que una entrada de un sensor se 
considera que incluye cualquier petición para entrar en funcionalidad ya que el usuario 
funcional no tiene capacidad de hacer frente a cualquier mensaje de un proceso funcional. 
El movimiento de datos (s) cuando se necesita decirles a los usuarios funcionales que se les 
diga qué enviar. 
EN TIEMPO REAL Ejemplo 6: Supongamos que un proceso funcional envía a uno de sus 
usuarios funcionales, tales como un dispositivo de hardware 'inteligente' u otra pieza de similar 
de software, algunos parámetros para una investigación o los parámetros para el cálculo, o


<!-- pág 35/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 35 
 
 
 
algunos datos para que sean comprimidos. Se obtiene la respuesta del  usuario funcional a 
través del proceso funcional emisión de una salida, seguido por la recepción de un movimiento 
de entrada de datos, como se describe en la sección 3.4, el Ejemplo 2. 
3.5 Manipulaciones de datos asociadas con los movimientos de datos. 
Se considera que la manipulación de datos se explica por los movimientos de datos asociados. 
Para la manipulación de datos en el contexto de los cambios a los requisitos que deben 
medirse ver 3.10. 
NEGOCIO Ejemplo 1: Una entrada incluye todo tipo de manipula ción necesaria para dar 
formato a una pantalla para permitir a un usuario humano introducir datos y validar los datos 
introducidos, excepto los productos de lectura (s) que podrían ser necesarios para validar 
algunos datos o códigos introducidos, o para ob tener alguna descripción  de los códigos 
asociados. 
NEGOCIO Ejemplo 2: Una salida incluye toda la manipulación para la salida de formato y 
preparar algunos atributos de datos para imprimir (o de salida en una pantalla), incluyendo los 
títulos de campo legible por humanos excepto la lectura (s) o las entradas que p odrían ser 
necesarias para suministrar los valores o las descripciones de algunos de los atributos de los 
datos impresos.  
Ejemplo: Considere dos ocurrencias de un proceso funcional dado. Supongamos que en la 
primera aparición de los valores de algunos atributos para ser movidos por un movimiento de 
datos dado a un sub-proceso de manipulación de datos A y que en otra ocurrencia del mismo 
proceso funcional los valores de atributo conducen a un sub -proceso de manipulación de 
datos diferente B, en tales circunstancias, tanto la manipulación de datos sub-procesos A y B 
debe estar asociado con este mismo movimiento de datos y por lo tanto sólo un movimiento 
de datos debe ser identificado en ese proceso funcional. 
3.6  Comandos de control. 
En el método COSMIC coma ndos de control no son movimientos de datos. Es importante 
identificar los comandos de control a fin de evitar que sean identificados como tales. 
Ejemplos de comandos de control. 
• Los comandos a página arriba / abajo o entre pantallas físicas. 
• Golpear a un Tabulador o Enter, o pulsando un botón para continuar. 
• Al hacer clic en un botón 'OK' para confirmar o cancelar una acción anterior, o para 
reconocer un mensaje de error o para confirmar algunos datos introducidos, etc.


<!-- pág 36/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 36 
 
 
 
• Funciones que permiten a un usuario controlar la visualización (o no) de una cabecera 
o de subtotales que han sido calculados. 
• Los comandos de menú que permiten al usuario navegar a uno o más procesos 
funcionales específicos. 
• Los comandos para mostrar una pantalla en blanco para la entrada de datos. 
3.7 Los mensajes de error / confirmación y otras indicaciones de condiciones de 
error. 
Los mensajes de error y de confirmación, si se requiere, son objeto de medición. 
Ejemplos: mensajes de error / confirmación puede transmitir éxito o fracaso de la validación 
de los datos introducidos o una llamada para recuperar datos o para hacer los datos 
persistentes, o la respuesta de un servicio solicitado de otra pieza de software. 
NEGOCIO Ejemplo 1: En un diálogo hombre-máquina, ejemplos de mensajes de error que se 
producen durante la validación de datos que se introducen podría ser 'error de formato', 
'cliente no encontrado', 'Error: por favor marque la casilla de verificación q ue indica que ha 
leído nuestros términos y condiciones ', 'límite de crédito excedido', etc. Todos estos mensajes 
de error se deben  considerar como ocurrencias de una salida en cada proceso funcional 
donde se producen este tipo de mensajes (que podría denominarse 'mensajes de error'). 
NEGOCIO Ejemplo 2: Un proceso funcional potencialmente puede emitir mensajes de 
confirmación y distintos mensajes de error a sus usuarios funcionales. Identificar una salida a 
la cuenta de todos los mensajes  de error / confirm ación. Proceso funcional B puede 
potencialmente emitir 8 mensajes de error a sus usuarios funcionales. Identificar una salida 
para dar cuenta de todos estos 8 mensajes de error. 
 
Un mensaje de error / confirmación con datos adicionales. 
NEGOCIO Ejemplo 3: Un proceso funcional de ATM de un banco (es decir, un 'cajero 
automático', o 'dispensador de efectivo') puede emitir cinco tipos de mensajes en respuesta a 
una solicitud de retiro de una cantidad específica de dinero en efectivo: 
• Error: la máquina no tiene efectivo disponible  
• Error: la cantidad solicitada debe ser múltiplo de 10 $ 
• La retirada se negó. Cuenta bloqueada. Contacta con el banco. 
• La retirada se negó (límite de crédito sería superado por $ 139,14) 
• La retirada aceptada; el saldo restante es de $ 756,25


<!-- pág 37/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 37 
 
 
 
Los cuatro primeros mensajes describen una condición de error y la primera parte del quinto 
mensaje es una confirmación. De acuerdo con las normas relativas a las indicaciones de las 
condiciones de error, para todas estas salidas, contar una salida. Los dos últimos mensajes 
también incluyen datos de atributos relacionados con la cuenta del cliente. Contar con una 
salida para estos datos, a la cuenta para mover datos de la cuenta del cliente. En total, 
identificar dos salidas para este proceso funcional, es decir 2 CFP para su salida. 
Condiciones de error a los usuarios humanos que no se especifican en los FUR. 
NEGOCIO Ejemplo 4: El mensaje A transmitido desde el sistema operativo podría ser 
'impresora X no está respondiendo', ignorar tales mensajes. 
EN TIEMPO REAL Ejemplo 1: En un sistema en tiempo real, un proceso funcional que 
comprueba periódicamente el correcto funcionamiento de todos los dispositivos de hardware 
podría emitir un mensaje que los informes de sensor S ha fallado ", donde 'S' es una variable. 
Este mensaje debe ser identificada como una salida en ese proceso funcional a la cuenta para 
mover datos sobre el usuario funcional (y objeto de interés) sensor S. 
Los valores de datos que indican una condición de error junto con otros datos. 
TIEMPO REAL EJEMPLO 2. El FUR del ejemplo 6 de tiempo real en la sección 3.4 también 
puede indicar que los PF A y B deben manejar una condición de error cuando el software del 
controlador del dispositivo no puede obtener los datos de uno o más de la matriz de sensores 
Un sensor no puede, por definición, emitir un mensaje de error. El controlador de dispositivo 
PF B, muy probablemente, obtendrá una serie de valores de la matriz de sensores, p. Ej. 
estado 1, estado 2, estado 3, sin respuesta, estado 5, sin respuesta, estado 7, etc. y emitirá 
esta cadena como una Salida al PF A de la aplicación donde se recibe como E ntrada. No 
debe identificarse ningún mensaje de error por separado como una Salida del PF B del 
software del controlador del dispositivo, ni como una Entrada al PF A de la aplicación de 
control de procesos.  
3.8 La medición de los componentes de un sistema de software distribuido. 
Véase el Ejemplo 2 en la sección 3.4. 
3.9 La reutilización de software. 
procesos funcionales que incluyen una funcionalidad común. 
NEGOCIO Ejemplo 1: Varios procesos funcionales en el mismo software que se está midiendo 
pueden necesitar la misma funcionalidad de validación para, por ejemplo, 'fecha de la orden', 
o puede necesitar acceder a los mismos datos persistentes, o puede necesitar llevar a cabo


<!-- pág 38/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 38 
 
 
 
el mismo cálculo de intereses. Medir la funcionalidad común como parte de cada proceso 
funcional que lo requiera. 
TIEMPO REAL Ejemplo 1: Varios procesos funcionales en el mismo software que se está 
midiendo puede necesitar obtener datos del mismo sensor (movimiento común de un mismo 
grupo de datos) o puede necesitar para llevar a cabo el cálculo de conversión misma escala, 
por ejemplo, de Fahrenheit a Centígrados (manipulación de datos común). Mida esta 
funcionalidad común como en el ejemplo anterior. 
Funcionalidad que no está en los FUR. 
NEGOCIO Ejemplo 2: Para una aplicación de  negocios, el usuario que inicia la aplicación 
puede ser un componente planificador del sistema operativo, un operador de ordenador, o 
cualquier otro usuario humano (por ejemplo,  cuando un usuario de PC lanza un software de 
navegación o de procesamiento de textos). Los datos transmitidos por estos usuarios no se 
procesan por la aplicación como se indica en los FUR, por lo que debe ser ignorado. 
TIEMPO REAL Ejemplo 2: Para una aplicación en tiempo real, el usuario que inicia la 
aplicación puede ser el sistema operativo o de gestión de red, la generación de una señal de 
reloj, o un operador humano (por ejemplo, para iniciar un sistema de control de proceso desde 
una estación de trabajo del operador) eso debe ser ignorado. 
NEGOCIO Ejemplo: Para un sistema operativo del ordenador, el usuario que inicia el sistema 
operativo es un programa de arranque que se inicia cuando la alimentación se enciende el 
equipo, debe ser ignorado. 
NEGOCIO Ejemplo 3: Una aplicación para procesar los datos de entrada pa ra una variedad 
de procesos funcionales en el modo por lotes puede ser iniciad a por un programador del 
sistema operativo. Si el propósito es medir l os FUR de la aplicación de lote, la funcionalidad 
puesta en el sistema debe ser ignorada. Las Entradas desencadenante para los procesos 
funcionales de la aplicación de proceso por lotes procesados y ninguna otra entrada que 
pueden ser necesarios formarán los datos de entrada para la aplicación de lote. 
NEGOCIO Ejemplo 4: Excepcionalmente, una aplicación de proceso por lotes para informes 
de resumen de productos al final de un período de tiempo se puede iniciar sin necesidad de 
cualquier dato de entrada proporcionados directamente del usuario funcional. Para el análisis 
véase el Ejemplo de negocios 7 en la sección 3.1. 
TIEMPO REAL Ejemplo 3: Un vehículo moderno tiene un sistema distribuido de unidades de 
control electrónico (ECU) para controlar muchas funciones, por ejemplo, la gestión del motor, 
frenos, aire acondicionado, etc. En la arquitectura AUTOSAR, en un sistema distribuido, la 
'Red gestión' (NM) del módulo, que siempre está en funcionamiento, es responsable de la 
activación de la ECU, que están conectados entre sí a través de una red ('bus'). Este módulo


<!-- pág 39/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 39 
 
 
 
NM también se ocupa de la conmutación coordinada en tre los estados de funcionamiento 
ECU: funcionamiento normal, de baja potencia y es espera. Por lo tanto, es el NM que se 
despierta o pone a ECUs en espera. Al medir cualquier software de aplicación ECU, esta 
funcionalidad NM debe ser ignorada. 
3.10 Medición del tamaño funcional de los cambios en el software. 
El tamaño del cambio en el método COSMIC incluye cambios en cualquiera de los elementos 
que contribuyen al tamaño, incluyendo las manipulaciones de datos de movimientos de datos. 
Ejemplo 1: una manipulación de datos A se modifica, por ejemplo, cambiando el cálculo, la 
específicación de formato, la presentación, y / o validación de los datos. 'Presentación' puede 
significar, por ejemplo, el tipo de letra, color de fondo, la longitud del campo, enc abezado de 
campo, el número de decimales, etc. 
Ejemplo 2: Supongamos que una solicitud de cambio para un proceso funcional requiere tres 
cambios en la manipulación de datos asociados con su entrada desencadenante  y dos 
cambios a la manipulación asociada con una salida, así como dos cambios a los atributos del 
grupo de datos movido por esta salida. Medir el tamaño del cambio como 2 CFP, es decir, 
contar el número total de movimientos de datos cuyos atributos y manipulación de datos 
asociada debe ser cambiado. NO cuente el número de manipulaciones de datos o datos de 
atributos para ser cambiado. 
Ejemplo 3: Supongamos que un requisito para añadir o modificar los atributos de datos de un 
grupo de datos D1, de tal manera que después de la modificación se conviert e en D2. En el 
proceso funcional A donde se requiere esta modificación, todos los movimientos de datos 
afectados por la modificación deben ser identificados y contados como modificado. Por lo 
tanto, si el grupo de datos modificados D2 se hace salida persis tente y / o está en proceso 
funcional A, identificar uno de escritura y / o el movimiento de datos una salida, 
respectivamente, como modificado. 
Si existen otros procesos funcionales de lectura o entrada en este mismo grupo de datos D2, 
pero su funcionalidad no se ve afectada por la modificación, ya que no procesan los atributos 
de datos cambiado o añadido. Estos procesos funcionales continúan su procesamiento el 
grupo de datos movido como si fuera todavía D1. Por lo tanto, estos movimientos de datos en 
los otros procesos funcionales que no están afectadas por la modificación en el movimiento 
de datos (s) de proceso funcional A. No deben ser identificados y contados como modificado. 
Ejemplo 4: A menudo, una parte obsoleta de una aplicación se elimina (‘desconectado' sería 
una mejor descripción) dejando el código del programa en su lugar y con sólo quitar el enlace 
a la funcionalidad obsoleta. Supongamos que la funcionalidad de la pieza obsoleta es de  100


<!-- pág 40/40 -->

COSMIC Medición Manual - Versión 5.0 - Parte 3: Ejemplos Copyright © 2020 40 
 
 
 
CFP pero la parte puede ser desconectado mediante el c ambio, por ejemplo, de 2 
movimientos de datos. El tamaño del cambio funcional depende de la finalidad. Si el propósito 
es utilizar el tamaño como entrada para la estimación del proyecto, el tamaño es de 2 CFP. Si 
el propósito es determinar el tamaño genera l de la aplicación, el tamaño del cambio es 100 
CFP. 
Para los propósitos de estimación puede ser aconsejable utilizar una productividad diferente para una parte del 
cambio funcional, ya que la desconexión es bastante diferente de eliminaciones 'reales'. Alternativamente, para la 
estimación de los propósitos, puede ser preferible para medir el tamaño que será implementado en lugar del 
tamaño del requisito. 
Ejemplo 5: Si en el ejemplo anterior se mide el 'tamaño del proyecto' de 2 CFP, esto debe ser 
claramente documentado y distinguirse de una medición de la FUR que requieren que la 
aplicación debe ser reducida en tamaño por 100 CFP. 
NEGOCIO Ejemplo 1: Si se requiere un mensaje de error / confirmación  a ser cambiado (es 
decir, textos añadido, modificado o eliminado) debe ser identificado para la medición, 
independientemente de si el texto modificado es una consecuencia de un requisito para 
cambiar otro movimiento de datos o no. 
Los cambios en los comandos de control y datos de aplicación general. 
NEGOCIO Ejemplo 2: Cuando se cambia el color de la pantalla para todas las pantallas, este 
cambio no se debe medir. 
3.11 Extendiendo el método de medición COSMIC. 
Aunque no es una parte formal del método COSMIC, cualquier aspecto de los FUR que no se 
puede medir usando las reglas del método pueden estar sujetos a un proceso de medición 
separado. El tamaño, sin embargo, no se debe notificar como CFP. 
Ejemplo 1: El método COSMIC podría extenderse para medir por separado y de forma 
explícita el tamaño de la FUR de los sub-procesos de manipulación de datos. 
Ejemplo 2: El método podría extenderse para medir por separado la influencia del número de 
atributos de datos por el movimiento de datos sobre el tamaño de software.