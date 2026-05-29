"""python -m canteen → 启动开发服务器（保留旧 5001 端口体验）。"""
from canteen.app import create_app

create_app().run(host="0.0.0.0", port=5001, debug=True)
