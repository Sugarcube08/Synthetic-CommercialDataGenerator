# CHANGELOG

All notable changes to the Synthetic Commercial Data Generator project will be documented in this file.

---

## [0.1.0] - 2026-06-10

### Added
- **Batch Generator Entrypoint**: Implemented a standalone, one-time batch generator in `src/synth_data_creator/main.py` that populates a database and terminates.
- **Bulk Insert Engine**: Configured chunked bulk insertion supporting 150k+ records without memory overhead.
- **Count Validation checks**: Database count checks added to query table sizes prior to container termination, verifying exact dataset targets.
- **Automatic Driver Conversion**: Built driver verification to translate standard `postgresql://` connection schemes to async-compatible `postgresql+asyncpg://` schemes automatically.

### Changed
- **Web App Decommission**: Removed the FastAPI server execution, REST endpoints, uvicorn dependency, and always-on lifespan hooks at runtime.
- **Docker Compose Updates**: Configured `docker-compose.yml` to support standalone generator execution against pre-existing Postgres containers using Linux host gateway DNS mappings.

### Fixed
- **Hatchling Package Discovery**: Added `[tool.hatch.build.targets.wheel]` configuration to `pyproject.toml` to fix the packaging metadata build error inside the container.
- **Dependency Caching**: Structured the `Dockerfile` with dummy package creation steps to ensure Python dependencies are cached correctly during Docker builds.
- **Numpy Seed Casting**: Fixed type errors when loading seeds as strings from compose environment variables by explicitly casting them to integers.
