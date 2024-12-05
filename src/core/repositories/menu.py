from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from starter_dto.pos.base import ObjectOut

from src.core.repositories.schemas.client import MealStarterCreated, MealOfferStarterCreated
from src.models import Category, Meal, ModifierGroup, Modifier, MealOffer, Client, ModifierOffer


class MenuRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_meals_by_client_id(self, client_id: int) -> Sequence[Meal]:
        return (
            self.session.scalars(select(Meal).where(Meal.client_id == client_id).options(joinedload(Meal.offers)))
            .unique()
            .all()
        )

    def get_categories_by_client_id(self, client_id: int) -> Sequence[Category]:
        return self.session.scalars(select(Category).where(Category.client_id == client_id)).all()

    def get_modifier_groups_by_client_id(self, client_id: int) -> Sequence[ModifierGroup]:
        return self.session.scalars(select(ModifierGroup).where(ModifierGroup.client_id == client_id)).all()

    def get_modifiers_by_client_id(self, client_id: int) -> Sequence[Modifier]:
        return (
            self.session.scalars(
                select(Modifier).options(joinedload(Modifier.offers)).where(Modifier.client_id == client_id)
            )
            .unique()
            .all()
        )

    def create_categories(self, client_id: int, categories: list[ObjectOut]) -> None:
        db_categories = [Category(pos_id=item.pos_id, starter_id=item.id, client_id=client_id) for item in categories]
        self.session.add_all(db_categories)

    def create_meals(self, client_id: int, new_meals: list[MealStarterCreated]) -> None:
        db_meals = [
            Meal(pos_id=meal.pos_id, starter_id=meal.id, external_id=meal.external_id, client_id=client_id)
            for meal in new_meals
        ]
        self.session.add_all(db_meals)

    def create_meal_offers(self, meals: list[MealOfferStarterCreated], shop_id: int) -> None:
        meal_offers = [
            MealOffer(meal_id=meal.meal_id, pos_id=meal.pos_id, starter_id=meal.id, shop_id=shop_id) for meal in meals
        ]
        self.session.add_all(meal_offers)

    def get_project_modifier_by_starter_ids(
        self, project_id: int, modifier_starter_ids: set[int]
    ) -> Sequence[Modifier]:
        return self.session.scalars(
            select(Modifier).where(
                Modifier.client.has(Client.project_id == project_id), Modifier.starter_id.in_(modifier_starter_ids)
            )
        ).all()

    def get_meals_by_client_id_and_starter_id(self, client_id: int, starter_ids: list[int]) -> Sequence[Meal]:
        return self.session.scalars(
            select(Meal).where(Meal.client_id == client_id, Meal.starter_id.in_(starter_ids))
        ).all()

    def get_modifier_by_client_id_and_starter_ids(
        self, client_id: int, modifier_starter_ids: list[int]
    ) -> Sequence[Modifier]:
        return self.session.scalars(
            select(Modifier).where(Modifier.client_id == client_id, Modifier.starter_id.in_(modifier_starter_ids))
        ).all()

    def get_modifiers_by_project_id(self, project_id: int) -> Sequence[Modifier]:
        return self.session.scalars(
            select(Modifier).where(Modifier.client.has(Client.project_id == project_id)).order_by(Modifier.id.desc())
        ).all()

    def get_modifiers_with_offers_by_project_id(self, project_id: int) -> Sequence[Modifier]:
        return self.session.scalars(
            select(Modifier).where(Modifier.client.has(Client.project_id == project_id)).order_by(Modifier.id.desc())
        ).all()

    def get_modifier_groups_by_project_id(self, project_id: int) -> Sequence[ModifierGroup]:
        return self.session.scalars(
            select(ModifierGroup)
            .where(ModifierGroup.client.has(Client.project_id == project_id))
            .order_by(ModifierGroup.id)
        ).all()

    def get_modifiers_with_offers_by_client_id(self, client_id: int) -> Sequence[Modifier]:
        return (
            self.session.scalars(
                select(Modifier)
                .where(Modifier.client_id == client_id)
                .options(joinedload(Modifier.offers))
                .order_by(Modifier.id.desc())
            )
            .unique()
            .all()
        )

    def get_modifier_offers_with_modifiers_by_shop_id(self, shop_id: int) -> Sequence[ModifierOffer]:
        return (
            self.session.scalars(
                select(ModifierOffer)
                .where(ModifierOffer.shop_id == shop_id)
                .options(joinedload(ModifierOffer.modifier))
                .order_by(ModifierOffer.id.desc())
            )
            .unique()
            .all()
        )
