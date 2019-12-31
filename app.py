from flask import Flask, render_template
import json
from waitress import serve

app = Flask(__name__)


@app.route('/')
def hello_world():

    return render_template("index.html", data=load_data())

def load_data():
    with open("data.json") as file:
        f = file.read()
    return json.loads(f)

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8000)
