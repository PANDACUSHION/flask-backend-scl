from src.app import create_app
from src.config import Config

cfg = Config()



if __name__ == '__main__':
    app = create_app(cfg)
    app.run(host=cfg.FLASK_HOST, port=cfg.FLASK_PORT, debug=cfg.FLASK_DEBUG)