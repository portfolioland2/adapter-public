from typing import TypeAlias, Sequence

from sqlalchemy import update, select
from starter_dto.pos.base import ObjectOut

from src.core.repositories.schemas.client import ClientUpdate, ClientCreate
from sqlalchemy.orm import Session
from src.exceptions import ObjectDoesNotExist
from src.models import Client, Shop, Category, Project
from src.utils.enums import Entity


PosId: TypeAlias = str
StarterId: TypeAlias = int
ExternalId: TypeAlias = str


class ClientRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_clients(self) -> Sequence[Client]:
        return self.session.scalars(select(Client).where(Client.is_active.is_(True))).all()

    def update_client(self, client_id: int, client_update_data: ClientUpdate) -> None:
        client_data = client_update_data.dict(exclude_unset=True)
        if client_data:
            self.session.execute(update(Client).where(Client.id == client_id).values(client_data))

    def get_shops(self, client_id: int) -> Sequence[Shop]:
        return self.session.scalars(select(Shop).where(Shop.client_id == client_id)).all()

    def get_shop_by_pos_id(self, client_id: int, pos_id: str) -> Shop:
        shop = self.session.scalar(select(Shop).where(Shop.pos_id == pos_id, Shop.client_id == client_id))
        if not shop:
            raise ObjectDoesNotExist(Entity.SHOP, pos_id)

        return shop

    def get_shop_by_starter_id(self, client_id: int, starter_id: int) -> Shop:
        shop = self.session.scalar(select(Shop).where(Shop.starter_id == starter_id, Shop.client_id == client_id))
        if not shop:
            raise ObjectDoesNotExist(Entity.SHOP, str(starter_id))

        return shop

    def get_client_by_api_key(self, client_api_key: str) -> Client | None:
        return self.session.query(Client).where(Client.api_key == client_api_key).first()

    def create_shops(self, client_id: int, shops_data: list[ObjectOut]) -> None:
        shops = [
            Shop(pos_id=shop_data.pos_id, starter_id=shop_data.id, client_id=client_id) for shop_data in shops_data
        ]

        self.session.add_all(shops)

    def get_client_by_client_id(self, client_id: str) -> Client:
        client = self.session.scalar(select(Client).where(Client.client_id == client_id))
        if not client:
            raise ObjectDoesNotExist(Entity.CLIENT, client_id)

        return client

    def get_or_create_client(self, client_data: ClientCreate, project_name: str) -> tuple[Client, bool]:
        is_created = False

        try:
            client = self.get_client_by_client_id(client_data.client_id)
        except ObjectDoesNotExist:
            is_created = True
            project, _ = self.get_or_create_project(project_name)
            client_data.project_id = project.id
            client = Client(**client_data.dict(exclude_none=True))
            self.session.add(client)
            self.session.flush()

        return client, is_created

    def get_or_create_project(self, project_name: str) -> tuple[Project, bool]:
        is_created = False
        project = self.session.query(Project).where(Project.title == project_name).first()

        if not project:
            is_created = True
            project = Project(title=project_name)
            self.session.add(project)
            self.session.flush()

        return project, is_created

    def get_category_by_client_id_and_pos_ids(
        self, client_id: int, rkeeper_category_pos_ids: set[str]
    ) -> Sequence[Category]:
        return self.session.scalars(
            select(Category).where(Category.client_id == client_id, Category.pos_id.in_(rkeeper_category_pos_ids))
        ).all()
