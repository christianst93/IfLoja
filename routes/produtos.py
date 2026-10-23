from flask import Blueprint, flash, redirect, render_template, request, url_for
import psycopg2

from db.conexao import consultar, consultar_um, mensagem_erro, transacao

bp = Blueprint("produtos", __name__, url_prefix="/produtos")


@bp.route("/", methods=["GET", "POST"])
def lista():
    disponibilidade = None

    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "cadastrar":
                nome = request.form.get("nome", "").strip()
                preco = request.form.get("preco", "").strip().replace(",", ".")
                if not nome:
                    raise ValueError("Informe o nome do produto.")
                if not preco:
                    raise ValueError("Informe o preço do produto.")
                estoque = int(request.form.get("estoque", ""))
                categoria_id = int(request.form["categoria_id"])
                with transacao() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO produto (nome, preco, estoque, categoria_id)
                            VALUES (%s, CAST(%s AS numeric)::money, %s, %s)
                            RETURNING nome
                            """,
                            (nome, preco, estoque, categoria_id),
                        )
                        gravado = cur.fetchone()[0]
                flash(f"Produto {gravado} cadastrado.", "sucesso")
                return redirect(url_for("produtos.lista"))

            if acao == "repor":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                with transacao() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "CALL repor_estoque(%s, %s)",
                            (produto_id, quantidade),
                        )
                        cur.execute(
                            "SELECT nome, estoque FROM produto WHERE id = %s",
                            (produto_id,),
                        )
                        produto = cur.fetchone()
                flash(
                    f"Estoque de {produto[0]} reposto. Agora: {produto[1]} un.",
                    "sucesso",
                )
                return redirect(url_for("produtos.lista"))

            if acao == "disponibilidade":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                produto = consultar_um(
                    """
                    SELECT nome, estoque,
                           consultar_disponibilidade(%s, %s) AS disponivel
                    FROM produto
                    WHERE id = %s
                    """,
                    (produto_id, quantidade, produto_id),
                )
                if produto is None:
                    flash("Produto inexistente.", "erro")
                else:
                    disponibilidade = {
                        "nome": produto["nome"],
                        "estoque": produto["estoque"],
                        "quantidade": quantidade,
                        "disponivel": produto["disponivel"],
                    }
        except ValueError as erro:
            texto = str(erro)
            if "invalid literal" in texto or texto.startswith("invalid"):
                flash("Estoque e categoria precisam ser números inteiros.", "erro")
            else:
                flash(texto, "erro")
        except psycopg2.Error as erro:
            flash(mensagem_erro(erro), "erro")

    produtos = consultar(
        """
        SELECT p.id, p.nome, p.preco::numeric AS preco, p.estoque, c.nome AS categoria
        FROM produto p
        JOIN categoria c ON c.id = p.categoria_id
        ORDER BY p.id
        """
    )
    categorias = consultar("SELECT id, nome FROM categoria ORDER BY nome")
    return render_template(
        "produtos.html",
        produtos=produtos,
        categorias=categorias,
        disponibilidade=disponibilidade,
    )
