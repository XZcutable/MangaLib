"""The server process the supervisor starts (`python -m mymangalib.child`). Every version keeps this
module and its flags, because an older supervisor starts newer versions through it."""
import argparse, os, time

READY_FILE = "MYMANGALIB_READY_FILE"
BIND_WAIT = 30


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()

    from waitress import create_server
    from . import create_app
    from .server import updater

    app = create_app()
    updater.start_background(app)

    # Tells the supervisor to let go of the port, then takes it over
    ready_file = os.environ.get(READY_FILE)
    if ready_file:
        with open(ready_file, "w") as file:
            file.write(str(os.getpid()))
    deadline = time.time() + BIND_WAIT
    while True:
        try:
            server = create_server(app, host=args.host, port=args.port, threads=args.threads)
            break
        except OSError:
            if time.time() > deadline:
                raise
            time.sleep(0.05)
    print(f"Serving on http://{args.host}:{args.port}", flush=True)
    server.run()


if __name__ == "__main__":
    main()
