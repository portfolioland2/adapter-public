import hashlib

from sqlalchemy import String, Boolean, ForeignKey, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)

    clients: Mapped[list["Client"]] = relationship("Client", back_populates="project")


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    client_secret: Mapped[str] = mapped_column(String, nullable=False)
    secret_key: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    api_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    currency_code: Mapped[str] = mapped_column(String, nullable=True)
    discount_id: Mapped[int] = mapped_column(Integer, nullable=True)

    get_modifier_max_amount: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_loyalty: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_split_order_items_for_keeper: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_modifier_external_id: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_meal_external_id: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_discounts_as_variable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_global_modifier_complex: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_skip_update_order_payment_status: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_use_minus_for_discount_amount: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    shops: Mapped[list["Shop"]] = relationship("Shop", back_populates="client")
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="client")
    modifiers: Mapped[list["Modifier"]] = relationship("Modifier", back_populates="client")
    modifier_groups: Mapped[list["ModifierGroup"]] = relationship("ModifierGroup", back_populates="client")
    meals: Mapped[list["Meal"]] = relationship("Meal", back_populates="client")
    discounts: Mapped[list["Discount"]] = relationship("Discount", back_populates="client")

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="client")

    project_id = mapped_column(ForeignKey("project.id"), nullable=True)
    project: Mapped[Project] = relationship("Project", cascade="all, delete", back_populates="clients")

    def __repr__(self) -> str:
        return (
            f"Client(id={self.id}, project_id={self.project_id}, "
            f"client_id={self.client_id}, api_key={self.api_key})"
        )


class Shop(Base):
    __tablename__ = "shop"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="shops")

    meal_offers: Mapped[list["MealOffer"]] = relationship("MealOffer", back_populates="shop")
    modifier_offers: Mapped[list["ModifierOffer"]] = relationship("ModifierOffer", back_populates="shop")

    def __repr__(self) -> str:
        return f"Shop(id={self.id}, client_id={self.client_id}, pos_id={self.pos_id}, starter_id={self.starter_id})"


class Meal(Base):
    __tablename__ = "meal"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=True)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="meals")

    offers: Mapped[list["MealOffer"]] = relationship("MealOffer", back_populates="meal")

    def __repr__(self) -> str:
        return f"Meal(id={self.id}, starter_id={self.starter_id}, pos_id={self.pos_id}, external_id={self.external_id})"


class MealOffer(Base):
    __tablename__ = "meal_offer"

    id: Mapped[int] = mapped_column(primary_key=True)

    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id"), nullable=False)
    meal: Mapped[Meal] = relationship("Meal", cascade="all, delete", back_populates="offers")

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    shop_id: Mapped[int] = mapped_column(ForeignKey("shop.id"), nullable=False)
    shop: Mapped[Shop] = relationship("Shop", cascade="all, delete", back_populates="meal_offers")

    def __repr__(self) -> str:
        return f"MealOffer(id={self.id}, meal_id={self.meal_id}, starter_id={self.starter_id}, pos_id={self.pos_id})"


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="categories")

    def __repr__(self) -> str:
        return f"Category(id={self.id}, starter_id={self.starter_id}, pos_id={self.pos_id})"


class Modifier(Base):
    __tablename__ = "modifier"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=True)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    min_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="modifiers")

    offers: Mapped[list["ModifierOffer"]] = relationship("ModifierOffer", back_populates="modifier")

    def __repr__(self) -> str:
        return f"Modifier(id={self.id}, starter_id={self.starter_id}, pos_id={self.pos_id}, external_id: {self.external_id})"

    @property
    def specific_id(self) -> str:
        return f"{self.pos_id}/{self.min_amount}/{self.max_amount}"

    @property
    def specific_external_id(self) -> str:
        return f"{self.external_id}/{self.min_amount}/{self.max_amount}"


class ModifierOffer(Base):
    __tablename__ = "modifier_offer"

    id: Mapped[int] = mapped_column(primary_key=True)

    modifier_id: Mapped[int] = mapped_column(ForeignKey("modifier.id"), nullable=False)
    modifier: Mapped[Modifier] = relationship("Modifier", cascade="all, delete", back_populates="offers")

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    shop_id: Mapped[int] = mapped_column(ForeignKey("shop.id"), nullable=False)
    shop: Mapped[Shop] = relationship("Shop", cascade="all, delete", back_populates="modifier_offers")

    def __repr__(self) -> str:
        return f"ModifierOffer(id={self.id}, modifier_id={self.modifier_id}, starter_id={self.starter_id}, pos_id={self.pos_id}, shop_id={self.shop_id})"


class ModifierGroup(Base):
    __tablename__ = "modifier_group"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[int] = mapped_column(Integer, nullable=False)

    min_amount: Mapped[int] = mapped_column(Integer, nullable=True)
    max_amount: Mapped[int] = mapped_column(Integer, nullable=True)

    modifier_external_ids: Mapped[str] = mapped_column(String, nullable=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="modifier_groups")

    def __repr__(self) -> str:
        return f"ModifierGroup(id={self.id}, starter_id={self.starter_id}, pos_id={self.pos_id})"

    @property
    def specific_id(self) -> str:
        return f"{self.pos_id}/{self.min_amount}/{self.max_amount}"

    @property
    def hashed_id(self) -> str:
        _modifier_data_to_hash = self.modifier_external_ids or ""
        _modifier_data_to_hash += f"{self.min_amount}/{self.max_amount}"

        return hashlib.md5(_modifier_data_to_hash.encode("utf-8")).hexdigest()


class Order(Base):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(primary_key=True)

    pos_id: Mapped[str] = mapped_column(String, nullable=False)
    starter_id: Mapped[str] = mapped_column(String, nullable=False)
    bonuses: Mapped[float] = mapped_column(Float, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    discount_price: Mapped[float] = mapped_column(Float, nullable=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    client: Mapped[Client] = relationship("Client", cascade="all, delete", back_populates="orders")

    def __repr__(self) -> str:
        return f"Order(id={self.id}, client_id={self.client_id}, pos_id={self.pos_id}, starter_id={self.starter_id}, done={self.done})"


class Discount(Base):
    __tablename__ = "discount"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)
    client: Mapped[Client] = relationship("Client", back_populates="discounts")

    starter_id: Mapped[str] = mapped_column(String, nullable=False)
    pos_id: Mapped[int] = mapped_column(Integer, nullable=False)
