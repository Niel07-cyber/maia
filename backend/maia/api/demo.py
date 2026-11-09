"""Demo controls: put the depot back to its starting state between demos."""

from typing import Annotated

from fastapi import APIRouter, Depends

from maia.agent.agent import TransactionFactory
from maia.api.deps import get_transaction
from maia.api.limits import RateLimited
from maia.db.seed import reset_demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset", dependencies=[RateLimited])
def reset(transaction: Annotated[TransactionFactory, Depends(get_transaction)]) -> dict[str, str]:
    """Delete everything the agent created and restore the stock."""
    with transaction() as session:
        reset_demo(session)
    return {"status": "reset"}
