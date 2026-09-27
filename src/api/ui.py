"""Server-rendered UI (Phase 10) — Jinja2 templates + a small vanilla-JS
file (`src/api/static/app.js`), no separate frontend framework/build step
(`docs/architecture.md` § 15's frontend-framework `OPEN QUESTION`, resolved
here: the dev machine has too little free RAM for a Node/npm toolchain
alongside everything else this project already runs — Docker, Postgres,
the ML pipeline — and a second language/runtime buys nothing a prototype
needs; server-rendered HTML keeps this a single Python process).

Every route here calls the exact same functions `src/api/cases.py`'s JSON
endpoints call — `Depends(...)` defaults are simply overridden with real
values when called directly in Python, so there is one implementation of
"how to build a case view," not two (customer/analyst response shaping
included).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.engine import Engine

from src.api.cases import get_case, list_cases
from src.api.deps import Role, get_current_role, get_db_engine, require_reviewer_role
from src.api.schemas import AnalystCaseView

router = APIRouter(include_in_schema=False)
_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, role: Role = Depends(get_current_role)) -> HTMLResponse:
    return _templates.TemplateResponse(request, "home.html", {"role": role})


@router.get("/session/{new_role}")
def switch_session_role(new_role: str, response: Response) -> Response:
    """A plain link-driven role switch for the demo UI — the trusted-test-
    identity abstraction (`src/api/deps.py`), never real login. An
    unrecognized role falls back to the default rather than setting a junk
    cookie value."""
    from fastapi.responses import RedirectResponse

    valid = new_role if new_role in ("customer", "analyst", "supervisor") else "customer"
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.set_cookie("role", valid, httponly=False, samesite="lax")
    return redirect


@router.get("/customer/cases/{case_id}", response_class=HTMLResponse)
def customer_case_page(
    request: Request,
    case_id: str,
    role: Role = Depends(get_current_role),
    engine: Engine = Depends(get_db_engine),
) -> HTMLResponse:
    case = get_case(case_id, engine=engine, role="customer")
    return _templates.TemplateResponse(
        request, "customer_case.html", {"role": role, "case": case}
    )


@router.get("/analyst/cases", response_class=HTMLResponse)
def analyst_queue_page(
    request: Request,
    role: Role = Depends(require_reviewer_role),
    engine: Engine = Depends(get_db_engine),
) -> HTMLResponse:
    """`require_reviewer_role` (not `get_current_role`): a customer session
    hitting this URL directly gets a real 403 (`src/api/errors.py`), not the
    queue — enforced the same way as the JSON API, not just a hidden link
    (`.claude/rules/frontend.md`)."""
    cases = list_cases(engine=engine, _role=role)
    return _templates.TemplateResponse(
        request, "analyst_queue.html", {"role": role, "cases": cases}
    )


@router.get("/analyst/cases/{case_id}", response_class=HTMLResponse)
def analyst_case_page(
    request: Request,
    case_id: str,
    role: Role = Depends(require_reviewer_role),
    engine: Engine = Depends(get_db_engine),
) -> HTMLResponse:
    case = get_case(case_id, engine=engine, role=role)
    # require_reviewer_role guarantees role is analyst/supervisor here.
    assert isinstance(case, AnalystCaseView)
    return _templates.TemplateResponse(
        request, "analyst_case.html", {"role": role, "case": case}
    )
