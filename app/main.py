from fastapi import FastAPI, Form, Request, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Core setup architecture and shared assets
from app.database import Base, engine, get_db, Ticket

# Bring in Developer 3's new modular router configuration block
from app.routes.ticket_actions import router as ticket_actions_router

# Automatically generate database tables in MySQL if missing
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Helpdesk Ticket Management System")

# Correct paths pointing inside the app directory
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(directory="app/templates")

# Constants for Validation
CATEGORIES = ["Technical", "Academic", "Finance", "Facilities", "Other"]
PRIORITIES = ["Low", "Medium", "High"]


def render_error(request: Request, message: str, status_code: int = 500):
    """Display a common error page."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"message": message},
        status_code=status_code,
    )


def validate_ticket_form(
    requester_name: str,
    email: str,
    category: str,
    title: str,
    description: str,
    priority: str,
) -> str | None:
    """Perform server-side ticket form validation."""
    if not requester_name:
        return "Requester name is required."
    if len(requester_name) > 100:
        return "Requester name cannot exceed 100 characters."
    if not email:
        return "Email address is required."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address."
    if len(email) > 150:
        return "Email address cannot exceed 150 characters."
    if category not in CATEGORIES:
        return "Select a valid issue category."
    if not title:
        return "Ticket title is required."
    if len(title) > 150:
        return "Ticket title cannot exceed 150 characters."
    if not description:
        return "Issue description is required."
    if priority not in PRIORITIES:
        return "Select a valid priority level."
    return None


# -------------------------------------------------------------
# Core Dashboard Route (Kept at root level)
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    """Display the dashboard with total, open, and resolved counts."""
    try:
        total_tickets = db.query(Ticket).count()
        open_tickets = db.query(Ticket).filter(Ticket.status == "Open").count()
        resolved_tickets = db.query(Ticket).filter(Ticket.status == "Resolved").count()

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "resolved_tickets": resolved_tickets,
            },
        )
    except Exception as error:
        print(f"Dashboard database error: {error}")
        return render_error(request, "Unable to load the dashboard.")


# -------------------------------------------------------------
# Include Team Sub-Routers
# -------------------------------------------------------------
# This registers all /tickets CRUD endpoints managed by Dev 2 & 3
app.include_router(ticket_actions_router)