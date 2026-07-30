from flask import Flask, jsonify


def create_app() -> Flask:
    """Tạo và cấu hình ứng dụng Flask."""

    app = Flask(__name__)

    @app.get("/api/v1/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "message": "License plate API is running",
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )