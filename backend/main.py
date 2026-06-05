from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Tenant

from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
from backend.scheduler import start_scheduler, stop_scheduler
from backend.utils.deps import get_current_admin, get_current_user
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up APScheduler Background Jobs...")
    start_scheduler()
    yield
    logger.info("Shutting down APScheduler...")
    stop_scheduler()

# Initialize FastAPI application
app = FastAPI(
    title="AI E-Commerce Platform API",
    lifespan=lifespan,
    description="Backend API for multi-tenant AI shopping mall with Crawler and VTON integration.",
    version="1.0.0",
)

# CORS Rules (Allowing Next.js frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI E-Commerce API is running."}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

from backend.routers.crawler import router as crawler_router
from backend.routers.products import router as products_router
from backend.routers.admin import router as admin_router
from backend.routers.auth import router as auth_router

app.include_router(crawler_router, prefix="/api/crawler", tags=["Crawler"])
app.include_router(products_router, prefix="/api/products", tags=["Products"])
app.include_router(admin_router, prefix="/api/admin", tags=["AdminHQ"], dependencies=[Depends(get_current_admin)])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])

from backend.routers.orders import router as orders_router
from backend.routers.upload import router as upload_router
from backend.routers.cart import router as cart_router
from backend.routers.wishlist import router as wishlist_router
from backend.routers.address import router as address_router
from backend.routers.reviews import router as reviews_router
from backend.routers.support import router as support_router
from backend.routers.vton import router as vton_router

app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
app.include_router(upload_router, prefix="/api/admin/upload", tags=["Uploads"], dependencies=[Depends(get_current_user)])
app.include_router(cart_router, prefix="/api/cart", tags=["Cart"])
app.include_router(wishlist_router, prefix="/api/wishlist", tags=["Wishlist"])
app.include_router(address_router, prefix="/api/address", tags=["Address"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(support_router, prefix="/api/support", tags=["Support"])
app.include_router(vton_router, prefix="/api/vton", tags=["VTON Pipeline"])

@app.get("/api/tenant/theme")
def get_tenant_theme(domain: str = "hq.mall.com", db: Session = Depends(get_db)):
    # Remove port if present
    clean_domain = domain.split(":")[0]
    if clean_domain in ["localhost", "127.0.0.1"]:
        clean_domain = "hq.mall.com"
        
    tenant = db.query(Tenant).filter(Tenant.domain == clean_domain).first()
    if not tenant:
        tenant = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not tenant:
        tenant = db.query(Tenant).filter(Tenant.is_active == True).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Active tenant not found")
        
    return {
        "id": tenant.id,
        "name": tenant.name,
        "domain": tenant.domain,
        "theme_config": tenant.theme_config or {},
        "is_active": tenant.is_active
    }


# Upload directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Ensure DB tables are created
from backend.database import engine, Base, SessionLocal
from backend.models import User, Tenant
from backend.utils.security import get_password_hash

Base.metadata.create_all(bind=engine)

# Ensure hq_products has video_url column (migration fallback for existing DBs)
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(hq_products)")).fetchall()
        column_names = [row[1] for row in res]
        if "video_url" not in column_names:
            conn.execute(text("ALTER TABLE hq_products ADD COLUMN video_url TEXT"))
            conn.commit()
            logger.info("Database migration: Added 'video_url' column to hq_products table.")
except Exception as db_err:
    logger.warning(f"Failed to check/add 'video_url' column to hq_products: {str(db_err)}")

# Seed admin user and default tenants
db = SessionLocal()
try:
    admin_exists = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin_exists:
        new_admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash(os.getenv("SEED_ADMIN_PASSWORD", "admin1234")),
            name="HQ 관리자",
            role="ADMIN",
            grade=0,
            reward_points=0,
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        logger.info("Default admin user 'admin@example.com' seeded with password 'admin1234'")

    luxai_admin_exists = db.query(User).filter(User.email == "admin@luxai.com").first()
    if not luxai_admin_exists:
        new_luxai_admin = User(
            email="admin@luxai.com",
            hashed_password=get_password_hash(os.getenv("SEED_ADMIN_PASSWORD", "admin1234")),
            name="LUXAI 관리자",
            role="ADMIN",
            grade=0,
            reward_points=0,
            is_active=True
        )
        db.add(new_luxai_admin)
        db.commit()
        logger.info("New admin user 'admin@luxai.com' seeded with password 'admin1234'")
        
    # Seed default tenants
    tenant_exists = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not tenant_exists:
        default_tenant = Tenant(
            domain="hq.mall.com",
            name="HQ Premium AI Shopping Mall",
            theme_config={
                "primaryColor": "#2563eb",
                "fontFamily": "Inter",
                "bannerTitle": "AI 가상피팅 명품 멀티숍",
                "bannerSubtitle": "Premium Artificial Intelligence Fitting Experience"
            },
            is_active=True
        )
        db.add(default_tenant)
        
        sub_tenant = Tenant(
            domain="sub1.mall.com",
            name="가방/지갑 전문 테넌트숍",
            theme_config={
                "primaryColor": "#4f46e5",
                "fontFamily": "Outfit",
                "bannerTitle": "럭셔리 가방 & 지갑 에디션",
                "bannerSubtitle": "Luxury Bag & Wallet Curation"
            },
            is_active=True
        )
        db.add(sub_tenant)
        db.commit()
        logger.info("Default tenants 'hq.mall.com' and 'sub1.mall.com' seeded successfully.")
except Exception as e:
    logger.error(f"Failed to seed default admin or tenants: {str(e)}")
finally:
    db.close()

