.PHONY: all frontend python clean

# Build everything from scratch (clean, then frontend, then Python package)
all: clean frontend python

# Install frontend dependencies and build the SvelteKit app
frontend:
	pnpm --dir frontend/ install && pnpm --dir frontend/ run build

# Build the Python package (depends on frontend assets being built first)
python: frontend
	cp -r frontend/build/* src/ontoloom_viz/static/
	uv build

# Remove frontend and Python build artifacts
clean:
	rm -rf frontend/build src/ontoloom_viz/static/* dist
