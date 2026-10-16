"""Brand repository inputs use the same shape as Training Studio's settings."""

from studios_config import check_brand_repository, check_brand_release


def check_repository(value):
    return check_brand_repository(value)


def check_release(value, repository=None):
    return check_brand_release(value, repository)
