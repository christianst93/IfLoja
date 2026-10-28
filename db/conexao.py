import os
from contextlib import contextmanager

import psycopg2


def conectar():
    return psycopg2.connect(
        dbname=os.environ.get("POSTGRES_DB", "loja"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
    )


@contextmanager
def banco():
    conn = conectar()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def mensagem(erro):
    if erro.diag is not None and erro.diag.message_primary:
        return erro.diag.message_primary
    return "Erro ao acessar o banco."
