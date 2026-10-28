from flask import Blueprint
from flask import render_template
from psycopg2.extras import RealDictCursor

from db.conexao import banco

inicio_bp = Blueprint("inicio", __name__)


@inicio_bp.route("/")
def inicio():
    with banco() as conn:
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

    return render_template(
        "index.html",
        totais=totais,
        vendas=vendas,
        estoque_baixo=estoque_baixo,
    )
