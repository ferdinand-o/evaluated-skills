from flask import Flask

app = Flask(__name__)


@app.route("/v1/widgets", methods=["GET"])
def list_widgets():
    return []


@app.route("/v1/widgets/<id>", methods=["GET"])
def get_widget(id):
    return {}
