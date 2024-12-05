from enum import Enum


class Entity(str, Enum):
    CLIENT = "Client"
    SHOP = "Shop"
    CATEGORY = "Category"
    MODIFIER = "Modifier"
    MODIFIER_GROUP = "ModifierGroup"
    MEAL = "Meal"
    MEAL_OFFER = "MealOffer"
    ORDER = "Order"
