from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

from config import DATABASE_URI

Base = declarative_base()

class Email(Base):
    __tablename__ = 'emails'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, unique=True) # TODO: maybe index=True though it is already unique
    thread_id = Column(String, nullable=False, index=True)
    from_address = Column(String, nullable=False)
    to_addresses = Column(Text) # Store as JSON string
    cc_addresses = Column(Text, nullable=True) # Store as JSON string
    bcc_addresses = Column(Text, nullable=True) # Store as JSON string
    subject = Column(Text)
    body_plain = Column(Text)
    body_html = Column(Text)
    received_datetime = Column(DateTime, nullable=False, index=True)
    snippet = Column(Text, nullable=True)
    labels = Column(Text) # Store as JSON string
    # is_read = Column(Integer, default=0)  # 0 for unread, 1 for read
    # is_starred = Column(Integer, default=0)  # 0 for not starred, 1 for starred
    raw_headers = Column(Text) # Storing as JSON string of all headers

    __table_args__ = (
        UniqueConstraint('message_id', name='uq_message_id'),
        Index('idx_received_datetime', 'received_datetime'),
        Index('idx_from_address', 'from_address'),
        Index('idx_subject', 'subject')
        )
    
    def __repr__(self):
        return f"<Email(message_id='{self.message_id}', subject='{self.subject}', from='{self.from_address}')>"

engine = create_engine(DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create the database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created (if they didn't exist).")

def store_email(session, email_data):
    """
    Stores a single email in the database.
    email_data is a dictionary matching the Email model fields.
    """
    # Ensure date is a datetime object
    if isinstance(email_data.get('received_datetime'), str):
        try:
            # Attempt to parse ISO format, adjust if Gmail provides a different one
            email_data['received_datetime'] = datetime.fromisoformat(email_data['received_datetime'].replace('Z', '+00:00'))
        except ValueError:
             # Fallback for RFC 2822 format (common in email headers)
            try:
                from email.utils import parsedate_to_datetime
                email_data['received_datetime'] = parsedate_to_datetime(email_data['received_datetime'])
            except Exception as e:
                print(f"Could not parse date string: {email_data.get('received_datetime')}. Error: {e}")
                # Set to now or skip, depending on requirements
                email_data['received_datetime'] = datetime.utcnow()
        
    # Convert lists to JSON strings
    for key in ['to_addresses', 'cc_addresses', 'bcc_addresses', 'labels', 'raw_headers']:
        if key in email_data and isinstance(email_data[key], list):
            email_data[key] = json.dumps(email_data[key])

    email = Email(**email_data)
    
    try:
        session.add(email)
        session.commit()
        print(f"Stored email: {email.message_id}")
        return email
    except IntegrityError:
        session.rollback()
        print(f"Email with message_id {email_data['message_id']} already exists.")
        return None
    except Exception as e:
        session.rollback()
        print(f"Error storing email {email_data.get('message_id', 'N/A')}: {e}")
        return None


def get_all_emails(session):
    """Retrieves all emails from the database."""
    return session.query(Email).all()


def get_emails_by_criteria(session, **kwargs):
    """
    Retrieves emails based on specific criteria.
    Example: get_emails_by_criteria(session, from_address="user@example.com")
    """
    return session.query(Email).filter_by(**kwargs).all()

if __name__ == '__main__':
    create_tables()
    # Example usage:
    db_session = SessionLocal()
    # test_email_data = {
    # 'message_id': 'test_msg_002',
    # 'thread_id': 'thread_001',
    # 'from_address': 'sender2@example.com',
    # 'to_addresses': ['receiver@example.com'],
    # 'subject': 'Another Test Email',
    # 'body_plain': 'This is the plain text body of another test email.',
    # 'snippet': 'Another test email snippet',
    # 'received_datetime': datetime.utcnow().isoformat(),
    #     'labels': ['INBOX', 'UNREAD']
    # }
    # store_email(db_session, test_email_data)
    # all_emails = get_all_emails(db_session)
    # all_emails = get_emails_by_criteria(db_session, from_address="user@example.com", to_addresses='["user@example.com"]')
    # for email in all_emails:
    #     print(email)
    # db_session.close()
