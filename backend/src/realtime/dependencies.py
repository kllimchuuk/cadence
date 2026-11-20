from typing import Annotated

from fastapi import Depends, WebSocket

from auth.dependencies import get_settings
from config import Settings
from orchestration.analysis_runner import SessionAnalysisRunner
from orchestration.dependencies import get_session_analysis_runner, get_session_runner
from orchestration.session_runner import SessionRunner
from realtime.websocket import PracticeSessionSocket


def get_practice_session_socket(
    websocket: WebSocket,
    runner: Annotated[SessionRunner, Depends(get_session_runner)],
    analysis_runner: Annotated[
        SessionAnalysisRunner, Depends(get_session_analysis_runner)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeSessionSocket:
    return PracticeSessionSocket(
        websocket, runner, analysis_runner, settings.cors_origins
    )
