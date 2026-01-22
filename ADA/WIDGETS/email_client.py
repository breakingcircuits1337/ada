import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email(to_email, subject, body):
    """
    Sends an email using SMTP.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "Error: Email credentials not configured in .env (EMAIL_ADDRESS, EMAIL_PASSWORD)."

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, to_email, text)
        server.quit()
        return f"Email sent to {to_email} successfully."
    except Exception as e:
        return f"Error sending email: {str(e)}"

def read_emails(limit=5):
    """
    Reads the latest N emails from the inbox.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "Error: Email credentials not configured in .env."

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        
        latest_email_ids = email_ids[-limit:]
        
        results = []
        for e_id in reversed(latest_email_ids):
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = msg['subject']
                    from_ = msg['from']
                    # Simple body extraction (could be improved for HTML)
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    results.append(f"From: {from_}\nSubject: {subject}\nSnippet: {body[:100]}...\n---")
        
        mail.close()
        mail.logout()
        
        if not results:
            return "No emails found."
            
        return "\n".join(results)
    except Exception as e:
        return f"Error reading emails: {str(e)}"

if __name__ == "__main__":
    # Test (will fail without creds)
    print("Email Client Initialized.")
