"""`python -m rootcause.api`: one FastAPI app served on two ports in one process —
8000 for the UI/API and 4318 for the collector's OTLP/HTTP exporter (only the first server runs the lifespan).
"""

import asyncio
import os

import uvicorn

from rootcause.api.main import app


async def main() -> None:
    api = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("RC_API_PORT", 8000)),
                                        log_level="info"))
    otlp = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("RC_OTLP_PORT", 4318)),
                                         lifespan="off", log_level="warning", access_log=False))
    await asyncio.gather(api.serve(), otlp.serve())


if __name__ == "__main__":
    asyncio.run(main())
