"""Brand repository inputs use the same shape as Training Studio's settings."""

from studios_config import check_brand_repository


def check_repository(value):
    return check_brand_repository(value)
