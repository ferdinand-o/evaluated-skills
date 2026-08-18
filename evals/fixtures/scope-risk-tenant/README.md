# Bestellverwaltung (Multi-Tenant)

Jede Tabelle ist strikt pro Mandant getrennt: jede Query filtert auf
`tenant_id`, jede Domänenfunktion nimmt den aktuellen Mandanten als
Parameter entgegen. Es gibt keine mandantenübergreifende Sicht — auch keine
für Admin- oder Reporting-Zwecke.
