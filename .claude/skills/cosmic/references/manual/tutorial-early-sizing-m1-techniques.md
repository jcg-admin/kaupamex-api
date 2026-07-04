<!-- Extraído de e208ecae-TutorialEarlySizingModule1Descriptionoftechniques.pdf (52 págs) por pypdf — 2026-06-03T03:41:43Z. Fuente COSMIC. -->
# COSMIC — Tutorial Early Sizing, Módulo 1: Descripción de técnicas



<!-- pág 1/52 -->

EARLY SIZING OF REQUIREMENTS 
FOR ESTIMATION PURPOSES
Module 1: Description of Techniques
Tutorial by Dr. ALAIN ABRAN
IWSM-MENSURA 2022, IZMIR (TURKEY)
A Tutorial with COSMIC Sizing – ISO 19761


<!-- pág 2/52 -->

Introduction
Tutorial modules:
1. Description of techniques
2. Which one to select?
3. Early sizing & Non-Functional 
Requirements (NFR)
➢ This tutorial does not include effort estimation.
2
Tutorial is based on:
© Copyrights 2022 Alain Abran


<!-- pág 3/52 -->

Key concepts
Early in the lifecycle: 
➢ Requirements do not describe the full scope 
of functionality of the software with all the 
necessary functional details.
➢ Most of the time: requirements will be 
detailed & changed later as the project 
moves through the life cycle or Sprints. 
3
© Copyrights 2022 Alain Abran


<!-- pág 4/52 -->

Key Concepts – Post implementation
4
 Measurement
Standards
Precision of 
mesurement
requires: 
full & complete
information
© Copyrights 2022 Alain Abran


<!-- pág 5/52 -->

Pre & Post Implementation
5
© Copyrights 2022 Alain Abran


<!-- pág 6/52 -->

Organization Data 
Repository
Measurers & developers must develop a 
clear understanding of: 
1. The ‘completeness’ of the information 
available at the time of measurement 
& 
2. How to deal with such incompleteness 
with an Early Sizing technique
3. How this impacts the accuracy or 
estimation of size. 
Measurement or Estimation of Size?
 
 
The COSMIC Functional Size Measurement Method 
Version 4.0.1 
  
GGuuiiddeelliinnee  ffoorr  EEaarrllyy  oorr  RRaappiidd  
CCOOSSMMIICC  FFuunnccttiioonnaall  SSiizzee  
MMeeaassuurreemmeenntt  
bbyy  uussiinngg  aapppprrooxxiimmaattiioonn  aapppprrooaacchheess 
 
 
 
 
 
July 2015 
Guidelines 
for Accuracy
6
© Copyrights 2022 Alain Abran


<!-- pág 7/52 -->

Early Sizing Techniques in this Tutorial
1. Software Iceberg Analogy
2. Average size of a functional process 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Patterns
7
© Copyrights 2022 Alain Abran
7


<!-- pág 8/52 -->

1- Iceberg Analogy
Initially visible 
requirements
Visibility increases
Additional sizing is 
required
8


<!-- pág 9/52 -->

1- Software iceberg analogy & sizing ratios
Level 2: 
Functions 
allocated to 
software
Level 1:
Business 
functions
Level 3:
Operational
Functionality
Level 4:
Quality & NFR 
allocated to software
%
% 100% 
9


<!-- pág 10/52 -->

1- Case study: Course Registration System
In the Course Registration Case Study: Distribution of COSMIC CFP 
size
➢ 21 % System functions allocated to software
➢ 9 % + Details of business functions
➢ 42 % Operational functionality
➢ 30 % Implementation of quality (data integrity)
10


<!-- pág 11/52 -->

1- Scaling factors of Requirements
In the Course Registration Case Study:
➢ System functions: 20% leads to a 1: 5 scaling factor  
✓ Example: a size of 10 FP would lead to 10x5= 50 CFP when fully specified, including operational 
functions and data integrity functions.
➢ Detailed functions: 20%+9% (= 29%) leads to a 1: 3.4 scaling factor 
✓ a size of 20 CFP would lead to 20CFP x 3.4 = 68 CFP
➢ Operational functionality: 20%+9%+41%= 70% leads to a 1: 1.43 scaling factor
✓ a size of 20 CFP would lead to 20CFP x 1.43 =  29 CFP 
1: 5 1: 3.4 1: 1.43
1: 1
11


<!-- pág 12/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of a functional process 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Patterns
12
© Copyrights 2022 Alain Abran
12


<!-- pág 13/52 -->

2- Average Size of a Functional Process - Example
Steps for Sampling & Calculation of an average functional 
process:
1. Identify a sample of requirements whose functional processes & 
data movements have been defined in detail.
2. Identify the functional processes within this sample.
3. Measure precisely the sizes of the functional processes of the 
sample.
4. Calculate the average size, in CFP, of the functional processes in the 
sample 
▪ average size = 8 CFP per Functional Process
-> ‘8’ is the scaling factor 
13
© Copyrights 2022 Alain Abran


<!-- pág 14/52 -->

2- Average Size of a Functional Process
Early sizing using the average of the sample
1. Identify & count all functional processes 
➢ 40 Functional Processes
2. Estimated functional size =
➢ Number of functional processes x scaling factor 
= 40 x 8 = 320 CFP
✓ Valid as long as the sample used to calculate the size of the average 
functional process is representative for the software being estimated.
14
© Copyrights 2022 Alain Abran


<!-- pág 15/52 -->

2- Average size of a functional process 
15
Exercise: add 20 new FP and Modify 5 existing ones
 From past projects, or from the few detailed FUR of the current 
project, calculate the average size of new FPs and modified FPs 
Solution:
 Extrapolate the size with the calculated FP averages:
Average size of New FP Modified FP
(in CFP) 8.0 CFP 3.5 CFP
New FP Modified FP Total
Number of 20 FP 5 FP 25 FP
Expected size (rounded) 160 CFP 18 CFP 178 CFP
© Copyrights 2022 Alain Abran


<!-- pág 16/52 -->

Example from the Restaurant Case Study
16
© Copyrights 2022 Alain Abran


<!-- pág 17/52 -->

Example - Resto-Sys
Users of the “Resto-Sys”:
▪ Administrator: manager of the 
application. 
▪ Can manage the entire “Resto-Sys”.
▪ Can access to the web application 
via his username and his password
▪ Waiter: responsible for customers' 
orders. 
▪ Can access to the mobile app via his 
Smartphone and using his username 
and his password
17
© Copyrights 2022 Alain Abran


<!-- pág 18/52 -->

Example - Resto-Sys
18
• Total Size: 126 CFP
• 31 Functional Processes
© Copyrights 2022 Alain Abran


<!-- pág 19/52 -->

EXAMPLE - Resto-Sys
Total Size: 126 CFP
▪ 31 Functional Processes
➢ Average Size:  126/31 =  4.1 CFP 
➢ Median: 3 CFP
➢ Std Deviation: 3.2 CFP [range 2 to 7.3 CFP]
❖ Exercise 1:
➢ Estimate the size of 7 Functional 
processes?
➢ = 7 x 4.1= 28.7 CFP = 29 CFP  
➢ [range 14 to 51 CFP]
19
© Copyrights 2022 Alain Abran


<!-- pág 20/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of functional processes 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Patterns
20
© Copyrights 2022 Alain Abran
20


<!-- pág 21/52 -->

3- Fixed Size Classification
A. Functional Processes are identified & classified 
according to their size in 1 of 3+ size classes: 
▪ Example of 3 classes: Small, Medium and Large. 
B. Each actual requirement is assigned: 
1. 1 or more functional processes, 
2. together with their appropriate size classification, and
3. corresponding size approximation. 
21
© Copyrights 2022 Alain Abran


<!-- pág 22/52 -->

3- Fixed Size Classification
Example 1 of a classification with 3 size classes: 
➢ sizes based on an expected number of data movements
Classification Size (CFP) #E #X #R #W Error messages
Small 5 1 1 1 1 1
Medium 10 2 2 3 2 1
Large 15 3 3 4 4 1
…
22
© Copyrights 2022 Alain Abran


<!-- pág 23/52 -->

3- Fixed size EXAMPLE – Resto-Sys 
Min: 2 CFP
Max: 18 CFP
Average: 4.1CFP
Median: 3 CFP
Std Deviation: 3.2 CFP
Data Set (FP sizes) Example with 4 classes of size:
• Small 
• Medium
• Large
• Very Large
Range  = max – min = 18 CFP -2 CFP = 16 CFP 
-> Class range = 16/4 = 4 CFP  
Size Class Scaling Factor
Small 4
Medium 8
Large 12
Very Large 16
23
© Copyrights 2022 Alain Abran


<!-- pág 24/52 -->

3- Fixed Size EXAMPLE – Resto-Sys
Exercise: estimate the size of 8 functional processes, 
of which:
1. 5 have been classified as Small
2. 2 have been classified as Medium
3. None classified as large
4. 1 has been classified as very large
Estimate size with the 4 classes of the Resto-Sys
Apply scaling factors: 
5 Small → 5 x 4 CFP 
2 Medium → 2 x 8 CFP
0 Large → 0 x 12 CFP
1 Very large → 1 x 16 CFP
~ 52 CFP 
24
© Copyrights 2022 Alain Abran


<!-- pág 25/52 -->

3- Fixed size classification
Example 2 of a fixed-size classification based on:
➢ number of data groups (DGs) within a functional process.
. 
• After identifying the number of Small, Medium and Large functional processes in 
your project, calculate the total approximated size in COSMIC function points 
(CFP).
25
Classification Size (CFP) Nbr of DGs
Small 5 1
Medium 10 2
Large 15 3-4
© Copyrights 2022 Alain Abran
25


<!-- pág 26/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of functional processes 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Size Patterns
26
© Copyrights 2022 Alain Abran
26


<!-- pág 27/52 -->

4- Equal Size Bands
1. Functional Processes are classified into a small number of size 
bands.
2. Boundaries of bands are chosen so that the total size of all the 
functional processes in each band is the same for each band. 
Examples:
▪ If 3 bands are used: 
➢ total size of all functional processes in each band = 33% of total size.
▪ If 5 bands are used: 
➢ total size of all functional processes in each band = 20% of total size
27
© Copyrights 2022 Alain Abran


<!-- pág 28/52 -->

4- Equal size bands 
To establish a classification of functional processes into equal size bands: 
1. Take a sample of precisely measured FPs, 
2. Sort them by size; 
3. Divide into 3-4 bands of equal size.
Example with 4 bands: Small, Medium, Large and Very Large  
28
Band Average FP Size (CFP) % of total size % of #FPs
Small 4.8 25% 40%
Medium 7.7 25% 26%
Large 10.7 25% 19%
Very large 16.4 25% 15%
© Copyrights 2022 Alain Abran
28


<!-- pág 29/52 -->

4- Equal Size EXAMPLE – Resto-Sys
Total Size: 126
▪ When 4 Equal Size Bands are selected:
➢ Each band should contribute %25 of the total 
size -> 126 ∕ 4 = 31,5
29
© Copyrights 2022 Alain Abran


<!-- pág 30/52 -->

4- Equal Size Band EXAMPLE – Resto-Sys
2 2 2 2 2 2
3 3 3 3 3 3 3 3 3 3
4 4 4 4 4 4 4 4 4 4 4 4
5
13
18
0
2
4
6
8
10
12
14
16
18
20
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
FP Sizes - Ordered
Series1
2 4 6 8 10 12 15 18 21 24 27 30 33 36 39 42 46 50 54 58 62 66 70 74 78 82 86 90
95
108
126
0
20
40
60
80
100
120
140
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
Chart Title30
© Copyrights 2022 Alain Abran


<!-- pág 31/52 -->

4- Equal Size Band EXAMPLE – Resto-Sys
Average sizes per class. 
▪
30
13 = 2.3
▪
(62−30)
(22−13) = 
28
9 = 3.1
▪
(95−62)
(29−22) = 
33
7 = 4.7
▪
(126−95)
(31−29) = 
31
2 = 15.52 4 6 8 10121518212427303336394246505458626670747882869095
108
126
0
20
40
60
80
100
120
140
1 3 5 7 9 11 13 15 17 19 21 23 25 27 29 31
31
© Copyrights 2022 Alain Abran


<!-- pág 32/52 -->

4- Equal Size Band EXAMPLE – Resto-Sys
Band Average size of a 
Functional Process
% of total
Functional Size
% of total number
of Functional Processes
Small 2.3 25% 42%
Medium 3.1 25% 29%
Large 4.7 25% 23%
Very Large 15.5 25% 6%
32
© Copyrights 2022 Alain Abran


<!-- pág 33/52 -->

4- Exercise: Equal Size Band
Steps:
1. Assign a size class (Judgement)
2. Use respective scaling factor for that class size. 
Example:
Approximate size = ~33 CFP
33
5 Small 
2 Medium
0 Large
1 Very large
5 Small         5 x 2.3 
2 Medium      2 x 3.1
0 Large         0 x 4.7
1 Very large  5 x 15.5 
© Copyrights 2022 Alain Abran


<!-- pág 34/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of functional processes 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Size Measurement Patterns
34
© Copyrights 2022 Alain Abran
34


<!-- pág 35/52 -->

5- Average size of Use Cases 
35
 A Use Case (UC) may be refined into one to several 
Functional Processes (FP)
 Local calibration might determine that a (locally-defined) UC 
comprises, on average, 3.5 functional processes, each FP of an 
average size = 8.0 CFP
 In that case, the average size of a UC, according to this local 
definition, is 3.5FP/UC x 8.0CFP/FP = 28 CFP per Use Case
 To approximate the project size, apply this average on the 
number of Use Cases
© Copyrights 2022 Alain Abran


<!-- pág 36/52 -->

5- Average Use Case Size
Example of a use case with:
▪ 6 functional processes on average for a use case (Std Deviation:  ?? FP) 
▪ each functional process on average size = 8 CFP
▪ Std Deviation:  ?? CFP           [range + or – 1 Std CFP]
➢ Hence the average size of a use case = ? = 8 x 6 = 48 CFP per use case.
For a new project with 12 use cases = ?
➢ software size would be 12 x 48 = 576 CFP.
Note: The uncertainty on this approximate size will be greater: 
➢ the scale factor 48 is the product of 2 scale factors (8 & 6) which are themselves estimated. 
36
© Copyrights 2022 Alain Abran


<!-- pág 37/52 -->

5- Average Use Case EXAMPLE – Resto-Sys
Use 
Case
Function
al 
Process
Use 
Case 
Size
FUR1 FP1 5 5
FUR2 FP2 18 31
FP3 13
FUR3 FP4 4 4
FUR4 FP5 4 16
FP6 4
FP7 3
FP8 2
FP9 3
FUR5 FP10 4 16
FP11 4
FP12 3
FP13 2
FP14 3
FUR6 FP15 4 13
FP16 4
FP17 3
FP18 2
FUR7 FP19 3 19
FP20 4
FP21 4
FP22 3
FP23 2
FP24 3
FUR8 FP25 4 16
FP26 4
FP27 3
FP28 2
FP29 3
FUR9 FP30 4 6
FP31 2
Total size = 126 CFP
➢ 9 Use Cases
▪ Average Use Case size = ? 
➢ 126/9 = 14 CFP per Use Case
➢ Std Deviation:  ?? CFP
37
© Copyrights 2022 Alain Abran


<!-- pág 38/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of functional processes 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Size Measurement Patterns
38
© Copyrights 2022 Alain Abran
38


<!-- pág 39/52 -->

6- Early & Rapid technique (1 of 2)
39
i.e. 
Module
i.e. 
App.
i.e. per 
business 
object
© Copyrights 2022 Alain Abran
39


<!-- pág 40/52 -->

Similar to fixed size classification:
➢ By analyzing the functional processes already measured, get an 
idea of the number of FPs and the size per business object
▪ Do we have a CRUD (3, 4 or 5 functional processes) or a report 
(one functional process)? 
▪ Examples: 
o Only one primary data group of a small CRUD → Use 15.6 CFP. 
o A report most often uses more than one data group → 6.9 CFP. 
Note: 
✓ For a CRUD, the expression is often ‘manage <business object>’, while 
for a report the expression is simply ‘list or report on <business object>’. 
40
6- Early & Rapid technique (2 of 2)
© Copyrights 2022 Alain Abran
40


<!-- pág 41/52 -->

Early Sizing Techniques in this Module
1. Software Iceberg Analogy
2. Average size of functional processes 
3. Fixed size classification
4. Equal size bands
5. Average size of use cases 
6. Early & Rapid sizing
7. Functional Size Patterns
41
© Copyrights 2022 Alain Abran
41


<!-- pág 42/52 -->

Functional Size Measurement Patterns
Observations of measurers:
➢ some patterns of measurement results recur 
repeatedly. 
➢ Four types of patterns
Micro 
Pattern 
e.g. error 
message
Basic 
Pattern 
one whole 
functional 
process
Composite 
Pattern
e.g. a 
CRUD set 
of 
functional 
processes 
for one 
OOI
Multi-
composite
Pattern
e.g. a sub-
system
42
© Copyrights 2022 Alain Abran


<!-- pág 43/52 -->

Functional Size Patterns
▪ Micro FSM patterns: A fragment of a functional process, involving one or several data 
groups.  
Example: displaying an error message.
▪ Basic FSM patterns: A complete single COSMIC functional process.
▪ Composite FSM pattern: A set of basic FSM patterns having a high level functional 
meaning together. 
Example: The CRUDL (Create, Retrieve, Update, Delete, List) set of FPs to 
maintain data . 
▪ Multi-composite FSM pattern: A set of composite and basic patterns having 
functional relationships among them. 
▪ In business application software, a multi-composite FSM pattern could represent a whole module, or 
component of a distributed application or even a whole application.
▪ In embedded/real-time systems, it could be the set of back-end subsystem functionalities for a 
family of devices.
43
© Copyrights 2022 Alain Abran


<!-- pág 44/52 -->

Functional Size Patterns
Example for Micro FSM pattern:
▪ Display simple error messages.
Functional Process Data Group Data Movements Functional Size 
(in CFP)
<Functional process> Error message X 1
Total: 1
44
© Copyrights 2022 Alain Abran


<!-- pág 45/52 -->

Functional Size Patterns
Example of a Composite pattern:
▪ CRUDL with 3 Data Groups 
Functional Process Data Group Data Movements Functional Size (in 
CFP)
Remark
Create <First DG> <First DG> ERW 3 Create new occurrence
<Second DG> RX 2 Read and display list
<Third DG> RX 2 Read and display list
Error message X 1 Subtotal: 8 CFP
Retrieve <First DG> <First DG> ERX 3 Select, read and display 
existing occurrence
<Second DG> RX 2 Must read its ID to display 
its name
<Third DG> RX 2 Same as above
Error message X 1 Subtotal: 8 CFP
Total: 36 For this FSM pattern
45
© Copyrights 2022 Alain Abran


<!-- pág 46/52 -->

Applicability & Reported Use
Example for a Basic Pattern:
▪ Create 1 data group
Functional Process Data 
Group
Data 
Movements
Functional Size 
(in CFP)
Remark
Create <data group> <data
group>
ERW 3 Creates a new
occurrence
Error
message
X 1
Total: 4
46
© Copyrights 2022 Alain Abran


<!-- pág 47/52 -->

Functional Size Measurement Patterns
Update <First DG> <First DG> ERW 3 Update existing occurrence
<Second DG> RX 2 Read and display list
<Third DG> RX 2 Read and display list
Error message X 1 Subtotal: 8 CFP
Delete a <First DG> <First DG> ERW 3 Delete an occurrence, reas it first, 
no other DG required
Message X 1 Subtotal: 4 CFP
List <First DG> <First DG> RX 2 Read and display list
Filter E 1 Search filter applicable to all DGs
<Second DG> RX 2 Read/display list (filter)
<Third DG> RX 2 Same as above
Error message X 1 Subtotal: 8 CFP
47
© Copyrights 2022 Alain Abran


<!-- pág 48/52 -->

Functional Size Patterns
Example of a Multi-Composite pattern:
▪ A Module with 3 Data Groups 
FSM Pattern Category Functional Size (in 
CFP)
Remark
CRUDL-3DG Composite 36 Ex. for “Customer”
CRUDL-1DG Composite 20 Ex. for “Sales Rep”
CRUDL-1DG Composite 20 Ex. for “Customer category”
CRUD-2DG Composite 22 Ex. for “Account aging parameters”
CRUD-3DG Composite 26 Ex. for “Invoicing parameters”
CRUD-3DG Composite 26 Ex. for “Cash receipt (C/R) parameters”
Transaction-7DG Basic 12 Ex. for “Enter manual invoices”
Transaction-6DG Basic 10 Ex. for “Enter a manual cash receipt”
Transaction-8DG Basic 14 Ex. for “Enter adjustment on Invoice or C/R”
Report-3DG Basic 7 Ex. for “Report on customer sales”
Report-4DG Basic 9 Ex. for “Customer aging report”
Report-5DG Basic 11 Ex. for “Customer statement of account”
Milestone-2DG Basic 10 Ex. for “End of month A/R processing”
Total: 223 For this FSM pattern
48
© Copyrights 2022 Alain Abran


<!-- pág 49/52 -->

Patterns EXAMPLE – Resto – Sys
▪ Basic Pattern: “Logon”
Functional Process Data Group Data 
Movements
Functional Size (in 
CFP)
Remark
Logon For <data 
group>
<data
group>
EXR 3 Checks credentials 
and opens a session 
for the user
Error
message
X 1
Total: 4
49
© Copyrights 2022 Alain Abran


<!-- pág 50/52 -->

Composite pattern in RestoSys
“Manage” =
➢Add, View, Modify, Delete, List : CRUDL
Functional Process Data Group Data 
Movements
Functional Size (in 
CFP)
Remark
Add <DG> <First DG> ERW 3 Create new occurrence
Error message X 1 Subtotal: 4 CFP
View <DG> <First DG> ERX 2 Select, read and display existing occurrence
Subtotal: 2 CFP
Modify  <DG> <First DG> EW 2 Update existing occurrence
Error message X 1 Subtotal: 3 CFP
Delete a <DG> <First DG> EW 2 Delete an occurrence, read it first, no other DG 
required
Message X 1 Subtotal: 3 CFP
View List of <DG> <First DG> ERX 3 Read and display list
Error message X 1 Subtotal: 4 CFP
Total: 16 For this FSM pattern
50
© Copyrights 2022 Alain Abran


<!-- pág 51/52 -->

Early or Rapid COSMIC Functional Size Measurement
QUESTIONS?


<!-- pág 52/52 -->

Group Exercise
52
Info Sources 
Quality
Functional
Process
Average
Use Case 
Average
Fixed Size 
Bands
Equal Size 
Bands
Functional
Patterns
A Complete
B Partial
C Identified
D Counted
E Implied
Which technique used in which context?
© Copyrights 2022 Alain Abran