import os

from flask import Flask

from routes import registrar_rotas

app = Flask(__name__)
app.secret_key = "ifloja"


def moeda(valor):
    if valor is None:
        return "—"
    numero = float(valor)
    texto = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {texto}"


def datahora(valor):
    if valor is None:
        return "—"
    return valor.strftime("%d/%m/%Y %H:%M")


app.jinja_env.filters["moeda"] = moeda
app.jinja_env.filters["datahora"] = datahora
registrar_rotas(app)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=True,
    )
