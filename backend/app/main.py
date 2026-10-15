from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.session import Base, engine
import app.models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment.strip().lower() == "production":
        # Production schema is managed only through reviewed Alembic migrations.
        yield
        return

    # PostgreSQL schema is migration-managed in every environment. A restricted
    # runtime role must never need CREATE privileges merely to start the API.
    if engine.dialect.name != "postgresql":
        # Importing the model above registers it with SQLAlchemy.
        Base.metadata.create_all(bind=engine)

    try:
        from app.db.session import SessionLocal, set_database_context
        from app.services.evaluation import seed_historical_evaluations
        from app.services.investors import seed_default_investor_profiles
        from app.services.rag import seed_demonstration_corpus

        db = SessionLocal()
        try:
            # Startup seeding is a trusted process operation outside production.
            set_database_context(db, operator=True)
            seed_demonstration_corpus(db)
            seed_default_investor_profiles(db)
            seed_historical_evaluations(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "Optional demo data seeding failed; API startup will continue (%s)",
            type(exc).__name__,
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Evidence-backed financial intelligence "
        "with independent analytical agents."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "message": "FinWiseAI API is running.",
        "docs": "/docs",
    }
