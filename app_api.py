if __name__ == "__main__":
    import uvicorn
    import os
    from src.sab_core.config import settings

    uvicorn.run(
        "src.app_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],
    )
