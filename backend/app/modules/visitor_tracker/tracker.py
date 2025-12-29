# backend/app/modules/visitor_tracker/tracker.py
import time
from fastapi import Request, APIRouter
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import ipapi
import logging

# ==================== 配置 ====================
DATABASE_URL = "sqlite:///./visitor_log.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger(__name__)

# 🔥 核心修复：改回复数 /api/visitors 以匹配 Vue 前端
router = APIRouter(prefix="/api/visitors", tags=["Visitor Tracker"])


# ==================== 数据库模型 ====================
class VisitorLog(Base):
    __tablename__ = "visitor_logs"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, index=True)
    user_agent = Column(String)
    country = Column(String, default="UNK")
    region = Column(String, default="UNK")
    city = Column(String, default="UNK")
    timestamp = Column(DateTime, default=datetime.utcnow)


# ==================== 数据库初始化 ====================
def create_db_and_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Visitor Tracker database tables created successfully.")
    except Exception as e:
        logger.error(f"❌ Could not create Visitor Tracker database tables: {e}")


# ==================== 中间件 ====================
async def visitor_tracker_middleware(request: Request, call_next):
    # 放行 OPTIONS 请求
    if request.method == "OPTIONS":
        return await call_next(request)

    # 只记录 API 请求，排除心跳监控接口
    if request.url.path.startswith("/api/") and "/stats" not in request.url.path:
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")

        try:
            db = SessionLocal()
            # 简单的防刷逻辑：同一IP 60秒内不重复记录
            last_entry = db.query(VisitorLog).filter(VisitorLog.ip_address == ip_address).order_by(
                VisitorLog.timestamp.desc()).first()

            if not last_entry or (datetime.utcnow() - last_entry.timestamp).total_seconds() > 60:
                country, region, city = "UNK", "UNK", "UNK"
                try:
                    # ⚠️ 注意：如果 ipapi 响应慢，建议在此处加超时或放入后台任务
                    # location = ipapi.location(ip=ip_address)
                    # country = location.get('country_name', 'UNK')
                    pass
                except Exception:
                    pass

                new_log = VisitorLog(
                    ip_address=ip_address,
                    user_agent=user_agent,
                    country=country,
                    region=region,
                    city=city
                )
                db.add(new_log)
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"❌ Visitor Tracker middleware error: {e}")

    response = await call_next(request)
    return response


# ==================== API 路由 ====================

# 1. 获取日志列表 (Vue Admin 使用)
@router.get("/")
async def get_visitor_logs(page: int = 1, limit: int = 20):
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        total_count = db.query(VisitorLog).count()
        logs = db.query(VisitorLog).order_by(VisitorLog.timestamp.desc()).offset(offset).limit(limit).all()

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "data": [
                {
                    "id": log.id,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "country": log.country,
                    "region": log.region,
                    "city": log.city,
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                } for log in logs
            ]
        }
    finally:
        db.close()


# 2. 获取统计数据 (为了兼容之前的 index.html 仪表盘)
@router.get("/stats")
async def get_visitor_stats():
    db = SessionLocal()
    try:
        total_count = db.query(VisitorLog).count()
        return {"total_visitors": total_count}
    finally:
        db.close()
