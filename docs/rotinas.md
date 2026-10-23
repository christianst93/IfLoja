# Rotinas do banco loja

As regras de integridade ficam nas triggers, para valer também quando alguém inserir ou atualizar os registros direto na tabela. As procedures conduzem a operação e não repetem a baixa nem a devolução do estoque.

Há 2 functions, 3 stored procedures e 8 triggers. O enunciado pede no mínimo duas de cada. As triggers a mais cobrem quantidade, preço, estoque, status e e-mail. Nenhuma existe só para completar a contagem.

A trigger `trg_validar_estoque_item` trava a linha do produto com `FOR UPDATE`. Duas vendas simultâneas não consomem a mesma unidade.

## Functions

### calcular_total_venda(var_venda_id integer) → money

Soma `preço unitário × quantidade` dos itens da venda. Se o bruto for de R$ 200 ou mais, aplica 10% de desconto e devolve o líquido.

A procedure `registrar_venda` usa esse retorno para gravar `valor_total` e `desconto`. A tela da venda também chama a function de novo, para mostrar o valor calculado ao lado do valor gravado.

Verificação na aplicação: abra uma venda de monitor (bruto R$ 800,00). O cartão `calcular_total_venda` mostra R$ 720,00.

Verificação no SQL:

```sql
SELECT calcular_total_venda(1);
```

### consultar_disponibilidade(var_produto_id integer, var_quantidade integer) → boolean

Lê o estoque do produto e devolve verdadeiro quando a quantidade pedida cabe. Produto inexistente devolve falso. A function não altera estoque.

Verificação na aplicação: em Produtos ou em Rotinas, peça uma quantidade maior que o estoque e outra que caiba.

Verificação no SQL:

```sql
SELECT consultar_disponibilidade(4, 1);
SELECT consultar_disponibilidade(4, 1000);
```

## Stored procedures

### registrar_venda(var_cliente_id, var_produto_id, var_quantidade)

Confere se o cliente e o produto existem, abre a venda, inclui um item com o preço atual e finaliza. O total e o desconto vêm de `calcular_total_venda`.

A procedure não dá `UPDATE` em `produto.estoque`. A baixa acontece na trigger `trg_movimentar_estoque_item`, disparada pelo `INSERT` do item. Quantidade, preço, estoque e venda aberta também são validados por triggers, então a mesma regra vale para um `INSERT` feito direto na tabela `item_venda`.

Verificação na aplicação: em Vendas, finalize uma venda e confira o estoque do produto e a linha nova em Auditoria.

Verificação no SQL:

```sql
CALL registrar_venda(3, 3, 1);
SELECT id, nome, estoque FROM produto WHERE id = 3;
```

Uma quantidade acima do estoque deve falhar sem gravar a venda:

```sql
CALL registrar_venda(1, 4, 1000);
```

### cancelar_venda(var_venda_id integer)

Só muda `venda.status` para `cancelada`. Se a venda não existe, gera erro. Se já está cancelada, avisa e não altera nada.

A devolução do estoque fica na trigger `trg_devolver_estoque_cancelamento`. Se a procedure também somasse o estoque, o cancelamento devolveria a quantidade duas vezes.

Verificação na aplicação: cancele uma venda finalizada e veja o estoque voltar. Cancelar de novo mostra que a venda já está cancelada.

Verificação no SQL:

```sql
CALL cancelar_venda(2);
SELECT id, nome, estoque FROM produto ORDER BY id;
```

### repor_estoque(var_produto_id integer, var_quantidade integer)

Soma a quantidade informada ao estoque de um produto que já existe. Quantidade nula ou menor ou igual a zero gera erro. A procedure trava a linha do produto com `FOR UPDATE` antes de somar.

Ela não passa pelas triggers da venda. A baixa continua em `trg_movimentar_estoque_item` e a devolução do cancelamento em `trg_devolver_estoque_cancelamento`.

Verificação na aplicação: em Produtos, no bloco Repor estoque, some unidades e confira a coluna Estoque.

Verificação no SQL:

```sql
CALL repor_estoque(1, 10);
SELECT id, nome, estoque FROM produto WHERE id = 1;
```

## Triggers básicas

### trg_validar_quantidade_item

`BEFORE INSERT OR UPDATE OF quantidade` em `item_venda`. Recusa quantidade nula ou menor ou igual a zero.

Verificação: em Vendas, informe quantidade 0. A mensagem é "A quantidade do item deve ser maior que zero."

### trg_validar_preco_item

`BEFORE INSERT OR UPDATE OF preco_unitario, produto_id` em `item_venda`. Se o preço vier nulo, copia o preço atual do produto. Recusa preço nulo ou menor ou igual a zero.

Verificação no SQL, com uma venda aberta criada antes:

```sql
INSERT INTO venda (cliente_id) VALUES (1) RETURNING id;
INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario)
VALUES (ID_DA_VENDA, 1, 1, NULL);
```

O item deve gravar o preço do mouse. Em seguida, apague esse teste ou cancele o fluxo para não misturar com a demonstração.

## Triggers intermediárias

### trg_normalizar_email

`BEFORE INSERT OR UPDATE OF email` em `cliente`. Exige e-mail e grava `lower(trim(email))`.

Verificação: cadastre o cliente com o e-mail `  MARIA@Email.COM `. A lista mostra `maria@email.com`.

### trg_validar_venda_aberta

`BEFORE INSERT OR UPDATE OR DELETE` em `item_venda`. Item só entra, muda ou sai enquanto a venda está aberta.

Verificação no SQL, usando uma venda já finalizada:

```sql
INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario)
VALUES (1, 2, 1, 120);
```

A mensagem é "Não é permitido alterar itens de uma venda que não está aberta."

### trg_validar_estoque_item

`BEFORE INSERT OR UPDATE OF quantidade, produto_id` em `item_venda`. Trava a linha do produto e recusa a quantidade que passa do estoque. No update do mesmo produto, compara só a diferença.

Verificação: peça, na tela de vendas, mais unidades do que o estoque do monitor.

### trg_validar_status_venda

`BEFORE UPDATE OF status` em `venda`. Venda cancelada permanece cancelada. Venda finalizada não volta para aberta. Finalizada pode seguir para cancelada, que é o caminho da procedure.

Verificação no SQL, depois de cancelar a venda 2:

```sql
UPDATE venda SET status = 'aberta' WHERE id = 2;
```

## Triggers avançadas

### trg_movimentar_estoque_item

`AFTER INSERT OR UPDATE OF quantidade, produto_id OR DELETE` em `item_venda`. Na inclusão, baixa a quantidade. Na alteração, ajusta a diferença ou troca o produto. Na exclusão de item de venda ainda aberta, devolve a quantidade.

Esta trigger e a de cancelamento não se atropelam: o cancelamento não apaga os itens. Ele só muda o status, e a outra trigger devolve o estoque uma vez. Depois do cancelamento, `trg_validar_venda_aberta` impede apagar o item, então a quantidade não volta uma segunda vez.

Verificação: anote o estoque, registre uma venda e confira a diferença. Ela deve ser igual à quantidade vendida.

### trg_devolver_estoque_cancelamento

`AFTER UPDATE OF status` em `venda`. Quando o status passa a `cancelada`, soma de volta a quantidade de cada item que continua na venda.

Verificação: cancele pela aplicação e compare o estoque com o valor anterior à venda.

## Ordem que vale na venda

1. `registrar_venda` insere a venda aberta.
2. A procedure insere o item. As triggers de venda aberta, quantidade, preço e estoque rodam antes. A trigger de movimentação baixa o estoque depois.
3. A procedure calcula o total e marca a venda como finalizada.
4. No cancelamento, a procedure só muda o status. A trigger devolve o estoque.
5. `repor_estoque` soma unidades direto no produto e não altera vendas já registradas.
