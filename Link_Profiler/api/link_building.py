import logging
import uuid
from datetime import datetime
from typing import Annotated, Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import logger, db, link_building_service_instance
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def save_link_prospect(self, prospect): pass
        def save_outreach_campaign(self, campaign): pass
        def get_all_outreach_campaigns(self, status_filter): return []
        def get_outreach_campaign(self, campaign_id): return None
        def save_outreach_event(self, event): pass
        def get_link_prospect(self, url): return None
        def get_outreach_events_for_prospect(self, prospect_url): return []
    db = DummyDB()
    class DummyLinkBuildingService:
        async def get_all_prospects(self, status_filter): return []
        async def update_prospect_status(self, url, new_status, last_outreach_date=None): return None
    link_building_service_instance = DummyLinkBuildingService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    LinkProspectResponse, LinkProspectUpdateRequest, ProspectIdentificationRequest,
    OutreachCampaignCreateRequest, OutreachCampaignResponse, OutreachEventCreateRequest,
    OutreachEventResponse
)
from Link_Profiler.api.dependencies import get_current_user

# Import queue-related functions and models
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue, QueueCrawlRequest

# Import Prometheus metrics
from Link_Profiler.monitoring.prometheus_metrics import JOBS_CREATED_TOTAL

# Import core models
from Link_Profiler.core.models import User, OutreachCampaign, OutreachEvent


link_building_router = APIRouter(prefix="/api/link_building", tags=["Link Building"])

@link_building_router.post("/prospects/identify", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def identify_link_prospects_job(
    request: ProspectIdentificationRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a job to identify and score link building prospects.
    """
    logger.info(f"API: Received request to submit link prospects identification for {request.target_domain} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='prospect_identification').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.target_domain,
        initial_seed_urls=[],
        config=request.dict(),
        priority=5
    )
    queue_request.config["job_type"] = "prospect_identification"

    return await submit_crawl_to_queue(queue_request)

@link_building_router.get("/prospects", response_model=List[LinkProspectResponse])
async def get_all_link_prospects_endpoint(
    status_filter: Annotated[Optional[str], Query(description="Filter prospects by status (e.g., 'identified', 'contacted', 'acquired').")] = None, # Corrected default value placement
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves all identified link building prospects, optionally filtered by status.
    """
    logger.info(f"API: Received request for all link prospects (status: {status_filter}) by user: {current_user.username}.")
    try:
        prospects = await link_building_service_instance.get_all_prospects(status_filter=status_filter)
        return [LinkProspectResponse.from_link_prospect(p) for p in prospects]
    except Exception as e:
        logger.error(f"API: Error retrieving link prospects: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link prospects: {e}")

@link_building_router.put("/prospects/{prospect_url:path}", response_model=LinkProspectResponse)
async def update_link_prospect_endpoint(
    prospect_url: str,
    request: LinkProspectUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Updates the status or other details of a specific link prospect.
    """
    logger.info(f"API: Received request to update link prospect {prospect_url} by user: {current_user.username}.")
    try:
        updated_prospect = await link_building_service_instance.update_prospect_status(
            url=prospect_url,
            new_status=request.status,
            last_outreach_date=request.last_outreach_date
        )
        if not updated_prospect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link prospect not found.")
        
        # Manually update other fields if provided
        if request.contact_info is not None:
            updated_prospect.contact_info = request.contact_info
        if request.reasons is not None:
            updated_prospect.reasons = request.reasons
        if request.score is not None:
            updated_prospect.score = request.score
        
        db.save_link_prospect(updated_prospect) # Save the full updated object
        return LinkProspectResponse.from_link_prospect(updated_prospect)
    except Exception as e:
        logger.error(f"API: Error updating link prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update link prospect: {e}")

@link_building_router.post("/campaigns", response_model=OutreachCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_outreach_campaign_endpoint(
    request: OutreachCampaignCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Creates a new link building outreach campaign.
    """
    logger.info(f"API: Received request to create outreach campaign '{request.name}' by user: {current_user.username}.")
    try:
        campaign = OutreachCampaign(
            id=str(uuid.uuid4()),
            name=request.name,
            target_domain=request.target_domain,
            description=request.description,
            start_date=request.start_date,
            end_date=request.end_date
        )
        db.save_outreach_campaign(campaign)
        return OutreachCampaignResponse.from_outreach_campaign(campaign)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"API: Error creating outreach campaign: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach campaign: {e}")

@link_building_router.get("/campaigns", response_model=List[OutreachCampaignResponse])
async def get_all_outreach_campaigns_endpoint(
    status_filter: Annotated[Optional[str], Query(description="Filter campaigns by status (e.g., 'active', 'completed').")] = None, # Corrected default value placement
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves all outreach campaigns, optionally filtered by status.
    """
    logger.info(f"API: Received request for all outreach campaigns (status: {status_filter}) by user: {current_user.username}.")
    try:
        campaigns = db.get_all_outreach_campaigns(status_filter=status_filter)
        return [OutreachCampaignResponse.from_outreach_campaign(c) for c in campaigns]
    except Exception as e:
        logger.error(f"API: Error retrieving outreach campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@link_building_router.get("/campaigns/{campaign_id}", response_model=OutreachCampaignResponse)
async def get_outreach_campaign_by_id_endpoint(
    campaign_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves a specific outreach campaign by its ID.
    """
    logger.info(f"API: Received request for outreach campaign {campaign_id} by user: {current_user.username}.")
    try:
        campaign = db.get_outreach_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach campaign not found.")
        return OutreachCampaignResponse.from_outreach_campaign(campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error retrieving outreach campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@link_building_router.post("/events", response_model=OutreachEventResponse, status_code=status.HTTP_201_CREATED)
async def create_outreach_event_endpoint(
    request: OutreachEventCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Records a new outreach event for a prospect within a campaign.
    """
    logger.info(f"API: Received request to record outreach event for prospect {request.prospect_url} in campaign {request.campaign_id} by user: {current_user.username}.")
    try:
        # Basic validation: check if campaign and prospect exist
        campaign = db.get_outreach_campaign(request.campaign_id)
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Outreach campaign {request.campaign_id} not found.")
        prospect = db.get_link_prospect(request.prospect_url)
        if not prospect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Link prospect {request.prospect_url} not found.")

        event = OutreachEvent(
            id=str(uuid.uuid4()),
            campaign_id=request.campaign_id,
            prospect_url=request.prospect_url,
            event_type=request.event_type,
            notes=request.notes,
            success=request.success
        )
        db.save_outreach_event(event)
        
        # Optionally update prospect status based on event type
        if request.event_type == "link_acquired":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "acquired")
        elif request.event_type == "email_sent":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "contacted", event.event_date)
        elif request.event_type == "rejected":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "rejected")

        return OutreachEventResponse.from_outreach_event(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error creating outreach event: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach event: {e}")

@link_building_router.get("/prospects/{prospect_url:path}/events", response_model=List[OutreachEventResponse])
async def get_outreach_events_for_prospect_endpoint(
    prospect_url: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves all outreach events for a specific link prospect.
    """
    logger.info(f"API: Received request for outreach events for prospect {prospect_url} by user: {current_user.username}.")
    try:
        events = db.get_outreach_events_for_prospect(prospect_url)
        return [OutreachEventResponse.from_outreach_event(e) for e in events]
    except Exception as e:
        logger.error(f"API: Error retrieving outreach events for prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach events: {e}")
