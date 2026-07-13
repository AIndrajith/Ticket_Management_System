from typing import Optional
from fastapi import FastAPI, Form, Request, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Keep your clean database architecture imports
from app.database import Base, engine, get_db, Ticket

# Automatically generate database tables in MySQL if missing
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Helpdesk Ticket Management System")

# Static files path verification config
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

# Jinja2 templates location configuration
templates = Jinja2Templates(directory="app/templates")

# Allowed form values
CATEGORIES = ["Technical", "Academic", "Finance", "Facilities", "Other"]
PRIORITIES = ["Low", "Medium", "High"]
STATUSES = ["Open", "In Progress", "Resolved"]


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

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
        ticket_status: Optional[str] = None,
) -> Optional[str]:
    """Basic server-side form validation."""
    if not requester_name:
        return "Requester name is required."
    if len(requester_name) > 100:
        return "Requester name cannot exceed 100 characters."
    if not email:
        return "Email address is required."
    if len(email) > 150:
        return "Email address cannot exceed 150 characters."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address."
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
    if ticket_status is not None and ticket_status not in STATUSES:
        return "Select a valid ticket status."
    return None


# -------------------------------------------------
# 1. Home page and dashboard counts
# GET /
# -------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
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


# -------------------------------------------------
# 2. View all tickets
# GET /tickets
# -------------------------------------------------
@app.get("/tickets", response_class=HTMLResponse)
def view_all_tickets(request: Request, db: Session = Depends(get_db)):
    try:
        tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
        return templates.TemplateResponse(
            request=request,
            name="ticket_list.html",
            context={"tickets": tickets},
        )
    except Exception as error:
        print(f"Ticket list database error: {error}")
        return render_error(request, "Unable to retrieve support tickets.")


# -------------------------------------------------
# 3. Display new-ticket form
# GET /tickets/new
# -------------------------------------------------
@app.get("/tickets/new", response_class=HTMLResponse)
def show_new_ticket_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ticket_create.html",
        context={
            "categories": CATEGORIES,
            "priorities": PRIORITIES,
            "statuses": STATUSES,
            "form_data": {},
            "error": None,
        },
    )


# -------------------------------------------------
# 4. Create a new ticket
# POST /tickets/new
# -------------------------------------------------
@app.post("/tickets/new", response_class=HTMLResponse)
def create_ticket(
        request: Request,
        requester_name: str = Form(...),
        email: str = Form(...),
        category: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        priority: str = Form("Medium"),
        ticket_status: str = Form("Open"),
        db: Session = Depends(get_db)
):
    form_data = {
        "requester_name": requester_name.strip(),
        "email": email.strip().lower(),
        "category": category.strip(),
        "title": title.strip(),
        "description": description.strip(),
        "priority": priority.strip(),
        "status": "Open",  # New tickets default to Open
    }

    validation_error = validate_ticket_form(
        requester_name=form_data["requester_name"],
        email=form_data["email"],
        category=form_data["category"],
        title=form_data["title"],
        description=form_data["description"],
        priority=form_data["priority"],
        ticket_status=form_data["status"],
    )

    if validation_error:
        return templates.TemplateResponse(
            request=request,
            name="ticket_create.html",
            context={
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "statuses": STATUSES,
                "form_data": form_data,
                "error": validation_error,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        new_ticket = Ticket(**form_data)
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
                "statuses": STATUSES,
                "form_data": form_data,
                "error": "Unable to save the ticket.",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# -------------------------------------------------
# 5. View ticket details
# GET /tickets/{ticket_id}
# -------------------------------------------------
@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def view_ticket_details(request: Request, ticket_id: int, db: Session = Depends(get_db)):
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
            context={"ticket": ticket, "statuses": STATUSES},
        )
    except Exception as error:
        print(f"Ticket details database error: {error}")
        return render_error(request, "Unable to retrieve the selected ticket.")


# -------------------------------------------------
# 6. Display ticket edit form
# GET /tickets/{ticket_id}/edit
# -------------------------------------------------
@app.get("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def show_edit_ticket_form(request: Request, ticket_id: int, db: Session = Depends(get_db)):
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
            name="ticket_edit.html",
            context={
                "ticket": ticket,
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "statuses": STATUSES,
                "error": None,
            },
        )
    except Exception as error:
        print(f"Edit form database error: {error}")
        return render_error(request, "Unable to load the ticket edit form.")


# -------------------------------------------------
# 7. Update ticket details
# POST /tickets/{ticket_id}/edit
# -------------------------------------------------
@app.post("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def update_ticket(
        request: Request,
        ticket_id: int,
        requester_name: str = Form(...),
        email: str = Form(...),
        category: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        priority: str = Form(...),
        status: str = Form(...),
        db: Session = Depends(get_db)
):
    ticket_data = {
        "id": ticket_id,
        "requester_name": requester_name.strip(),
        "email": email.strip().lower(),
        "category": category.strip(),
        "title": title.strip(),
        "description": description.strip(),
        "priority": priority.strip(),
        "status": status.strip(),
    }

    validation_error = validate_ticket_form(
        requester_name=ticket_data["requester_name"],
        email=ticket_data["email"],
        category=ticket_data["category"],
        title=ticket_data["title"],
        description=ticket_data["description"],
        priority=ticket_data["priority"],
        ticket_status=ticket_data["status"],
    )

    if validation_error:
        return templates.TemplateResponse(
            request=request,
            name="ticket_edit.html",
            context={
                "ticket": ticket_data,
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "statuses": STATUSES,
                "error": validation_error,
            },
            status_code=400,
        )

    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=404,
            )

        # Apply updates securely
        ticket.requester_name = ticket_data["requester_name"]
        ticket.email = ticket_data["email"]
        ticket.category = ticket_data["category"]
        ticket.title = ticket_data["title"]
        ticket.description = ticket_data["description"]
        ticket.priority = ticket_data["priority"]
        ticket.status = ticket_data["status"]

        db.commit()

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=303,
        )
    except Exception as error:
        print(f"Ticket update database error: {error}")
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="ticket_edit.html",
            context={
                "ticket": ticket_data,
                "categories": CATEGORIES,
                "priorities": PRIORITIES,
                "statuses": STATUSES,
                "error": "Unable to update the ticket.",
            },
            status_code=500,
        )


# -------------------------------------------------
# 8. Update only ticket status
# POST /tickets/{ticket_id}/status
# -------------------------------------------------
@app.post("/tickets/{ticket_id}/status")
def update_ticket_status(
        request: Request,
        ticket_id: int,
        status: str = Form(...),
        db: Session = Depends(get_db)
):
    status_clean = status.strip()

    if status_clean not in STATUSES:
        return render_error(
            request,
            "Invalid ticket status.",
            status_code=400,
        )

    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=404,
            )

        ticket.status = status_clean
        db.commit()

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=303,
        )
    except Exception as error:
        print(f"Status update database error: {error}")
        db.rollback()
        return render_error(request, "Unable to update the ticket status.")


# -------------------------------------------------
# 9. Display delete confirmation page
# GET /tickets/{ticket_id}/delete
# -------------------------------------------------
@app.get("/tickets/{ticket_id}/delete", response_class=HTMLResponse)
def show_delete_confirmation(request: Request, ticket_id: int, db: Session = Depends(get_db)):
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
            name="ticket_delete.html",
            context={"ticket": ticket},
        )
    except Exception as error:
        print(f"Delete confirmation database error: {error}")
        return render_error(request, "Unable to load the delete confirmation page.")


# -------------------------------------------------
# 10. Delete ticket
# POST /tickets/{ticket_id}/delete
# -------------------------------------------------
@app.post("/tickets/{ticket_id}/delete")
def delete_ticket(request: Request, ticket_id: int, db: Session = Depends(get_db)):
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        db.delete(ticket)
        db.commit()

        return RedirectResponse(
            url="/tickets",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as error:
        print(f"Ticket deletion database error: {error}")
        db.rollback()
        return render_error(request, "Unable to delete the ticket.")