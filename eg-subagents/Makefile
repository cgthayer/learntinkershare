all: uv.lock

uv.lock: pyproject.toml
	uv lock

setup:
	uv sync

lint:
	ruff format
	ruff check

test:
	uv run python test_offline.py

demo:
	uv run python demo.py

native:
	uv run python native_multiagent.py

demo-async:
	uv run python demo_async.py
