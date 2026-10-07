import os
import json
import hmac
import hashlib
import time
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

app = FastAPI()

# Configuration from environment variables
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1CXANEZxW4UMzrjZQ7xliekchNCk3XTWZa-qQrWZeItc")

# Parse Google service account
try:
    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
except:
    service_account_info = {}

# Slack client
slack_client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
)

def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature"""
    if abs(time.time() - int(timestamp)) > 300:
        return False
    
    sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

def get_sheets_service():
    """Get Google Sheets API service"""
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials)

async def append_to_sheet(data: dict):
    """Append submission to Google Sheet"""
    try:
        service = get_sheets_service()
        
        row = [
            data.get("submission_id", ""),
            datetime.now().isoformat(),
            data.get("requester_name", ""),
            data.get("backup_coordinator", ""),
            data.get("start_date", ""),
            data.get("end_date", ""),
            data.get("roles", ""),
            data.get("handover_link", ""),
            data.get("additional_docs_note", ""),
            data.get("additional_docs_links", ""),
            data.get("briefed", ""),
            data.get("remarks", ""),
            data.get("access_confirm", ""),
            data.get("ooo_calendar", ""),
            data.get("ooo_slack", ""),
            data.get("ooo_email", ""),
            data.get("slack_user_id", ""),
        ]
        
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="SlackSubmissions!A:Q",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        
        return True
    except Exception as e:
        print(f"Error appending to sheet: {e}")
        return False

@app.post("/slack/commands")
async def handle_command(request: Request):
    """Handle /ooo-handover slash command"""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Request-Signature", "")
    
    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    data = await request.form()
    user_id = data.get("user_id", "")
    trigger_id = data.get("trigger_id", "")
    
    # Show modal form
    modal_payload = {
        "type": "modal",
        "callback_id": "ooo_handover_submission",
        "title": {"type": "plain_text", "text": "OOO Handover Request"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "blocks": [
            {
                "type": "input",
                "block_id": "requester_block",
                "label": {"type": "plain_text", "text": "Your Name"},
                "element": {"type": "plain_text_input", "action_id": "requester_input"}
            },
            {
                "type": "input",
                "block_id": "backup_block",
                "label": {"type": "plain_text", "text": "Backup Coordinator"},
                "element": {"type": "plain_text_input", "action_id": "backup_input"}
            },
            {
                "type": "input",
                "block_id": "start_date_block",
                "label": {"type": "plain_text", "text": "Start Date"},
                "element": {"type": "datepicker", "action_id": "start_date_input"}
            },
            {
                "type": "input",
                "block_id": "end_date_block",
                "label": {"type": "plain_text", "text": "End Date"},
                "element": {"type": "datepicker", "action_id": "end_date_input"}
            },
            {
                "type": "input",
                "block_id": "roles_block",
                "label": {"type": "plain_text", "text": "Roles/Requisitions"},
                "element": {"type": "plain_text_input", "action_id": "roles_input", "multiline": True}
            },
            {
                "type": "input",
                "block_id": "handover_link_block",
                "label": {"type": "plain_text", "text": "Handover Document Link"},
                "element": {"type": "plain_text_input", "action_id": "handover_link_input"}
            },
            {
                "type": "input",
                "block_id": "remarks_block",
                "label": {"type": "plain_text", "text": "Remarks (Optional)"},
                "element": {"type": "plain_text_input", "action_id": "remarks_input", "multiline": True},
                "optional": True
            }
        ]
    }
    
    await slack_client.post(
        "https://slack.com/api/views.open",
        json={"trigger_id": trigger_id, "view": modal_payload}
    )
    
    return JSONResponse({"status": "ok"})

@app.post("/slack/interactivity")
async def handle_interactivity(request: Request):
    """Handle modal submissions and button clicks"""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Request-Signature", "")
    
    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = json.loads(body.decode())
    
    if payload.get("type") == "view_submission":
        # Handle modal submission
        values = payload["view"]["state"]["values"]
        
        submission_data = {
            "submission_id": payload["user"]["id"] + "_" + str(int(time.time())),
            "requester_name": values["requester_block"]["requester_input"]["value"],
            "backup_coordinator": values["backup_block"]["backup_input"]["value"],
            "start_date": values["start_date_block"]["start_date_input"]["selected_date"],
            "end_date": values["end_date_block"]["end_date_input"]["selected_date"],
            "roles": values["roles_block"]["roles_input"]["value"],
            "handover_link": values["handover_link_block"]["handover_link_input"]["value"],
            "remarks": values["remarks_block"]["remarks_input"]["value"],
            "slack_user_id": payload["user"]["id"],
        }
        
        # Append to Google Sheet
        await append_to_sheet(submission_data)
        
        # Send confirmation DM to user
        await slack_client.post(
            "https://slack.com/api/chat.postMessage",
            json={
                "channel": payload["user"]["id"],
                "text": "✅ Your OOO handover request has been submitted!"
            }
        )
        
        return JSONResponse({"response_action": "clear"})
    
    return JSONResponse({"status": "ok"})

@app.post("/slack/options")
async def handle_options(request: Request):
    """Handle dynamic dropdown options"""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Request-Signature", "")
    
    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return JSONResponse({
        "options": [
            {"text": {"type": "plain_text", "text": "Option 1"}, "value": "option_1"},
            {"text": {"type": "plain_text", "text": "Option 2"}, "value": "option_2"}
        ]
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
