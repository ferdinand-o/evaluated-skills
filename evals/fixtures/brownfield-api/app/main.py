from fastapi import FastAPI

app = FastAPI()


@app.get("/getUsers")
def get_users():
    return []


@app.post("/users")
def createUser(user: dict):
    return {"userId": 1, "userName": "x"}
