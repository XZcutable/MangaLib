"""`mymangalib` command: starts the server with settings given as flags.

    mymangalib serve --library /var/manga --site-name "Home library" --no-auto-update
    mymangalib version

Each flag sets the matching FLASK_<KEY> environment variable before the app starts, so flags win over
config.toml exactly like environment variables do. Settings the owner later changes in the app (site name,
registration switches) are saved in the database and win over both.
"""
import argparse, json, os, sys, tomllib

from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mymangalib",
        description="Self-hosted manga server. Flags override config.toml.",
    )
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "version"],
                        help="serve (default) starts the server; version prints the version")

    server = parser.add_argument_group("server")
    server.add_argument("--host", help="Address to listen on (default 127.0.0.1; the Docker image uses 0.0.0.0)")
    server.add_argument("--port", type=int, help="Port to listen on (default 5000)")
    server.add_argument("--threads", type=int, help="Request threads (default 8)")
    server.add_argument("--data-dir", metavar="DIR",
                        help="Keep the database, config.toml, covers and updates in this folder "
                             "(the Docker image uses /data)")
    server.add_argument("--config", metavar="FILE", help="Path to config.toml")

    library = parser.add_argument_group("library")
    library.add_argument("--library", metavar="PATH", action="append",
                         help="A manga folder to add and scan on the first start. Repeat for more folders.")
    library.add_argument("--library-moved", metavar="OLD=NEW", action="append",
                         help="A library folder now at NEW (e.g. a new mount) instead of OLD. Done once at startup; "
                              "the manga keep their reading progress. Repeat for more folders.")
    library.add_argument("--site-name", help="Name shown in the browser tab and the app")
    library.add_argument("--public-url", help="Address people use to reach the server, for invite links and QR codes")

    access = parser.add_argument_group("access")
    access.add_argument("--allow-new-users", action=argparse.BooleanOptionalAction, default=None,
                        help="Let people create accounts")
    access.add_argument("--auto-approve-users", action=argparse.BooleanOptionalAction, default=None,
                        help="New accounts can read without waiting for an admin")
    access.add_argument("--behind-proxy", action=argparse.BooleanOptionalAction, default=None,
                        help="Trust X-Forwarded-* headers from a reverse proxy")
    access.add_argument("--url-prefix", metavar="PATH", help="Sub-path the server is reached at, e.g. /manga")
    access.add_argument("--cors-origins", metavar="LIST",
                        help="Comma-separated web pages allowed to call the API from a browser")

    updates = parser.add_argument_group("updates")
    updates.add_argument("--no-auto-update", action="store_true",
                         help="Don't check for or download updates automatically. The owner can still check in Settings.")
    updates.add_argument("--update-check-hours", type=float, metavar="HOURS",
                         help="How often to check for updates (default 6)")
    return parser


def flags_to_env(args: argparse.Namespace) -> dict[str, str]:
    """The FLASK_* variables the flags stand for. Values are JSON, as Flask's from_prefixed_env reads them."""
    env: dict[str, str] = {}

    def put(key, value):
        if value is not None:
            env[f"FLASK_{key}"] = json.dumps(value)

    if args.data_dir:
        data_dir = os.path.abspath(args.data_dir)
        os.makedirs(data_dir, exist_ok=True)
        for key, value in data_paths(data_dir).items():
            put(key, value)
    if args.config:
        put("CONFIG_PATH", os.path.abspath(args.config))
    if args.library:
        put("LIBRARY_PATHS", [os.path.abspath(path) for path in args.library])
    if args.library_moved:
        moves = {}
        for move in args.library_moved:
            old, separator, new = move.partition("=")
            if not separator or not old.strip() or not new.strip():
                raise SystemExit(f"--library-moved needs OLD=NEW, got '{move}'")
            moves[old.strip()] = new.strip()
        put("LIBRARY_MOVES", moves)
    put("SITE_NAME", args.site_name)
    put("PUBLIC_URL", args.public_url)
    put("ALLOW_NEW_USERS", args.allow_new_users)
    put("AUTO_APPROVE_NEW_USERS", args.auto_approve_users)
    put("BEHIND_PROXY", args.behind_proxy)
    put("URL_PREFIX", args.url_prefix)
    if args.cors_origins:
        put("CORS_ORIGINS", [origin.strip() for origin in args.cors_origins.split(",") if origin.strip()])
    if args.no_auto_update:
        put("AUTO_UPDATE", False)
    put("UPDATE_CHECK_HOURS", args.update_check_hours)
    return env


def data_paths(data_dir: str) -> dict[str, str]:
    """Everything the server keeps, in one folder."""
    return {
        "DATABASE_PATH": os.path.join(data_dir, "database.db"),
        "CONFIG_PATH": os.path.join(data_dir, "config.toml"),
        "THUMBNAIL_CACHE_PATH": os.path.join(data_dir, "covers"),
        "UPDATE_PATH": os.path.join(data_dir, "updates"),
    }


# Docker images up to 1.2 kept data in two volumes: /var/db (database, covers, updates) and /var/config
# (config.toml). Compose put them in ./data/db and ./data/config, so a new compose file that mounts ./data
# at /data finds them at /data/db and /data/config.
def split_paths(db_dir: str, config_dir: str) -> dict[str, str]:
    return {
        "DATABASE_PATH": os.path.join(db_dir, "database.db"),
        "CONFIG_PATH": os.path.join(config_dir, "config.toml"),
        "THUMBNAIL_CACHE_PATH": os.path.join(db_dir, "covers"),
        "UPDATE_PATH": os.path.join(db_dir, "updates"),
    }


def docker_data_paths(data_dir: str, old_root: str = "/var", ismount=os.path.ismount) -> tuple[dict[str, str], str]:
    """Where a Docker container keeps its data, and why. An existing database wins wherever it is, so
    upgrading the image never starts a server with an empty library."""
    old_volumes = split_paths(os.path.join(old_root, "db"), os.path.join(old_root, "config"))
    old_compose = split_paths(os.path.join(data_dir, "db"), os.path.join(data_dir, "config"))
    new = data_paths(data_dir)
    has_database = lambda paths: os.path.isfile(paths["DATABASE_PATH"])

    if has_database(new):
        if has_database(old_volumes):
            return new, f"Using {data_dir}. There's also an older database in {old_root}/db, which isn't used."
        return new, f"Using {data_dir}"
    if has_database(old_compose):
        return old_compose, f"Using {data_dir}/db and {data_dir}/config (the older two-folder layout)"
    if has_database(old_volumes):
        return old_volumes, (f"Using the older volumes {old_root}/db and {old_root}/config. "
                             f"They keep working; see UPGRADING.md to move to a single {data_dir} volume.")
    # A new server. The image only declares /data, so a volume at /var/db was mounted on purpose
    # (an older compose file or docker run command)
    if ismount(os.path.join(old_root, "db")):
        return old_volumes, f"Using the mounted {old_root}/db and {old_root}/config"
    return new, f"Using {data_dir}"


def apply_default_data_dir() -> None:
    """FLASK_DATA_DIR (set by the Docker image): fills in the paths that weren't set some other way."""
    data_dir = env_value("DATA_DIR")
    if not data_dir:
        return
    data_dir = os.path.abspath(str(data_dir))
    if os.environ.get("MYMANGALIB_DOCKER"):
        paths, reason = docker_data_paths(data_dir)
        print(f"Data: {reason}", flush=True)
    else:
        paths = data_paths(data_dir)
    for key, value in paths.items():
        os.environ.setdefault(f"FLASK_{key}", json.dumps(value))
    for key in ("DATABASE_PATH", "CONFIG_PATH"):
        os.makedirs(os.path.dirname(os.path.abspath(str(env_value(key)))), exist_ok=True)


def env_value(key: str, default=None):
    """A FLASK_<KEY> variable, read the way Flask reads it (JSON when it parses, else text)."""
    raw = os.environ.get(f"FLASK_{key}")
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def default_instance_path() -> str:
    """Flask's instance folder for this installed copy. An applied update lives in another folder, where
    Flask would pick a different one, so the supervisor passes this one on (MYMANGALIB_INSTANCE_PATH)."""
    if os.environ.get("MYMANGALIB_INSTANCE_PATH"):
        return os.environ["MYMANGALIB_INSTANCE_PATH"]
    from flask import Flask
    return Flask("mymangalib", instance_relative_config=True).instance_path


def update_path() -> str:
    """Where updates are kept. The supervisor needs it before the app exists, so it follows the same
    rules: FLASK_UPDATE_PATH, then UPDATE_PATH or DATABASE_PATH in config.toml, then the instance folder."""
    configured = env_value("UPDATE_PATH")
    if configured:
        return os.path.abspath(configured)

    instance_path = default_instance_path()
    config = {}
    config_path = env_value("CONFIG_PATH") or os.path.join(instance_path, "config.toml")
    try:
        with open(config_path, "rb") as file:
            config = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        pass
    if config.get("UPDATE_PATH"):
        return os.path.abspath(config["UPDATE_PATH"])
    database = env_value("DATABASE_PATH") or config.get("DATABASE_PATH")
    if database:
        return os.path.join(os.path.dirname(os.path.abspath(database)), "updates")
    return os.path.join(instance_path, "updates")


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0

    os.environ.update(flags_to_env(args))
    if not args.data_dir:
        apply_default_data_dir()  # After the flags, so FLASK_* variables set by hand still win
    host = args.host or env_value("HOST") or "127.0.0.1"
    port = args.port or env_value("PORT") or 5000
    threads = args.threads or env_value("THREADS") or 8
    os.environ["MYMANGALIB_INSTANCE_PATH"] = default_instance_path()
    path = update_path()
    # The server (child process) must use the same folder as the supervisor
    os.environ["FLASK_UPDATE_PATH"] = json.dumps(path)

    from .supervisor import Supervisor
    return Supervisor(str(host), int(port), int(threads), path).run()


if __name__ == "__main__":
    sys.exit(main())
