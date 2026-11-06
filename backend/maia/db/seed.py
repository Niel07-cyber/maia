"""Load the demo reference data, or reset the demo to its starting state.

Usage:
    uv run python -m maia.db.seed            # insert or update reference data
    uv run python -m maia.db.seed --reset    # also delete work orders, reservations, step logs
"""

import argparse
import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from maia.db import seed_data
from maia.db.models import PartReservation, StepLog, WorkOrder
from maia.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


def seed(session: Session) -> None:
    """Insert or update the reference data. Safe to run any number of times."""
    reference_data = [
        *seed_data.vehicles(),
        *seed_data.assets(),
        *seed_data.parts(),
        *seed_data.measurement_limits(),
    ]
    for obj in reference_data:
        session.merge(obj)  # insert if the primary key is new, update it otherwise


def reset_demo(session: Session) -> None:
    """Remove everything the agent created, then restore the reference data."""
    session.execute(delete(PartReservation))
    session.execute(delete(WorkOrder))
    session.execute(delete(StepLog))
    seed(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--reset", action="store_true", help="delete agent-created records before seeding"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with get_sessionmaker()() as session, session.begin():
        if args.reset:
            reset_demo(session)
        else:
            seed(session)
    logger.info("Demo data %s.", "reset" if args.reset else "loaded")


if __name__ == "__main__":
    main()
