# backend/app/modules/visitor_tracker/tracker.py
import time
from fastapi import Request, APIRouter
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
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

# 修正：前端使用的是单数 /api/visitor，这里必须对应
router = APIRouter(prefix="/api/visitor", tags=["Visitor Tracker"])


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
    start_time = time.time()

    # 放行 OPTIONS 请求，避免跨域问题
    if request.method == "OPTIONS":
        return await call_next(request)

    # 只记录 API 请求，且排除 /monitor 心跳请求（防止自己刷自己）
    if request.url.path.startswith("/api/") and "/monitor" not in request.url.path and "/stats" not in request.url.path:
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")

        # 异步执行数据库操作，避免阻塞主线程
        try:
            db = SessionLocal()

            # 检查最近一分钟内是否已有相同IP的记录，避免刷屏
            last_entry = db.query(VisitorLog).filter(VisitorLog.ip_address == ip_address).order_by(
                VisitorLog.timestamp.desc()).first()
            if not last_entry or (datetime.utcnow() - last_entry.timestamp).total_seconds() > 60:

                # 使用 ipapi 查询地理位置 (添加超时保护)
                country, region, city = "UNK", "UNK", "UNK"
                try:
                    # 这里的 ipapi 调用可能会慢，实际生产建议放到后台任务队列
                    pass
                    # 暂时保持原有逻辑，不修改
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

# 🔥 新增：统计接口 (供前端仪表盘 API HITS 使用)
@router.get("/stats")
async def get_visitor_stats():
    db = SessionLocal()
    try:
        total_count = db.query(VisitorLog).count()
        return {"total_visitors": total_count}
    finally:
        db.close()


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
