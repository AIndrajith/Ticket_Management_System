from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mysql.connector import Error

from app.database import get_db_connection


app = FastAPI(title="Campus Helpdesk Ticket Management System")

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(directory="app/templates")


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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Display the dashboard.

    Dashboard values:
    - Total tickets
    - Open tickets
    - Resolved tickets
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_tickets,
                SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END)
                    AS open_tickets,
                SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END)
                    AS resolved_tickets
            FROM tickets
            """
        )

        counts = cursor.fetchone()

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "total_tickets": counts["total_tickets"] or 0,
                "open_tickets": counts["open_tickets"] or 0,
                "resolved_tickets": counts["resolved_tickets"] or 0,
            },
        )

    except Error as error:
        print(f"Dashboard database error: {error}")

        return render_error(
            request,
            "Unable to load the dashboard.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.get("/tickets", response_class=HTMLResponse)
def ticket_list(request: Request):
    """Retrieve and display all support tickets."""

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
                category,
                title,
                priority,
                status,
                created_at
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
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


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
):
    """Validate and save a new support ticket."""

    requester_name = requester_name.strip()
    email = email.strip().lower()
    category = category.strip()
    title = title.strip()
    description = description.strip()
    priority = priority.strip()

    form_data = {
        "requester_name": requester_name,
        "email": email,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority,
    }

    validation_error = validate_ticket_form(
        requester_name=requester_name,
        email=email,
        category=category,
        title=title,
        description=description,
        priority=priority,
    )

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
                "Open",
            ),
        )

        connection.commit()

        ticket_id = cursor.lastrowid

        return RedirectResponse(
            url=f"/tickets/{ticket_id}",
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
                "form_data": form_data,
                "error": "Unable to save the ticket. Please try again.",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_details(
    request: Request,
    ticket_id: int,
):
    """Retrieve and display one selected ticket."""

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
            },
        )

    except Error as error:
        print(f"Ticket details database error: {error}")

        return render_error(
            request,
            "Unable to retrieve the selected ticket.",
        )

    finally:
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
) -> str | None:
    """Perform basic server-side ticket form validation."""

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