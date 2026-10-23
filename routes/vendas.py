from flask import Blueprint, flash, redirect, render_template, request, url_for
import psycopg2

from db.conexao import consultar, consultar_um, mensagem_erro, transacao

bp = Blueprint("vendas", __name__, url_prefix="/vendas")


def _moeda(valor):
    numero = float(valor)
    texto = f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _opcoes():
    clientes = consultar("SELECT id, nome FROM cliente ORDER BY nome")
    produtos = consultar(
        """
        SELECT id, nome, estoque, preco::numeric AS preco
        FROM produto
        ORDER BY nome
        """
    )
    return clientes, produtos


@bp.route("/", methods=["GET", "POST"])
def lista():
    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "registrar":
                cliente_id = int(request.form["cliente_id"])
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                with transacao() as conn:
                    with conn.cursor() as cur:
                        # Estoque, preço e status ficam nas triggers.
                        cur.execute(
                            "CALL registrar_venda(%s, %s, %s)",
                            (cliente_id, produto_id, quantidade),
                        )
                        cur.execute(
                            """
                            SELECT id, valor_total::numeric AS valor_total,
                                   desconto::numeric AS desconto
                            FROM venda
                            ORDER BY id DESC
                            LIMIT 1
                            """
                        )
                        venda = cur.fetchone()
                        cur.execute(
                            "SELECT nome, estoque FROM produto WHERE id = %s",
                            (produto_id,),
                        )
                        produto = cur.fetchone()
                flash(
                    f"Venda {venda[0]} finalizada. Total { _moeda(venda[1]) }, "
                    f"desconto { _moeda(venda[2]) }. Estoque de {produto[0]}: {produto[1]}.",
                    "sucesso",
                )
                return redirect(url_for("vendas.detalhe", venda_id=venda[0]))
        except ValueError:
            flash("Informe cliente, produto e quantidade válidos.", "erro")
        except psycopg2.Error as erro:
            flash(mensagem_erro(erro), "erro")
            return redirect(url_for("vendas.lista"))

    vendas = consultar(
        """
        SELECT v.id, c.nome AS cliente, v.data_hora, v.status,
               v.valor_total::numeric AS valor_total,
               v.desconto::numeric AS desconto
        FROM venda v
        JOIN cliente c ON c.id = v.cliente_id
        ORDER BY v.id DESC
        """
    )
    clientes, produtos = _opcoes()
    return render_template(
        "vendas.html",
        vendas=vendas,
        clientes=clientes,
        produtos=produtos,
    )


@bp.route("/<int:venda_id>")
def detalhe(venda_id):
    venda = consultar_um(
        """
        SELECT v.id, v.cliente_id, c.nome AS cliente, v.data_hora, v.status,
               v.valor_total::numeric AS valor_total,
               v.desconto::numeric AS desconto,
               calcular_total_venda(v.id)::numeric AS total_funcao
        FROM venda v
        JOIN cliente c ON c.id = v.cliente_id
        WHERE v.id = %s
        """,
        (venda_id,),
    )
    if venda is None:
        flash("Venda inexistente.", "erro")
        return redirect(url_for("vendas.lista"))

    itens = consultar(
        """
        SELECT p.nome, i.quantidade, i.preco_unitario::numeric AS preco_unitario,
               (i.preco_unitario::numeric * i.quantidade) AS subtotal
        FROM item_venda i
        JOIN produto p ON p.id = i.produto_id
        WHERE i.venda_id = %s
        ORDER BY i.id
        """,
        (venda_id,),
    )
    bruto = sum((item["subtotal"] for item in itens), 0)
    return render_template("venda.html", venda=venda, itens=itens, bruto=bruto)


@bp.post("/<int:venda_id>/cancelar")
def cancelar(venda_id):
    try:
        return _cancelar(venda_id)
    except psycopg2.Error as erro:
        flash(mensagem_erro(erro), "erro")
        return redirect(url_for("vendas.detalhe", venda_id=venda_id))


def _cancelar(venda_id):
    atual = consultar_um("SELECT id, status FROM venda WHERE id = %s", (venda_id,))
    if atual is None:
        flash("Venda inexistente.", "erro")
        return redirect(url_for("vendas.lista"))
    if atual["status"] == "cancelada":
        flash(f"Venda {venda_id} já está cancelada.", "erro")
        return redirect(url_for("vendas.detalhe", venda_id=venda_id))

    with transacao() as conn:
        with conn.cursor() as cur:
            # A procedure só muda o status. A trigger devolve o estoque.
            cur.execute("CALL cancelar_venda(%s)", (venda_id,))
            cur.execute(
                """
                SELECT p.nome, p.estoque
                FROM item_venda i
                JOIN produto p ON p.id = i.produto_id
                WHERE i.venda_id = %s
                ORDER BY p.nome
                """,
                (venda_id,),
            )
            estoques = cur.fetchall()

    partes = [f"{nome} com {estoque} un." for nome, estoque in estoques]
    texto = ", ".join(partes) if partes else "sem itens"
    flash(f"Venda {venda_id} cancelada. Estoque atual: {texto}.", "sucesso")
    return redirect(url_for("vendas.detalhe", venda_id=venda_id))
