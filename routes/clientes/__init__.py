from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor

from db.conexao import banco, mensagem

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.route("/clientes", methods=["GET", "POST"], strict_slashes=False)
def clientes():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "")
        telefone = request.form.get("telefone", "").strip() or None
        try:
            with banco() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO cliente (nome, email, telefone) VALUES (%s, %s, %s) RETURNING email;",
                        [nome, email, telefone],
                    )
                    email_gravado = cur.fetchone()[0]
            flash("Cliente cadastrado. O e-mail foi gravado como " + email_gravado + ".", "sucesso")
            return redirect(url_for("clientes.clientes"))
        except psycopg2.Error as erro:
            flash(mensagem(erro), "erro")

    with banco() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, email, telefone FROM cliente ORDER BY id;")
            lista = cur.fetchall()

    return render_template("clientes.html", clientes=lista)
