
DROP DATABASE IF EXISTS loja;

CREATE DATABASE loja;

\c loja;

CREATE TABLE categoria (
    id serial primary key,
    nome varchar(100) not null unique
);

CREATE TABLE produto (
    id serial primary key,
    nome varchar(200) not null,
    preco numeric(20,2) not null default 0,
    estoque integer not null default 0,
    categoria_id integer not null references categoria (id)
);

CREATE TABLE cliente (
    id serial primary key,
    nome varchar(200) not null,
    email varchar(200) unique not null,
    telefone varchar(20)
);

CREATE TABLE venda (
    id serial primary key,
    cliente_id integer not null references cliente (id),
    data_hora timestamp not null default current_timestamp,
    status varchar(20) not null default 'aberta',
    valor_total numeric(20,2) not null default 0,
    desconto numeric(20,2) not null default 0
);

CREATE TABLE item_venda (
    id serial primary key,
    venda_id integer not null references venda (id),
    produto_id integer not null references produto (id),
    quantidade integer not null,
    preco_unitario numeric(20,2) not null
);


INSERT INTO categoria (nome) VALUES
('COMPONENTES'),
('PERIFERICOS'),
('MONITORES');


INSERT INTO produto (nome, preco, estoque, categoria_id) VALUES
('PROCESSADOR INTEL I5', 890.00, 10, 1),
('MEMORIA RAM 16GB', 260.00, 20, 1),
('SSD 512GB', 310.00, 16, 1),
('PLACA DE VIDEO RTX 4060', 2100.00, 6, 1),
('FONTE 650W', 390.00, 12, 1),
('MOUSE GAMER', 140.00, 30, 2),
('TECLADO MECANICO', 270.00, 18, 2),
('HEADSET', 210.00, 16, 2),
('WEBCAM FULL HD', 190.00, 14, 2),
('MONITOR 24 POLEGADAS', 980.00, 8, 3);

INSERT INTO cliente (nome, email, telefone) VALUES
('ANA SOUZA', 'ana.souza@email.com', '53999990001'),
('BRUNO LIMA', 'bruno.lima@email.com', '53999990002'),
('CARLA NUNES', 'carla.nunes@email.com', '53999990003'),
('DIEGO MARTINS', 'diego.martins@email.com', '53999990004'),
('ELENA COSTA', 'elena.costa@email.com', '53999990005'),
('FELIPE ROCHA', 'felipe.rocha@email.com', '53999990006'),
('GABRIELA ALVES', 'gabriela.alves@email.com', '53999990007'),
('HENRIQUE DIAS', 'henrique.dias@email.com', '53999990008'),
('ISABELA FERREIRA', 'isabela.ferreira@email.com', '53999990009'),
('JOAO PEREIRA', 'joao.pereira@email.com', '53999990010');


CREATE OR REPLACE FUNCTION calcular_total_venda(var_venda_id integer) RETURNS numeric(20,2) AS
$$
DECLARE
    var_bruto numeric(20,2) := 0;
    var_desconto numeric(20,2) := 0;
BEGIN
    SELECT COALESCE(SUM(preco_unitario * quantidade), 0) FROM item_venda WHERE venda_id = var_venda_id INTO var_bruto;

    IF (var_bruto >= 200) THEN
        var_desconto := var_bruto * 0.10;
    END IF;

    RETURN var_bruto - var_desconto;
END;
$$ LANGUAGE 'plpgsql';


CREATE OR REPLACE FUNCTION consultar_disponibilidade(var_produto_id integer, var_quantidade integer) RETURNS boolean AS
$$
DECLARE
    var_estoque integer;
BEGIN
    SELECT estoque FROM produto WHERE id = var_produto_id INTO var_estoque;

    IF (var_estoque IS NULL) THEN
        RETURN FALSE;
    END IF;

    RETURN var_estoque >= var_quantidade;
END;
$$ LANGUAGE 'plpgsql';


CREATE OR REPLACE FUNCTION validar_quantidade_item() RETURNS TRIGGER AS
$$
BEGIN
    IF (NEW.quantidade IS NULL OR NEW.quantidade <= 0) THEN
        RAISE EXCEPTION 'A quantidade do item deve ser maior que zero.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_quantidade_item BEFORE INSERT OR UPDATE OF quantidade ON item_venda FOR EACH ROW EXECUTE FUNCTION validar_quantidade_item();


CREATE OR REPLACE FUNCTION validar_preco_item() RETURNS TRIGGER AS
$$
BEGIN
    IF (NEW.preco_unitario IS NULL) THEN
        SELECT preco FROM produto WHERE id = NEW.produto_id INTO NEW.preco_unitario;
    END IF;

    IF (NEW.preco_unitario IS NULL OR NEW.preco_unitario <= 0) THEN
        RAISE EXCEPTION 'O preço do item deve ser maior que zero.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_preco_item BEFORE INSERT OR UPDATE OF preco_unitario, produto_id ON item_venda FOR EACH ROW EXECUTE FUNCTION validar_preco_item();


CREATE OR REPLACE FUNCTION normalizar_email() RETURNS TRIGGER AS
$$
BEGIN
    IF (NEW.email IS NULL OR length(trim(NEW.email)) = 0) THEN
        RAISE EXCEPTION 'O e-mail do cliente é obrigatório.';
    END IF;

    NEW.email := lower(trim(NEW.email));

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_normalizar_email BEFORE INSERT OR UPDATE OF email ON cliente FOR EACH ROW EXECUTE FUNCTION normalizar_email();


CREATE OR REPLACE FUNCTION validar_venda_aberta() RETURNS TRIGGER AS
$$
DECLARE
    var_status varchar(20);
    var_venda_id integer;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        var_venda_id := OLD.venda_id;
    ELSE
        var_venda_id := NEW.venda_id;
    END IF;

    SELECT status FROM venda WHERE id = var_venda_id INTO var_status;

    IF (var_status IS NULL) THEN
        RAISE EXCEPTION 'Venda inexistente.';
    END IF;

    IF (var_status <> 'aberta') THEN
        RAISE EXCEPTION 'Não é permitido alterar itens de uma venda que não está aberta.';
    END IF;

    IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_venda_aberta BEFORE INSERT OR UPDATE OR DELETE ON item_venda FOR EACH ROW EXECUTE FUNCTION validar_venda_aberta();


CREATE OR REPLACE FUNCTION validar_estoque_item() RETURNS TRIGGER AS
$$
DECLARE
    var_estoque integer;
    var_necessario integer;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        var_necessario := NEW.quantidade;
    ELSIF (OLD.produto_id = NEW.produto_id) THEN
        var_necessario := NEW.quantidade - OLD.quantidade;
    ELSE
        var_necessario := NEW.quantidade;
    END IF;

    SELECT estoque FROM produto WHERE id = NEW.produto_id FOR UPDATE INTO var_estoque;

    IF (var_estoque IS NULL) THEN
        RAISE EXCEPTION 'Produto inexistente.';
    END IF;

    IF (var_necessario > var_estoque) THEN
        RAISE EXCEPTION 'Estoque insuficiente. Disponível: %.', var_estoque;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_estoque_item BEFORE INSERT OR UPDATE OF quantidade, produto_id ON item_venda FOR EACH ROW EXECUTE FUNCTION validar_estoque_item();


CREATE OR REPLACE FUNCTION validar_preco_produto() RETURNS TRIGGER AS
$$
BEGIN
    IF (NEW.preco IS NOT NULL AND NEW.preco > 0 AND NEW.estoque IS NOT NULL AND NEW.estoque >= 0) THEN
        RETURN NEW;
    END IF;

    IF (NEW.preco IS NULL OR NEW.preco <= 0) THEN
        RAISE EXCEPTION 'O preço do produto deve ser maior que zero.';
    END IF;

    RAISE EXCEPTION 'O estoque não pode ficar negativo.';
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_preco_produto BEFORE INSERT OR UPDATE OF preco, estoque ON produto FOR EACH ROW EXECUTE FUNCTION validar_preco_produto();


CREATE OR REPLACE FUNCTION validar_status_venda() RETURNS TRIGGER AS
$$
BEGIN
    IF (NEW.status IS NULL OR NEW.status NOT IN ('aberta', 'finalizada', 'cancelada')) THEN
        RAISE EXCEPTION 'Status de venda inválido.';
    END IF;

    IF (TG_OP = 'UPDATE' AND OLD.status = 'cancelada' AND NEW.status IS DISTINCT FROM 'cancelada') THEN
        RAISE EXCEPTION 'Uma venda cancelada não pode mudar de status.';
    END IF;

    IF (TG_OP = 'UPDATE' AND OLD.status = 'finalizada' AND NEW.status = 'aberta') THEN
        RAISE EXCEPTION 'Uma venda finalizada não pode voltar a aberta.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_validar_status_venda BEFORE INSERT OR UPDATE OF status ON venda FOR EACH ROW EXECUTE FUNCTION validar_status_venda();


CREATE OR REPLACE FUNCTION movimentar_estoque_item() RETURNS TRIGGER AS
$$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE produto SET estoque = estoque - NEW.quantidade WHERE id = NEW.produto_id;
        RETURN NEW;
    END IF;

    IF (TG_OP = 'UPDATE') THEN
        IF (OLD.produto_id = NEW.produto_id) THEN
            UPDATE produto SET estoque = estoque - (NEW.quantidade - OLD.quantidade) WHERE id = NEW.produto_id;
        ELSE
            UPDATE produto SET estoque = estoque + OLD.quantidade WHERE id = OLD.produto_id;
            UPDATE produto SET estoque = estoque - NEW.quantidade WHERE id = NEW.produto_id;
        END IF;

        RETURN NEW;
    END IF;

    UPDATE produto SET estoque = estoque + OLD.quantidade WHERE id = OLD.produto_id;
    RETURN OLD;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_movimentar_estoque_item AFTER INSERT OR UPDATE OF quantidade, produto_id OR DELETE ON item_venda FOR EACH ROW EXECUTE FUNCTION movimentar_estoque_item();


CREATE OR REPLACE FUNCTION devolver_estoque_cancelamento() RETURNS TRIGGER AS
$$
DECLARE
    reg record;
BEGIN
    IF (OLD.status IS DISTINCT FROM 'cancelada' AND NEW.status = 'cancelada') THEN
        FOR reg IN SELECT produto_id, quantidade FROM item_venda WHERE venda_id = NEW.id LOOP
            UPDATE produto SET estoque = estoque + reg.quantidade WHERE id = reg.produto_id;
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
CREATE TRIGGER trigger_devolver_estoque_cancelamento AFTER UPDATE OF status ON venda FOR EACH ROW EXECUTE FUNCTION devolver_estoque_cancelamento();


CREATE OR REPLACE PROCEDURE registrar_venda(var_cliente_id integer, var_produtos integer[], var_quantidades integer[]) AS
$$
DECLARE
    var_venda_id integer;
    var_preco numeric(20,2);
    var_bruto numeric(20,2) := 0;
    var_liquido numeric(20,2);
    i integer;
BEGIN
    IF (NOT EXISTS(SELECT * FROM cliente WHERE id = var_cliente_id)) THEN
        RAISE EXCEPTION 'Cliente inexistente.';
    END IF;

    IF (COALESCE(array_length(var_produtos, 1), 0) = 0 OR COALESCE(array_length(var_quantidades, 1), 0) <> array_length(var_produtos, 1)) THEN
        RAISE EXCEPTION 'Informe ao menos um produto, com a quantidade de cada um.';
    END IF;

    INSERT INTO venda (cliente_id, status) VALUES (var_cliente_id, 'aberta') RETURNING id INTO var_venda_id;

    FOR i IN 1 .. array_length(var_produtos, 1) LOOP
        SELECT preco FROM produto WHERE id = var_produtos[i] INTO var_preco;

        IF (var_preco IS NULL) THEN
            RAISE EXCEPTION 'Produto inexistente.';
        END IF;

        INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario) VALUES (var_venda_id, var_produtos[i], var_quantidades[i], var_preco);
    END LOOP;

    SELECT COALESCE(SUM(preco_unitario * quantidade), 0) FROM item_venda WHERE venda_id = var_venda_id INTO var_bruto;

    var_liquido := calcular_total_venda(var_venda_id);

    UPDATE venda
    SET status = 'finalizada',
        valor_total = var_liquido,
        desconto = var_bruto - var_liquido
    WHERE id = var_venda_id;
END;
$$ LANGUAGE 'plpgsql';


CREATE OR REPLACE PROCEDURE cancelar_venda(var_venda_id integer) AS
$$
DECLARE
    var_status varchar(20);
BEGIN
    SELECT status FROM venda WHERE id = var_venda_id INTO var_status;

    IF (var_status IS NULL) THEN
        RAISE EXCEPTION 'Venda inexistente.';
    END IF;

    IF (var_status = 'cancelada') THEN
        RAISE EXCEPTION 'Venda % já está cancelada.', var_venda_id;
    END IF;

    UPDATE venda SET status = 'cancelada' WHERE id = var_venda_id;
END;
$$ LANGUAGE 'plpgsql';


CREATE OR REPLACE PROCEDURE repor_estoque(var_produto_id integer, var_quantidade integer) AS
$$
DECLARE
    var_estoque integer;
BEGIN
    IF (var_quantidade IS NULL OR var_quantidade <= 0) THEN
        RAISE EXCEPTION 'A quantidade da reposição deve ser maior que zero.';
    END IF;

    IF (NOT EXISTS(SELECT * FROM produto WHERE id = var_produto_id)) THEN
        RAISE EXCEPTION 'Produto inexistente.';
    END IF;

    SELECT estoque FROM produto WHERE id = var_produto_id FOR UPDATE INTO var_estoque;

    UPDATE produto SET estoque = estoque + var_quantidade WHERE id = var_produto_id;
END;
$$ LANGUAGE 'plpgsql';

CALL registrar_venda(1, ARRAY[10], ARRAY[1]);
CALL registrar_venda(2, ARRAY[6], ARRAY[2]);
CALL registrar_venda(3, ARRAY[7, 8], ARRAY[1, 1]);
CALL registrar_venda(4, ARRAY[1], ARRAY[1]);
CALL registrar_venda(5, ARRAY[9], ARRAY[1]);
CALL registrar_venda(6, ARRAY[2], ARRAY[2]);
CALL registrar_venda(7, ARRAY[6, 9], ARRAY[1, 1]);
CALL registrar_venda(8, ARRAY[5], ARRAY[1]);
CALL registrar_venda(9, ARRAY[8], ARRAY[2]);
CALL registrar_venda(10, ARRAY[3, 6], ARRAY[1, 1]);
