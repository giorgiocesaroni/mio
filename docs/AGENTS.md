# Mio

The monorepo of Mio, the AI nutritionist. Additional details can be found at `docs/README.md`.

## Repository Structure

| Directory   | Notes                                   | Core Technologies  |
| ----------- | --------------------------------------- | ------------------ |
| `frontend/` | The frontend of the application.        | Next.js            |
| `backend/`  | The backend of the application.         | Python             |
| `docs/`     | The documentation of the project.       |                    |
| `database/` | Database schema, views, and migrations. | Postgres, Supabase |

## `backend/`

### Folder Structure

| Directory   | Notes                           | Core Technologies |
| ----------- | ------------------------------- | ----------------- |
| `adapters/` | The platform-specific adapters. | Telegram          |
| `agent/`    | The agent's core logic.         | Gemini API        |
| `api/`      | The API of the application.     | FastAPI           |

### Module Structure

A typical module may contain the following files, along with module-specific files that don't fit any of these definitions.

| File            | Notes                                   |
| --------------- | --------------------------------------- |
| `service.py`    | The entry point of the module.          |
| `models.py`     | The Pydantic models of the module.      |
| `logic.py`      | The testable, pure logic of the module. |
| `repository.py` | The repository functions of the module. |
| `utils.py`      | The shared utilities of the module.     |

## `frontend/`

### Folder Structure

The folder structure follows a typical Next.js application (using App Router).

### Database and Backend Interactions

The `repository/` folder contains:

1. `supabase/`: queries and types for the database, read-only. `types.ts` is an auto-generated file using the Supabase CLI.
2. `backend/`: queries and types for the backend.

## Development Workflow

The development of a feature typically follows:

1. Start with the `backend/` code: models, repository, service, API, and whatever else is needed.
2. Move onto the `frontend/` code: models, repository, and UI components.
