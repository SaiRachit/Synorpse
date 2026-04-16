import smtplib
from dotenv import dotenv_values
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import base64
from groq import Groq
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
 
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
env_vars = dotenv_values(".env")

class ProfessionalEmailSender:
    def __init__(self, groq_api_key, credentials_file=r'Data/credentials.json'):
        """
        Initialize Professional Email Sender with OAuth2
        
        Args:
            groq_api_key: Your Groq API key
            credentials_file: Path to Google OAuth2 credentials JSON file
        """
        self.groq_client = Groq(api_key=groq_api_key)
        self.credentials_file = credentials_file
        self.gmail_service = None
        self._authenticate_gmail()
    
    def _authenticate_gmail(self):
        """Authenticate with Gmail using OAuth2"""
        creds = None
        
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.gmail_service = build('gmail', 'v1', credentials=creds)
    
    def generate_email_content(self, context, additional_instructions=""):
        """
        Generate professional email content using Groq AI
        
        Args:
            context: Brief description of what the email should be about
            additional_instructions: Any specific requirements
        
        Returns:
            dict: Contains 'subject' and 'body'
        """
        prompt = f"""Generate a professional email based on the following context:

Context: {context}

Additional Instructions: {additional_instructions}

The sender of this email is Sai Rachit Singh. Always sign off with this name.

Please provide:
1. A clear and professional subject line
2. A well-structured professional email body with proper greeting and closing, signed by Sai Rachit Singh

Format your response as:
SUBJECT: [subject line here]
BODY:
[email body here]
"""
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional email writing assistant. Write clear, concise, and professional emails suitable for business communication. Always use proper business email etiquette with appropriate greetings and professional sign-offs."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024
            )
            
            response = chat_completion.choices[0].message.content
            
            subject = ""
            body = ""
            
            lines = response.split('\n')
            capturing_body = False
            
            for line in lines:
                if line.startswith('SUBJECT:'):
                    subject = line.replace('SUBJECT:', '').strip()
                elif line.startswith('BODY:'):
                    capturing_body = True
                elif capturing_body:
                    body += line + '\n'
            
            return {
                'subject': subject,
                'body': body.strip()
            }
            
        except Exception as e:
            print(f"Error generating email content: {str(e)}")
            return None
    
    def create_message(self, to, subject, body, attachment_path=None):
        """Create email message"""
        message = MIMEMultipart()
        message['To'] = to
        message['Subject'] = subject
        
        message.attach(MIMEText(body, 'plain'))
        
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            filename = os.path.basename(attachment_path)
            part.add_header('Content-Disposition', f'attachment; filename= {filename}')
            message.attach(part)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}
    
    def send_email(self, recipient_email, subject, body, attachment_path=None):
        try:
            message = self.create_message(recipient_email, subject, body, attachment_path)
            
            sent_message = self.gmail_service.users().messages().send(
                userId='me', 
                body=message
            ).execute()
            
            return True
            
        except HttpError as error:
            print(f" Failed to send email: {error}")
            return False
    
    def resolve_attachment(self, context):
        """Try to find a file mentioned in the context"""
        try:
            from TemporalFileSearch import find_files_with_temporal_context
        except ImportError:
            return None

        # Simple extraction logic: check for "file", "document", "resume", "report"
        # and look for temporal keywords
        
        lower_context = context.lower()
        search_term = None
        temporal_key = None
        
        if "yesterday" in lower_context:
            temporal_key = "yesterday"
        elif "today" in lower_context:
            temporal_key = "today"
            
        # Extract search term (naive: remove common words)
        words = lower_context.split()
        keywords = [w for w in words if w not in ['send', 'email', 'file', 'document', 'to', 'me', 'the', 'my', 'attachment', 'check']]
        
        if keywords:
            search_term = " ".join(keywords)
            matches = find_files_with_temporal_context(search_term, temporal_key)
            if matches:
                return matches[0][0] # Return best match path
        
        return None

    def format_search_results_email(self, query, results):
        """Format search results into an email body"""
        html_body = f"<h2>Search Results for: {query}</h2><br>"
        html_body += "<ul>"
        
        for link in results:
            html_body += f"<li><a href='{link}'>{link}</a></li>"
            
        html_body += "</ul><br><p>Sent by Synorpse AI</p>"
        return html_body

    def compose_and_send(self, recipient_email, context, additional_instructions="", 
                        attachment_path=None, preview=True, search_results=None):
        """
        Generate professional email content with AI and send it
        """
        
        # Auto-resolve attachment from context if not provided
        if not attachment_path and ("file" in context.lower() or "document" in context.lower() or "resume" in context.lower()):
            found_path = self.resolve_attachment(context)
            if found_path:
                attachment_path = found_path
        
        if search_results:
             # If sharing search results, skip AI generation for body or use simpler template
             subject = f"Search Results: {context}"
             body = self.format_search_results_email(context, search_results)
             # Note: send_email currently expects plain text body for MIMEText, 
             # need to update create_message to handle HTML if we want links
             # For now, just list them in plain text
             body = f"Search Results for: {context}\n\n" + "\n".join(search_results)
             email_content = {'subject': subject, 'body': body}
        else:
            email_content = self.generate_email_content(context, additional_instructions)
        
        if not email_content:
            return False
        
        if preview:
            confirmation = input("Send this email? (yes/no): ").strip().lower()
            if confirmation not in ['yes', 'y']:
                return False
        
        return self.send_email(recipient_email, email_content['subject'], 
                              email_content['body'], attachment_path)

if __name__ == "__main__":
    GROQ_API_KEY = env_vars.get("GroqAPIKey")
    

    email_sender = ProfessionalEmailSender(GROQ_API_KEY)
    
    email_sender.compose_and_send(
        recipient_email="",
        context=""
    )
    
