from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Умножает значение на аргумент"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Делит значение на аргумент"""
    try:
        arg = float(arg)
        if arg == 0:
            return 0
        return float(value) / arg
    except (ValueError, TypeError):
        return 0

@register.filter
def hash_to_color(value):
    """Генерирует цвет на основе значения (обычно ID)"""
    colors = [
        '#3498db', '#2ecc71', '#e74c3c', '#f39c12', 
        '#9b59b6', '#1abc9c', '#d35400', '#c0392b',
        '#16a085', '#27ae60', '#2980b9', '#8e44ad'
    ]
    
    try:
        # Преобразуем значение в строку, чтобы работать с любыми типами
        value_str = str(value)
        
        # Простая хэш-функция для выбора цвета
        hash_val = 0
        for char in value_str:
            hash_val = ord(char) + ((hash_val << 5) - hash_val)
        
        # Выбираем цвет из набора
        color_index = abs(hash_val) % len(colors)
        return colors[color_index]
    except:
        # В случае ошибки возвращаем стандартный синий цвет
        return '#3498db'