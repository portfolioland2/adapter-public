from typing import Generator


def generate_batch(source_list: list, batch_size: int = 300) -> Generator:
    for batch_start_index in range(0, len(source_list), batch_size):
        yield source_list[batch_start_index : batch_start_index + batch_size]
