"""Where `mymangalib serve` keeps its data: one folder (/data in Docker), or the older two volumes."""
import json, os

from mymangalib import cli

def make_database(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as file:
        file.write("")

def choose(tmp_path, mounted=()):
    data, old = tmp_path / "data", tmp_path / "var"
    paths, reason = cli.docker_data_paths(str(data), old_root=str(old), ismount=lambda path: path in mounted)
    return paths, reason, str(data), str(old)

def test_new_server_uses_the_data_folder(tmp_path):
    paths, _, data, _ = choose(tmp_path)
    assert paths == cli.data_paths(data)
    assert paths["CONFIG_PATH"] == os.path.join(data, "config.toml")
    assert paths["UPDATE_PATH"] == os.path.join(data, "updates")

def test_existing_old_volumes_keep_working(tmp_path):
    make_database(tmp_path / "var" / "db" / "database.db")
    paths, reason, _, old = choose(tmp_path)
    assert paths["DATABASE_PATH"] == os.path.join(old, "db", "database.db")
    assert paths["CONFIG_PATH"] == os.path.join(old, "config", "config.toml")
    assert paths["UPDATE_PATH"] == os.path.join(old, "db", "updates")
    assert "older volumes" in reason

def test_old_compose_folders_inside_the_new_mount(tmp_path):
    """./data/db and ./data/config from the old compose file, now mounted as ./data:/data."""
    make_database(tmp_path / "data" / "db" / "database.db")
    paths, _, data, _ = choose(tmp_path)
    assert paths["DATABASE_PATH"] == os.path.join(data, "db", "database.db")
    assert paths["CONFIG_PATH"] == os.path.join(data, "config", "config.toml")

def test_data_folder_wins_when_both_have_a_database(tmp_path):
    make_database(tmp_path / "data" / "database.db")
    make_database(tmp_path / "var" / "db" / "database.db")
    paths, reason, data, _ = choose(tmp_path)
    assert paths == cli.data_paths(data)
    assert "isn't used" in reason

def test_new_server_with_an_old_style_mount(tmp_path):
    """An older compose file or docker run command mounts /var/db; the image no longer declares it."""
    old_db = str(tmp_path / "var" / "db")
    paths, _, _, old = choose(tmp_path, mounted={old_db, str(tmp_path / "data")})
    assert paths["DATABASE_PATH"] == os.path.join(old, "db", "database.db")

def test_env_paths_set_by_hand_win(tmp_path, monkeypatch):
    # A private copy: apply_default_data_dir sets variables, which mustn't reach the other tests
    environ = {key: value for key, value in os.environ.items() if not key.startswith(("FLASK_", "MYMANGALIB_"))}
    environ["FLASK_DATA_DIR"] = str(tmp_path / "data")
    environ["FLASK_DATABASE_PATH"] = str(tmp_path / "elsewhere" / "my.db")  # Plain text, not JSON
    monkeypatch.setattr(os, "environ", environ)
    cli.apply_default_data_dir()
    assert cli.env_value("DATABASE_PATH") == str(tmp_path / "elsewhere" / "my.db")
    assert json.loads(os.environ["FLASK_CONFIG_PATH"]) == str(tmp_path / "data" / "config.toml")
    assert os.path.isdir(tmp_path / "elsewhere") and os.path.isdir(tmp_path / "data")
