from routes.inicio import inicio_bp
from routes.produtos import produtos_bp
from routes.clientes import clientes_bp
from routes.vendas import vendas_bp


def registrar_rotas(app):
    app.register_blueprint(inicio_bp)
    app.register_blueprint(produtos_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(vendas_bp)
