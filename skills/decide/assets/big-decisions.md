<!-- skill: decide | schema: 1 | generated: python decide_log.py add -->

# Große Entscheidungen

Jede große Frage steht hier als Block mit Überschrift `D-<n> · <datum> · <status>`, Status
`offen`, `freigegeben` oder `abgelehnt`. `decide_log.py add --class gross` legt einen Block an,
`decide_log.py resolve D-<n>` trägt die Antwort ein; Blöcke bleiben danach stehen. Bis ein Block
auf `freigegeben` steht, unterbleibt der Schritt, nach dem er fragt.
