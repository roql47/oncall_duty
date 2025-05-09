from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """딕셔너리에서 키로 값을 조회하는 필터"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def index(list_data, i):
    """리스트에서 인덱스로 항목을 조회하는 필터"""
    if list_data is None:
        return None
    try:
        return list_data[i]
    except (IndexError, TypeError):
        return None 