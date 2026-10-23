# Loja — vendas e estoque

Trabalho prático de Programação em Banco de Dados. A aplicação registra vendas de uma loja pequena. As regras de estoque, desconto e status ficam no PostgreSQL. O Flask chama as procedures e as functions e mostra o efeito das triggers.

## Integrantes

- Christian Torres
- Alessandro Fernandes

## O que o sistema faz

- Cadastra categorias, produtos e clientes.
- Consulta se uma quantidade cabe no estoque, sem alterar o saldo.
- Registra uma venda de um produto, aplica 10% de desconto quando o bruto chega a R$ 200 e baixa o estoque.
- Cancela a venda e devolve o estoque.
- Repõe o estoque de um produto já cadastrado.
- Recusa quantidade inválida, preço inválido, estoque insuficiente, item em venda que não está aberta e mudança indevida de status.


## Tecnologias

- PostgreSQL, com PL/pgSQL
- Flask
- Jinja
- psycopg2
- HTML e CSS

# Executar

- Para executar o projeto use docker compose up --build no terminal.