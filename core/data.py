import random
import math

# --- Константы для Атрибутов ---

# Цвета
COLORS_TECH = ["Черный", "Белый", "Серебристый", "Серый космос", "Золотой", "Розовое золото", "Синий", "Зеленый", "Фиолетовый", "Красный"]
COLORS_CLOTHING_CLASSIC = ["Черный", "Белый", "Серый", "Темно-синий", "Бежевый", "Коричневый", "Хаки", "Бордовый"]
COLORS_CLOTHING_VIBRANT = ["Красный", "Ярко-синий", "Зеленый", "Желтый", "Оранжевый", "Розовый", "Голубой", "Бирюзовый", "Фиолетовый", "Лайм"]
COLORS_HOME_NEUTRAL = ["Белый", "Бежевый", "Серый", "Кремовый", "Слоновая кость", "Древесный", "Светло-коричневый"]
COLORS_GENERIC = ["Красный", "Синий", "Зеленый", "Черный", "Белый", "Желтый", "Оранжевый", "Фиолетовый", "Коричневый", "Серый"]
COLORS_JEWELRY = ["Золото", "Серебро", "Платина", "Розовое золото"]
COLORS_COSMETICS_NUDE = ["Бежевый", "Персиковый", "Светло-розовый", "Коричневый", "Карамельный"]
COLORS_COSMETICS_BRIGHT = ["Красный", "Бордовый", "Фуксия", "Коралловый", "Сливовый"]

# Размеры
# Телефоны/Планшеты/Ноутбуки (Память)
PHONE_RAM_OPTIONS = ["4GB", "6GB", "8GB", "12GB", "16GB"]
PHONE_ROM_OPTIONS = ["64GB", "128GB", "256GB", "512GB", "1TB"]
LAPTOP_RAM_OPTIONS = ["8GB", "16GB", "32GB", "64GB"]
LAPTOP_SSD_OPTIONS = ["256GB", "512GB", "1TB", "2TB"]

# Одежда
CLOTHES_SIZES_INT = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]
CLOTHES_SIZES_RU = [str(i) for i in range(40, 64, 2)] # 40, 42, ..., 62

# Обувь
RU_SHOES_CHILD = [str(i) for i in range(18, 36)]
RU_SHOES_WOMEN = [str(i) for i in range(35, 43)]
RU_SHOES_MEN = [str(i) for i in range(39, 48)]
RU_SHOES = sorted(list(set(RU_SHOES_WOMEN + RU_SHOES_MEN)))

# ТВ
TV_DIAGONALS = ["24\"", "32\"", "40\"", "43\"", "50\"", "55\"", "65\"", "75\"", "85\""]

# Разное
GENERIC_SIZE = ["Маленький", "Средний", "Большой", "Стандартный", "Универсальный"]
VOLUME_ML = ["50мл", "100мл", "150мл", "200мл", "250мл", "500мл", "1000мл"]
WEIGHT_G_KG = ["100г", "250г", "500г", "1кг", "2кг", "5кг"]
CAPACITY_L = ["1л", "1.5л", "2л", "5л", "10л", "20л"]
NONE_SIZE = [None] # Для товаров без размера

# --- Словари-Генераторы Атрибутов ---
# Эти функции будут вызываться по ключу

def generate_phone_variant():
    ram = random.choice(PHONE_RAM_OPTIONS)
    rom = random.choice(PHONE_ROM_OPTIONS)
    return f"{rom}/{ram}"

def generate_laptop_variant():
    ram = random.choice(LAPTOP_RAM_OPTIONS)
    ssd = random.choice(LAPTOP_SSD_OPTIONS)
    return f"{ssd}/{ram}"

SIZE_GENERATORS = {
    "PHONE_VARIANTS": generate_phone_variant,
    "LAPTOP_VARIANTS": generate_laptop_variant,
    "CLOTHES_INT": lambda: random.choice(CLOTHES_SIZES_INT),
    "CLOTHES_RU": lambda: random.choice(CLOTHES_SIZES_RU),
    "RU_SHOES_CHILD": lambda: random.choice(RU_SHOES_CHILD),
    "RU_SHOES_WOMEN": lambda: random.choice(RU_SHOES_WOMEN),
    "RU_SHOES_MEN": lambda: random.choice(RU_SHOES_MEN),
    "RU_SHOES": lambda: random.choice(RU_SHOES),
    "TV_DIAGONAL": lambda: random.choice(TV_DIAGONALS),
    "GENERIC": lambda: random.choice(GENERIC_SIZE),
    "VOLUME_ML": lambda: random.choice(VOLUME_ML),
    "WEIGHT_G_KG": lambda: random.choice(WEIGHT_G_KG),
    "CAPACITY_L": lambda: random.choice(CAPACITY_L),
    "NONE": lambda: None,
}

COLOR_GENERATORS = {
    "TECH": lambda: random.choice(COLORS_TECH),
    "CLOTHES_CLASSIC": lambda: random.choice(COLORS_CLOTHING_CLASSIC),
    "CLOTHES_VIBRANT": lambda: random.choice(COLORS_CLOTHING_VIBRANT),
    "CLOTHES_ANY": lambda: random.choice(COLORS_CLOTHING_CLASSIC + COLORS_CLOTHING_VIBRANT),
    "HOME_NEUTRAL": lambda: random.choice(COLORS_HOME_NEUTRAL),
    "GENERIC": lambda: random.choice(COLORS_GENERIC),
    "JEWELRY": lambda: random.choice(COLORS_JEWELRY),
    "COSMETICS_NUDE": lambda: random.choice(COLORS_COSMETICS_NUDE),
    "COSMETICS_BRIGHT": lambda: random.choice(COLORS_COSMETICS_BRIGHT),
    "COSMETICS_ANY": lambda: random.choice(COLORS_COSMETICS_NUDE + COLORS_COSMETICS_BRIGHT),
    "NONE": lambda: None, # Для товаров без цвета (продукты, книги и т.д.)
}

# --- Структура данных для типов товаров ---
# Каждый элемент - словарь, описывающий тип товара

PRODUCT_TYPES = [
    # --- Электроника ---
    {
        "category": "Электроника",
        "base_name": "Смартфон",
        "brands": ["Samsung", "Apple", "Xiaomi", "Realme", "OnePlus", "Google Pixel"],
        "models": {
            "Samsung": [("Galaxy S22", ["", "Plus", "Ultra"]), ("Galaxy S23", ["", "Plus", "Ultra"]), ("Galaxy S24", ["", "Plus", "Ultra"]), ("Galaxy A54", [""]), ("Galaxy Z Fold 5", [""]), ("Galaxy Z Flip 5", [""])],
            "Apple": [("iPhone 14", ["", "Plus", "Pro", "Pro Max"]), ("iPhone 15", ["", "Plus", "Pro", "Pro Max"]), ("iPhone 16", ["", "Plus", "Pro", "Pro Max"]), ("iPhone SE", [""])], # Добавим гипотетический 16
            "Xiaomi": [("13", ["", "Pro", "Ultra", "Lite"]), ("14", ["", "Pro"]), ("Redmi Note 12", ["", "Pro"]), ("Redmi Note 13", ["", "Pro", "Pro+"]), ("Poco F5", ["", "Pro"])],
            "Realme": [("11", ["", "Pro", "Pro+"]), ("12", ["", "Pro", "Pro+"]), ("GT Neo 5", [""]), ("GT 5", ["", "Pro"])],
            "OnePlus": [("11", [""]), ("12", [""]), ("Nord 3", [""])],
            "Google Pixel": [("7", ["", "Pro"]), ("8", ["", "Pro"]), ("7a", [""]), ("Fold", [""])],
        },
        "size_generator": "PHONE_VARIANTS",
        "color_generator": "TECH",
        "base_price_range": (20000, 150000),
        "variant_price_modifier": {"Plus": 1.1, "Pro": 1.2, "Ultra": 1.4, "Max": 1.3, "Lite": 0.8, "Fold": 1.8, "Flip": 1.5, "Pro+": 1.25} # Множители к цене
    },
    {
        "category": "Электроника",
        "base_name": "Ноутбук",
        "brands": ["Apple", "Asus", "Lenovo", "HP", "Dell", "Acer", "MSI", "Huawei"],
        "models": {
            "Apple": [("MacBook Air", ["M1", "M2", "M3"]), ("MacBook Pro", ["13 M2", "14 Pro", "16 Pro", "14 Max", "16 Max"])],
            "Asus": [("Zenbook", ["14", "15", "Flip"]), ("Vivobook", ["15", "16", "S"]), ("ROG Strix", ["G15", "G17", "SCAR"]), ("TUF Gaming", ["A15", "F17"])],
            "Lenovo": [("ThinkPad", ["X1 Carbon", "T14", "E15"]), ("Yoga", ["Slim 7", "9i"]), ("Legion", ["5 Pro", "7 Slim"]), ("IdeaPad", ["3", "5 Gaming"])],
            "HP": [("Spectre", ["x360 14", "x360 16"]), ("Envy", ["13", "x360 15"]), ("Pavilion", ["15", "Aero 13"]), ("Omen", ["16", "17"])],
            # Добавить больше моделей для Dell, Acer, MSI, Huawei по аналогии
        },
        "size_generator": "LAPTOP_VARIANTS",
        "color_generator": "TECH",
        "base_price_range": (40000, 250000),
        "variant_price_modifier": {"Pro": 1.3, "Max": 1.5, "Gaming": 1.2, "Slim": 1.1, "Carbon": 1.4, "SCAR": 1.6}
    },
    {
        "category": "Электроника",
        "base_name": "Планшет",
        "brands": ["Apple", "Samsung", "Xiaomi", "Huawei", "Lenovo"],
        "models": {
            "Apple": [("iPad", ["", "Air", "Pro", "mini"])],
            "Samsung": [("Galaxy Tab S8", ["", "+", "Ultra"]), ("Galaxy Tab S9", ["", "+", "Ultra", "FE"])],
            "Xiaomi": [("Pad 6", ["", "Pro"])],
            # Добавить Huawei, Lenovo
        },
        "size_generator": "PHONE_VARIANTS", # Используем те же опции памяти
        "color_generator": "TECH",
        "base_price_range": (15000, 120000),
        "variant_price_modifier": {"Pro": 1.4, "Ultra": 1.6, "Air": 1.2, "+": 1.15, "FE": 0.9, "mini": 0.85}
    },
     {
        "category": "Электроника",
        "base_name": "Телевизор",
        "brands": ["Samsung", "LG", "Sony", "Xiaomi", "TCL", "Philips", "Hisense"],
        "models": { brand: [("QLED", [""]), ("OLED", [""]), ("Neo QLED", [""]), ("Crystal UHD", [""]), ("The Frame", [""])] for brand in ["Samsung", "LG", "Sony", "Xiaomi", "TCL", "Philips", "Hisense"] }, # Упрощенная модель
        "size_generator": "TV_DIAGONAL",
        "color_generator": "TECH", # Обычно черный или серебристый корпус
        "base_price_range": (15000, 500000),
        "variant_price_modifier": {"OLED": 1.8, "Neo QLED": 1.6, "QLED": 1.3, "The Frame": 1.4}
    },
     {
        "category": "Электроника",
        "base_name": "Наушники",
        "brands": ["Apple", "Sony", "Samsung", "JBL", "Sennheiser", "Bose", "Xiaomi", "Marshall"],
        "models": {
             "Apple": [("AirPods", ["2", "3", "Pro", "Pro 2"]), ("AirPods Max", [""])],
             "Sony": [("WH-1000XM4", [""]), ("WH-1000XM5", [""]), ("WF-1000XM4", [""]), ("WF-1000XM5", [""])],
             "Samsung": [("Galaxy Buds", ["2", "2 Pro", "FE", "Live"])],
             # Добавить другие бренды и модели (TWS, накладные, полноразмерные)
        },
        "size_generator": "NONE", # Размер обычно не указывается так
        "color_generator": "TECH",
        "base_price_range": (1500, 45000),
         "variant_price_modifier": {"Pro": 1.5, "Max": 2.5}
    },
    # --- Одежда ---
    {
        "category": "Одежда",
        "base_name": "Футболка",
        "brands": ["Nike", "Adidas", "Puma", "Reebok", "Levi's", "Tommy Hilfiger", "Calvin Klein", "Zara", "H&M", "Uniqlo", "ТВОЕ"],
        "models": { brand: [("Базовая", [""]), ("С принтом", [""]), ("Поло", [""]), ("Оверсайз", [""])] for brand in ["Nike", "Adidas", "Puma", "Reebok", "Levi's", "Tommy Hilfiger", "Calvin Klein", "Zara", "H&M", "Uniqlo", "ТВОЕ"] },
        "size_generator": "CLOTHES_INT", # или CLOTHES_RU
        "color_generator": "CLOTHES_ANY",
        "base_price_range": (500, 5000),
        "variant_price_modifier": {"Поло": 1.3, "Оверсайз": 1.1}
    },
    {
        "category": "Одежда",
        "base_name": "Джинсы",
        "brands": ["Levi's", "Wrangler", "Lee", "Diesel", "Calvin Klein Jeans", "G-Star RAW", "Colin's", "Gloria Jeans"],
        "models": { brand: [("Slim Fit", [""]), ("Regular Fit", [""]), ("Skinny", [""]), ("Loose Fit", [""]), ("Bootcut", [""])] for brand in ["Levi's", "Wrangler", "Lee", "Diesel", "Calvin Klein Jeans", "G-Star RAW", "Colin's", "Gloria Jeans"] },
        "size_generator": "CLOTHES_RU", # Часто указывают W/L, но для простоты RU
        "color_generator": "CLOTHES_CLASSIC", # В основном синие, черные, серые
        "base_price_range": (2000, 15000),
    },
     {
        "category": "Одежда",
        "base_name": "Куртка",
        "brands": ["The North Face", "Canada Goose", "Columbia", "Nike", "Adidas", "Zara", "Bask", "Finn Flare"],
        "models": { brand: [("Пуховик", [""]), ("Ветровка", [""]), ("Демисезонная", [""]), ("Парка", [""]), ("Бомбер", [""])] for brand in ["The North Face", "Canada Goose", "Columbia", "Nike", "Adidas", "Zara", "Bask", "Finn Flare"] },
        "size_generator": "CLOTHES_INT",
        "color_generator": "CLOTHES_ANY",
        "base_price_range": (3000, 80000),
        "variant_price_modifier": {"Пуховик": 1.5, "Парка": 1.3}
    },
    # --- Обувь ---
     {
        "category": "Обувь",
        "base_name": "Кроссовки",
        "brands": ["Nike", "Adidas", "New Balance", "Reebok", "Puma", "Asics", "Salomon", "Hoka"],
        "models": {
             "Nike": [("Air Force 1", [""]), ("Air Max", ["90", "95", "270", "Plus"]), ("Dunk", ["Low", "High"]), ("Jordan 1", ["Low", "Mid", "High"])],
             "Adidas": [("Superstar", [""]), ("Stan Smith", [""]), ("Gazelle", [""]), ("Forum", ["Low", "Mid"]), ("Yeezy", ["350 V2", "500", "700"])], # Добавим Yeezy для примера
             "New Balance": [("574", [""]), ("990", ["v3", "v4", "v5", "v6"]), ("327", [""]), ("530", [""])],
             # Добавить другие бренды/модели
         },
        "size_generator": "RU_SHOES",
        "color_generator": "CLOTHES_ANY", # Кроссовки бывают разных цветов
        "base_price_range": (3000, 25000),
         "variant_price_modifier": {"Yeezy": 2.0, "Jordan 1 High": 1.5, "Air Force 1": 1.1, "990": 1.8}
    },
    {
        "category": "Обувь",
        "base_name": "Туфли женские",
        "brands": ["ECCO", "Geox", "Salamander", "Rieker", "Tamaris", "Guess", "Michael Kors"],
        "models": { brand: [("Лодочки", [""]), ("На каблуке", [""]), ("На платформе", [""]), ("Балетки", [""]), ("Лоферы", [""])] for brand in ["ECCO", "Geox", "Salamander", "Rieker", "Tamaris", "Guess", "Michael Kors"] },
        "size_generator": "RU_SHOES_WOMEN",
        "color_generator": "CLOTHES_CLASSIC",
        "base_price_range": (2500, 20000),
    },
    # --- Косметика и Парфюмерия ---
    {
        "category": "Косметика и Парфюмерия",
        "base_name": "Туалетная вода",
        "brands": ["Chanel", "Dior", "Gucci", "Versace", "Dolce & Gabbana", "Paco Rabanne", "Hugo Boss", "Calvin Klein"],
        "models": { # Модели тут - названия ароматов
            "Chanel": [("Bleu de Chanel", [""]), ("Coco Mademoiselle", [""]), ("Chance Eau Tendre", [""])],
            "Dior": [("Sauvage", [""]), ("J'adore", [""]), ("Miss Dior", [""])],
            "Paco Rabanne": [("1 Million", [""]), ("Invictus", [""]), ("Lady Million", [""])],
            # Добавить другие
        },
        "size_generator": "VOLUME_ML", # Объем флакона
        "color_generator": "NONE", # Цвет не важен, важен аромат (который мы не генерим)
        "base_price_range": (3000, 15000),
    },
    {
        "category": "Косметика и Парфюмерия",
        "base_name": "Крем для лица",
        "brands": ["La Roche-Posay", "Vichy", "CeraVe", "Clinique", "Estée Lauder", "Nivea", "L'Oréal Paris", "Garnier"],
        "models": { brand: [("Увлажняющий", [""]), ("Антивозрастной", [""]), ("Для проблемной кожи", [""]), ("Солнцезащитный SPF30", [""]), ("Солнцезащитный SPF50", [""])] for brand in ["La Roche-Posay", "Vichy", "CeraVe", "Clinique", "Estée Lauder", "Nivea", "L'Oréal Paris", "Garnier"] },
        "size_generator": "VOLUME_ML",
        "color_generator": "NONE",
        "base_price_range": (300, 8000),
        "variant_price_modifier": {"Антивозрастной": 1.4, "Солнцезащитный SPF50": 1.2}
    },
    # --- Товары для дома ---
    {
        "category": "Товары для дома",
        "base_name": "Постельное белье",
        "brands": ["Togas", "Asabella", "Cleo", "Valtery", "TAC", "Arya Home"],
        "models": { brand: [("Двуспальное", [""]), ("Евро", [""]), ("Семейное", [""]), ("Полуторное", [""])] for brand in ["Togas", "Asabella", "Cleo", "Valtery", "TAC", "Arya Home"] },
        "size_generator": "GENERIC", # Тип комплекта как размер
        "color_generator": "HOME_NEUTRAL", # Часто нейтральные или с узорами
        "base_price_range": (2000, 15000),
    },
    # --- Книги ---
    {
        "category": "Книги",
        "base_name": "Книга", # Очень обобщенно
        "brands": ["Эксмо", "АСТ", "МИФ", "Альпина Паблишер", "Азбука-Аттикус", "Росмэн"], # Издательства как бренды
        "models": { # Жанры/типы как модели
            "Эксмо": [("Современный детектив", [""]), ("Российская фантастика", [""]), ("Психология и саморазвитие", [""])],
            "АСТ": [("Зарубежная классика", [""]), ("Исторический роман", [""]), ("Молодежная проза (Young Adult)", [""])],
            "МИФ": [("Бизнес-литература", [""]), ("Творчество и дизайн", [""]), ("Детские развивающие книги", [""])],
             # Добавить другие
        },
        "size_generator": "NONE", # Размер - кол-во страниц, не используется здесь
        "color_generator": "NONE", # Обложка имеет цвет, но не является ключевым атрибутом
        "base_price_range": (300, 2500),
    },
    # --- Продукты питания ---
    {
        "category": "Продукты питания",
        "base_name": "Кофе молотый",
        "brands": ["Lavazza", "Jacobs", "Jardin", "Paulig", "Kimbo", "Illy"],
        "models": { brand: [("Espresso", [""]), ("Crema e Gusto", [""]), ("Arabica", [""]), ("Robusta", [""])] for brand in ["Lavazza", "Jacobs", "Jardin", "Paulig", "Kimbo", "Illy"] },
        "size_generator": "WEIGHT_G_KG", # Вес упаковки
        "color_generator": "NONE",
        "base_price_range": (250, 1500),
    },
    # --- Добавить еще категории по аналогии: ---
    # Зоотовары (Корм для кошек/собак, Наполнитель)
    # Детские товары (Подгузники, Конструктор Lego)
    # Спорттовары (Велосипед, Гантели)
    # Автотовары (Шины, Моторное масло)
    # ... и т.д.
]

# --- Функция генерации процедурного имени ---
def generate_procedural_name(base_name, brand, models_config):
    """Генерирует полное имя товара на основе бренда и модели."""
    if brand not in models_config or not models_config[brand]:
        # Если для бренда нет моделей или конфиг пуст, возвращаем базовое имя + бренд
        return f"{brand} {base_name}"

    model_options = models_config[brand]
    base_model, variants = random.choice(model_options) # Выбираем базовую модель и её варианты

    chosen_variant = random.choice(variants) if variants else "" # Выбираем вариант (может быть пустым)

    # Собираем имя
    full_name_parts = [brand, base_model, chosen_variant]
    full_name = " ".join(part for part in full_name_parts if part) # Убираем пустые строки

    # Иногда базовая модель уже включает тип товара, избегаем дублирования
    if base_name.lower() in base_model.lower():
         return full_name
    elif base_model.lower().startswith(brand.lower()): # Если модель начинается с бренда (Apple MacBook)
        name_parts_no_base = [base_model, chosen_variant]
        return " ".join(part for part in name_parts_no_base if part)
    else:
        # Стандартный случай: Бренд + Модель + Вариант
        return full_name


# --- Основная функция генератора ---
def generate_product():
    """Генерирует один случайный товар с атрибутами."""
    product_type = random.choice(PRODUCT_TYPES)

    category = product_type["category"]
    base_name = product_type["base_name"]
    brands = product_type["brands"]
    models_config = product_type.get("models", {}) # .get чтобы избежать ошибки, если 'models' нет
    size_gen_key = product_type["size_generator"]
    color_gen_key = product_type["color_generator"]
    base_price_range = product_type["base_price_range"]
    variant_modifiers = product_type.get("variant_price_modifier", {})

    # 1. Выбрать бренд
    brand = random.choice(brands)

    # 2. Сгенерировать имя (модель + вариант)
    # Немного переделаем логику, чтобы вариант влиял на цену
    chosen_model_info = None
    chosen_variant = ""
    if brand in models_config and models_config[brand]:
         model_options = models_config[brand]
         chosen_model_info = random.choice(model_options)
         base_model, variants = chosen_model_info
         if variants:
             chosen_variant = random.choice(variants)

         # Собираем имя
         full_name_parts = [brand, base_model, chosen_variant]
         name = " ".join(part for part in full_name_parts if part)
         # Корректировка имени (если нужно)
         if base_name.lower() in base_model.lower():
             name_parts_no_base = [brand, base_model, chosen_variant]
             name = " ".join(part for part in name_parts_no_base if part)
         elif base_model.lower().startswith(brand.lower()):
             name_parts_no_base = [base_model, chosen_variant]
             name = " ".join(part for part in name_parts_no_base if part)

    else: # Если моделей для бренда нет
        name = f"{base_name} {brand}"


    # 3. Сгенерировать размер
    size_func = SIZE_GENERATORS.get(size_gen_key, lambda: None) # Безопасное получение функции
    size = size_func()

    # 4. Сгенерировать цвет
    color_func = COLOR_GENERATORS.get(color_gen_key, lambda: None)
    color = color_func()

    # 5. Сгенерировать цену
    price_mod = 1.0
    # Ищем модификатор для выбранного варианта
    if chosen_variant and chosen_variant in variant_modifiers:
        price_mod = variant_modifiers[chosen_variant]
    else:
        # Если нет точного совпадения варианта, ищем модификатор для части варианта (напр., "Pro" в "16 Pro")
        for mod_key, mod_value in variant_modifiers.items():
            if mod_key in chosen_variant:
                 price_mod = mod_value
                 break # Берем первый попавшийся
        # Можно добавить модификатор для базовой модели если варианта нет
        # elif base_model and base_model in variant_modifiers:
        #     price_mod = variant_modifiers[base_model]


    # Добавляем немного случайности к базовой цене
    base_price = random.uniform(base_price_range[0], base_price_range[1])
    
    # Рассчитываем финальную цену с учетом модификатора
    final_price = base_price * price_mod

    # Генерируем диапазон цен (например, +/- 15-20% от расчетной цены)
    price_variation = random.uniform(0.15, 0.25)
    price_low = max(10, math.floor(final_price * (1 - price_variation) / 10) * 10) # Округляем до 10 вниз, минимум 10
    price_max = math.ceil(final_price * (1 + price_variation) / 10) * 10  # Округляем до 10 вверх

    # Убедимся что low < max
    if price_low >= price_max:
        price_max = price_low + random.randint(1, 5) * 10 # Добавляем небольшую разницу

    # Корректировка цены для дорогих товаров (чтобы не было слишком маленького разброса)
    if price_max > 50000 and price_max - price_low < 2000:
         price_max += 2000
    elif price_max > 10000 and price_max - price_low < 500:
         price_max += 500


    return name, size, color, price_low, price_max

# --- Пример использования ---
if __name__ == "__main__":
    
    print("Примеры сгенерированных товаров:")
    for _ in range(20): # Сгенерируем 20 примеров
        product_data = generate_product()
        # Форматируем вывод для наглядности (убираем None из строки)
        name, size, color, price_low, price_max = product_data
        size_str = f'"{size}"' if size is not None else "N/A"
        color_str = f'"{color}"' if color is not None else "N/A"
        print(f'"{name}", {size_str}, {color_str}, {price_low}, {price_max}')

    # Проверка количества уникальных комбинаций (примерная оценка)
    # Уникальность сильно зависит от наполнения PRODUCT_TYPES
    # Давайте грубо оценим для смартфонов:
    # Бренды: 6
    # Модели/Варианты (очень грубо): ~10-15 на бренд -> ~75
    # Размеры (Память): 5 * 5 = 25
    # Цвета: 10
    # Итого только для смартфонов: 6 * 75 * 25 * 10 = 112,500 теоретических комбинаций (многие будут нереалистичны, но потенциал большой)
    # С учетом других категорий, достичь 10k уникальных *правдоподобных* вызовов вполне реально.
