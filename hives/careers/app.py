"""workBee careers website, served independently from the Kalshi dashboard."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from hives.careers.refresh import router as refresh_router,shutdown as stop_refreshes
from hives.careers.bee import router as bee_router
from hives.careers.api import router
from hives.careers.accounts import router as accounts_router
from hives.careers.oauth import router as oauth_router
from hives.careers.subscriptions import router as subscriptions_router

@asynccontextmanager
async def lifespan(app):
    yield
    await stop_refreshes()

app = FastAPI(title='workBee', version='0.2.0',lifespan=lifespan)
app.include_router(router)
app.include_router(accounts_router)
app.include_router(oauth_router)
app.include_router(subscriptions_router)
app.include_router(bee_router)
app.include_router(refresh_router)


@app.get('/health')
async def health():
    return {'status': 'ok', 'app': 'workBee'}
