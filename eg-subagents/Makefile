all: uv.lock

uv.lock: pyproject.toml
	uv lock

setup:
	uv sync

lint:
	ruff format
	ruff check

demo:
	uv run python demo.py

native:
	uv run python native_multiagent.py
