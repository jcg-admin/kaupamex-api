<!-- Extraído de a635ff4b-TutorialEarlySizingModule3EarlyandNFR.pdf (32 págs) por pypdf — 2026-06-03T03:41:43Z. Fuente COSMIC. -->
# COSMIC — Tutorial Early Sizing, Módulo 3: Early & NFR



<!-- pág 1/32 -->

EARLY SIZING OF REQUIREMENTS FOR 
ESTIMATION PURPOSES
MODULE 3: EARLY SIZING & NON-
FUNCTIONAL REQUIREMENTS (NFR)
Tutorial by Dr. ALAIN ABRAN
IWSM-MENSURA 2022, IZMIR (TURKEY)
A Tutorial with COSMIC Sizing – ISO 19761


<!-- pág 2/32 -->

Introduction
➢ Presents Early Sizing of software 
functions derived from System 
NFR (Non functional 
requirements) 
❖ This tutorial does not 
include effort estimation.
2
© Copyrights 2022 Alain Abran


<!-- pág 3/32 -->

List of Topics
© Copyrights 2022 Alain Abran
3
1. Key Concepts
2. From System NFR to Software Functions
3. Examples
4. EcoSystems & Architecture implementing
Systems NFR


<!-- pág 4/32 -->

Key concepts
Early in the lifecycle: 
➢ Requirements do not describe the full scope 
of functionality of the software with all the 
necessary functional details.
➢ Most of the time: requirements will be 
detailed & changed as the project 
moves through the life cycle. 
4
© Copyrights 2022 Alain Abran


<!-- pág 5/32 -->

Key Concept: from Simple to Complex Software
5


<!-- pág 6/32 -->

What is visible at Early requirements Phase
Contextual
1. Purpose
2. Scope
3. Product perspective
4. Product functions
5. User characteristics
6. Limitations 
7. Assumptions & dependencies
8. Apportioning of requirements
9. Specified requirements
1. Verification
2. Supporting documents 
Non-Functional & Quality
1. Usability requirements
2. Performance requirements
3. Logical database requirements
4. Design constraints
5. Standards compliance 
6. Software system attributes
External Interfaces
Functions
6
© Copyrights 2022 Alain Abran


<!-- pág 7/32 -->

List of Topics
© Copyrights 2022 Alain Abran
7
1. Key Concepts
2. From System NFR to Software Functions
3. Examples
4. EcoSystems & Architecture implementing
Systems NFR


<!-- pág 8/32 -->

Non-functional requirements (distinctions)
▪ There are types of requirements that cannot become functional: 
▪ Organizational constraints (location of operations, equipment used, 
compliance with standards) 
▪ Certain environmental constraints (e.g. interoperability) 
▪ Implementation constraints (development language, delivery date) 
▪ There are types of requirements that can be non-functional and 
become operational: 
▪ Quality constraints (reliability, efficiency) 
▪ Environmental constraints (safety)
8
© Copyrights 2022 Alain Abran
September 2022
8


<!-- pág 9/32 -->

Non-Functional Requirements (NFR)
Dr. Thomas Fehlmann, Dec. 2020
9
© Copyrights 2022 Alain Abran


<!-- pág 10/32 -->

NFR in Systems Standards
 
 
 
 
 
Non-Functional Requirements  
and  
COSMIC Sizing  
 
 Practitioner’s Guide 
 
 
 
 
May 19, 2020 
 
A- List of System-NFRs 
 
Id. NFR Standards used 
1 Performance ECSS-ISO-IEEE 
2 Maintainability ECSS-ISO-IEEE 
3 Portability ECSS-ISO-IEEE 
4 Security ECSS-ISO-IEEE 
5 Reliability ECSS-ISO-IEEE 
6 Interfaces ECSS-ISO-IEEE 
7 Operations ECSS-ISO-IEEE 
8 Adaptation & Installation ECSS-ISO-IEEE 
9 Safety ECSS-ISO-IEEE 
10 Resources ECSS-ISO-IEEE 
11 Human Factors ECSS-ISO-IEEE 
12 Data Definition & Data Bases ECSS-ISO-IEEE 
13 Configuration ECSS-ISO-IEEE 
14 Design ECSS-ISO-IEEE 
 
10


<!-- pág 11/32 -->

Some System NFR can be allocated to software & sized
Contextual
1. Purpose
2. Scope
3. Product perspective
4. Product functions
5. User characteristics
6. Limitations 
7. Assumptions & 
dependencies
8. Apportioning of 
requirements
9. Specified
requirements
1. Verification
2. Supporting doc. 
Non-Functional & 
Quality
1. Usability req. 
2. Performance req.
3. Logical database
req.
4. Design constraints
5. Standards 
compliance 
6. Software system 
attributes
External Interfaces
Functions Detailed Software 
Functions
Software 
Functions
Software 
Functions
© Copyrights 2022 Alain Abran
11


<!-- pág 12/32 -->

List of Topics
© Copyrights 2022 Alain Abran
12
1. Key Concepts
2. From System NFR to Software Functions
3. Examples
4. EcoSystems & Architecture implementing Systems NFR


<!-- pág 13/32 -->

NFR Example: System Security Requirements
4. Systems Security Requirements 
ID System Security Requirements  
 Model Sub-models Functions 
4 
System 
Security 
Environment 
(SSE) 
System confidentiality 
[1] Identification function 
[2] Authentication function 
[3] Authorization function 
System availability 
[4] Network redundancy function 
[5] Power redundancy function 
[6] Automatic restart function 
System integrity 
[7] Backup data function 
[8] Firewall function 
[9] Antivirus function 
[10] External PKI function 
[11] Encryption\decryption function 
 
13


<!-- pág 14/32 -->

System Security NFR -Example
ATM System security requirements defined in Meridji et al.  : 
▪ Requirement 1: the customer must insert his bank card into the ATM, allowing 
the latter to identify the customer. 
▪ Requirement 2: After the customer inserts the card, the system extracts the 
encrypted PIN and asks the user to enter their 8-digit PIN using the keypad to 
authenticate their identity. 
▪ Requirement 3: If the customer is authenticated, the ATM system must ensure 
that the customer's daily withdrawals do not exceed $800. Once verified, the 
customer can access the system. 
14
© Copyrights 2022 Alain Abran
14


<!-- pág 15/32 -->

Security Identification of requirements &  
control plans
ATM Security Services has a number of control plans: 
➢ User-plan Authentication: Determines at the start of the connection that 
the calling and/or called party identities are authentic. 
➢ User-plan Privacy: Provides cryptographic mechanisms that protect 
“user” data on a VC (Virtual Channel) from unauthorized disclosure. 
➢ User-plan Data integrity: Provides a mechanism to detect modification 
of data values or sequences of data values, even in the presence of 
malicious modification threats. 
➢ User-plan Access control: Requires mechanisms to convey access 
control information used during connection establishment, as well as 
mechanisms within ATM components to use this information to 
determine whether access to the connection must be granted. 
15
© Copyrights 2022 Alain Abran
15


<!-- pág 16/32 -->

Measurement of requirements 
➢ User-plan Authentication: Determines at the start of the 
connection that the calling and/or called party identities 
are authentic. 
❖ To identify the caller, we have an Entry, a Read and an Exit (*). 
➢ User-plan Privacy: Provides cryptographic mechanisms that 
protect 'user' data on a VC from unauthorized disclosure. 
❖ To do this there is an Entry (user code), 2 Reads (user and VC) 
and an eXit (recognition/non-recognition of the user) (*) 
(*) Actually more complex. Here we simplify a lot by considering only 1 or 2 data groups.
16
© Copyrights 2022 Alain Abran
16


<!-- pág 17/32 -->

Safety (NFR)
Example from: Khalid T. Al-Sarayreh
17
© Copyrights 2022 Alain Abran
17


<!-- pág 18/32 -->

Portability (NFR)
18
© Copyrights 2022 Alain Abran
18


<!-- pág 19/32 -->

Performance (NFR)
19
© Copyrights 2022 Alain Abran
19


<!-- pág 20/32 -->

Performance Example
System requirement: 7-day software availability level - Target = 95% 
▪ The data is in a log. Develop a weekly report from the log data on the WEB site. 
▪ Detailed requirements (& data movements): 
▪ an Entry for the information coming from the log
▪ an eXit for the information presented to the user
▪ a Read and an Exit for the error message
➢ Functional =  4 CFP (COSMIC Function Points)
Exercise: What if availability and date belong to two different data groups? Could 
you do the CFP calculation. 
20
© Copyrights 2022 Alain Abran
20


<!-- pág 21/32 -->

Performance (NFR)
Example 2: Performance NFR that can be 
translated into different functional requirements:
• Bandwidth Function: 
• Bandwidth history log to be created. 
• Workload Function: A history of the workload. 
• Response time: A log of the response time. 
• Setting the time function: 
• an interface to set the time function and 
• a process to show the results
• Tracking Error Function: A log of tracking errors 
We identify at least 6 functional processes.  
Exercise: How many CFP?
21
© Copyrights 2022 The COSMIC Group
© Copyrights 2022 Alain Abran
21


<!-- pág 22/32 -->

Exercise
▪ This exercise is about defining four quality standards and showing how 
you can measure them as a functional process. 
▪ If this is not possible, explain why. 
▪ Use a document you know. 
Note: it is always important to keep traceability. 
22
© Copyrights 2022 Alain Abran
22


<!-- pág 23/32 -->

List of Topics
© Copyrights 2022 Alain Abran
23
1. Key Concepts
2. From System NFR to Software Functions
3. Examples
4. EcoSystems & Architecture implementing
Systems NFR


<!-- pág 24/32 -->

Software: Applications & Infrastructure
24


<!-- pág 25/32 -->

Software Ecosystem
25


<!-- pág 26/32 -->

Software: Applications & Infrastructure & Ecosystem
26
Brisebois, Abran,  Nadembega, ‘A Semantic Metadata Enrichment Software Ecosystem (SMESE) Based on a 
Multi-Platform Metadata Model for Digital Libraries’, Journal of Software Engineering and Applications –
JSEA, Vol. 10, April 2017, pp. 370-405.


<!-- pág 27/32 -->

September 2022
27
Service Oriented Architecture Sizing with COSMIC
COSMIC-SOA Exchange 
Messages
COSMIC-SOA 
Intermediary Services
COSMIC-SOA Exchange 
Data 
© Copyrights 2022 Alain Abran


<!-- pág 28/32 -->

28
Source: Charles Symons – Sept. 2018


<!-- pág 29/32 -->

Conclusion
▪ A certain number of system requirements, which appear at first 
glance without measurable software functions, can be 
translated into software functional requirements and be 
measured with the COSMIC method. 
29
© Copyrights 2022 Alain Abran
29


<!-- pág 30/32 -->

COSMIC Guides through the lifecycle
© Copyrights 2022 Alain Abran
30


<!-- pág 31/32 -->

COSMIC Key Resources Available
✓ Sizing with accuracy : ISO rules in ISO 19761
✓ Early sizing techniques
✓ System non-functional reqmts (NFR) allocated to software 
functions
✓ Case studies
✓ Industry examples
Free www.cosmic-sizing.org
31


<!-- pág 32/32 -->

Early or Rapid COSMIC Functional Size Measurement
QUESTIONS?