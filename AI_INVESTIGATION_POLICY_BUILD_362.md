# AI Investigation Policy — Build 362

After explicit GO, the AI investigator may autonomously plan and execute bounded research waves through approved queues/workers, monitor crawler and infrastructure state, fuse evidence, form reviewable hypotheses, assign calibrated plausibility bands and prepare a written dossier for the case lead.

Build 362 adds infrastructure awareness: the dossier records whether the PostgreSQL team backend is actually externally validated. A missing PostgreSQL validation does not stop portable local investigation, but it prevents any team-scale production claim.

The AI investigator has no direct network, shell, credential or operating-system control and cannot self-approve sources, merge identities, release dossiers or bypass OPSEC.
