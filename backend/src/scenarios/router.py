from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from scenarios.schemas import ScenarioPublic, ScenarioRecommendationPublic
from scenarios.service import (
    ScenarioCatalogService,
    ScenarioRecommendationService,
    get_scenario_catalog_service,
    get_scenario_recommendation_service,
)
from users.models import User

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get(
    "",
    response_model=list[ScenarioPublic],
    dependencies=[Depends(get_current_user)],
)
async def list_scenarios(
    catalog: Annotated[ScenarioCatalogService, Depends(get_scenario_catalog_service)],
) -> list[ScenarioPublic]:
    return [ScenarioPublic.model_validate(s) for s in catalog.list_scenarios()]


@router.get("/recommendation", response_model=ScenarioRecommendationPublic)
async def get_recommendation(
    user: Annotated[User, Depends(get_current_user)],
    recommendation_service: Annotated[
        ScenarioRecommendationService, Depends(get_scenario_recommendation_service)
    ],
) -> ScenarioRecommendationPublic:
    recommendation = await recommendation_service.recommend(user.id)
    return ScenarioRecommendationPublic.model_validate(recommendation)
