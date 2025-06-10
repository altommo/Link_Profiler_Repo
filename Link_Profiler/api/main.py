from fastapi import FastAPI
from Link_Profiler.api.routes import admin

app = FastAPI(
    title="Link Profiler API",
    description="API for managing link profiling, crawling, and SEO analysis tasks.",
    version="0.1.0",
)

# Include the admin router
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Link Profiler API. Visit /docs for API documentation."}

# You might have other routers to include here, e.g.:
# from Link_Profiler.api.routes import crawl_jobs
# app.include_router(crawl_jobs.router, prefix="/jobs", tags=["Crawl Jobs"])

# from Link_Profiler.api.routes import users
# app.include_router(users.router, prefix="/users", tags=["Users"])

# from Link_Profiler.api.routes import auth
# app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

