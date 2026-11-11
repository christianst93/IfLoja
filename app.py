import os

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "ifloja"


def conectar():
    return psycopg2.connect(
        dbname=os.environ.get("POSTGRES_DB", "loja"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
    )


def mensagem(erro):
    if erro.diag is not None and erro.diag.message_primary:
        return erro.diag.message_primary
    return "Erro ao acessar o banco."


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


@app.route("/")
def inicio():
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM produto) AS produtos,
                    (SELECT COUNT(*) FROM cliente) AS clientes,
                    (SELECT COUNT(*) FROM venda WHERE status = 'finalizada') AS finalizadas,
                    (SELECT COUNT(*) FROM venda WHERE status = 'cancelada') AS canceladas,
                    (SELECT COALESCE(SUM(estoque), 0) FROM produto) AS unidades
                """
            )
            totais = cur.fetchone()
            cur.execute(
                """
                SELECT v.id, c.nome AS cliente, v.data_hora, v.status,
                       v.valor_total::numeric AS valor_total
                FROM venda v
                JOIN cliente c ON c.id = v.cliente_id
                ORDER BY v.id DESC
                LIMIT 6
                """
            )
            vendas = cur.fetchall()
            cur.execute(
                """
                SELECT id, nome, estoque
                FROM produto
                WHERE estoque <= 5
                ORDER BY estoque, nome
                """
            )
            estoque_baixo = cur.fetchall()
    finally:
        conn.close()

    return render_template(
        "index.html",
        totais=totais,
        vendas=vendas,
        estoque_baixo=estoque_baixo,
    )


@app.route("/produtos", methods=["GET", "POST"], strict_slashes=False)
def produtos():
    disponibilidade = None

    if request.method == "POST":
        acao = request.form.get("acao")
        conn = conectar()
        try:
            if acao == "cadastrar":
                nome = request.form.get("nome", "").strip()
                preco = request.form.get("preco", "").strip().replace(",", ".")
                estoque = int(request.form.get("estoque", ""))
                categoria_id = int(request.form["categoria_id"])
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO produto (nome, preco, estoque, categoria_id) VALUES (%s, CAST(%s AS numeric)::money, %s, %s);",
                        [nome, preco, estoque, categoria_id],
                    )
                conn.commit()
                flash("Produto " + nome + " cadastrado.", "sucesso")
                return redirect(url_for("produtos"))

            if acao == "repor":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("CALL repor_estoque(%s, %s);", [produto_id, quantidade])
                    cur.execute("SELECT nome, estoque FROM produto WHERE id = %s;", [produto_id])
                    produto = cur.fetchone()
                conn.commit()
                flash(
                    "Estoque de " + produto["nome"] + " reposto. Agora: " + str(produto["estoque"]) + " un.",
                    "sucesso",
                )
                return redirect(url_for("produtos"))

            if acao == "disponibilidade":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
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
            conn.rollback()
            flash("Preencha os campos com valores válidos.", "erro")
        except psycopg2.Error as erro:
            conn.rollback()
            flash(mensagem(erro), "erro")
        finally:
            conn.close()

    conn = conectar()
    try:
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
    finally:
        conn.close()

    return render_template(
        "produtos.html",
        produtos=lista,
        categorias=categorias,
        disponibilidade=disponibilidade,
    )


@app.route("/clientes", methods=["GET", "POST"], strict_slashes=False)
def clientes():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "")
        telefone = request.form.get("telefone", "").strip() or None
        conn = conectar()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cliente (nome, email, telefone) VALUES (%s, %s, %s) RETURNING email;",
                    [nome, email, telefone],
                )
                email_gravado = cur.fetchone()[0]
            conn.commit()
            flash("Cliente cadastrado. O e-mail foi gravado como " + email_gravado + ".", "sucesso")
            return redirect(url_for("clientes"))
        except psycopg2.Error as erro:
            conn.rollback()
            flash(mensagem(erro), "erro")
        finally:
            conn.close()

    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nome, email, telefone FROM cliente ORDER BY id;")
            lista = cur.fetchall()
    finally:
        conn.close()

    return render_template("clientes.html", clientes=lista)


@app.route("/vendas", methods=["GET", "POST"], strict_slashes=False)
def vendas():
    if request.method == "POST":
        conn = conectar()
        try:
            cliente_id = int(request.form["cliente_id"])
            produto_id = int(request.form["produto_id"])
            quantidade = int(request.form["quantidade"])
            with conn.cursor() as cur:
                cur.execute(
                    "CALL registrar_venda(%s, %s, %s);",
                    [cliente_id, produto_id, quantidade],
                )
                cur.execute("SELECT id FROM venda ORDER BY id DESC LIMIT 1;")
                venda_id = cur.fetchone()[0]
            conn.commit()
            return redirect(url_for("venda", venda_id=venda_id))
        except ValueError:
            conn.rollback()
            flash("Informe cliente, produto e quantidade válidos.", "erro")
        except psycopg2.Error as erro:
            conn.rollback()
            flash(mensagem(erro), "erro")
        finally:
            conn.close()

    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.id, c.nome AS cliente, v.data_hora, v.status,
                       v.valor_total::numeric AS valor_total,
                       v.desconto::numeric AS desconto
                FROM venda v
                JOIN cliente c ON c.id = v.cliente_id
                ORDER BY v.id DESC
                """
            )
            lista = cur.fetchall()
            cur.execute("SELECT id, nome FROM cliente ORDER BY nome;")
            clientes_opcoes = cur.fetchall()
            cur.execute(
                "SELECT id, nome, estoque, preco::numeric AS preco FROM produto ORDER BY nome;"
            )
            produtos_opcoes = cur.fetchall()
    finally:
        conn.close()

    return render_template(
        "vendas.html",
        vendas=lista,
        clientes=clientes_opcoes,
        produtos=produtos_opcoes,
    )


@app.route("/vendas/<int:venda_id>", strict_slashes=False)
def venda(venda_id):
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.id, c.nome AS cliente, v.data_hora, v.status,
                       v.valor_total::numeric AS valor_total,
                       v.desconto::numeric AS desconto,
                       calcular_total_venda(v.id)::numeric AS total_funcao
                FROM venda v
                JOIN cliente c ON c.id = v.cliente_id
                WHERE v.id = %s
                """,
                [venda_id],
            )
            registro = cur.fetchone()
            if registro is None:
                flash("Venda inexistente.", "erro")
                return redirect(url_for("vendas"))

            cur.execute(
                """
                SELECT p.nome, i.quantidade, i.preco_unitario::numeric AS preco_unitario,
                       (i.preco_unitario::numeric * i.quantidade) AS subtotal
                FROM item_venda i
                JOIN produto p ON p.id = i.produto_id
                WHERE i.venda_id = %s
                ORDER BY i.id
                """,
                [venda_id],
            )
            itens = cur.fetchall()
    finally:
        conn.close()

    bruto = sum((item["subtotal"] for item in itens), 0)
    return render_template("venda.html", venda=registro, itens=itens, bruto=bruto)


@app.route("/vendas/<int:venda_id>/cancelar", methods=["POST"])
def cancelar(venda_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM venda WHERE id = %s;", [venda_id])
            atual = cur.fetchone()
            if atual is None:
                flash("Venda inexistente.", "erro")
                return redirect(url_for("vendas"))
            if atual[0] == "cancelada":
                flash("Venda " + str(venda_id) + " já está cancelada.", "erro")
                return redirect(url_for("venda", venda_id=venda_id))

            cur.execute("CALL cancelar_venda(%s);", [venda_id])
        conn.commit()
        flash("Venda " + str(venda_id) + " cancelada. O estoque foi devolvido.", "sucesso")
    except psycopg2.Error as erro:
        conn.rollback()
        flash(mensagem(erro), "erro")
    finally:
        conn.close()

    return redirect(url_for("venda", venda_id=venda_id))


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=True,
    )
