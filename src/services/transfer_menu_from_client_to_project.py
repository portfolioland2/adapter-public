from sqlalchemy.orm import Session

from src.core.repositories.client import ClientRepository
from src.core.repositories.menu import MenuRepository
from src.models import Client
from src.schemas.rkeeper import RKeeperMenu, RKeeperModifiers


class MenuTransfer:
    def __init__(self, session: Session, client: Client, keeper_menu: RKeeperMenu):
        self.session = session
        self.client_repo = ClientRepository(session)
        self.menu_repo = MenuRepository(session)
        self.client = client
        self.keeper_menu = keeper_menu

    def transfer_modifiers(self) -> None:
        project_modifiers = self.menu_repo.get_modifiers_by_project_id(self.client.project_id)
        exist_modifier_map = {modifier.specific_id: modifier for modifier in project_modifiers}
        modifiers_pos_external_id_map = dict()

        modifier_data_by_id: dict[str, RKeeperModifiers] = {
            modifier.pos_id: modifier for modifier in self.keeper_menu.modifiers
        }
        modifier_group_by_id = {
            modifier_group.pos_id: modifier_group for modifier_group in self.keeper_menu.modifier_groups
        }

        for keeper_modifier_schema in self.keeper_menu.modifier_schemas:
            for keeper_modifier_group_in_schema in keeper_modifier_schema.modifier_groups:
                keeper_group = modifier_group_by_id[keeper_modifier_group_in_schema.id]
                for keeper_modifier_id in keeper_group.modifiers:
                    keeper_modifier = modifier_data_by_id[keeper_modifier_id]
                    modifiers_pos_external_id_map[keeper_modifier.pos_id] = str(keeper_modifier.external_id)
                    modifier_min_amount = 0
                    modifier_max_amount = keeper_modifier_group_in_schema.max_amount
                    if self.client.get_modifier_max_amount and keeper_modifier.max_amount:
                        modifier_max_amount = keeper_modifier.max_amount

                    specific_id = f"{keeper_modifier.pos_id}/{modifier_min_amount}/{modifier_max_amount}"
                    domain_modifier = exist_modifier_map.get(specific_id)
                    if not domain_modifier:
                        continue

                    if not domain_modifier.external_id:
                        domain_modifier.external_id = keeper_modifier.external_id
                        self.session.add(domain_modifier)

    def transfer_modifier_groups(self) -> None:
        domain_modifier_groups = self.menu_repo.get_modifier_groups_by_client_id(self.client.id)
        domain_modifier_groups_specific_map = {group.specific_id: group for group in domain_modifier_groups}

        modifier_pos_id_map = {modifier.pos_id: modifier for modifier in self.keeper_menu.modifiers}
        modifier_group_pos_id_map = {
            modifier_group.pos_id: modifier_group for modifier_group in self.keeper_menu.modifier_groups
        }

        for keeper_schema in self.keeper_menu.modifier_schemas:
            for modifier_group_in_schema in keeper_schema.modifier_groups:
                modifier_group = modifier_group_pos_id_map[modifier_group_in_schema.id]
                group_modifiers_external_ids = [
                    modifier_pos_id_map[group_modifier].external_id for group_modifier in modifier_group.modifiers
                ]
                old_specific_modifier_group_id = f"{modifier_group.pos_id}/{modifier_group_in_schema.min_amount}/{modifier_group_in_schema.max_amount}"

                group_modifiers_external_ids.sort()
                concat_group_modifiers_external_ids = "/".join(group_modifiers_external_ids)

                domain_group = domain_modifier_groups_specific_map.get(old_specific_modifier_group_id)
                if not domain_group:
                    continue

                domain_group.modifier_external_ids = concat_group_modifiers_external_ids
                self.session.add(domain_group)

    def transfer_meals(self) -> None:
        domain_meals = self.menu_repo.get_meals_by_client_id(self.client.id)
        if not domain_meals:
            return

        without_external_id_meal_pos_id_map = {meal.pos_id: meal for meal in domain_meals if not meal.external_id}
        for keeper_meal in self.keeper_menu.meals:
            if domain_meal := without_external_id_meal_pos_id_map.get(keeper_meal.pos_id):
                domain_meal.external_id = keeper_meal.external_id
                self.session.add(domain_meal)

        without_pos_id_meal_external_id_map = {
            meal.external_id: meal
            for meal in domain_meals
            if (meal.pos_id and meal.pos_id.isdigit() and meal.external_id)
        }
        for keeper_meal in self.keeper_menu.meals:
            if domain_meal := without_pos_id_meal_external_id_map.get(keeper_meal.external_id):
                domain_meal.pos_id = keeper_meal.pos_id
                self.session.add(domain_meal)
