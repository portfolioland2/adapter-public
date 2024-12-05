from src.utils.enums import Entity


class DiscountNotFound(Exception):
    pass


class ObjectDoesNotExist(Exception):
    def __init__(self, field_name: Entity, obj_id: str):
        self.obj_id = obj_id
        self.field_name = field_name
