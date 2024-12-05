import pytest

from src.models import Modifier, Meal, ModifierOffer


@pytest.fixture
def rkeeper_menu_for_sync_meals():
    return {
        "name": "Касса",
        "isPossibleDelete": False,
        "categories": [
            {"id": "5", "name": "categoryName", "parentId": "parent"},
            {"id": "6", "name": "categoryName2", "parentId": "parent2"},
        ],
        "products": [
            {
                "id": "prodictId",
                "categoryId": "5",
                "name": "ProductName",
                "price": 500,
                "schemeId": "schemaId",
                "description": "description_string",
                "imageUrls": ["http://test2.com"],
                "measure": {"value": 0, "unit": "string"},
                "isContainInStopList": ["string"],
                "calories": 50,
                "energyValue": 40,
                "proteins": 30,
                "fats": 20,
                "carbohydrates": 10,
            },
            {
                "id": "prodictId2",
                "categoryId": "6",
                "name": "ProductName2",
                "price": 5000,
                "schemeId": "schemaId",
                "description": "description_string",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 0, "unit": "string"},
                "isContainInStopList": ["string"],
                "calories": 50,
                "energyValue": 40,
                "proteins": 30,
                "fats": 20,
                "carbohydrates": 10,
            },
        ],
        "ingredientsSchemes": [
            {
                "id": "IngredientSchemaId1",
                "ingredientsGroups": [{"id": "string", "minCount": 0, "maxCount": 0}],
            }
        ],
        "ingredientsGroups": [
            {
                "id": "IngredientGroupId",
                "name": "IngredientName",
                "ingredients": ["2222"],
            },
            {
                "id": "IngredientGroupId2",
                "name": "IngredientName2",
                "ingredients": ["3333"],
            },
        ],
        "ingredients": [
            {
                "id": 2222,
                "name": "IngredientName",
                "price": 100,
                "schemeId": "IngredientSchemaId1",
                "description": "description-ingredients",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 10, "unit": "string"},
            },
            {
                "id": 3333,
                "name": "IngredientName2",
                "price": 100,
                "schemeId": "IngredientSchemaId1",
                "description": "description-ingredients",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 10, "unit": "string"},
            },
            {
                "id": 4444,
                "name": "IngredientName3",
                "price": 100,
                "schemeId": "IngredientSchemaId1",
                "description": "description-ingredients",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 10, "unit": "string"},
            },
        ],
        "haveChanges": True,
        "dateModified": "2022-04-30T02:03:04.565+00:00",
    }


@pytest.fixture
def rkeeper_menu():
    return {
        "name": "Касса",
        "isPossibleDelete": False,
        "categories": [{"id": "55555", "name": "categoryName", "parentId": "parent"}],
        "products": [
            {
                "id": "prodictId",
                "categoryId": "55555",
                "externalId": "1111",
                "name": "ProductName",
                "price": 500,
                "schemeId": "IngredientSchemaId1",
                "description": "description_string",
                "imageUrls": ["http://vk.com"],
                "measure": {"value": 0, "unit": "string"},
                "isContainInStopList": ["string"],
                "calories": 50,
                "energyValue": 40,
                "proteins": 30,
                "fats": 20,
                "carbohydrates": 10,
            }
        ],
        "ingredientsSchemes": [
            {
                "id": "IngredientSchemaId1",
                "ingredientsGroups": [{"id": "IngredientGroupId", "minCount": 0, "maxCount": 1}],
            },
        ],
        "ingredientsGroups": [
            {
                "id": "IngredientGroupId",
                "name": "IngredientName",
                "ingredients": ["2222"],
            }
        ],
        "ingredients": [
            {
                "id": 2222,
                "name": "IngredientName",
                "price": 100,
                "schemeId": "IngredientSchemaId1",
                "externalId": "2222",
                "description": "description-ingredients",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 10, "unit": "string"},
            },
            {
                "id": 8888,
                "name": "IngredientName",
                "price": 100,
                "schemeId": "IngredientSchemaId1",
                "externalId": "8888",
                "description": "description-ingredients",
                "imageUrls": ["http://test.com"],
                "measure": {"value": 10, "unit": "string"},
            },
        ],
        "haveChanges": True,
        "dateModified": "2022-04-30T02:03:04.565+00:00",
    }


@pytest.fixture
def create_modifier(db_session):
    def wrapper(
        client_id: int = 1,
        starter_id: int = 1,
        pos_id: str = "modifier-pos-id-1",
        external_id: str = "1111",
        min_amount: int = 0,
        max_amount: int = 1,
    ):
        modifier = Modifier(
            client_id=client_id,
            pos_id=pos_id,
            external_id=external_id,
            starter_id=starter_id,
            min_amount=min_amount,
            max_amount=max_amount,
        )
        db_session.add(modifier)
        db_session.commit()
        return modifier

    return wrapper


@pytest.fixture
def create_meal(db_session):
    def wrapper(
        client_id: str = 1,
        starter_id: str = 1,
        pos_id: str = "meal-pos-id-1",
        external_id: str = "2222",
    ):
        meal = Meal(
            pos_id=pos_id,
            external_id=external_id,
            starter_id=starter_id,
            client_id=client_id,
        )
        db_session.add(meal)
        db_session.commit()
        return meal

    return wrapper


@pytest.fixture
def create_modifier_offer(db_session):
    def wrapper(
        modifier_id: int = 1,
        pos_id: str = "modifier-pos-id-1",
        starter_id: int = "333",
        shop_id: int = 1,
    ):
        modifier_offer = ModifierOffer(
            modifier_id=modifier_id,
            pos_id=pos_id,
            starter_id=starter_id,
            shop_id=shop_id,
        )
        db_session.add(modifier_offer)
        db_session.commit()
        return modifier_offer

    return wrapper
