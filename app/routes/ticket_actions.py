from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


ALLOWED_CATEGORIES = {
    "Technical",
    "Academic",
    "Finance",
    "Facilities",
    "Other",
}

ALLOWED_PRIORITIES = {
    "Low",
    "Medium",
    "High",
}

ALLOWED_STATUSES = {
    "Open",
    "In Progress",
    "Resolved",
}


def get_ticket(ticket_id: int) -> Optional[dict]:
    """
    Retrieve one ticket from the database.

    Returns:
        A dictionary containing the ticket, or None if it does not exist.
    """
    query = text(
        """
        SELECT
            id,
            requester_name,
            email,
            category,
            title,
            description,
            priority,
            status,
            created_at,
            updated_at
        FROM tickets
        WHERE id = :ticket_id
        """
    )

    with engine.connect() as connection:
        result = connection.execute(
            query,
            {"ticket_id": ticket_id}
        )

        row = result.mappings().first()

        if row is None:
            return None

        return dict(row)


def show_error(
    request: Request,
    message: str,
    status_code: int = 400
) -> HTMLResponse:
    """
    Display the common error page.
    """
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "message": message
        },
        status_code=status_code
    )


def validate_ticket_data(
    requester_name: str,
    email: str,
    category: str,
    title: str,
    description: str,
    priority: str,
    status: str
) -> Optional[str]:
    """
    Validate the ticket edit form.

    Returns:
        None when valid, otherwise an error message.
    """
    if not requester_name.strip():
        return "Requester name is required."

    if not email.strip():
        return "Email address is required."

    if "@" not in email or "." not in email:
        return "Enter a valid email address."

    if not title.strip():
        return "Ticket title is required."

    if not description.strip():
        return "Ticket description is required."

    if category not in ALLOWED_CATEGORIES:
        return "Invalid ticket category."

    if priority not in ALLOWED_PRIORITIES:
        return "Invalid priority level."

    if status not in ALLOWED_STATUSES:
        return "Invalid ticket status."

    return None


# ---------------------------------------------------------
# 1. DISPLAY THE EDIT TICKET FORM
# GET /tickets/{ticket_id}/edit
# ---------------------------------------------------------

@router.get(
    "/tickets/{ticket_id}/edit",
    response_class=HTMLResponse
)
def show_edit_ticket_form(
    request: Request,
    ticket_id: int
):
    try:
        ticket = get_ticket(ticket_id)

        if ticket is None:
            return show_error(
                request=request,
                message="Ticket not found.",
                status_code=404
            )

        return templates.TemplateResponse(
            request=request,
            name="ticket_edit.html",
            context={
                "ticket": ticket,
                "categories": sorted(ALLOWED_CATEGORIES),
                "priorities": ["Low", "Medium", "High"],
                "statuses": ["Open", "In Progress", "Resolved"]
            }
        )

    except SQLAlchemyError as error:
        print(f"Database error while loading ticket: {error}")

        return show_error(
            request=request,
            message="A database error occurred while loading the ticket.",
            status_code=500
        )


# ---------------------------------------------------------
# 2. UPDATE ALL TICKET DETAILS
# POST /tickets/{ticket_id}/edit
# ---------------------------------------------------------

@router.post("/tickets/{ticket_id}/edit")
def update_ticket(
    request: Request,
    ticket_id: int,
    requester_name: str = Form(...),
    email: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form(...),
    status: str = Form(...)
):
    requester_name = requester_name.strip()
    email = email.strip()
    title = title.strip()
    description = description.strip()

    validation_error = validate_ticket_data(
        requester_name=requester_name,
        email=email,
        category=category,
        title=title,
        description=description,
        priority=priority,
        status=status
    )

    if validation_error:
        return show_error(
            request=request,
            message=validation_error,
            status_code=400
        )

    try:
        existing_ticket = get_ticket(ticket_id)

        if existing_ticket is None:
            return show_error(
                request=request,
                message="Ticket not found.",
                status_code=404
            )

        update_query = text(
            """
            UPDATE tickets
            SET
                requester_name = :requester_name,
                email = :email,
                category = :category,
                title = :title,
                description = :description,
                priority = :priority,
                status = :status
            WHERE id = :ticket_id
            """
        )

        with engine.begin() as connection:
            connection.execute(
                update_query,
                {
                    "requester_name": requester_name,
                    "email": email,
                    "category": category,
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "status": status,
                    "ticket_id": ticket_id
                }
            )

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=303
        )

    except SQLAlchemyError as error:
        print(f"Database error while updating ticket: {error}")

        return show_error(
            request=request,
            message="A database error occurred while updating the ticket.",
            status_code=500
        )


# ---------------------------------------------------------
# 3. UPDATE ONLY THE TICKET STATUS
# POST /tickets/{ticket_id}/status
# ---------------------------------------------------------

@router.post("/tickets/{ticket_id}/status")
def update_ticket_status(
    request: Request,
    ticket_id: int,
    status: str = Form(...)
):
    if status not in ALLOWED_STATUSES:
        return show_error(
            request=request,
            message="Invalid ticket status.",
            status_code=400
        )

    try:
        existing_ticket = get_ticket(ticket_id)

        if existing_ticket is None:
            return show_error(
                request=request,
                message="Ticket not found.",
                status_code=404
            )

        update_query = text(
            """
            UPDATE tickets
            SET status = :status
            WHERE id = :ticket_id
            """
        )

        with engine.begin() as connection:
            connection.execute(
                update_query,
                {
                    "status": status,
                    "ticket_id": ticket_id
                }
            )

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=303
        )

    except SQLAlchemyError as error:
        print(f"Database error while updating status: {error}")

        return show_error(
            request=request,
            message="A database error occurred while updating the status.",
            status_code=500
        )


# ---------------------------------------------------------
# 4. DISPLAY DELETE CONFIRMATION
# GET /tickets/{ticket_id}/delete
# ---------------------------------------------------------

@router.get(
    "/tickets/{ticket_id}/delete",
    response_class=HTMLResponse
)
def show_delete_confirmation(
    request: Request,
    ticket_id: int
):
    try:
        ticket = get_ticket(ticket_id)

        if ticket is None:
            return show_error(
                request=request,
                message="Ticket not found.",
                status_code=404
            )

        return templates.TemplateResponse(
            request=request,
            name="ticket_delete.html",
            context={
                "ticket": ticket
            }
        )

    except SQLAlchemyError as error:
        print(f"Database error while loading delete page: {error}")

        return show_error(
            request=request,
            message="A database error occurred while loading the ticket.",
            status_code=500
        )


# ---------------------------------------------------------
# 5. DELETE THE TICKET
# POST /tickets/{ticket_id}/delete
# ---------------------------------------------------------

@router.post("/tickets/{ticket_id}/delete")
def delete_ticket(
    request: Request,
    ticket_id: int
):
    try:
        existing_ticket = get_ticket(ticket_id)

        if existing_ticket is None:
            return show_error(
                request=request,
                message="Ticket not found.",
                status_code=404
            )

        delete_query = text(
            """
            DELETE FROM tickets
            WHERE id = :ticket_id
            """
        )

        with engine.begin() as connection:
            connection.execute(
                delete_query,
                {"ticket_id": ticket_id}
            )

        return RedirectResponse(
            url="/tickets",
            status_code=303
        )

    except SQLAlchemyError as error:
        print(f"Database error while deleting ticket: {error}")

        return show_error(
            request=request,
            message="A database error occurred while deleting the ticket.",
            status_code=500
        )