from fastapi import FastAPI, Form, Request, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Keep your unified database architecture configuration
from app.database import Base, engine, get_db, Ticket

# Automatically generate database tables in MySQL if missing
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Helpdesk Ticket Management System")

# Restored the correct paths pointing inside the app directory
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


@app.get("/tickets", response_class=HTMLResponse)
def ticket_list(request: Request, db: Session = Depends(get_db)):
    """Retrieve and display all support tickets."""
    try:
        # Fetch tickets ordered by creation date descending
        tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
        return templates.TemplateResponse(
            request=request,
            name="ticket_list.html",
            context={"tickets": tickets},
        )
    except Exception as error:
        print(f"Ticket list database error: {error}")
        return render_error(request, "Unable to retrieve support tickets.")


@app.get("/tickets/new", response_class=HTMLResponse)
def show_new_ticket_form(request: Request):
    """Display the ticket submission form."""
    return templates.TemplateResponse(
        request=request,
        name="ticket_create.html",
        context={
            "categories": CATEGORIES,
            "priorities": PRIORITIES,
            "form_data": {},
            "error": None,
        },
    )


@app.post("/tickets/new", response_class=HTMLResponse)
def create_ticket(
    request: Request,
    requester_name: str = Form(...),
    email: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form("Medium"),
    db: Session = Depends(get_db),
):
    """Validate and save a new support ticket using SQLAlchemy ORM."""
    form_data = {
        "requester_name": requester_name.strip(),
        "email": email.strip().lower(),
        "category": category.strip(),
        "title": title.strip(),
        "description": description.strip(),
        "priority": priority.strip(),
    }

    validation_error = validate_ticket_form(**form_data)
    if validation_error:
        return templates.TemplateResponse(
            request=request,
            name="ticket_create.html",
            context={
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "form_data": form_data,
                "error": validation_error,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        new_ticket = Ticket(
            requester_name=form_data["requester_name"],
            email=form_data["email"],
            category=form_data["category"],
            title=form_data["title"],
            description=form_data["description"],
            priority=form_data["priority"],
            status="Open",
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        return RedirectResponse(
            url=f"/tickets/{new_ticket.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as error:
        print(f"Ticket creation database error: {error}")
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="ticket_create.html",
            context={
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "form_data": form_data,
                "error": "Unable to save the ticket. Please try again.",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_details(request: Request, ticket_id: int, db: Session = Depends(get_db)):
    """Retrieve and display one selected ticket."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket is None:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return templates.TemplateResponse(
            request=request,
            name="ticket_details.html",
            context={"ticket": ticket},
        )
    except Exception as error:
        print(f"Ticket details database error: {error}")
        return render_error(request, "Unable to retrieve the selected ticket.")