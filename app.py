import os

import psycopg2
from flask import Flask, render_template

from routes import registrar_rotas


def formatar_moeda(valor):
    if valor is None:
        return "—"
    numero = float(valor)
    texto = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {texto}"


def formatar_data(valor):
    if valor is None:
        return "—"
    return valor.strftime("%d/%m/%Y %H:%M")


def criar_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "loja-pbd")
    app.add_template_filter(formatar_moeda, "moeda")
    app.add_template_filter(formatar_data, "datahora")

    @app.errorhandler(psycopg2.OperationalError)
    def banco_indisponivel(erro):
        linhas = str(erro).strip().splitlines()
        mensagem = linhas[0] if linhas else "Não foi possível conectar ao PostgreSQL."
        return render_template("erro_banco.html", mensagem=mensagem), 500

    registrar_rotas(app)
    return app


app = criar_app()


if __name__ == "__main__":
    app.run(
        debug=True,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )
