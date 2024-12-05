from src.schemas.base import Base


class OrderStatusUpdater(Base):
    id: str
    pos_number: str
    status: str
