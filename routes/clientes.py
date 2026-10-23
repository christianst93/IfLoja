from flask import Blueprint, flash, redirect, render_template, request, url_for
import psycopg2

from db.conexao import consultar, mensagem_erro, transacao

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@bp.route("/", methods=["GET", "POST"])
def lista():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "")
        telefone = request.form.get("telefone", "").strip() or None
        try:
            if not nome:
                raise ValueError("Informe o nome do cliente.")
            with transacao() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO cliente (nome, email, telefone)
                        VALUES (%s, %s, %s)
                        RETURNING email
                        """,
                        (nome, email, telefone),
                    )
                    email_gravado = cur.fetchone()[0]
            flash(
                f"Cliente cadastrado. O e-mail foi gravado como {email_gravado}.",
                "sucesso",
            )
            return redirect(url_for("clientes.lista"))
        except ValueError as erro:
            flash(str(erro), "erro")
        except psycopg2.Error as erro:
            flash(mensagem_erro(erro), "erro")

    clientes = consultar(
        """
        SELECT id, nome, email, telefone
        FROM cliente
        ORDER BY id
        """
    )
    return render_template("clientes.html", clientes=clientes)
