<!-- Extraído de 931b8707-GuidelineRequirementsCOSMICFormat.pdf (8 págs) por pypdf — 2026-06-03T03:39:47Z. Fuente COSMIC. -->
# COSMIC — Guideline: Requirements in COSMIC Format



<!-- pág 1/8 -->

COSMIC Measurement Manual  
for ISO 19761  
 
 
Guideline Software Requirements 
Specification 
In  
COSMIC Format 
 
 
COSMIC Version 5.0 
December 2025


<!-- pág 2/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 2 
Foreword. 
The purpose of this Guideline is to show how the COSMIC Functional Size Measurement 
method (ISO 19761) can be used to specify software requirements in what is called ‘COSMIC 
Format’. In consequence, the COSMIC measurement is a byproduct of this and hence a 
separate measurement is unneeded . Moreover, the software requirements texts have a 
universal pattern and are clear, well-structured and easy accessible.  
This Guideline is aligned with the ISO 29148 on Requirements Engineering document [1]. 
 
 
 
 
 
Editors: 
Alain Abran, Ecole de technologie supérieure – University of Quebec (Canada), 
Arlan Lesterhuis (The Netherlands). 
Other members of COSMIC Measurement Practices Committee: 
Jean-Marc Desharnais, Ecole de technologie supérieure – University of Quebec (Canada),  
Peter Fagg, Pentad (UK),  
Andrés Gutierrez (Colombia), 
Dylan Ren, Measures Technology LLC (China),  
Bruce Reynolds, Tecolote Research (USA),  
Hassan Soubra, ECE – Engineering School, Lyon (France),  
Sylvie Trudel, Université du Québec à Montréal - UQAM (Canada),   
Francisco Valdés Souto, Spingere (Mexico), 
Frank Vogelezang, Adviescollege ICT-toetsing (The Netherlands). 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
Copyright 2025. All Rights Reserved. The Common Software Measurement International Consortium (COSMIC). 
Permission to copy all or part of this material is granted provided that the copies are not made or distributed for 
commercial advantage and that the title of the pub lication, its version number, and its date are cited and notice is 
given that copying is by permission of the Common Software Measurement International Consortium (COSMIC). 
To copy otherwise requires specific permission.


<!-- pág 3/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 3 
Table of Contents 
 
1 INTRODUCTION. ................................ ................................ ................................ .......... 4 
2 SOFTWARE REQUIREMENTS SPECIFICATION. ................................ ....................... 4 
2.1 Describing layers. ................................ ................................ ................................ ......... 4 
2.2 Describing functional processes. ................................ ................................ .................. 4 
2.3 Describing data of a functional process. ................................ ................................ ....... 5 
2.4 Measurement (determining functional size of requirements). ................................ ........ 5 
3 SOFTWARE REQUIREMENTS SPECIFICATION EXAMPLES. ................................ ... 6 
3.1 Functional process of an order-processing application. ................................ ................ 6 
3.2 Functional process of a client-registration application. ................................ .................. 6 
3.3 Functional process of an enquiry. ................................ ................................ ................. 6 
3.4 A clock triggering a control process. ................................ ................................ ............. 7 
4 REFERENCES AND DOCUMENTATION. ................................ ................................ .... 8


<!-- pág 4/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 4 
1 INTRODUCTION. 
The purpose of a COSMIC measurement of a piece of software is to use the latter’s functional 
size for cost estimation. To obtain this functional size, in a separate action the information that 
COSMIC needs must be extracted from the functional requirements. Usually, functional 
requirements are textual, differing from organization to organization and from project to project, 
even within the same organization.  
As the COSMIC concepts and procedures provide a standard for functional measurement of 
any kind of software, it therefore also provides concepts and procedures for stating upfront any 
kind of software functional requirements in a COSMIC compatible format. As a consequence, 
stating requirements and sizing can be combined, standardized and made much more effective 
by u sing the COSMIC  concepts (in terms of definitions, rules, procedures, etc.)  to state 
functional requirements. Requirements descriptions using this so called ‘Requirements COMIC 
Format’ (short: ‘COMIC Format’) has a number of important benefits: 
• The COSMIC Format provides a universal way of documenting functional requirements for 
any kind of software. 
• A separate measurement of the functional requirements is unneeded as the functional size 
is a byproduct of the functional requirements.  
• When drafting the functional requirements, financial consequence of possible changes to 
the functional requirements is visible ‘on the spot’ by comparing the sizes with and without 
change. 
2 SOFTWARE REQUIREMENTS SPECIFICATION. 
According to ISO 29148  on Requirements Engineering , a fter having g athered the  
stakeholders’ requirements, these requirements (functional and other requirements) must be 
documented in a clear and standardized document that can be understood by all interested 
parties: the Software requirements specification in COSMIC Format . Note that ISO 29148 
itself is 'generic' to the Requirements Engineering independently of which specific 
requirements technique is used. 
When following the instructions below it may be helpful to consult the examples in Chapter 3. 
2.1 Describing layers. 
If not applicable, skip this step. 
The functionality to be realized may be grouped into layers. Identify layers as a functional 
division of functionality, with the understanding that  
• functionality shares data with other functionality, and  
• identically interpret the data attributes that they share. 
If the productivity of the layers differ, different productivit y ratios and hence production costs 
apply per layer. In that case dividing software into layers is unavoidable for estimating software 
production costs. Identify these layers and draft a COSMIC Format per layer.  
2.2 Describing functional processes. 
First identify and describe the functional processes of the stakeholders requirements (per 
layer, if applicable).  
A functional process is an elementary component of the stakeholders requirements. A  
functional user is a human or other software or hardware that triggers, provides information to, 
or receives information from functional processes in the stakeholders requirements. Identify a 
functional process based on the following characteristics:


<!-- pág 5/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 5 
• Identify a functional process where a triggering event is detected by a functional user, 
who/which in turn initiates to  enter the data  that the functional process needs to start 
processing. 
• A functional user is a sender and/or an intended recipient of data in the  stakeholders 
requirements. 
• A triggering event causes a functional user in the stakeholders requirements to initiate 
(‘trigger’) one or more functional processes. 
• Briefly characterize the data to be entered  that the functional process needs to start 
processing. 
2.3 Describing data of a functional process. 
A functional process  exchanges (moves) data with its environment, i.e. with its functional 
user(s) and with persistent storage. P ersistent storage enables a functional process to store 
and/or retrieve data.  
For each functional process, identify the data it needs to move and the data manipulation 
concerned on basis of the stakeholder requirements. There are four types of data movements:  
• Receiving data from and/or forwarding data to a functional user, called the Entry (short: E) 
and Exit (short: X) data movements respectively, and  
• Reading data from and/or storing data into persistent storage , called the Read (short: R) 
and Write (short: W) data movements respectively. 
Based on the stakeholder requirements describe the data being moved: 
• The data being moved has a type of data movement: E, X, R or W. 
• The data being moved describes one object of interest by means of one data group. 
• An object of interest is any physical thing, as well as any conceptual thing or part of a 
conceptual thing in the world of a functional user.  
• A data group is a distinct, non-empty, non-ordered and non-redundant set of data attributes 
that each describes a complementary aspect of the same one object of interest. 
• Identify an Entry, Exit, Read or Write data movement for the movement of all data 
describing a single object of interest of that type , as required by  the stakeholders 
requirements. 
• An object of interest key consists of the data attribute(s) of which the value(s) identify one 
occurrence of the object of interest. Different object of interest keys imply different objects 
of interest and hence different data movements. 
• Register a E, R, W or X data movement per object of interest key being moved.  
• The first Entry of a functional process is its triggering Entry. 
Note. For measurement, data manipulation plays no part as each data movement includes the 
data manipulation concerned. 
2.4 Measurement (determining functional size of requirements). 
When required, the functional size of the functional requirements can now be determined: 
• The size of the functional requirements is the sum of the sizes of its functional processes.  
• The size of a functional process is the sum of its Entry, Exit, Read and Write data 
movements. 
• The size of an Entry, Exit, Read or Write data movement of one data group is one COSMIC 
function point (CFP) per object of interest being moved, i.e. per object of interest key.  
• Non-functional system requirements may have software functional consequences, when 
applicable add their software functional sizes.


<!-- pág 6/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 6 
3 SOFTWARE REQUIREMENTS SPECIFICATION EXAMPLES. 
On the basis of the stakeholder requirements specification identify the functional processes, 
by translating one or more requirements into a functional process. Given a candidate functional 
process, identify entering, reading, writing and sending data movements (possibly multiple 
times), put the data movements as best as possible in order of processing and add additional 
information where needed.  
In the examples a triggering event and associated functional user of a functional process are 
indicated. 
3.1 Functional process of an order-processing application. 
Stakeholders’ requirements: 
An order is received, causing an employee to enter the order data.  The Order-processing 
application is required to send the details of any new client to the central Client-registration 
application. 
COSMIC Format functional process: Order Entry 
Triggering event: Order received. Functional user: Employee to enter the order data. 
Data 
Movmt 
Data moved Object of interest 
E Receipt of data about order Order 
W Store order data Order 
R Check if new client Client 
X If new client send client details to the Client-
registration application 
Client 
3.2 Functional process of a client-registration application. 
Stakeholders’ requirements: 
On receipt of the details of a  new client the central Client-registration application store s 
these data. 
COSMIC Format requirement 
Triggering event: receipt of details of new client. Functional user: Order entry application. 
Data 
Movmt 
Data moved Object of interest 
E Details of new client Client 
W Details of new client Client 
3.3 Functional process of an enquiry. 
Stakeholders’ requirements: 
Display a list of lecturer names, selected from a file of lecturer data, by any combination of 
three input parameters, namely, ‘age’, ‘gender’ and ‘education level’. The three parameters 
must also be output. If no lecturers meet the selection criteria, an error message must be 
issued.  
COSMIC Format requirement 
Triggering event: Request to d isplay a list of lecturer names. Functional user: Employee 
that enters the input parameters.


<!-- pág 7/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 7 
Data 
Movmt 
Data moved Object of interest 
E Age, gender code, education-level Selection parameters 
R Lecturer data Lecturer 
X Age, Gender code, Education-level Selection parameters 
X Lecturer name Lecturer 
X Message ID Error/confirmation 
message  
3.4 A clock triggering a control process. 
Stakeholders’ requirements: 
The speedometer software of a car is connected to a rotation measurement sensor located 
on the drive shaft that measures its revolutions per minute (rpm), and to a key-in sensor, a 
clock, and a display unit for the driver. The software's persistent storage contains the 
parameters needed to send messages to a pre -defined variety of display units. The 
speedometer software is required to capture at key -in time the display parameters and 
initialize the installed display unit. A clock triggers the software at five millisecond intervals 
to capture rpm information from the drive shaft, calculate the speed, and send the speed to 
update the display unit using parameters appropriate for this display unit.  
 
Figure 2.1 – Context diagram for the speedometer software 
The context diagram shows the four functional users of the speedometer software, namely: 
• three input devices (the rpm sensor, the key-in sensor and the clock), and  
• the one output device (the driver display). 
There are two events that need to be responded to by the speedometer software (i.e. are 
triggering events):  
• the key-in event, and  
• the 5 millisecond clock tick.  
Hence the speedometer control software has two functional processes: FP1 and FP2. 
 
FP1 initializes the speedometer control software on the event of ‘key-in’ detected by the key-
in sensor, which includes reading the parameter data for the display; 
COSMIC Format requirement 
Triggering event: key-in. Functional user: key-in sensor.


<!-- pág 8/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Software Req. Specification in COSMIC Format    Copyright © 2025 8 
Data 
Movmt 
Data moved Object of interest 
E Key-in signal Key-in signal 
R Parameter data for the display Display parameters 
X Parameter data to display unit Display parameters 
 
FP2 measures the speed on the event of the tick generated by the clock every 5 ms and sends 
the speed to the display. 
COSMIC Format requirement 
Triggering event: Clock tick. Functional user: Clock. 
Data 
Movmt 
Data moved Object of interest 
E Clock tick Clock tick 
X Request to rpm sensor Rpm 
E Rpm received Rpm 
X Calculated speed to display Speed 
 
 
4 REFERENCES AND DOCUMENTATION. 
[1] ISO/IEC/IEEE 29148:2018 - Systems and software engineering — Life cycle processes 
— Requirements engineering. 
[2] Guideline Measurement Manual v5 Part 1 Principles, Defs. & Rules. 
[3] Guideline Measurement Manual v5 Part 2 Guidelines.