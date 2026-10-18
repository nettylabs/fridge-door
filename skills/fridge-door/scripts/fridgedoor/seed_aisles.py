"""The bundled lookup that files common grocery items into aisles, and the item-name key everything shares.

The household's own corrections always win over this list (shopping.py). Keys go through item_key(), the same
rule that keys purchase history and corrections, so "Eggs", "egg" and " eggs " are one item.
"""

from __future__ import annotations

import re

from .util import fold

# Words that look plural but aren't, or whose singular would be confusing.
_KEEP = {
    "hummus", "couscous", "asparagus", "molasses", "swiss", "brussels", "series", "species", "news", "citrus",
    "octopus", "bananas foster", "grits", "oats", "lentils", "chips", "fries", "nuts", "greens", "herbs",
}  # fmt: skip


def _singular(word: str) -> str:
    if word in _KEEP or len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"  # berries -> berry, cookies -> cooky (cookie -> cooky too, below)
    if word.endswith("ie") and len(word) > 4:
        return word[:-2] + "y"
    if word.endswith("oes") and len(word) > 5:
        return word[:-2]  # tomatoes -> tomato, potatoes -> potato
    if word.endswith(("ches", "shes", "xes", "sses", "zzes")):
        return word[:-2]  # peaches -> peach, radishes -> radish, boxes -> box
    if word.endswith("s"):
        return word[:-1]
    return word


def item_key(name) -> str:
    """Matching key for an item: lower case, no accents, single spaces, the last word made singular.

    It only has to be stable, not good English: "cookies" and "cookie" both become "cooky".
    """
    text = re.sub(r"[^\w\s&'-]", " ", fold(name))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    words = text.split(" ")
    if " ".join(words) in _KEEP:
        return text
    words[-1] = _singular(words[-1])
    key = " ".join(words)
    if words[-1] == "cheese" and len(words) > 1 and words[-2] in _CHEESES:
        return " ".join(words[:-1])  # "cheddar cheese" is cheddar
    return _SAME_THING.get(key, key)


_CHEESES = {"cheddar", "mozzarella", "parmesan", "feta", "brie", "gouda", "halloumi", "ricotta", "paneer", "swiss",
            "monterey", "colby", "provolone", "gruyere", "emmental", "manchego", "pecorino", "stilton", "camembert",
            "edam", "havarti", "jarlsberg", "mascarpone"}  # fmt: skip
_SAME_THING = {"garlic clove": "garlic", "clove of garlic": "garlic", "egg yolk": "egg", "egg white": "egg"}


_RAW = {
    "Produce": [
        "apples", "bananas", "oranges", "lemons", "limes", "grapes", "strawberries", "blueberries", "raspberries",
        "blackberries", "watermelon", "cantaloupe", "pineapple", "mango", "peaches", "pears", "plums", "kiwi",
        "cherries", "avocado", "tomatoes", "cherry tomatoes", "potatoes", "sweet potatoes", "onions", "red onions",
        "garlic", "carrots", "celery", "broccoli", "cauliflower", "spinach", "lettuce", "romaine", "kale",
        "cucumber", "zucchini", "courgette", "eggplant", "aubergine", "bell peppers", "capsicum", "berries",
        "mushrooms", "cilantro", "coriander", "parsley", "basil", "mint", "ginger", "green onions", "spring onions",
        "scallions", "leeks", "beets", "beetroot", "cabbage", "corn on the cob", "green beans", "snow peas",
        "mangetout", "asparagus", "brussels sprouts", "butternut squash", "pumpkin", "rocket", "arugula",
        "salad greens", "salad", "herbs", "chillies", "jalapenos", "swede", "turnip", "parsnips", "radishes",
        "tofu", "fresh herbs", "lemongrass", "bok choy", "pak choi", "rockmelon", "melon",
        "red peppers", "green peppers", "yellow peppers", "orange peppers", "baby carrots", "brown onions",
        "white onions", "shallots", "thyme", "rosemary", "dill", "chives", "sage", "spring greens", "corn",
        "sweet corn", "nectarines", "apricots", "figs", "pomegranate", "grapefruit", "clementines", "mandarins",
        "satsumas", "fennel", "okra", "edamame", "bean sprouts", "beansprouts", "chili peppers", "chilli peppers",
        "hot peppers", "sweet peppers",
    ],
    "Bakery": [
        "bread", "sourdough", "bagels", "tortillas", "wraps", "buns", "rolls", "hamburger buns", "hot dog buns",
        "croissants", "muffins", "english muffins", "crumpets", "pita", "naan", "baguette", "cake", "donuts",
        "pitta", "pitta bread", "scones", "loaf", "garlic bread", "brioche", "flatbread",
    ],
    "Deli": [
        "ham", "deli turkey", "salami", "prosciutto", "hummus", "rotisserie chicken", "olives", "deli meat",
        "sliced turkey", "pastrami", "pate", "dips", "chorizo", "pepperoni",
    ],
    "Meat": [
        "chicken breast", "chicken thighs", "chicken", "chicken wings", "ground beef", "beef mince", "mince",
        "minced beef", "steak", "pork chops", "pork", "bacon", "sausages", "ground turkey",
        "chicken mince", "hot dogs", "lamb", "lamb chops", "roast beef", "beef", "ribs", "meatballs", "gammon",
        "turkey", "turkey mince", "pork mince", "lamb mince", "pork belly", "chicken drumsticks", "veal",
    ],
    "Seafood": ["salmon", "shrimp", "prawns", "cod", "tilapia", "crab", "scallops", "tuna steak", "fish", "mussels"],
    "Dairy": [
        "milk", "eggs", "butter", "cheese", "cheddar", "mozzarella", "parmesan", "feta", "yogurt", "yoghurt",
        "greek yogurt", "natural yoghurt", "cream cheese", "sour cream", "heavy cream", "double cream",
        "single cream", "whipping cream", "creme fraiche", "half and half", "cottage cheese", "oat milk",
        "almond milk", "soy milk", "margarine", "custard", "cream", "buttermilk", "halloumi", "ricotta",
        "goats cheese", "paneer", "brie", "gouda", "skyr",
    ],
    "Frozen": [
        "ice cream", "frozen pizza", "frozen peas", "frozen corn", "frozen berries", "frozen fries", "fish sticks",
        "fish fingers", "frozen waffles", "popsicles", "ice lollies", "frozen vegetables", "ice", "frozen dumplings",
    ],
    "Pantry": [
        "flour", "plain flour", "self-raising flour", "sugar", "brown sugar", "caster sugar", "icing sugar",
        "powdered sugar", "rice", "pasta", "spaghetti", "noodles", "ramen", "oats", "porridge oats", "oatmeal",
        "cereal", "muesli", "granola", "peanut butter", "jam", "honey", "olive oil", "vegetable oil", "canola oil",
        "baking powder", "baking soda", "bicarbonate of soda", "vanilla extract", "salt", "pepper", "black pepper",
        "cinnamon", "spices", "quinoa", "lentils", "bread crumbs", "breadcrumbs", "pancake mix", "maple syrup",
        "stock cubes", "bouillon", "yeast", "cocoa", "chocolate chips", "nutella", "couscous", "tea bags",
        "cumin", "ground cumin", "paprika", "smoked paprika", "chili powder", "chilli powder", "oregano",
        "dried oregano", "taco seasoning", "seasoning", "italian seasoning", "garlic powder", "onion powder",
        "curry powder", "turmeric", "garam masala", "bay leaves", "nutmeg", "macaroni", "penne", "fusilli",
        "lasagne sheets", "egg noodles", "cornflour", "cornstarch", "vanilla", "basmati rice", "brown rice",
        "jasmine rice", "long grain rice", "polenta", "gravy granules", "coconut oil", "sesame oil",
    ],
    "Canned": [
        "canned tomatoes", "tinned tomatoes", "tomato sauce", "passata", "tomato paste", "tomato puree",
        "canned tuna", "tinned tuna", "tuna", "canned beans", "baked beans", "black beans", "kidney beans",
        "chickpeas", "canned corn", "sweetcorn", "soup", "coconut milk", "broth", "chicken broth", "stock",
        "chicken stock", "beef stock", "vegetable stock", "diced tomatoes", "chopped tomatoes", "crushed tomatoes",
        "beans", "cannellini beans", "pinto beans", "refried beans", "lentil soup", "canned fruit", "pineapple chunks",
    ],
    "Condiments": [
        "ketchup", "tomato ketchup", "mustard", "mayo", "mayonnaise", "soy sauce", "hot sauce", "bbq sauce",
        "salsa", "ranch", "salad dressing", "relish", "sriracha", "vinegar", "pickles", "gravy", "pesto",
        "worcestershire sauce", "fish sauce", "chutney",
    ],
    "Snacks": [
        "chips", "crisps", "tortilla chips", "pretzels", "popcorn", "crackers", "cookies", "biscuits",
        "granola bars", "muesli bars", "trail mix", "nuts", "almonds", "peanuts", "chocolate", "candy", "sweets",
        "lollies", "fruit snacks", "rice cakes", "dried fruit", "raisins", "digestives", "digestive biscuits",
    ],
    "Beverages": [
        "water", "sparkling water", "juice", "orange juice", "apple juice", "coffee", "ground coffee",
        "coffee beans", "tea", "soda", "cola", "fizzy drinks", "soft drinks", "lemonade", "beer", "wine",
        "kombucha", "energy drinks", "sports drinks", "coconut water", "cordial",
    ],
    "Household": [
        "paper towels", "kitchen roll", "toilet paper", "loo roll", "dish soap", "washing-up liquid",
        "laundry detergent", "washing powder", "fabric softener", "trash bags", "bin bags", "garbage bags",
        "washing up liquid", "dishwashing liquid", "dish detergent", "foil", "zip bags", "ziploc bags",
        "sponges", "aluminum foil", "aluminium foil", "tin foil", "plastic wrap", "cling film", "sandwich bags",
        "batteries", "light bulbs", "bleach", "dishwasher pods", "dishwasher tablets", "napkins", "tissues",
        "cleaning spray", "surface spray", "baking paper", "parchment paper",
    ],
    "Personal Care": [
        "shampoo", "conditioner", "body wash", "shower gel", "soap", "hand soap", "toothpaste", "toothbrush",
        "deodorant", "razors", "floss", "mouthwash", "lotion", "moisturiser", "moisturizer", "sunscreen",
        "sunblock", "cotton swabs", "cotton buds", "tampons", "pads", "painkillers",
    ],
    "Baby": ["diapers", "nappies", "baby wipes", "wipes", "baby food", "formula", "baby shampoo", "baby lotion"],
    "Pet": ["dog food", "cat food", "cat litter", "kitty litter", "dog treats", "cat treats", "pet food"],
}  # fmt: skip

SEED = {}
NAMES = {}  # key -> the name as written above, for showing suggestions ("cookies", not the key "cooky")
for _aisle, _items in _RAW.items():
    for _item in _items:
        SEED.setdefault(item_key(_item), _aisle)
        NAMES.setdefault(item_key(_item), _item)
