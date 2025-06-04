import logging
import time
import json
import os
import sys
from datetime import datetime
from typing import Annotated, Dict, List, Any, Optional

import psutil
import psycopg2 # For database stats

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query # Removed Request as it's no longer needed for middleware

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import (
        logger, db, redis_client, config_loader,
        domain_service_instance, backlink_service_instance, serp_service_instance,
        keyword_service_instance, ai_service_instance, clickhouse_loader_instance,
        auth_service_instance, get_coordinator # Import get_coordinator from main
    )
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def ping(self): raise Exception("DB not connected")
        def get_all_crawl_jobs(self): return []
        def get_all_link_profiles(self): return []
        def get_all_domains(self): return []
        def get_count_of_competitive_keyword_analyses(self): return 0
        def get_all_backlinks(self): return []
        class Session:
            @staticmethod
            def remove(): pass
    db = DummyDB()
    class DummyRedisClient:
        async def ping(self): raise Exception("Redis not connected")
        async def get(self, key): return None
        async def lrange(self, key, start, end): return []
        async def delete(self, key): return 0
        async def zadd(self, key, mapping): pass
        async def zcard(self, key): return 0
        async def llen(self, key): return 0
        async def zrangebyscore(self, key, min_score, max_score, withscores=False): return []
        def info(self): return {}
    redis_client = DummyRedisClient()
    class DummyConfigLoader:
        def get(self, key, default=None): return default
    config_loader = DummyConfigLoader()
    class DummyService:
        api_client = None
        enabled = False
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
    domain_service_instance = DummyService()
    backlink_service_instance = DummyService()
    serp_service_instance = DummyService()
    keyword_service_instance = DummyService()
    ai_service_instance = DummyService()
    clickhouse_loader_instance = None
    class DummyAuthService:
        def _check_secret_key(self): raise HTTPException(status_code=500, detail="Secret key not set.")
    auth_service_instance = DummyAuthService()
    # Dummy get_coordinator for testing
    class DummyCoordinator:
        async def get_queue_stats(self):
            return {
                "pending_jobs": 0,
                "results_pending": 0,
                "active_crawlers": 0,
                "satellite_crawlers": {},
                "timestamp": datetime.now().isoformat()
            }
        async def control_satellite(self, crawler_id: str, command: str):
            return {"message": f"Dummy: Command {command} sent to {crawler_id}"}
        async def control_all_satellites(self, command: str):
            return {"message": f"Dummy: Command {command} sent to all satellites"}
        async def cancel_job(self, job_id: str):
            return True
        async def pause_job_processing(self):
            return True
        async def resume_job_processing(self):
            return True
    async def get_coordinator():
        return DummyCoordinator()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import CrawlJobResponse
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User, CrawlStatus

# Re-import get_metrics_text for the /metrics endpoint
from Link_Profiler.monitoring.prometheus_metrics import get_metrics_text


monitoring_debug_router = APIRouter(tags=["Monitoring & Debug"])

# --- Admin Access Verification ---
def verify_admin_access(current_user: User):
    """Verify that the current user has admin access"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required to access this endpoint" # More generic message
        )

# --- Helper function for comprehensive health check ---
async def health_check_internal() -> Dict[str, Any]:
    """
    Performs a comprehensive health check of the API and its dependencies.
    Internal function, results are used by /health and /api/stats.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dependencies": {
            "environment_variables": {
                "LP_AUTH_SECRET_KEY": "SET" if os.getenv("LP_AUTH_SECRET_KEY") else "MISSING",
                "LP_DATABASE_URL": "SET" if os.getenv("LP_DATABASE_URL") else "MISSING", 
                "LP_REDIS_URL": "SET" if os.getenv("LP_REDIS_URL") else "MISSING"
            }
        }
    }

    # Check Redis connectivity
    try:
        if redis_client:
            await redis_client.ping()
            health_status["dependencies"]["redis"] = {"status": "connected"}
        else:
            health_status["dependencies"]["redis"] = {"status": "disabled", "message": "Redis client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["redis"] = {"status": "disconnected", "error": str(e)}
        logger.error(f"Health check: Redis connection failed: {e}")

    # Check PostgreSQL connectivity
    try:
        db.ping()
        health_status["dependencies"]["postgresql"] = {"status": "connected"}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["postgresql"] = {"status": "disconnected", "error": str(e)}
        logger.error(f"Health check: PostgreSQL connection failed: {e}")

    # Check external API services (Domain, Backlink, SERP, Keyword, AI)
    # This is a high-level check, not a deep ping to external APIs
    
    # Domain Service
    try:
        async with domain_service_instance as ds:
            if ds.api_client:
                health_status["dependencies"]["domain_service"] = {"status": "ready", "client": ds.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["domain_service"] = {"status": "not_ready", "message": "API client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["domain_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Domain Service failed: {e}")

    # Backlink Service
    try:
        async with backlink_service_instance as bs:
            if bs.api_client:
                health_status["dependencies"]["backlink_service"] = {"status": "ready", "client": bs.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["backlink_service"] = {"status": "not_ready", "message": "API client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["backlink_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Backlink Service failed: {e}")

    # SERP Service
    try:
        async with serp_service_instance as ss:
            if ss.api_client or ss.serp_crawler:
                health_status["dependencies"]["serp_service"] = {"status": "ready", "client": ss.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["serp_service"] = {"status": "not_ready", "message": "No client or crawler initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["serp_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: SERP Service failed: {e}")

    # Keyword Service
    try:
        async with keyword_service_instance as ks:
            if ks.api_client or ks.keyword_scraper:
                health_status["dependencies"]["keyword_service"] = {"status": "ready", "client": ks.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["keyword_service"] = {"status": "not_ready", "message": "No client or scraper initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["keyword_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Keyword Service failed: {e}")

    # AI Service
    try:
        async with ai_service_instance as ais:
            if ais.enabled:
                health_status["dependencies"]["ai_service"] = {"status": "enabled", "client": ais.openrouter_client.__class__.__name__}
            else:
                health_status["dependencies"]["ai_service"] = {"status": "disabled", "message": "AI service is disabled by config or missing API key."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["ai_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: AI Service failed: {e}")

    # ClickHouse Loader
    try:
        if clickhouse_loader_instance:
            await clickhouse_loader_instance.__aenter__()
            if clickhouse_loader_instance.client:
                health_status["dependencies"]["clickhouse_loader"] = {"status": "connected"}
            else:
                health_status["dependencies"]["clickhouse_loader"] = {"status": "disconnected", "message": "Client not active after init."}
            await clickhouse_loader_instance.__aexit__(None, None, None)
        else:
            health_status["dependencies"]["clickhouse_loader"] = {"status": "disabled", "message": "ClickHouse integration is disabled."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["clickhouse_loader"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: ClickHouse Loader failed: {e}")

    # Auth Service
    try:
        auth_service_instance._check_secret_key()
        health_status["dependencies"]["auth_service"] = {"status": "enabled"}
    except HTTPException as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["auth_service"] = {"status": "disabled", "error": e.detail}
        logger.error(f"Health check: Auth Service failed: {e.detail}")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["auth_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Auth Service failed: {e}")
    
    return health_status

# --- Helper function for aggregated stats ---
async def _get_aggregated_stats_for_api() -> Dict[str, Any]:
    """Aggregates various statistics for the /api/stats endpoint."""
    
    coord = await get_coordinator()
    stats_from_coordinator = await coord.get_queue_stats()

    # Queue Metrics
    queue_metrics = {
        "pending_jobs": stats_from_coordinator.get("pending_jobs", 0),
        "results_pending": stats_from_coordinator.get("results_pending", 0),
        "active_crawlers": stats_from_coordinator.get("active_crawlers", 0),
        "satellites": [],
        "timestamp": datetime.now().isoformat()
    }
    
    detailed_satellites = []
    for crawler_id, details in stats_from_coordinator.get("satellite_crawlers", {}).items():
        satellite_data = details.copy()
        if "timestamp" in satellite_data and isinstance(satellite_data["timestamp"], datetime):
            satellite_data["timestamp"] = satellite_data["timestamp"].isoformat()
        if "last_seen" in satellite_data and isinstance(satellite_data["last_seen"], datetime):
            satellite_data["last_seen"] = satellite_data["last_seen"].isoformat()
        detailed_satellites.append(satellite_data)
    
    queue_metrics["satellites"] = detailed_satellites


    # Performance Stats
    performance_stats = {"error": "Database not connected"}
    if db:
        try:
            all_jobs = db.get_all_crawl_jobs()
            total_jobs = len(all_jobs)
            successful_jobs = sum(1 for job in all_jobs if job.status == CrawlStatus.COMPLETED)
            
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0.0
            
            performance_stats = {
                "total_jobs_processed": total_jobs,
                "successful_jobs": successful_jobs,
                "success_rate": round(success_rate, 1),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting performance stats for /api/stats: {e}", exc_info=True)
            performance_stats = {"error": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    # Data Summaries
    data_summaries = {"error": "Database not connected"}
    if db:
        try:
            total_link_profiles = len(db.get_all_link_profiles())
            total_domains_analyzed = len(db.get_all_domains())
            competitive_keyword_analyses = db.get_count_of_competitive_keyword_analyses()
            total_backlinks_stored = len(db.get_all_backlinks())

            data_summaries = {
                "total_link_profiles": total_link_profiles,
                "total_domains_analyzed": total_domains_analyzed,
                "competitive_keyword_analyses": competitive_keyword_analyses,
                "total_backlinks_stored": total_backlinks_stored,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting data summaries for /api/stats: {e}", exc_info=True)
            data_summaries = {"error": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    # System Stats
    system_stats = {}
    try:
        system_stats = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used
            },
            "disk": {
                "percent": psutil.disk_usage('/').percent,
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free
            },
            "uptime": time.time() - psutil.boot_time()
        }
    except Exception as e:
        logger.error(f"Error getting system stats for /api/stats: {e}", exc_info=True)
        system_stats = {"error": str(e)}

    # API Health
    api_health = {}
    try:
        health_response = await health_check_internal() # Call the internal health check
        api_health = health_response
    except Exception as e:
        logger.error(f"Error getting API health for /api/stats: {e}", exc_info=True)
        api_health = {"status": "error", "message": str(e)}

    # Redis Stats
    redis_stats = {"status": "disconnected"}
    if redis_client:
        try:
            info = await redis_client.info()
            redis_stats = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "status": "connected"
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats for /api/stats: {e}", exc_info=True)
            redis_stats = {"status": "error", "message": str(e)}

    # Database Stats
    database_stats = {"status": "disconnected"}
    if db:
        try:
            db.ping()
            conn = psycopg2.connect(db.db_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    relname,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes
                FROM pg_stat_user_tables;
            """)
            tables = []
            for row in cur.fetchall():
                tables.append({
                    "table": row[0],
                    "inserts": row[1],
                    "updates": row[2],
                    "deletes": row[3]
                })
            cur.close()
            conn.close()
            database_stats = {
                "status": "connected",
                "tables": tables
            }
        except Exception as e:
            logger.error(f"Error getting database stats for /api/stats: {e}", exc_info=True)
            database_stats = {"status": "error", "message": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    return {
        "queue_metrics": queue_metrics,
        "performance_stats": performance_stats,
        "data_summaries": data_summaries,
        "system": system_stats,
        "api_health": api_health,
        "redis": redis_stats,
        "database": database_stats,
        "timestamp": datetime.now().isoformat()
    }

async def _get_satellites_data_internal() -> Dict[str, Any]:
    """
    Internal helper to retrieve detailed health information for all satellite crawlers.
    Does not require authentication.
    """
    job_coordinator = await get_coordinator()
    stats = await job_coordinator.get_queue_stats() # This already contains satellite_crawlers

    satellite_list = list(stats.get("satellite_crawlers", {}).values())
    
    return {"satellites": satellite_list, "active_count": len(satellite_list)}


@monitoring_debug_router.get("/api/stats")
async def get_api_stats(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves aggregated statistics for the Link Profiler system.
    This endpoint is primarily consumed by the monitoring dashboard and requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request for aggregated stats by admin: {current_user.username}.")
    return await _get_aggregated_stats_for_api()

@monitoring_debug_router.get("/api/jobs/all", response_model=List[CrawlJobResponse])
async def get_all_jobs_api(
    status_filter: Annotated[Optional[str], Query(description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED').")] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None # Protect this endpoint
):
    """
    Retrieves all crawl jobs, optionally filtered by status.
    This endpoint is primarily consumed by the monitoring dashboard and requires authentication.
    Returns the most recent 50 jobs.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request for all jobs by admin: {current_user.username} (status_filter: {status_filter}).")
    
    # Handle empty string status filter
    if status_filter == "":
        status_filter = None
    try:
        all_jobs = db.get_all_crawl_jobs()
        logger.debug(f"API: Retrieved {len(all_jobs)} jobs from database before filtering.")
        
        if status_filter:
            try:
                filter_status = CrawlStatus[status_filter.upper()]
                all_jobs = [job for job in all_jobs if job.status == filter_status]
            except KeyError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
        sorted_jobs = sorted(all_jobs, key=lambda job: job.created_date, reverse=True)[:50]
        
        return [CrawlJobResponse.from_crawl_job(job) for job in sorted_jobs]
    except Exception as e:
        logger.error(f"API: Error retrieving all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve all jobs: {e}")
    finally:
        if db and hasattr(db, 'Session'):
            db.Session.remove()

@monitoring_debug_router.get("/api/jobs/is_paused", response_model=Dict[str, bool])
async def is_jobs_paused_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Checks if global job processing is currently paused.
    This endpoint is primarily consumed by the monitoring dashboard and requires authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request to check if jobs are paused by admin: {current_user.username}.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available.")
    
    try:
        is_paused = await redis_client.get("processing_paused")
        return {"is_paused": is_paused is not None and is_paused.decode('utf-8').lower() == 'true'}
    except Exception as e:
        logger.error(f"API: Error checking if jobs are paused: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check pause status: {e}")

@monitoring_debug_router.post("/api/jobs/{job_id}/cancel")
async def cancel_job_api(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Cancels a specific crawl job.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request to cancel job {job_id} by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.cancel_job(job_id)
        if success:
            return {"message": f"Job {job_id} cancelled successfully."}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or could not be cancelled.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}: {e}")

@monitoring_debug_router.post("/api/jobs/pause_all")
async def pause_all_jobs_api(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Pauses all new job processing.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request to pause all jobs by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        await coordinator.pause_job_processing()
        return {"message": "All new job processing paused."}
    except Exception as e:
        logger.error(f"Error pausing all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause all jobs: {e}")

@monitoring_debug_router.post("/api/jobs/resume_all")
async def resume_all_jobs_api(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Resumes all job processing.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request to resume all jobs by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        await coordinator.resume_job_processing()
        return {"message": "All job processing resumed."}
    except Exception as e:
        logger.error(f"Error resuming all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume all jobs: {e}")

@monitoring_debug_router.get("/api/monitoring/satellites")
async def get_monitoring_satellites(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves detailed health information for all satellite crawlers.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received request for detailed satellite health by admin: {current_user.username}.")
    return await _get_satellites_data_internal()

@monitoring_debug_router.post("/api/satellites/control/{crawler_id}/{command}")
async def control_single_satellite_api(crawler_id: str, command: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Sends a control command to a specific satellite crawler.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received command '{command}' for satellite '{crawler_id}' by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.control_satellite(crawler_id, command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling satellite {crawler_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control satellite {crawler_id}: {e}")

@monitoring_debug_router.post("/api/satellites/control/all/{command}")
async def control_all_satellites_api(command: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Sends a control command to all active satellite crawlers.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    """
    verify_admin_access(current_user)
    logger.info(f"API: Received command '{command}' for all satellites by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.control_all_satellites(command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling all satellites: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control all satellites: {e}")


@monitoring_debug_router.get("/public/health")
async def public_health_check_endpoint():
    """
    Public endpoint: Performs a comprehensive health check of the API and its dependencies.
    """
    health_status = await health_check_internal()
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)


@monitoring_debug_router.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """
    Exposes Prometheus metrics.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")

@monitoring_debug_router.get("/status")
async def get_system_status():
    """
    Provides detailed system status information.
    """
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0", # Placeholder for application version
        "uptime_seconds": time.time() - psutil.boot_time(),
        "python_version": sys.version,
        "system_info": {
            "hostname": os.uname().nodename,
            "platform": sys.platform,
            "architecture": os.uname().machine,
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_total_bytes": psutil.virtual_memory().total,
            "memory_available_bytes": psutil.virtual_memory().available,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_bytes": psutil.disk_usage('/').total,
            "disk_used_bytes": psutil.disk_usage('/').used,
            "disk_free_bytes": psutil.disk_usage('/').free,
            "disk_percent": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict()
        }
    }

@monitoring_debug_router.get("/debug/dead_letters")
async def get_dead_letters(current_user: Annotated[User, Depends(get_current_user)]):
    """
    DEBUG endpoint: Retrieves messages from the Redis dead-letter queue.
    """
    logger.info(f"DEBUG endpoint: Received request for dead letters by user: {current_user.username}.")
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be accessed.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        messages = await redis_client.lrange(dead_letter_queue_name, 0, -1)
        decoded_messages = [json.loads(msg.decode('utf-8')) for msg in messages]
        logger.info(f"Retrieved {len(decoded_messages)} messages from dead-letter queue.")
        return {"dead_letter_messages": decoded_messages}
    except Exception as e:
        logger.error(f"Error retrieving dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve dead-letter messages: {e}")

@monitoring_debug_router.post("/debug/clear_dead_letters")
async def clear_dead_letters(current_user: Annotated[User, Depends(get_current_user)]):
    """
    DEBUG endpoint: Clears all messages from the Redis dead-letter queue.
    """
    logger.info(f"DEBUG endpoint: Received request to clear dead letters by user: {current_user.username}.")
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be cleared.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        count = await redis_client.delete(dead_letter_queue_name)
        logger.info(f"Cleared {count} messages from dead-letter queue.")
        return {"status": "success", "message": f"Cleared {count} messages from dead-letter queue."}
    except Exception as e:
        logger.error(f"Error clearing dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clear dead-letter messages: {e}")

@monitoring_debug_router.post("/debug/reprocess_dead_letters", response_model=Dict[str, str])
async def reprocess_dead_letters(current_user: Annotated[User, Depends(get_current_user)]):
    """
    DEBUG endpoint: Moves all messages from the dead-letter queue back to the main job queue for reprocessing.
    """
    logger.info(f"DEBUG endpoint: Received request to reprocess dead letters by user: {current_user.username}.")
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be reprocessed.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
    
    try:
        messages = await redis_client.lrange(dead_letter_queue_name, 0, -1)
        if not messages:
            return {"status": "success", "message": "Dead-letter queue is empty. Nothing to reprocess."}
        
        requeued_count = 0
        for msg in messages:
            try:
                job_data = json.loads(msg.decode('utf-8'))
                job_data.pop('dead_letter_reason', None)
                job_data.pop('dead_letter_timestamp', None)
                
                if job_data.get('status') == CrawlStatus.FAILED.value:
                    job_data['status'] = CrawlStatus.PENDING.value
                    job_data['errors_count'] = 0
                    job_data['error_log'] = []
                
                priority = job_data.get('priority', 5)
                await redis_client.zadd(job_queue_name, {json.dumps(job_data): priority})
                requeued_count += 1
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode dead-letter message during reprocess: {msg.decode('utf-8')[:100]}... Error: {e}")
            except Exception as e:
                logger.error(f"Error re-queuing dead-letter message {msg.decode('utf-8')[:100]}... Error: {e}")
        
        await redis_client.delete(dead_letter_queue_name)
        
        logger.info(f"Reprocessed {requeued_count} messages from dead-letter queue to {job_queue_name}.")
        return {"status": "success", "message": f"Reprocessed {requeued_count} messages from dead-letter queue."}
    except Exception as e:
        logger.error(f"Error reprocessing dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reprocess dead-letter messages: {e}")

@monitoring_debug_router.get("/public/satellites") # New: Implement /public/satellites endpoint
async def public_satellites_endpoint():
    """
    Public endpoint: Retrieves detailed health information for all satellite crawlers.
    """
    logger.info("API: Received request for public satellite health.")
    return await _get_satellites_data_internal()

@monitoring_debug_router.get("/public/stats")
async def public_stats_endpoint():
    """
    Public endpoint: Retrieves aggregated statistics for the Link Profiler system.
    """
    logger.info("API: Received request for public aggregated stats.")
    return await _get_aggregated_stats_for_api()
