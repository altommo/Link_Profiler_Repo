import pytest
from Link_Profiler.services.mission_control_service import mission_control_service

@pytest.mark.asyncio
async def test_realtime_updates_keys():
    data = await mission_control_service.get_realtime_updates()
    expected_keys = {
        "active_jobs",
        "satellite_status",
        "queue_depth",
        "recent_discoveries",
        "api_quotas",
        "alerts",
    }
    assert expected_keys.issubset(data.keys())

