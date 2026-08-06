import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    from waitress import serve

    host = os.environ.get("NETGUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("NETGUARD_PORT", "5000"))
    print(f"Network Security Lab: http://{host}:{port}", flush=True)
    serve(app, host=host, port=port, threads=6)
