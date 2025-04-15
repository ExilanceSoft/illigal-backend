import os
import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException,Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, date
import mysql.connector
from mysql.connector import Error
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import uuid

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Devita@#2001',
    'database': 'illegal_dumping_db'
}

# Email configuration
EMAIL_SENDER = "exilancesoft@gmail.com"
EMAIL_PASSWORD = "dcuh dlsr njgr llqd"

# Models
class ReportBase(BaseModel):
    location: str
    city: str
    state: str
    waste_type: List[str]
    size: str
    date: str
    time: str
    description: Optional[str] = None
    video_link: Optional[str] = None
    anonymous: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class ReportResponse(ReportBase):
    id: int
    created_at: datetime
    status: str
    photos: List[str] = []

class MemberBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    membership_level: str = "basic"
    volunteer_interest: bool = False
    newsletter_consent: bool = True

class MemberResponse(MemberBase):
    id: int
    created_at: datetime

class EventBase(BaseModel):
    title: str
    description: str
    location: str
    date: str
    time: str
    organizer: str
    contact: str
    requirements: Optional[str] = None

class EventResponse(EventBase):
    id: int
    participants: int
    status: str
    image: Optional[str] = None
    created_at: datetime

# Database connection helper
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

# Initialize database tables
def init_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Create reports table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            location VARCHAR(255) NOT NULL,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(100) NOT NULL,
            waste_type JSON NOT NULL,
            size VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            time VARCHAR(20) NOT NULL,
            description TEXT,
            video_link VARCHAR(255),
            anonymous BOOLEAN DEFAULT FALSE,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(100),
            phone VARCHAR(20),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create report_photos table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_photos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            report_id INT NOT NULL,
            photo_path VARCHAR(255) NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
        )
        """)

        # Create members table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            phone VARCHAR(20),
            street VARCHAR(255),
            city VARCHAR(100),
            state VARCHAR(100),
            zip_code VARCHAR(20),
            membership_level VARCHAR(50) DEFAULT 'basic',
            volunteer_interest BOOLEAN DEFAULT FALSE,
            newsletter_consent BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create events table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            location VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            time VARCHAR(50) NOT NULL,
            image VARCHAR(255),
            participants INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'upcoming',
            organizer VARCHAR(255) NOT NULL,
            contact VARCHAR(255) NOT NULL,
            requirements TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        connection.commit()
        print("Database tables initialized successfully")
    except Error as e:
        print(f"Error initializing database: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Initialize database on startup
init_db()

# Helper functions
def save_uploaded_file(file: UploadFile) -> str:
    try:
        # Generate unique filename
        file_ext = file.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())
        
        return filename
    except Exception as e:
        print(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail="Error saving file")

def send_email(to_email: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Error sending email: {e}")

# API Endpoints

@app.patch("/reports/{report_id}/status/")
async def update_report_status(
    report_id: int,
    status_update: dict = Body(...)
):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        new_status = status_update.get('status')
        if not new_status:
            raise HTTPException(status_code=400, detail="Status is required")

        valid_statuses = ['pending', 'in progress', 'completed', 'rejected']
        if new_status.lower() not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status value")

        query = "UPDATE reports SET status = %s WHERE id = %s"
        cursor.execute(query, (new_status.lower(), report_id))
        connection.commit()

        return {"message": "Status updated successfully"}
    except Error as e:
        connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
@app.post("/reports/", response_model=ReportResponse)
async def create_report(
    location: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    waste_type: str = Form(...),
    size: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    description: str = Form(None),
    video_link: str = Form(None),
    anonymous: bool = Form(False),
    first_name: str = Form(None),
    last_name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    files: List[UploadFile] = File([])
):
    try:
        # Validate and parse date
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD"
            )

        # Parse waste_type - handle both JSON array and comma-separated string
        try:
            waste_types = json.loads(waste_type)
            if not isinstance(waste_types, list):
                waste_types = [waste_types]
        except json.JSONDecodeError:
            waste_types = [wt.strip() for wt in waste_type.split(",") if wt.strip()]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Insert report
        query = """
        INSERT INTO reports (
            location, city, state, waste_type, size, date, time, description,
            video_link, anonymous, first_name, last_name, email, phone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            location, city, state, json.dumps(waste_types), size, date_obj, time,
            description, video_link, anonymous, first_name, last_name, email, phone
        )
        cursor.execute(query, values)
        report_id = cursor.lastrowid

        # Save photos
        photo_paths = []
        for file in files:
            if file.content_type.startswith('image/'):
                filename = save_uploaded_file(file)
                photo_paths.append(filename)
                
                cursor.execute(
                    "INSERT INTO report_photos (report_id, photo_path) VALUES (%s, %s)",
                    (report_id, filename)
                )

        connection.commit()

        # Get the created report
        cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        
        report['date'] = report['date'].strftime('%Y-%m-%d')
        report['waste_type'] = json.loads(report['waste_type'])
        report['photos'] = photo_paths

        # Send confirmation email
        if not anonymous and email:
            subject = "Your Illegal Dumping Report Has Been Received"
            body = f"""Hello {first_name or 'there'},

Thank you for reporting illegal dumping in {city}, {state}. Your report has been received and assigned case ID #{report_id}.

Location: {location}
Date Observed: {date}
Type of Waste: {', '.join(waste_types)}
Size: {size}

We will review your report and take appropriate action.

Thank you for helping keep our community clean!

Sincerely,
The Illegal Dumping Prevention Team
"""
            send_email(email, subject, body)

        return report
    except Error as e:
        connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating report: {e}")
        raise HTTPException(status_code=500, detail="Error creating report")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

@app.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        cursor.execute("SELECT photo_path FROM report_photos WHERE report_id = %s", (report_id,))
        photos = [row['photo_path'] for row in cursor.fetchall()]

        report['date'] = report['date'].strftime('%Y-%m-%d')
        report['waste_type'] = json.loads(report['waste_type'])
        report['photos'] = photos

        return report
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.post("/members/", response_model=MemberResponse)
async def create_member(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    street: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    zip_code: str = Form(None),
    membership_level: str = Form("basic"),
    volunteer_interest: bool = Form(False),
    newsletter_consent: bool = Form(True)
):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        INSERT INTO members (
            first_name, last_name, email, phone, street, city, state, zip_code,
            membership_level, volunteer_interest, newsletter_consent
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            first_name, last_name, email, phone, street, city, state, zip_code,
            membership_level, volunteer_interest, newsletter_consent
        )
        cursor.execute(query, values)
        member_id = cursor.lastrowid

        connection.commit()

        cursor.execute("SELECT * FROM members WHERE id = %s", (member_id,))
        member_data = cursor.fetchone()

        # Send welcome email
        subject = "Welcome to Our Community!"
        body = f"""Hello {first_name},

Thank you for joining our community as a {membership_level} member. 

Together we can make a difference in preventing illegal dumping.

"""
        if membership_level != "basic":
            body += f"\nAs a {membership_level} member, you'll receive additional benefits.\n"

        body += """
Sincerely,
The Illegal Dumping Prevention Team
"""
        send_email(email, subject, body)

        return member_data
    except Error as e:
        connection.rollback()
        if e.errno == 1062:
            raise HTTPException(status_code=400, detail="Email already registered")
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.get("/members/{member_id}", response_model=MemberResponse)
async def get_member(member_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT * FROM members WHERE id = %s", (member_id,))
        member = cursor.fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return member
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.post("/events/", response_model=EventResponse)
async def create_event(
    title: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    organizer: str = Form(...),
    contact: str = Form(...),
    requirements: str = Form(None),
    file: UploadFile = File(None)
):
    try:
        # Validate date
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD"
            )

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Save image if provided
        image_path = None
        if file and file.content_type.startswith('image/'):
            image_path = save_uploaded_file(file)

        # Insert event
        query = """
        INSERT INTO events (
            title, description, location, date, time, image,
            organizer, contact, requirements
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            title, description, location, date_obj, time, image_path,
            organizer, contact, requirements
        )
        cursor.execute(query, values)
        event_id = cursor.lastrowid

        connection.commit()

        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        event['date'] = event['date'].strftime('%Y-%m-%d')

        return event
    except Error as e:
        connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail="Error creating event")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.get("/events/", response_model=List[EventResponse])
async def get_events(status: Optional[str] = None):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if status:
            cursor.execute("SELECT * FROM events WHERE status = %s ORDER BY date", (status,))
        else:
            cursor.execute("SELECT * FROM events ORDER BY date")

        events = cursor.fetchall()
        for event in events:
            event['date'] = event['date'].strftime('%Y-%m-%d')

        return events
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.post("/events/{event_id}/join")
async def join_event(event_id: int, member_id: Optional[int] = None, email: Optional[str] = None):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("UPDATE events SET participants = participants + 1 WHERE id = %s", (event_id,))
        
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        connection.commit()

        if email:
            subject = f"Event Registration Confirmation: {event['title']}"
            body = f"""Thank you for registering for:

{event['title']}
Date: {event['date'].strftime('%Y-%m-%d')}
Time: {event['time']}
Location: {event['location']}

Details:
{event['description']}
"""
            if event['requirements']:
                body += f"\nRequirements: {event['requirements']}\n"

            body += "\nWe look forward to seeing you there!"
            send_email(email, subject, body)

        return {"message": "Successfully joined event", "event_id": event_id}
    except Error as e:
        connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
@app.get("/reports/")
async def get_all_reports(
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None
):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Base query
        query = "SELECT * FROM reports"
        count_query = "SELECT COUNT(*) as total FROM reports"
        conditions = []
        params = []

        # Add filters if provided
        if status:
            conditions.append("status = %s")
            params.append(status)
        if state:
            conditions.append("state = %s")
            params.append(state)
        if city:
            conditions.append("city = %s")
            params.append(city)

        # Add WHERE clause if there are conditions
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
            query += where_clause
            count_query += where_clause

        # Add pagination
        offset = (page - 1) * limit
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # Get total count
        cursor.execute(count_query, params[:-2])  # Exclude limit/offset params
        total = cursor.fetchone()['total']

        # Get paginated results
        cursor.execute(query, params)
        reports = cursor.fetchall()

        # Convert waste_type from JSON string to list
        for report in reports:
            report['waste_type'] = json.loads(report['waste_type'])
            
            # Get photos for each report
            cursor.execute(
                "SELECT photo_path FROM report_photos WHERE report_id = %s",
                (report['id'],)  # Fixed: Added missing closing parenthesis
            )
            report['photos'] = [row['photo_path'] for row in cursor.fetchall()]

        return {
            "data": reports,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        }
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
@app.get("/reports/stats/")
async def get_report_stats():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get total reports count
        cursor.execute("SELECT COUNT(*) as total FROM reports")
        total_reports = cursor.fetchone()['total']

        # Get pending reports count
        cursor.execute("SELECT COUNT(*) as pending FROM reports WHERE status = 'pending'")
        pending_reports = cursor.fetchone()['pending']

        # Get active volunteers count (members with volunteer interest)
        cursor.execute("SELECT COUNT(*) as volunteers FROM members WHERE volunteer_interest = TRUE")
        active_volunteers = cursor.fetchone()['volunteers']

        return {
            "pendingReports": pending_reports,
            "totalReports": total_reports,
            "activeVolunteers": active_volunteers
        }
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Illegal Dumping Reporting System API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)