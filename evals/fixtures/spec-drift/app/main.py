from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/orders")
def list_orders(cursor: str | None = None, limit: int = 50):
    return {"items": [], "next_cursor": None}
