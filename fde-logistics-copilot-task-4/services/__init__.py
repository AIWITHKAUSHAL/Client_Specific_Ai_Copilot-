"""Service layer.

Services orchestrate tools, monitoring and configuration on behalf of a
delivery channel (CLI, REST API, and later Slack/Teams).  Keeping the
orchestration here means a new channel is a thin adapter, not a rewrite.
"""

from services.agent_service import AgentService, agent_service
from services.monitoring_service import MonitoringService, monitoring

__all__ = ["AgentService", "MonitoringService", "agent_service", "monitoring"]
