from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor

from db.conexao import banco, mensagem

produtos_bp = Blueprint("produtos", __name__)


@produtos_bp.route("/produtos", methods=["GET", "POST"], strict_slashes=False)
def produtos():
    disponibilidade = None

    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "cadastrar":
                nome = request.form.get("nome", "").strip()
                preco = request.form.get("preco", "").strip().replace(",", ".")
                estoque = int(request.form.get("estoque", ""))
                categoria_id = int(request.form["categoria_id"])
                with banco() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO produto (nome, preco, estoque, categoria_id) VALUES (%s, CAST(%s AS numeric)::money, %s, %s);",
                            [nome, preco, estoque, categoria_id],
                        )
                flash("Produto " + nome + " cadastrado.", "sucesso")
                return redirect(url_for("produtos.produtos"))

            if acao == "repor":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                with banco() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("CALL repor_estoque(%s, %s);", [produto_id, quantidade])
                        cur.execute("SELECT nome, estoque FROM produto WHERE id = %s;", [produto_id])
                        produto = cur.fetchone()
                flash(
                    "Estoque de " + produto["nome"] + " reposto. Agora: " + str(produto["estoque"]) + " un.",
                    "sucesso",
                )
                return redirect(url_for("produtos.produtos"))

            if acao == "disponibilidade":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                with banco() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            "SELECT nome, estoque, consultar_disponibilidade(%s, %s) AS disponivel FROM produto WHERE id = %s;",
                            [produto_id, quantidade, produto_id],
                        )
                        produto = cur.fetchone()
                if produto is None:
                    flash("Produto inexistente.", "erro")
                else:
                    disponibilidade = {
                        "nome": produto["nome"],
                        "estoque": produto["estoque"],
                        "quantidade": quantidade,
                        "disponivel": produto["disponivel"],
                    }
        except ValueError:
            flash("Preencha os campos com valores válidos.", "erro")
        except psycopg2.Error as erro:
            flash(mensagem(erro), "erro")

    with banco() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.id, p.nome, p.preco::numeric AS preco, p.estoque, c.nome AS categoria
                FROM produto p
                JOIN categoria c ON c.id = p.categoria_id
                ORDER BY p.id
                """
            )
            lista = cur.fetchall()
            cur.execute("SELECT id, nome FROM categoria ORDER BY nome;")
            categorias = cur.fetchall()

    return render_template(
        "produtos.html",
        produtos=lista,
        categorias=categorias,
        disponibilidade=disponibilidade,
    )
