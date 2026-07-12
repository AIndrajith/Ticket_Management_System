from typing import Optional

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mysql.connector import Error

from app.database import get_db_connection


app = FastAPI(
    title="Campus Helpdesk Ticket Management System"
)

# Static files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


# Allowed form values
CATEGORIES = [
    "Technical",
    "Academic",
    "Finance",
    "Facilities",
    "Other",
]

PRIORITIES = [
    "Low",
    "Medium",
    "High",
]

STATUSES = [
    "Open",
    "In Progress",
    "Resolved",
]


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

def render_error(
    request: Request,
    message: str,
    status_code: int = 500,
):
    """Display a common error page."""

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "message": message,
        },
        status_code=status_code,
    )


def close_database(connection, cursor):
    """Safely close database cursor and connection."""

    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()


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

    if (
        "@" not in email
        or "." not in email.split("@")[-1]
    ):
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
def home(request: Request):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_tickets,
                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Open'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS open_tickets,
                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Resolved'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS resolved_tickets
            FROM tickets
            """
        )

        counts = cursor.fetchone()

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "total_tickets": counts["total_tickets"],
                "open_tickets": counts["open_tickets"],
                "resolved_tickets": counts["resolved_tickets"],
            },
        )

    except Error as error:
        print(f"Dashboard database error: {error}")

        return render_error(
            request,
            "Unable to load the dashboard.",
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 2. View all tickets
# GET /tickets
# -------------------------------------------------

@app.get("/tickets", response_class=HTMLResponse)
def view_all_tickets(request: Request):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
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
            ORDER BY created_at DESC
            """
        )

        tickets = cursor.fetchall()

        return templates.TemplateResponse(
            request=request,
            name="ticket_list.html",
            context={
                "tickets": tickets,
            },
        )

    except Error as error:
        print(f"Ticket list database error: {error}")

        return render_error(
            request,
            "Unable to retrieve support tickets.",
        )

    finally:
        close_database(connection, cursor)


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
):
    requester_name = requester_name.strip()
    email = email.strip().lower()
    category = category.strip()
    title = title.strip()
    description = description.strip()
    priority = priority.strip()
    ticket_status = ticket_status.strip()

    # New tickets must begin as Open
    ticket_status = "Open"

    form_data = {
        "requester_name": requester_name,
        "email": email,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority,
        "status": ticket_status,
    }

    validation_error = validate_ticket_form(
        requester_name=requester_name,
        email=email,
        category=category,
        title=title,
        description=description,
        priority=priority,
        ticket_status=ticket_status,
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

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO tickets (
                requester_name,
                email,
                category,
                title,
                description,
                priority,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                requester_name,
                email,
                category,
                title,
                description,
                priority,
                ticket_status,
            ),
        )

        connection.commit()

        new_ticket_id = cursor.lastrowid

        return RedirectResponse(
            url=f"/tickets/{new_ticket_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Error as error:
        print(f"Ticket creation database error: {error}")

        if connection is not None:
            connection.rollback()

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

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 5. View ticket details
# GET /tickets/{ticket_id}
# -------------------------------------------------

@app.get(
    "/tickets/{ticket_id}",
    response_class=HTMLResponse,
)
def view_ticket_details(
    request: Request,
    ticket_id: int,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
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
            WHERE id = %s
            """,
            (ticket_id,),
        )

        ticket = cursor.fetchone()

        if ticket is None:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return templates.TemplateResponse(
            request=request,
            name="ticket_details.html",
            context={
                "ticket": ticket,
                "statuses": STATUSES,
            },
        )

    except Error as error:
        print(f"Ticket details database error: {error}")

        return render_error(
            request,
            "Unable to retrieve the selected ticket.",
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 6. Display ticket edit form
# GET /tickets/{ticket_id}/edit
# -------------------------------------------------

@app.get(
    "/tickets/{ticket_id}/edit",
    response_class=HTMLResponse,
)
def show_edit_ticket_form(
    request: Request,
    ticket_id: int,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM tickets
            WHERE id = %s
            """,
            (ticket_id,),
        )

        ticket = cursor.fetchone()

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

    except Error as error:
        print(f"Edit form database error: {error}")

        return render_error(
            request,
            "Unable to load the ticket edit form.",
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 7. Update ticket details
# POST /tickets/{ticket_id}/edit
# -------------------------------------------------

@app.post(
    "/tickets/{ticket_id}/edit",
    response_class=HTMLResponse,
)
def update_ticket(
    request: Request,
    ticket_id: int,
    requester_name: str = Form(...),
    email: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form(...),
    ticket_status: str = Form(...),
):
    requester_name = requester_name.strip()
    email = email.strip().lower()
    category = category.strip()
    title = title.strip()
    description = description.strip()
    priority = priority.strip()
    ticket_status = ticket_status.strip()

    ticket_data = {
        "id": ticket_id,
        "requester_name": requester_name,
        "email": email,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority,
        "status": ticket_status,
    }

    validation_error = validate_ticket_form(
        requester_name=requester_name,
        email=email,
        category=category,
        title=title,
        description=description,
        priority=priority,
        ticket_status=ticket_status,
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
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE tickets
            SET
                requester_name = %s,
                email = %s,
                category = %s,
                title = %s,
                description = %s,
                priority = %s,
                status = %s
            WHERE id = %s
            """,
            (
                requester_name,
                email,
                category,
                title,
                description,
                priority,
                ticket_status,
                ticket_id,
            ),
        )

        if cursor.rowcount == 0:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        connection.commit()

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Error as error:
        print(f"Ticket update database error: {error}")

        if connection is not None:
            connection.rollback()

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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 8. Update only ticket status
# POST /tickets/{ticket_id}/status
# -------------------------------------------------

@app.post("/tickets/{ticket_id}/status")
def update_ticket_status(
    request: Request,
    ticket_id: int,
    ticket_status: str = Form(...),
):
    ticket_status = ticket_status.strip()

    if ticket_status not in STATUSES:
        return render_error(
            request,
            "Invalid ticket status.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE tickets
            SET status = %s
            WHERE id = %s
            """,
            (
                ticket_status,
                ticket_id,
            ),
        )

        if cursor.rowcount == 0:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        connection.commit()

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Error as error:
        print(f"Status update database error: {error}")

        if connection is not None:
            connection.rollback()

        return render_error(
            request,
            "Unable to update the ticket status.",
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 9. Display delete confirmation page
# GET /tickets/{ticket_id}/delete
# -------------------------------------------------

@app.get(
    "/tickets/{ticket_id}/delete",
    response_class=HTMLResponse,
)
def show_delete_confirmation(
    request: Request,
    ticket_id: int,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM tickets
            WHERE id = %s
            """,
            (ticket_id,),
        )

        ticket = cursor.fetchone()

        if ticket is None:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return templates.TemplateResponse(
            request=request,
            name="ticket_delete.html",
            context={
                "ticket": ticket,
            },
        )

    except Error as error:
        print(f"Delete confirmation database error: {error}")

        return render_error(
            request,
            "Unable to load the delete confirmation page.",
        )

    finally:
        close_database(connection, cursor)


# -------------------------------------------------
# 10. Delete ticket
# POST /tickets/{ticket_id}/delete
# -------------------------------------------------

@app.post("/tickets/{ticket_id}/delete")
def delete_ticket(
    request: Request,
    ticket_id: int,
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM tickets
            WHERE id = %s
            """,
            (ticket_id,),
        )

        if cursor.rowcount == 0:
            return render_error(
                request,
                "The requested ticket was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        connection.commit()

        return RedirectResponse(
            url="/tickets",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Error as error:
        print(f"Ticket deletion database error: {error}")

        if connection is not None:
            connection.rollback()

        return render_error(
            request,
            "Unable to delete the ticket.",
        )

    finally:
        close_database(connection, cursor)