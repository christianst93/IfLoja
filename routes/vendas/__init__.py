from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor

from db.conexao import banco, mensagem

vendas_bp = Blueprint("vendas", __name__)


@vendas_bp.route("/vendas", methods=["GET", "POST"], strict_slashes=False)
def vendas():
    if request.method == "POST":
        try:
            cliente_id = int(request.form["cliente_id"])
            produto_id = int(request.form["produto_id"])
            quantidade = int(request.form["quantidade"])
            with banco() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "CALL registrar_venda(%s, %s, %s);",
                        [cliente_id, produto_id, quantidade],
                    )
                    cur.execute("SELECT id FROM venda ORDER BY id DESC LIMIT 1;")
                    venda_id = cur.fetchone()[0]
            return redirect(url_for("vendas.venda", venda_id=venda_id))
        except ValueError:
            flash("Informe cliente, produto e quantidade válidos.", "erro")
        except psycopg2.Error as erro:
            flash(mensagem(erro), "erro")

    with banco() as conn:
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

    return render_template(
        "vendas.html",
        vendas=lista,
        clientes=clientes_opcoes,
        produtos=produtos_opcoes,
    )


@vendas_bp.route("/vendas/<int:venda_id>", strict_slashes=False)
def venda(venda_id):
    with banco() as conn:
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
                return redirect(url_for("vendas.vendas"))

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

    bruto = sum((item["subtotal"] for item in itens), 0)
    return render_template("venda.html", venda=registro, itens=itens, bruto=bruto)


@vendas_bp.route("/vendas/<int:venda_id>/cancelar", methods=["POST"])
def cancelar(venda_id):
    try:
        with banco() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM venda WHERE id = %s;", [venda_id])
                atual = cur.fetchone()
                if atual is None:
                    flash("Venda inexistente.", "erro")
                    return redirect(url_for("vendas.vendas"))
                if atual[0] == "cancelada":
                    flash("Venda " + str(venda_id) + " já está cancelada.", "erro")
                    return redirect(url_for("vendas.venda", venda_id=venda_id))

                cur.execute("CALL cancelar_venda(%s);", [venda_id])
        flash("Venda " + str(venda_id) + " cancelada. O estoque foi devolvido.", "sucesso")
    except psycopg2.Error as erro:
        flash(mensagem(erro), "erro")

    return redirect(url_for("vendas.venda", venda_id=venda_id))
