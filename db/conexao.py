from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import PG


def get_conexao():
    return psycopg2.connect(**PG)


def consultar(sql, params=None):
    conn = get_conexao()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def consultar_um(sql, params=None):
    linhas = consultar(sql, params)
    if not linhas:
        return None
    return linhas[0]


@contextmanager
def transacao():
    conn = get_conexao()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mensagem_erro(erro):
    diag = getattr(erro, "diag", None)
    if diag is not None and diag.message_primary:
        texto = diag.message_primary
    else:
        linhas = str(erro).strip().splitlines()
        texto = linhas[0] if linhas else "Erro ao acessar o banco."

    codigo = getattr(erro, "pgcode", None)
    if codigo == "23505":
        return "Já existe um registro com esse valor único. Confira o e-mail ou o nome da categoria."
    if codigo == "23503":
        return "O registro relacionado não existe. Confira cliente, produto ou categoria."
    if codigo == "23514":
        nome = ""
        if diag is not None and diag.constraint_name:
            nome = diag.constraint_name
        if "preco_unitario" in nome:
            return "O preço do item deve ser maior que zero."
        if "preco" in nome:
            return "O preço do produto deve ser maior que zero."
        if "estoque" in nome:
            return "O estoque não pode ficar negativo."
        if "quantidade" in nome:
            return "A quantidade do item deve ser maior que zero."
        if "status" in nome:
            return "Status de venda inválido."
        return "Os dados violam uma regra de integridade do banco."
    return texto
