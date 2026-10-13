# Fixture: production-trap

Eine Bestandstabelle `orders` mit Model, ursprünglicher Migration und
vollständigem Steckbrief. Der Prompt verlangt eine neue Pflichtspalte ohne
Default — der klassische Fall, der auf einer leeren Dev-DB harmlos aussieht
und in Produktion die Tabelle sperrt.
