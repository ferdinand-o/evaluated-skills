"""Mandanten-Kontext. Jede Datenzugriffsfunktion in dieser Codebase nimmt
`tenant_id` entgegen — es gibt keine Funktion, die mandantenübergreifend
liest."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
