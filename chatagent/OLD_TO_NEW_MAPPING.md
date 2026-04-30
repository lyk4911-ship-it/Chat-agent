# Old-to-New Structure Mapping

## Layered Architecture

- `domain/`
  - `domain/user.py`: user account password verification logic.
  - `domain/session.py`: session metadata value object.
- `application/`
  - `application/auth_service.py`: register/login use-cases.
  - `application/chat_service.py`: chat orchestration + ownership checks.
  - `application/session_service.py`: session list/create/history use-cases.
  - `application/monitor_service.py`: admin monitoring use-cases.
- `infrastructure/`
  - `infrastructure/user_repository.py`: `data/users.json` persistence.
  - `infrastructure/runtime.py`: wraps `ApplicationServices` and `ChatSessionRegistry`.
- `interfaces/http/`
  - `interfaces/http/app.py`: FastAPI app factory.
  - `interfaces/http/routes_*.py`: route modules by responsibility.
  - `interfaces/http/schemas.py`: request/response DTO models.

## API Mapping

- Old monolithic `/auth/*`, `/chat`, `/users/*`, `/sessions/*` endpoints are kept.
- Route implementation moved from `api_server.py` into `interfaces/http/routes_*.py`.
- `api_server.py` is now a thin entrypoint that only builds and serves the app.

## Legacy Core Integration

- Existing OOP engine remains reusable:
  - `application_services.py`
  - `chat_session.py`
  - `state_tracker.py`
  - `response_service.py`
  - `admin_monitor.py`
- New layers call into the existing engine through `infrastructure/runtime.py`.

