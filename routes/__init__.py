def registrar_rotas(app):
    from routes.clientes import bp as clientes
    from routes.painel import bp as painel
    from routes.produtos import bp as produtos
    from routes.vendas import bp as vendas

    app.register_blueprint(painel)
    app.register_blueprint(produtos)
    app.register_blueprint(clientes)
    app.register_blueprint(vendas)
