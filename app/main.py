from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import ValidationError
from app.services.workflow_service import workflow
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Webhook listener for Access Afya Franchisee Vetting",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"status": "active", "environment": settings.ENVIRONMENT}

@app.post("/webhook/google-form")
async def ingest_lead(payload: dict, background_tasks: BackgroundTasks):
    """
    Receives raw JSON from Google Forms (via Zapier/Make or Script).
    Triggers the Vetting Agent.
    """
    try:
        # We use background tasks so the Form gets a 200 OK immediately
        # while the AI chugs along in the background.
        background_tasks.add_task(workflow.process_incoming_lead, payload)
        
        return {
            "status": "received", 
            "message": "Lead queued for vetting", 
            "lead_email": payload.get("email", "unknown")
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)