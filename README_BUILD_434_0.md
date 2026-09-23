# EagleEye Build 434.0 — Registry / Organization Integration

Build 434 connects structured public registry records to the Build-433 organization-intelligence layer. A registry record is bound to an existing Build-422 acquisition event and Build-423 content object and is then normalized into a provenance-bound organization observation.

Supported registry contracts include company, association, charity/NGO, government, LEI and generic public registry records. Public identifiers and named officers/representatives remain source claims. A record can create a new organization subject or be attached explicitly to an existing subject.

Build 434 can search exact identifier matches across organization observations, but the result is deliberately labelled a **candidate**. It never automatically merges subjects or claims that two records are the same legal entity. Cross-source Entity Resolution remains scheduled for Build 437.

No live registry network executor is introduced in this build. The case-specific self-test and test guide remain available. Production readiness remains false; Build 435 is the next hard checkpoint.
