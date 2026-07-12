from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Campus Helpdesk Ticket Management System"
)

# Mount static files for CSS styling (Developer 5)
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# Configure Jinja2 templates directory (Developer 4)
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    # This is the landing dashboard placeholder for Developer 2
    return templates.TemplateResponse("index.html", {"request": request})