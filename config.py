import os


def carregar_env():
    caminho = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(caminho):
        return

    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


carregar_env()

PG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "loja"),
    "user": os.environ.get("PGUSER", "postgres"),
}

senha = os.environ.get("PGPASSWORD")
if senha:
    PG["password"] = senha
