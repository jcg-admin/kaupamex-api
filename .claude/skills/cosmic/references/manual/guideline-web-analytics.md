<!-- Extraído de f6555753-GuidelineWebAnalytics.pdf (8 págs) por pypdf — 2026-06-03T03:37:21Z. Fuente COSMIC oficial. -->
# COSMIC — Guideline: Web Analytics



<!-- pág 1/8 -->

COSMIC Measurement Manual  
for ISO 19761  
 
Guideline for the Functional Sizing 
of 
Web Analytics Implementations 
 
 
 
 
COSMIC Version 5.0 
October 2025


<!-- pág 2/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 2 
Foreword. 
The purpose of this Guideline is to show how the COSMIC Functional Size Measurement 
method (e.g., ISO 19761)  can be used to measure the functional size of Web Analytics 
implementations. It includes three measurement examples.  
Software functional size is useful to estimate the development effort that comes with a 
functional size, by relating it to sizes and accompanying efforts of comparable sized software. 
One of the estimation approaches is applying machine learning: see  [1] that illustrates how 50 
web analytics project data sets were sized in COSMIC Function Points and estimated with a 
number of machine learning effort estimation models. 
• For COSMIC method terminology: see the Measurement Manual Part 1 [2],  
• For the COSMIC method: see the Measurement Manual Part 2 [3]. 
• For fundamentals of software estimation: see [4] 
 
 
 
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

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 3 
Table of Contents 
1 INTRODUCTION. ................................ ................................ ................................ .......... 4 
2 COSMIC CONCEPTS AND WEB ANALYTICS. ................................ ........................... 4 
3 ESTIMATING EFFORT. ................................ ................................ ................................  5 
3.1 Effort estimating techniques. ................................ ................................ ........................ 5 
3.2 Effort collection. ................................ ................................ ................................ ............ 5 
4 WEB ANALYTICS EXAMPLES. ................................ ................................ ................... 5 
4.1 E-commerce company. ................................ ................................ ................................  5 
4.2 Insurance company ................................ ................................ ................................ ...... 6 
4.3 Hospital. ................................ ................................ ................................ ....................... 7 
4.4 An early size technique. ................................ ................................ ...............................  7 
5 REFERENCES AND DOCUMENTATION. ................................ ................................ .... 8


<!-- pág 4/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 4 
1 INTRODUCTION. 
Web Analytics concerns collecting, measuring, analysing and reporting digital data to gain 
insights into the behaviour of website visitors. These insights allow organizations to enhance 
online presence by improving website  usability and engagement through data -driven 
recommendations to optimize website performance. 
The text and examples are based on human end user Functional User Requirements (FUR), 
for effort estimation purposes, and hence cost estimation. 
2 COSMIC CONCEPTS AND WEB ANALYTICS. 
This section summarizes the COSMIC mai n concepts and rules, with bullet points showing  
their implementation for the Web Analytics (WA) domain. The implementation is based on the 
requirements stated in section 4. 
Note: COSMIC rules require identification of types rather than occurrences. In 
consequence, if single things are identified as objects of interest, it must be distinct types 
of things and not multiple occurrences of the same type of things. 
 
1. Functional User Requirements (FUR) describe what a piece of software shall do, in terms 
of tasks and services.  
• The FUR consist of the functionality as described in Examples 1, 2 and 3 in section 4. 
Examples 1 and 2 are based on both examples in [1]. 
2. Software may consist of layers, which must be identified if required for the purpose of the 
measurement.  
• For the present measurement it is not required to identify layers 
3. Persistent storage enables a functional process to store and/or retrieve data.  
• For the present measurement persistent storage concerns  
− Event data (user actions such as page view, button click, or form submission), and  
− User data (user details). 
4. A piece of software interacts with its functional users and with persistent storage.  
• For the present measurement the functional users are  
− human users who provide the tracking data via devices such as web browsers and 
smartphones. 
− human users who require tracking data output (not further mentioned), 
− the Web Analytics platform for persistent storage of the tracking data.  
5. A functional process is initiated by a triggering event, detected by a functional user and 
which in turn initiates the triggering Entry.  
• For the present measurement  
− a triggering event is an interaction of a human functional user (such as entering a 
site, adding products to a cart, etc.) that leads to an action to be tracked (clicks etc.).  
− a functional process receives the interaction data and directly forwards the data to 
the Web Analytics platform for persistent storage. 
6. A functional process consists of data movements.  There are four data movement sub -
types: Entry, Exit, Write and Read. Each data movement includes the data manipulation 
concerned.  
7. An object of interest (OOI) is any ‘thing’ in the FUR about which the software is required to 
process and⁄or store data. In case of different frequencies of data groups, identify 
corresponding objects of interest. 
• For example, in the first functional process in Example 4.1 the object of interest is twice 
‘User’.


<!-- pág 5/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 5 
8. A data movement moves a single data group. A data group consists of data attributes that 
describe a single object of interest.  
• For example, in the first functional process in Example 4.1 the data group in both data 
movements is indicated by ‘User data’. 
3 ESTIMATING EFFORT. 
3.1 Effort estimating techniques. 
For estimating with machine learning techniques, see [1].  
For constructing a simple linear regression effort estimating model with Excel, see [5]. 
3.2 Effort collection. 
The effort to be collected and registered for a Web Analytics implementation include: 
Discovery & Planning 
• Requirements gathering (stakeholders, KPIs, goals) 
• Audit of existing Analytics setup 
• Definition of events and user properties 
• Drafting documentation 
Technical Implementation 
• Setting up metrics 
• Implementing event tracking 
Reporting 
• Creating reports for different business teams 
• Documentation on implementation and reporting 
• Customizing standard reports. 
See also the ISBSG Data Collection Questionnaire [6]. 
4 WEB ANALYTICS EXAMPLES. 
Note 1. The data movement names Entry, Exit, Read and Write are abbreviated to E, X, R and 
W respectively. 
Note 2. If the event tracker detects event data only identify one object of interest, if it also 
detects user data that is not directly related to the event, identify two objects of interest. 
4.1 E-commerce company. 
Description. 
An e -commerce company implements Web Analytics to track essential user interactions 
related to their online stores.  
• Interactions to be tracked include that users enter the site, add products to a cart, 
remove products from the cart, view product details, and make purchases.  
• By implementing event tags, the company aims to gain  insights into customer 
behaviour and optimize ‘funnels’, i.e. how users move through a site and where they 
drop off. 
• User and event data is sent to and stored at the Web Analytics platform. 
 
Tracking Customer behaviour, 14 CFP  
Functional process User enters site, 2 CFP.


<!-- pág 6/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 6 
E User enters site 
X User data 
Functional process Track Product viewing, 3 CFP. 
E User data (views product) 
X Event data 
X User data 
Functional process Track Add to cart data, 3 CFP. 
E User data (adds to cart) 
X Event data 
X User data 
Functional process Track Remove from cart data, 3 CFP. 
E User data (removes from cart) 
X Event data 
X User data 
Functional process Track Purchase data, 3 CFP. 
E User data (purchases) 
X Event data 
X User data 
4.2 Insurance company 
Description. 
An insurance company implements Web Analytics to track essential user interactions related 
to its website.  
• Interactions to be tracked include when users view policy plan details, downloading 
documents, and submitting requests in quote form.  
• By implementing event tags, the company aims to gain insights into customer 
behaviour and optimize its lead-generation funnel.  
User and event data is sent to and stored at the Web Analytics platform. 
Tracking Customer behaviour, 11 CFP  
Functional process User enters site,2 CFP. 
E User data (enters site) 
X User data 
Functional process Track Policy plan details viewing, 3 CFP. 
E User data (views policy plan) 
X Event data 
X User data 
Functional process Track Downloading documents, 3 CFP. 
E User data (downloads documents) 
X Event data 
X User data 
Functional process Track Submitting requests in quote form, 3 CFP. 
E User data (submit request in quote form) 
X Event data 
X User data


<!-- pág 7/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 7 
4.3 Hospital. 
Description. 
A hospital management aims to gain insight s to optimize patient appointment behaviour , 
because appointments are not always kept or are changed late. The hospital implements Web 
Analytics to track relevant patient interactions with respect to appointments.  
• Interactions to be tracked include that patients enter the site, make appointments, 
change appointments and view the conditions page for making appointments. 
• User and event data is sent to and stored at the Web Analytics platform. 
Tracking Patient appointment behaviour, 11 CFP  
Functional process Patient enters site, 2 CFP. 
E Patient data (enters site) 
X Patient data 
Functional process Track Patient makes Appointment, 3 CFP. 
E Patient data (makes appointment) 
X Event data 
X Patient data 
Functional process Track Patient changes Appointment, 3 CFP. 
E Patient data (changes appointment) 
X Event data 
X Patient data 
Functional process Track Patient views conditions page for making Appointment, 3 CFP. 
E Patient data (views appointment conditions details) 
X Event data 
X Patient data 
4.4 An early size technique. 
An early siz ing technique may be used to establish the size of a piece of software without 
enough measurement time or requirements details available to use the standard COSMIC 
method.  
For example, the measurements in section 4 show a pattern: the first functional process is 
‘User enters site’ of 2 CFP, followed by a number of functional processes that represent an 
aspect to be tracked, each of which of 2 or 3 CFP.   
If the measured functional processes are part of a collection of say 
• N2 functional processes of 2 CFP, and 
• N3 functional processes of size 3 CFP 
and assuming that the pattern applies to most or all of them, an early size of the Web Analytics 
implementation would be  
• N2*2 CFP + N3*3 CFP. 
Comparing early sizes and actual sizes of a number of projects indicates if it makes sense to 
continue using (this ‘pattern’ technique of) early sizing. 
 
For more on early sizing techniques, see both COSMIC Early Sizing Guidelines [7] and [8].


<!-- pág 8/8 -->

COSMIC Measurement Manual - version 5.0 – Guideline Web Analytics Measurement    Copyright © 2025 8 
5 REFERENCES AND DOCUMENTATION. 
[1] Measurement of the Functional Size of  Web Analytics  Implementation: A COSMIC -
Based Case Study Using  Machine Learning. A. Abdallah, A. Abran, M. Qasaimeh, M. 
Qasaimeh, B. Abdallah. 
[2] Guideline Measurement Manual v5 Part 1 Principles, Defs. & Rules. 
[3] Guideline Measurement Manual v5 Part 2 Guidelines. 
[4] Abran, A., Software Project Estimation, John Wiley & Sons, 2015. 
[5] Estimating with functional Size - Cosmic Sizing. 
[6] ISBSG Concise Data Collection Questionnaire. 
[7] Early Software Sizing with COSMIC, Practitioners. 
[8] Early Software Sizing with COSMIC, Experts.