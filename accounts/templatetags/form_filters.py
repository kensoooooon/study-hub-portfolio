from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    """フォームのフィールドにクラスを追加"""
    return field.as_widget(attrs={"class": css_class})
