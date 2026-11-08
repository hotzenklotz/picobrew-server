from pathlib import Path

import pytest

from picobrew_server import create_app
from picobrew_server.cli import GUNICORN_CONFIG, gunicorn_argv, parse_args


def test_defaults_serve_the_machine_on_port_80(monkeypatch):
    monkeypatch.delenv("PICOBREW_DATA_DIR", raising=False)
    args = parse_args([])
    assert args.data_dir == Path(".")
    assert gunicorn_argv(args) == ["--config", GUNICORN_CONFIG, "--bind", "0.0.0.0:80", "--workers", "2"]


@pytest.mark.parametrize(("host", "bind"), [("127.0.0.1", "127.0.0.1:8080"), ("::", "[::]:8080")])
def test_host_and_port_become_a_gunicorn_bind(host, bind):
    argv = gunicorn_argv(parse_args(["--host", host, "--port", "8080", "--workers", "1"]))
    assert argv[argv.index("--bind") + 1] == bind
    assert argv[argv.index("--workers") + 1] == "1"


def test_data_dir_defaults_to_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PICOBREW_DATA_DIR", str(tmp_path))
    assert parse_args([]).data_dir == tmp_path
    assert parse_args(["--data-dir", "elsewhere"]).data_dir == Path("elsewhere")


def test_app_stores_data_under_the_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PICOBREW_DATA_DIR", str(tmp_path))
    config = create_app({"TESTING": True}).config
    assert config["UPLOAD_FOLDER"] == str(tmp_path / "recipes")
    assert config["BREW_DATABASE"] == str(tmp_path / "sessions" / "brew_sessions.sqlite3")
    assert config["LEGACY_SESSION_PATH"] == str(tmp_path / "sessions")
    assert config["MACHINE_PATH"] == str(tmp_path / "machines")


def test_app_keeps_relative_paths_without_a_data_dir(monkeypatch):
    monkeypatch.delenv("PICOBREW_DATA_DIR", raising=False)
    config = create_app({"TESTING": True, "LEGACY_SESSION_PATH": None}).config
    assert config["UPLOAD_FOLDER"] == "recipes"
    assert config["BREW_DATABASE"] == str(Path("sessions") / "brew_sessions.sqlite3")
    assert config["MACHINE_PATH"] == "machines"
