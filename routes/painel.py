from flask import Blueprint, flash, redirect, render_template, request, url_for
import psycopg2

from db.conexao import consultar, consultar_um, mensagem_erro

bp = Blueprint("painel", __name__)


@bp.route("/")
def inicio():
    totais = consultar_um(
        """
        SELECT
            (SELECT COUNT(*) FROM produto) AS produtos,
            (SELECT COUNT(*) FROM cliente) AS clientes,
            (SELECT COUNT(*) FROM venda WHERE status = 'finalizada') AS finalizadas,
            (SELECT COUNT(*) FROM venda WHERE status = 'cancelada') AS canceladas,
            (SELECT COALESCE(SUM(estoque), 0) FROM produto) AS unidades
        """
    )
    vendas = consultar(
        """
        SELECT v.id, c.nome AS cliente, v.data_hora, v.status,
               v.valor_total::numeric AS valor_total,
               v.desconto::numeric AS desconto
        FROM venda v
        JOIN cliente c ON c.id = v.cliente_id
        ORDER BY v.id DESC
        LIMIT 6
        """
    )
    estoque_baixo = consultar(
        """
        SELECT id, nome, estoque
        FROM produto
        WHERE estoque <= 5
        ORDER BY estoque, nome
        """
    )
    return render_template(
        "index.html",
        totais=totais,
        vendas=vendas,
        estoque_baixo=estoque_baixo,
    )


@bp.route("/rotinas", methods=["GET", "POST"])
def rotinas():
    resultado_total = None
    resultado_disp = None

    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "total":
                venda_id = int(request.form["venda_id"])
                linha = consultar_um(
                    """
                    SELECT v.id, v.status, calcular_total_venda(%s)::numeric AS total
                    FROM venda v
                    WHERE v.id = %s
                    """,
                    (venda_id, venda_id),
                )
                if linha is None:
                    flash("Venda inexistente.", "erro")
                else:
                    resultado_total = linha
            elif acao == "disponibilidade":
                produto_id = int(request.form["produto_id"])
                quantidade = int(request.form["quantidade"])
                produto = consultar_um(
                    """
                    SELECT id, nome, estoque,
                           consultar_disponibilidade(%s, %s) AS disponivel
                    FROM produto
                    WHERE id = %s
                    """,
                    (produto_id, quantidade, produto_id),
                )
                if produto is None:
                    flash("Produto inexistente.", "erro")
                else:
                    resultado_disp = {
                        "produto": produto,
                        "quantidade": quantidade,
                    }
        except ValueError:
            flash("Informe números inteiros válidos.", "erro")
        except psycopg2.Error as erro:
            flash(mensagem_erro(erro), "erro")

    vendas = consultar(
        """
        SELECT id, status
        FROM venda
        ORDER BY id
        """
    )
    produtos = consultar(
        """
        SELECT id, nome, estoque
        FROM produto
        ORDER BY nome
        """
    )
    return render_template(
        "rotinas.html",
        vendas=vendas,
        produtos=produtos,
        resultado_total=resultado_total,
        resultado_disp=resultado_disp,
    )
