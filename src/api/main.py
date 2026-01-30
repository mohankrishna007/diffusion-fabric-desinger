"""
FastAPI application - Main entry point for the pipeline REST API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import pipeline, health
import logging

# Import stages to trigger registration decorators
# This must happen before any pipeline operations
try:
    import weaver.diffusion.stages
    logging.info(f"Loaded {len(weaver.diffusion.stages.STAGE_CLASSES)} stages")
except Exception as e:
    logging.warning(f"Failed to auto-register stages: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="Diffusion Fabric Designer API",
        description="AI-Powered Fabric Design Pipeline - Orchestration & Manufacturing Compliance API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Pipeline"])
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("Diffusion Fabric Designer API starting up...")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Diffusion Fabric Designer API shutting down...")
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
