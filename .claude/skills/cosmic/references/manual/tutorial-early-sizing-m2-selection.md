<!-- Extraído de ba7ad660-TutorialEarlySizingModule2Selectionoftechniques.pdf (34 págs) por pypdf — 2026-06-03T03:41:43Z. Fuente COSMIC. -->
# COSMIC — Tutorial Early Sizing, Módulo 2: Selección de técnicas



<!-- pág 1/34 -->

EARLY SIZING OF REQUIREMENTS FOR 
ESTIMATION PURPOSES
MODULE 2: SELECTION OF TECHNIQUES
Tutorial by Dr. ALAIN ABRAN
IWSM-MENSURA 2022, IZMIR (TURKEY)
A Tutorial with COSMIC Sizing – ISO 19761


<!-- pág 2/34 -->

Introduction
➢ This tutorial presents strengths & 
weaknesses of Early Sizing 
technique 
❖ This tutorial does not 
include effort estimation.
2
Tutorial is based on:
© Copyrights 2022 Alain Abran


<!-- pág 3/34 -->

Topics in this Module 2
3 Selection of a technique based on:
1. Strengths & Weaknesses
2. Quality of the Sources of Information
3. Which technique to select?
4. Recommendations (optional)
© Copyrights 2022 Alain Abran


<!-- pág 4/34 -->

Average Functional Process technique
Strength: 
▪ Easy to use. 
Weaknesses:
▪ Domain dependent.
▪ Requires sampling of detailed measurements from 
the organization. 
▪ This data is often not (yet) available.
4
© Copyrights 2022 Alain Abran


<!-- pág 5/34 -->

Average Use Case technique
Strengths:
▪ Easy to use if there is a local standard on what is a Use Case, more specifically 
describing the expected level of granularity of a Use Case.
Weaknesses:
▪ Concept of Use Case is interpreted in different ways by different organizations 
and people, so that the amount of functionality associated to a Use Case can 
vary widely [11]: 
➢ will not work unless the organization producing Use Cases adopts some sort of 
standard to ensure consistency in their size.
▪ The scaling factor is the product of 2 other scaling factors which are 
themselves estimated. 
➢ This increases the uncertainty of the approximation result.
5
© Copyrights 2022 Alain Abran


<!-- pág 6/34 -->

Fixed Size Classification technique
Strengths:
▪ Easy to use.
▪ Can be implemented in a simple way.
Weaknesses: 
▪ Domain dependent.
▪ Assigning functional processes to a size class is 
subjective.  
6
© Copyrights 2022 Alain Abran


<!-- pág 7/34 -->

Fixed Size Classification technique
1. Proved to be useful on software with small, relatively 
simple FPs of limited size range. 
2. The approach can easily be extended to account for FPs 
with more data movements. 
3. Adequate choice of size classes is crucial for achieving 
good estimates.
4. Valid as long as size classifications are representative for 
the measured software. 
5. Objective local rules to assist Measurers in assigning the 
correct classification are suggested.
7
© Copyrights 2022 Alain Abran


<!-- pág 8/34 -->

Equal Size Bands technique
Strengths:
• Easy to use.
• Applicable for both business application and real-time domains.
Weaknesses:
• Band sizes should be determined carefully. (Variance analysis can be 
used). 
• Assigning FPs to a size class is a subjective process. 
• When there are few number of FPs in the “Very Large” band, “average 
size” should be used carefully. 
8
© Copyrights 2022 Alain Abran


<!-- pág 9/34 -->

Equal Size Bands technique 
Recommended Area of Application
1. Recommended for software that has a significantly 
skewed distribution of the size of its FPs.
2. Valid as long as size classification is considered to be 
representative for the software at hand. 
3. Local rules should be determined to assist Measurers in 
assigning the correct classification.
4. The greater the skew, the accurate the method gets. 
9
© Copyrights 2022 Alain Abran


<!-- pág 10/34 -->

Equal Size Bands technique
Applicability and Reported Use
▪ Software systems typically have many small FPS and 
larger FPs are fewer. 
10
© Copyrights 2022 Alain Abran


<!-- pág 11/34 -->

Software Iceberg Analogy
11
Strengths:
Very earliest stages with requirements known only in the broadest outline:
it is possible to determine sizing factors using the iceberg analogy with
known sizes of other existing software already sized.
Weakness:
Can be used in most organizations provided that data can collected on past
projects and identify classifications of functionalities and levels of
documentation that are relevant to the context.
Scaling factors in the Course Registration Case Study
1: 5 1: 3.4 1: 1.43 1: 1
© Copyrights 2022 Alain Abran


<!-- pág 12/34 -->

Functional Size  Patterns
Strengths:
▪ Reduces measurement effort.
▪ Could be applied by relatively inexperienced users of 
the COSMIC method.
▪ Increases accuracy by helping to avoid common 
measurement mistakes.
▪ Enables improved repeatability of early size estimation.
12
© Copyrights 2022 Alain Abran


<!-- pág 13/34 -->

Functional Size Patterns
Weaknesses:
▪ FSM patterns and their usage have not yet been 
quantitatively evaluated against the solution objectives 
for COSMIC FSM. More case studies and research is 
needed.
▪ A set of COSMIC FSM Patterns still needs to be 
developed and made available.
▪ COSMIC measurement support tools should implement 
the concept of FSM patterns.
13
© Copyrights 2022 Alain Abran


<!-- pág 14/34 -->

Topics in this Module 2
14 Selection of a technique based on:
1. Strengths & Weaknesses
2. Quality of the Sources of Information
3. Which technique to select?
4. Recommendations (optional)
© Copyrights 2022 Alain Abran


<!-- pág 15/34 -->

Analogy in Engineering: 
Quality of Information Sources at Measurement
Availability of 
requirements for 
measurement
purposes
15
© Copyrights 2022 Alain Abran


<!-- pág 16/34 -->

Quality of Information Sources
Table 1: Quality rating of an individual functional process 
Rating Functional Process Quality 
Level 
Quality of the functional process definition 
(a) Completely defined The functional process and its data movements are 
completely defined 
(b) Partially Documented The functional process is partially documented: not in 
sufficient detail to identify all the data movements 
(c) Identified The functional process is listed but no details are 
given of its data movements 
(d) Counted A count of the functional processes is given, but there 
are no more details 
(e) Implied (a ‘k nown unknown’), not 
mentioned or missing (an 
‘unknown unknown’) 
The functional process is implied in the actual 
requirements but is not explicitly mentioned, or is 
missing 
 
 
 
 
 
Guideline on the Accuracy of  
COSMIC Function Points 
 
 
 
VERSION 1.1 
July 2018 
 
 
 
 
 
 
 
 
 
Copyright 2018. All Rights Reserved. The Common Software Measurement International Consortium (COSMIC).  Permission 
to copy all or part of this material is granted provided that the copies are not made or distributed for commercial advantage 
and that the title of the publication, its version number, and its date are cited and notice is given that copying is by permission 
of the Common Software Measurement International Consortium (COSMIC). To copy otherwise requires specific permission. 
A public domain version of the COSMIC documentation and other technical reports, including translations into other languages 
can be found on the Web at www.cosmic-sizing.org . 
16
© Copyrights 2022 Alain Abran


<!-- pág 17/34 -->

Context Approach
▪ Based on the characteristics they could choose to 
utilize different Early Sizing techniques for different 
categories: 
Rating Sizing technique to be Used
A Precise COSMIC Measurement
B Precise COSMIC Measurement x 1.2
C Average, Patterns
D FSM Patterns
E %12 of sum of other categories
17
© Copyrights 2022 Alain Abran


<!-- pág 18/34 -->

Quality of Actual Requirements
b – Partially  Documented
▪ Functional processes are documented but not in sufficient 
detail to identify the data movements.
➢ May Use:
▪ Average Functional Process Approximation
▪ Average Use Case Approximation
▪ Fixed Size Classification Approximation
▪ Equal Size Bands Approximation
▪ Functional Size Patterns
18
© Copyrights 2022 Alain Abran


<!-- pág 19/34 -->

Quality of Actual Requirements
c - Identified
▪ Functional processes are listed but no details are given of 
its data movements
➢ May use:
▪ Average Functional Process Approximation
▪ Average Use Case Approximation
▪ Functional Size Measurement Patterns
19
© Copyrights 2022 Alain Abran


<!-- pág 20/34 -->

Quality of Actual Requirements
d - Counted
A count of the functional processes is given, but there are no 
more details
➢ May use:
▪ Average Functional Process Approximation
▪ Average Use Case Approximation
▪ Functional Size Patterns
20
© Copyrights 2022 Alain Abran


<!-- pág 21/34 -->

Quality of Actual Requirements
e - Implied (A ‘known unknown’)
▪ The functional process is implied in the actual 
requirements but is not explicitly mentioned
➢ May Use:
1. Average Functional Process Approximation
2. Average Use Case Approximation
3. Fixed Size Classification Approximation
4. Equal Size Bands Approximation
5. Functional Size Patterns
➢ May require Judgements.
21
© Copyrights 2022 Alain Abran


<!-- pág 22/34 -->

Quality of Actual Requirements
Not mentioned requirements: 
➢ An ‘unknown unknown’
▪ Existence of the functional processes is completely 
unknown at present
▪ Expert judgment with a contingency for ‘scope creep’ on 
the basis of past experience.
22
© Copyrights 2022 Alain Abran


<!-- pág 23/34 -->

Quality of Actual Requirements
a - Completely Defined
▪ Functional process and its data movements are completely 
defined.
➢ Use standard COSMIC FSM method
23
© Copyrights 2022 Alain Abran


<!-- pág 24/34 -->

Topics in this Module 2
24 Selection of a technique based on:
1. Strengths & Weaknesses
2. Quality of the Sources of Information
3. Which technique to select?
4. Recommendations (Optional)
© Copyrights 2022 Alain Abran


<!-- pág 25/34 -->

How to select which technique to use
❖ Is there a list of functional processes? 
➢ If yes - candidate techniques: 
▪ Average size of functional processes 
▪ Fixed size classification, 
▪ Equal size bands
❖ Is there a meaningful sample of requirements? 
➢ Average Size of Functional Processes,
➢ Equal size bands 
➢ Software Iceberg analogy
25
© Copyrights 2022 Alain Abran
25


<!-- pág 26/34 -->

How to select which technique to use (2 of 2)
❖ Is there only a list of Use Cases? 
➢ If yes, 
➢ Average size of use cases, or 
➢ Early & rapid sizing (typical process) 
➢ Software Iceberg analogy
❖ Can the number of functional processes be approximated by looking at 
Use Cases ? 
➢ If yes: Fixed size classification
➢ If not:, approximate the size of the use cases 
(small, medium or large)?
▪ If yes, Early & Rapid sizing
▪ If not, estimate size by asking whether the overall process is small-medium- large. 
26
© Copyrights 2022 Alain Abran
26


<!-- pág 27/34 -->

Summary comparison of some techniques
27
© Copyrights 2022 Alain Abran
27


<!-- pág 28/34 -->

Group Exercise
28
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
Which technique to select in which context?
© Copyrights 2022 Alain Abran


<!-- pág 29/34 -->

Topics in this Module 2
29 Selection of a technique based on:
1. Strengths & Weaknesses
2. Quality of the Sources of Information
3. Which technique to select?
4. Recommendations (Optional)
© Copyrights 2022 Alain Abran


<!-- pág 30/34 -->

Recommendations
Before selecting any early sizing technique: 
1. Assess the quality of requirements  at hand.
2. Examine historical data: 
➢ identify characteristics such as averages, deviation and distribution. 
3. Determine management’s need for accuracy of sizing. 
4. Select early sizing technique that suits your conditions.
30
© Copyrights 2022 Alain Abran


<!-- pág 31/34 -->

Recommendations
With a requirements document that you know, it is suggested 
that you use 2 techniques: 
A) Average size of functional processes or 
B) Early & Rapid COSMIC approximation
When you have the list of functional processes:
➢ Technique A will be more accurate. 
When you only have the list of Use Cases: 
➢ look at the values at the level of Typical Processes. 
31
© Copyrights 2022 Alain Abran
31


<!-- pág 32/34 -->

Applicability of techniques
Some techniques may be more suitable for certain contexts, than 
the others. 
Choice of the best technique will depend on: 
✓ Software domain (e.g. business, real-time or infrastructure)
✓ Typical size,
✓ Adequacy of historical data. 
✓ Measurer’s level of experience level. 
32
© Copyrights 2022 Alain Abran


<!-- pág 33/34 -->

Emerging Early Sizing techniques
33
1. Informally written textual requirements.
2. Average number of data groups.
3. Use Case names.
4. Actions in UML Use Case diagrams.
5. Equal Number Bands.
6. Equal Range Bands..
7. ….
© Copyrights 2022 Alain Abran


<!-- pág 34/34 -->

Early or Rapid COSMIC Functional Size Measurement
QUESTIONS?