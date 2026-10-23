

DROP DATABASE IF EXISTS loja;

CREATE DATABASE loja;

\c loja;

CREATE TABLE categoria (
    id serial primary key,
    nome character varying(100) not null unique
);

CREATE TABLE produto (
    id serial primary key,
    nome character varying(200) not null,
    preco money not null check (preco::numeric > 0),
    estoque integer not null default 0 check (estoque >= 0),
    categoria_id integer not null references categoria (id)
);

CREATE TABLE cliente (
    id serial primary key,
    nome character varying(200) not null,
    email character varying(200) unique not null,
    telefone character varying(20)
);

CREATE TABLE venda (
    id serial primary key,
    cliente_id integer not null references cliente (id),
    data_hora timestamp not null default current_timestamp,
    status character varying(20) not null default 'aberta' check (status in ('aberta', 'finalizada', 'cancelada')),
    valor_total money not null default 0::money,
    desconto money not null default 0::money
);

CREATE TABLE item_venda (
    id serial primary key,
    venda_id integer not null references venda (id),
    produto_id integer not null references produto (id),
    quantidade integer not null check (quantidade > 0),
    preco_unitario money not null check (preco_unitario::numeric > 0)
);

INSERT INTO categoria (nome) VALUES
('INFORMATICA'),
('PAPELARIA'),
('ELETRONICOS');

INSERT INTO produto (nome, preco, estoque, categoria_id) VALUES
('MOUSE USB', 45.00, 20, 1),
('TECLADO', 120.00, 15, 1),
('CADERNO', 25.00, 40, 2),
('MONITOR', 800.00, 5, 3),
('PEN DRIVE', 40.00, 30, 1);

INSERT INTO cliente (nome, email, telefone) VALUES
('ANA SOUZA', 'ana.souza@email.com', '53999990001'),
('BRUNO LIMA', 'bruno.lima@email.com', '53999990002'),
('CARLA NUNES', 'carla.nunes@email.com', '53999990003');


-- Function 1. Total a pagar da venda.
-- Compras a partir de 200 recebem 10% de desconto.
CREATE OR REPLACE FUNCTION calcular_total_venda(var_venda_id integer)
RETURNS money AS $$
DECLARE
    var_bruto numeric := 0;
    var_desconto numeric := 0;
BEGIN
    SELECT COALESCE(SUM(preco_unitario::numeric * quantidade), 0)
    INTO var_bruto
    FROM item_venda
    WHERE venda_id = var_venda_id;

    IF var_bruto >= 200 THEN
        var_desconto := var_bruto * 0.10;
    END IF;

    RETURN CAST((var_bruto - var_desconto) AS money);
END;
$$ LANGUAGE plpgsql;


-- Function 2. Consulta se a quantidade pedida cabe no estoque atual.
CREATE OR REPLACE FUNCTION consultar_disponibilidade(var_produto_id integer, var_quantidade integer)
RETURNS boolean AS $$
DECLARE
    var_estoque integer;
BEGIN
    SELECT estoque
    INTO var_estoque
    FROM produto
    WHERE id = var_produto_id;

    IF var_estoque IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN var_estoque >= var_quantidade;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------------
-- Básicas
-- ---------------------------------------------------------------------------

-- Trigger 1. A quantidade do item tem de ser maior que zero.
CREATE OR REPLACE FUNCTION validar_quantidade_item()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.quantidade IS NULL OR NEW.quantidade <= 0 THEN
        RAISE EXCEPTION
            'A quantidade do item deve ser maior que zero.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_quantidade_item
BEFORE INSERT OR UPDATE OF quantidade ON item_venda
FOR EACH ROW
EXECUTE FUNCTION validar_quantidade_item();


-- Trigger 2. O preço gravado no item tem de ser maior que zero.
-- Se o INSERT não informar o preço, usa o preço atual do produto.
CREATE OR REPLACE FUNCTION validar_preco_item()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.preco_unitario IS NULL THEN
        SELECT preco
        INTO NEW.preco_unitario
        FROM produto
        WHERE id = NEW.produto_id;
    END IF;

    IF NEW.preco_unitario IS NULL OR NEW.preco_unitario <= 0::money THEN
        RAISE EXCEPTION
            'O preço do item deve ser maior que zero.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_preco_item
BEFORE INSERT OR UPDATE OF preco_unitario, produto_id ON item_venda
FOR EACH ROW
EXECUTE FUNCTION validar_preco_item();


-- ---------------------------------------------------------------------------
-- Intermediárias
-- ---------------------------------------------------------------------------

-- Trigger 3. Guarda o e-mail sem espaços e em minúsculas.
CREATE OR REPLACE FUNCTION normalizar_email()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.email IS NULL OR length(trim(NEW.email)) = 0 THEN
        RAISE EXCEPTION
            'O e-mail do cliente é obrigatório.';
    END IF;

    NEW.email := lower(trim(NEW.email));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_normalizar_email
BEFORE INSERT OR UPDATE OF email ON cliente
FOR EACH ROW
EXECUTE FUNCTION normalizar_email();


-- Trigger 4. Item só entra, muda ou sai enquanto a venda está aberta.
-- Equivale a impedir uma operação fora da janela válida do negócio.
CREATE OR REPLACE FUNCTION validar_venda_aberta()
RETURNS TRIGGER AS $$
DECLARE
    var_status character varying(20);
    var_venda_id integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        var_venda_id := OLD.venda_id;
    ELSE
        var_venda_id := NEW.venda_id;
    END IF;

    SELECT status
    INTO var_status
    FROM venda
    WHERE id = var_venda_id;

    IF var_status IS NULL THEN
        RAISE EXCEPTION 'Venda inexistente.';
    END IF;

    IF var_status <> 'aberta' THEN
        RAISE EXCEPTION
            'Não é permitido alterar itens de uma venda que não está aberta.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_venda_aberta
BEFORE INSERT OR UPDATE OR DELETE ON item_venda
FOR EACH ROW
EXECUTE FUNCTION validar_venda_aberta();


-- Trigger 5. Trava a linha do produto e recusa a quantidade que passa do estoque.
-- O FOR UPDATE segura o saldo até o fim da transação, para duas vendas
-- simultâneas não consumirem a mesma unidade.
CREATE OR REPLACE FUNCTION validar_estoque_item()
RETURNS TRIGGER AS $$
DECLARE
    var_estoque integer;
    var_necessario integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        var_necessario := NEW.quantidade;
    ELSIF OLD.produto_id = NEW.produto_id THEN
        var_necessario := NEW.quantidade - OLD.quantidade;
    ELSE
        var_necessario := NEW.quantidade;
    END IF;

    SELECT estoque
    INTO var_estoque
    FROM produto
    WHERE id = NEW.produto_id
    FOR UPDATE;

    IF var_estoque IS NULL THEN
        RAISE EXCEPTION 'Produto inexistente.';
    END IF;

    IF var_necessario > var_estoque THEN
        RAISE EXCEPTION
            'Estoque insuficiente. Disponível: %.', var_estoque;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_estoque_item
BEFORE INSERT OR UPDATE OF quantidade, produto_id ON item_venda
FOR EACH ROW
EXECUTE FUNCTION validar_estoque_item();


-- Trigger 6. Venda cancelada permanece cancelada.
-- Venda finalizada só pode seguir para cancelada.
CREATE OR REPLACE FUNCTION validar_status_venda()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'cancelada' AND NEW.status IS DISTINCT FROM 'cancelada' THEN
        RAISE EXCEPTION
            'Uma venda cancelada não pode mudar de status.';
    END IF;

    IF OLD.status = 'finalizada' AND NEW.status = 'aberta' THEN
        RAISE EXCEPTION
            'Uma venda finalizada não pode voltar a aberta.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_status_venda
BEFORE UPDATE OF status ON venda
FOR EACH ROW
EXECUTE FUNCTION validar_status_venda();


-- ---------------------------------------------------------------------------
-- Avançadas
-- ---------------------------------------------------------------------------

-- Trigger 7. A baixa do estoque acontece na inclusão do item.
-- Na alteração, ajusta só a diferença. Na exclusão de item de venda
-- ainda aberta, devolve a quantidade.
CREATE OR REPLACE FUNCTION movimentar_estoque_item()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE produto
        SET estoque = estoque - NEW.quantidade
        WHERE id = NEW.produto_id;

        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.produto_id = NEW.produto_id THEN
            UPDATE produto
            SET estoque = estoque - (NEW.quantidade - OLD.quantidade)
            WHERE id = NEW.produto_id;
        ELSE
            UPDATE produto
            SET estoque = estoque + OLD.quantidade
            WHERE id = OLD.produto_id;

            UPDATE produto
            SET estoque = estoque - NEW.quantidade
            WHERE id = NEW.produto_id;
        END IF;

        RETURN NEW;
    END IF;

    UPDATE produto
    SET estoque = estoque + OLD.quantidade
    WHERE id = OLD.produto_id;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movimentar_estoque_item
AFTER INSERT OR UPDATE OF quantidade, produto_id OR DELETE ON item_venda
FOR EACH ROW
EXECUTE FUNCTION movimentar_estoque_item();


-- Trigger 8. Ao cancelar, devolve as quantidades dos itens que continuam na venda.
-- A procedure só muda o status. Quem devolve o estoque é esta trigger.
CREATE OR REPLACE FUNCTION devolver_estoque_cancelamento()
RETURNS TRIGGER AS $$
DECLARE
    reg RECORD;
BEGIN
    IF OLD.status IS DISTINCT FROM 'cancelada' AND NEW.status = 'cancelada' THEN
        FOR reg IN
            SELECT produto_id, quantidade
            FROM item_venda
            WHERE venda_id = NEW.id
        LOOP
            UPDATE produto
            SET estoque = estoque + reg.quantidade
            WHERE id = reg.produto_id;
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_devolver_estoque_cancelamento
AFTER UPDATE OF status ON venda
FOR EACH ROW
EXECUTE FUNCTION devolver_estoque_cancelamento();


-- Procedure 1. Abre a venda, inclui o item e finaliza o total.
-- Estoque, preço e status válido ficam por conta das triggers.
CREATE OR REPLACE PROCEDURE registrar_venda(var_cliente_id integer, var_produto_id integer, var_quantidade integer)
AS $$
DECLARE
    var_venda_id integer;
    var_preco money;
    var_bruto numeric := 0;
    var_liquido money;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM cliente WHERE id = var_cliente_id) THEN
        RAISE EXCEPTION 'Cliente inexistente.';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM produto WHERE id = var_produto_id) THEN
        RAISE EXCEPTION 'Produto inexistente.';
    END IF;

    SELECT preco
    INTO var_preco
    FROM produto
    WHERE id = var_produto_id;

    INSERT INTO venda (cliente_id, status)
    VALUES (var_cliente_id, 'aberta')
    RETURNING id INTO var_venda_id;

    INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario)
    VALUES (var_venda_id, var_produto_id, var_quantidade, var_preco);

    SELECT COALESCE(SUM(preco_unitario::numeric * quantidade), 0)
    INTO var_bruto
    FROM item_venda
    WHERE venda_id = var_venda_id;

    var_liquido := calcular_total_venda(var_venda_id);

    UPDATE venda
    SET status = 'finalizada',
        valor_total = var_liquido,
        desconto = CAST((var_bruto - var_liquido::numeric) AS money)
    WHERE id = var_venda_id;

    RAISE NOTICE 'Venda % finalizada. Bruto: % Líquido: %',
        var_venda_id, CAST(var_bruto AS money), var_liquido;
END;
$$ LANGUAGE plpgsql;


-- Procedure 2. Cancela a venda.
-- A devolução do estoque ocorre na trigger trg_devolver_estoque_cancelamento.
CREATE OR REPLACE PROCEDURE cancelar_venda(var_venda_id integer)
AS $$
DECLARE
    var_status character varying(20);
BEGIN
    SELECT status
    INTO var_status
    FROM venda
    WHERE id = var_venda_id;

    IF var_status IS NULL THEN
        RAISE EXCEPTION 'Venda inexistente.';
    END IF;

    IF var_status = 'cancelada' THEN
        RAISE NOTICE 'Venda % já está cancelada.', var_venda_id;
        RETURN;
    END IF;

    UPDATE venda
    SET status = 'cancelada'
    WHERE id = var_venda_id;

    RAISE NOTICE 'Venda % cancelada.', var_venda_id;
END;
$$ LANGUAGE plpgsql;


-- Procedure 3. Soma unidades ao estoque de um produto já cadastrado.
-- A baixa e a devolução da venda continuam nas triggers do item e do cancelamento.
CREATE OR REPLACE PROCEDURE repor_estoque(var_produto_id integer, var_quantidade integer)
AS $$
DECLARE
    var_estoque integer;
BEGIN
    IF var_quantidade IS NULL OR var_quantidade <= 0 THEN
        RAISE EXCEPTION
            'A quantidade da reposição deve ser maior que zero.';
    END IF;

    SELECT estoque
    INTO var_estoque
    FROM produto
    WHERE id = var_produto_id
    FOR UPDATE;

    IF var_estoque IS NULL THEN
        RAISE EXCEPTION 'Produto inexistente.';
    END IF;

    UPDATE produto
    SET estoque = estoque + var_quantidade
    WHERE id = var_produto_id;

    RAISE NOTICE 'Estoque do produto % agora é %.',
        var_produto_id, var_estoque + var_quantidade;
END;
$$ LANGUAGE plpgsql;


-- Venda do monitor: 800, com 10% de desconto.
CALL registrar_venda(1, 4, 1);

-- Venda de dois mouses: 90, sem desconto.
CALL registrar_venda(2, 1, 2);


-- SELECT calcular_total_venda(1);
-- SELECT consultar_disponibilidade(4, 1);
-- CALL cancelar_venda(2);
-- SELECT id, nome, estoque FROM produto ORDER BY id;
-- SELECT * FROM venda ORDER BY id;
-- SELECT * FROM item_venda ORDER BY id;
-- CALL repor_estoque(1, 10);
