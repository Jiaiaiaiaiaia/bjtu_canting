"""Flask 入口。"""
import os
import sys

from flask import Flask, render_template
from flask_cors import CORS

# 将 backend 目录加入 sys.path，便于子模块相对导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import api_bp, init_db  # noqa: E402


def create_app():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'frontend', 'templates'),
        static_folder=os.path.join(project_root, 'frontend', 'static'),
        static_url_path='/static',
    )
    CORS(app)
    init_db()
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5001, debug=True)
