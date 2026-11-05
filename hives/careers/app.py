"""workBee careers website, served independently from the Kalshi dashboard."""
from fastapi import FastAPI
from hives.careers.bee import router as bee_router
from hives.careers.api import router
from hives.careers.accounts import router as accounts_router

app = FastAPI(title='workBee', version='0.2.0')
app.include_router(router)
app.include_router(accounts_router)
app.include_router(bee_router)


@app.get('/health')
async def health():
    return {'status': 'ok', 'app': 'workBee'}
