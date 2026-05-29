"""Flask 入口。"""
from flask import Flask, render_template
from flask_cors import CORS

from canteen.api import api_bp, init_db
from canteen.api.campus_routes import campus_bp
from canteen.paths import FRONTEND_ROOT


def create_app():
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_ROOT / 'templates'),
        static_folder=str(FRONTEND_ROOT / 'static'),
        static_url_path='/static',
    )
    CORS(app)
    init_db()
    app.register_blueprint(api_bp)
    app.register_blueprint(campus_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5001, debug=True)
