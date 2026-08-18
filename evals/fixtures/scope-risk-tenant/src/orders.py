"""Bestellungen. Jede Query ist auf `tenant_id` gescoped — siehe
`src/tenants.py`. Es gibt keinen Pfad, der Bestellungen mehrerer Mandanten
in einem Ergebnis zurückgibt."""

from src.tenants import TenantContext


def list_orders(ctx: TenantContext, db) -> list[dict]:
    return db.query("SELECT * FROM orders WHERE tenant_id = ?", [ctx.tenant_id])


def get_order(ctx: TenantContext, order_id: str, db) -> dict | None:
    return db.query_one(
        "SELECT * FROM orders WHERE tenant_id = ? AND id = ?", [ctx.tenant_id, order_id]
    )
