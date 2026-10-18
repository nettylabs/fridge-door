"""Sample households, so anyone can try Fridge Door in two minutes. Every name is made up.

Each later module adds its own sample records through DEMO_FILLERS (lists, chores, events, recipes, budget...).
"""

from __future__ import annotations

from types import SimpleNamespace

from . import access
from .onboarding import _create
from .store import Hub
from .util import ToolError, now_stamp

REGIONS = {
    "CA": {
        "name": "The Okafor-Laurent family",
        "members": "Ada (owner), Marc, Zoe (teen), Theo (kid), Lily (kid)",
        "country": "CA",
        "timezone": "America/Toronto",
        "chat": ("family-chat", True, {"@ada": "Ada", "@marc": "Marc"}),
    },
    "GB": {
        "name": "Priya and Tom's flat",
        "members": "Priya (owner), Tom",
        "country": "GB",
        "timezone": None,
        "chat": ("flat-chat", False, {"@priya": "Priya", "@tom": "Tom"}),
    },
    "AU": {
        "name": "The share house",
        "members": "Jess (owner), Kai, Sam",
        "country": "AU",
        "timezone": "Australia/Melbourne",
        "chat": ("house-chat", False, {"@jess": "Jess", "@kai": "Kai", "@sam": "Sam"}),
    },
    "US": {
        "name": "The Rivera home",
        "members": "Dana (owner), Ruby (teen), Max (kid)",
        "country": "US",
        "timezone": "America/Chicago",
        "chat": None,
    },
}

# function(household, region_code) -> None; later modules register sample data here.
DEMO_FILLERS: list = []
WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# Sample lists and chores per region: (groceries, crossed off, history {item: times}, extra list, tasks, stars).
# A task is (title, assignee or None, due offset in days or None, repeat words or None, rotation or None, priority).
DAILY = {
    "CA": {
        "groceries": ["milk x2", "bananas", "eggs", "bread", "cheddar", "apples", "frozen peas", "yogurt"],
        "crossed": ["coffee", "maple syrup"],
        "history": {"milk": 9, "bananas": 7, "eggs": 8, "bread": 6, "coffee": 4, "yogurt": 5, "apples": 3, "pasta": 2},
        "extra": ("Warehouse run", "shopping", "Northside Warehouse Club", ["paper towels", "laundry detergent",
                                                                            "batteries"]),
        "tasks": [
            ("Take out the bins", None, 0, "weekly", "Theo, Lily, Zoe", 0),
            ("Unload the dishwasher", None, 0, "daily", "Lily, Theo", 0),
            ("Book the winter tyre swap", "Marc", 3, None, None, 3),
            ("Sign Lily's field trip form", "Ada", 0, None, None, 2),
            ("Clean out the garage", None, 5, None, None, 1),
            ("Practise piano", "Zoe", 0, "weekdays", None, 0),
        ],
        "personal": ("Ada", "Renew passport", 10),
        "stars": {"Zoe": 2, "Theo": 3, "Lily": 5},
    },
    "GB": {
        "groceries": [
            "semi-skimmed milk", "courgettes", "crumpets", "tinned tomatoes", "washing-up liquid", "tea bags",
        ],  # fmt: skip
        "crossed": ["bread"],
        "history": {"semi-skimmed milk": 6, "bread": 5, "tea bags": 3, "crumpets": 2},
        "extra": None,
        "tasks": [
            ("Hoover the flat", None, 5, "weekly on sat", "Priya, Tom", 0),
            ("Book the boiler service", "Tom", 7, None, None, 2),
            ("Water the plants", None, 0, "every 3 days", None, 0),
            ("Pay the window cleaner", "Priya", 0, None, None, 0),
        ],
        "personal": ("Priya", "Dentist check-up", 3),
        "stars": {},
    },
    "AU": {
        "groceries": ["bread", "milk", "avocado", "coffee beans", "capsicum"],
        "crossed": ["toilet paper"],
        "history": {"milk": 5, "bread": 5, "coffee beans": 4, "toilet paper": 3},
        "extra": ("Hardware", "shopping", "Corner Hardware", ["light bulbs", "picture hooks"]),
        "tasks": [
            ("Put the bins out", None, 1, "weekly on tue", "Jess, Kai, Sam", 0),
            ("Clean the bathroom", None, 5, "every 2 weeks on sat", "Kai, Sam, Jess", 0),
            ("Fix the wifi router", "Kai", 0, None, None, 3),
            ("Transfer the rent", "Jess", 0, None, None, 2),
        ],
        "personal": ("Jess", "Renew rego", 12),
        "stars": {},
    },
    "US": {
        "groceries": ["milk", "cereal", "apples", "chicken breast", "string cheese", "peanut butter"],
        "crossed": ["bread"],
        "history": {"milk": 8, "cereal": 5, "apples": 4, "bread": 6},
        "extra": None,
        "tasks": [
            ("Feed the dog", None, 0, "daily", "Ruby, Max", 0),
            ("Make bed", "Max", 0, "weekdays", None, 0),
            ("Science project due", "Ruby", 4, None, None, 2),
            ("Schedule car service", "Dana", 0, None, None, 1),
        ],
        "personal": ("Dana", "Call the pediatrician", 1),
        "stars": {"Ruby": 6, "Max": 4},
    },
}


def _fill_daily(hh, region: str) -> None:
    import datetime as _dt

    from . import recur, shopping, todos
    from .util import now_stamp

    spec = DAILY[region]
    today = hh.today()
    stamp = now_stamp()
    by_name = {m["name"]: m for m in hh.members}
    owner = next(m for m in hh.members if m["role"] == "owner")
    shop = hh.data("shopping")
    grocery = next(lst for lst in shop["lists"] if lst.get("default") == "grocery")
    for raw in spec["groceries"] + spec["crossed"]:
        shopping.add_one(hh, shop, grocery, raw, owner["id"], stamp=stamp)
    for raw in spec["crossed"]:
        item = shopping.find_items(shop, grocery, raw, crossed=False)[0]
        item["crossed_at"], item["crossed_by"] = stamp, owner["id"]
    for name, times in spec["history"].items():
        days_ago = 2 if times > 4 else 20
        when = (hh.now() - _dt.timedelta(days=days_ago)).astimezone(_dt.timezone.utc).replace(microsecond=0)
        shop["history"][shopping.item_key(name)] = {"name": name, "times": times, "last_qty": None,
                                                     "last_at": when.isoformat()}  # fmt: skip
    if spec["extra"]:
        name, kind, store, items = spec["extra"]
        lst = shopping.new_list(hh, name, kind, store=store)
        shop["lists"].append(lst)
        for raw in items:
            shopping.add_one(hh, shop, lst, raw, owner["id"], stamp=stamp)
    hh.touch("shopping")

    data = hh.data("todos")
    shared = next(lst for lst in data["lists"] if lst.get("default") == "household")
    for title, who, offset, repeat, rotate, priority in spec["tasks"]:
        due = today + _dt.timedelta(days=offset) if offset is not None else None
        rrule = recur.from_words(repeat, due or today) if repeat else None
        rotation, assignee = None, by_name[who]["id"] if who else None
        if rotate:
            ids = [by_name[n.strip()]["id"] for n in rotate.split(",")]
            rotation, assignee = {"members": ids, "index": 0}, ids[0]
        if rrule and due:
            first = recur.next_after(recur.parse(rrule), due, due - _dt.timedelta(days=1))
            due = first or due
        task = todos.new_task(
            hh, shared, title, owner["id"], assignee=assignee, due=due.isoformat() if due else None,
            priority=priority, rrule=rrule, rotation=rotation,
        )  # fmt: skip
        data["tasks"].append(task)
    who, title, offset = spec["personal"]
    personal = next(lst for lst in data["lists"] if lst.get("owner") == by_name[who]["id"])
    data["tasks"].append(todos.new_task(hh, personal, title, by_name[who]["id"],
                                        due=(today + _dt.timedelta(days=offset)).isoformat()))  # fmt: skip
    hh.touch("todos")
    for name, stars in spec["stars"].items():
        by_name[name]["stars"] = stars
    hh.touch("household")
    adults = [m for m in hh.members if m["role"] == "adult"]
    if adults:  # one waiting notice, to show how assignments reach people
        task = next((t for t in data["tasks"] if t.get("assignee") == adults[0]["id"] and not t.get("rrule")), None)
        if task:
            from . import notices

            notices.add(hh, adults[0]["id"], "task_assigned", f"New task from {owner['name']}: {task['title']}",
                        owner["id"], ref=task["id"])  # fmt: skip


DEMO_FILLERS.append(_fill_daily)


def cmd_demo(home, args) -> dict:
    if not getattr(args, "home", None):  # never the real data folder ($FRIDGE_HOME or the default)
        raise ToolError(
            "The demo needs a folder of its own, so it never mixes with a real household.",
            hint="Run it with --home, e.g. fridge --home /tmp/fridge-door-demo demo --region CA, and keep using that "
            "--home for the demo.",
            code="needs_home",
        )
    region = (args.region or "CA").upper()
    if region not in REGIONS:
        raise ToolError(f"No demo for {region}.", hint="Demos: " + ", ".join(REGIONS) + ".", code="bad_region")
    spec = REGIONS[region]
    hub = Hub(home)
    if hub.exists() and not args.force:
        raise ToolError(
            f"{hub.home} already has data.",
            hint="Use an empty folder for the demo (--home /tmp/fridge-demo), or add --force to add the demo "
            "household alongside.",
            code="not_empty",
        )
    previous_active = (hub.data or {}).get("active")
    setup_args = SimpleNamespace(
        name=spec["name"],
        members=spec["members"],
        country=spec["country"],
        currency=None,
        timezone=args.timezone or spec["timezone"],
        week_start=None,
        date_format=None,
        time_format=None,
        units=None,
        paper=None,
        dry_run=False,
    )
    created = _create(hub, setup_args)
    household = hub.household(created["household"]["id"])
    with household.transaction():
        meta = household.meta()
        if spec["chat"]:
            chat_id, minors, links = spec["chat"]
            by_name = {m["name"]: m for m in meta["members"]}
            meta["chats"][chat_id] = {
                "type": "group",
                "minors_present": minors,
                "participants": {handle: by_name[name]["id"] for handle, name in links.items()},
                "registered_at": now_stamp(),
            }
            for name in links.values():
                member = by_name[name]
                if member["role"] in access.ADULT_ROLES and not member.get("chat_ok"):
                    member["chat_ok"] = {"owner_said": "demo: a made-up adult", "at": now_stamp(), "by": "M1"}
        household.touch("household")
        for filler in DEMO_FILLERS:
            filler(household, region)
        household.log("demo.create", None, region=region)
    with hub.transaction() as data:
        if spec["chat"]:
            data.setdefault("chats", {})[spec["chat"][0]] = household.id
        if args.force and previous_active:
            data["active"] = previous_active  # adding a demo never changes a real household's active state
    tries = [
        "fridge today",
        "fridge shop show",
        "fridge todo chores",
        "fridge member list",
    ]
    if spec["chat"]:
        tries.append(f"fridge who am-i --chat {spec['chat'][0]} --from {next(iter(spec['chat'][2]))}")
    return {
        "home": str(hub.home),
        "household": created["household"],
        "members": [m["name"] for m in created["members"]],
        "summary": f"Sample household ready: {spec['name']} ({region}). Try: {tries[0]}",
        "try": tries,
    }


def register(cli) -> None:
    p = cli.top(
        "demo",
        "Create a sample household in an empty folder (use --home): CA family of five, GB couple, AU share house, "
        "US single parent.",
        ["fridge --home /tmp/fridge-demo demo", "fridge --home /tmp/fridge-demo-uk demo --region GB"],
        cmd_demo,
        needs="none",
    )
    p.add_argument("--region", choices=sorted(REGIONS), help="Which sample household (default CA)")
    p.add_argument("--force", action="store_true", help="Add the demo household even if the folder has data")
    p.add_argument("--timezone", help="The person's own time zone (IANA name), so the demo's day matches theirs")


# Sample recipes, calendar and a week of meals per region. Every recipe here is a plain home version written for
# the demo; every name and date is made up. Events: (title, weekday offset from today, time, end, who, repeat).
PLANNING = {
    "CA": {
        "recipes": [
            ("Weeknight chili", 4, 15, 45, ["500 g ground beef", "1 onion, chopped", "2 cloves garlic, minced",
             "1 (796 ml) can diced tomatoes", "1 (540 ml) can kidney beans", "1 tbsp chili powder", "salt to taste"],
             ["Brown the beef with the onion and garlic.", "Add the tomatoes, beans and chili powder.",
              "Simmer for 40 minutes; season to taste."], ["dinner"]),
            ("Maple salmon and rice", 4, 10, 20, ["4 salmon fillets", "3 tbsp maple syrup", "2 tbsp soy sauce",
             "1 1/2 cups rice", "2 cups broccoli"], ["Cook the rice.", "Brush the salmon with maple and soy; bake "
             "15 minutes at 200°C.", "Steam the broccoli."], ["dinner", "quick"]),
            ("Saturday pancakes", 4, 10, 15, ["1 1/2 cups flour", "1 1/4 cups milk", "1 egg", "1 tbsp baking powder",
             "1 tbsp sugar", "2 tbsp butter, melted"], ["Whisk everything into a smooth batter.", "Cook on a hot "
             "pan until bubbles form, then flip."], ["breakfast", "quick"]),
        ],
        "events": [
            ("Recycling pickup", 0, None, None, None, "weekly"),
            ("Soccer practice", 1, "17:30", "19:00", "Lily", "weekly"),
            ("Hockey", 2, "17:30", "19:00", "Zoe", "weekly"),
            ("Piano lesson", 3, "16:00", "16:45", "Theo", "weekly"),
            ("Dentist", 4, "14:00", "14:45", "Marc", None),
        ],
        "birthdays": [("Nana Joy", None, 9, 1952), ("Lily", "Lily", 40, None)],
        "meals": [(0, "Weeknight chili", None), (1, None, "leftovers"), (2, "Maple salmon and rice", None),
                  (4, None, "Pizza night"), (5, "Saturday pancakes", "breakfast")],
    },
    "GB": {
        "recipes": [
            ("Shepherd's pie", 4, 20, 40, ["500 g lamb mince", "1 onion, diced", "2 carrots, diced", "1 cup peas",
             "300 ml stock", "800 g potatoes", "50 g butter"], ["Brown the mince with the onion and carrots; add "
             "the stock and peas.", "Mash the potatoes with the butter.", "Top the mince with the mash; bake 30 "
             "minutes."], ["dinner"]),
            ("Beans on toast", 2, 2, 5, ["1 (415 g) tin baked beans", "4 slices bread", "butter to taste"],
             ["Heat the beans.", "Toast and butter the bread; pour the beans over."], ["quick"]),
        ],
        "events": [
            ("Yoga", 0, "18:30", "19:30", "Priya", "weekly"),
            ("Five-a-side football", 2, "19:00", "20:00", "Tom", "weekly"),
            ("Dinner with Sam and Alex", 5, "19:30", None, "Priya, Tom", None),
        ],
        "birthdays": [("Priya's mum", None, 12, None)],
        "meals": [(0, "Beans on toast", None), (1, "Shepherd's pie", None), (2, None, "leftovers"),
                  (5, None, "Eating out")],
    },
    "AU": {
        "recipes": [
            ("Green curry", 3, 15, 25, ["400 g chicken thighs", "2 tbsp green curry paste", "1 (400 ml) can coconut "
             "milk", "1 capsicum, sliced", "1 1/2 cups jasmine rice"], ["Fry the paste, add the chicken.", "Add the "
             "coconut milk and capsicum; simmer 15 minutes.", "Serve with rice."], ["dinner"]),
            ("Smashed avo toast", 3, 5, 5, ["2 avocados", "6 slices sourdough", "1 lemon", "salt to taste"],
             ["Toast the bread.", "Smash the avocado with lemon and salt; spread."], ["breakfast", "quick"]),
        ],
        "events": [
            ("Grocery delivery", 0, "18:00", "19:00", None, None),
            ("Kai's late shift", 1, "16:00", "22:00", "Kai", "weekly"),
            ("House meeting", 6, "18:00", "18:30", None, "monthly"),
        ],
        "birthdays": [("Jess", "Jess", 15, None)],
        "meals": [(0, "Green curry", None), (1, None, "leftovers"), (3, None, "Takeaway night")],
    },
    "US": {
        "recipes": [
            ("Mac and cheese", 4, 10, 25, ["8 oz elbow pasta", "2 tbsp butter", "2 tbsp flour", "2 cups milk",
             "2 cups shredded cheddar"], ["Cook the pasta.", "Make a sauce with the butter, flour and milk; melt in "
             "the cheese.", "Stir in the pasta."], ["dinner", "kids"]),
            ("Taco night", 4, 10, 15, ["1 lb ground beef", "1 packet taco seasoning", "8 taco shells",
             "1 cup shredded lettuce", "1 cup shredded cheddar", "1/2 cup salsa"], ["Brown the beef with the "
             "seasoning.", "Fill the shells and top."], ["dinner", "quick"]),
        ],
        "events": [
            ("Swim practice", 0, "16:30", "18:00", "Ruby", "weekly on mon, wed"),
            ("Library books due", 0, None, None, "Max", None),
            ("Parent-teacher conference", 1, "17:00", "17:30", "Dana", None),
            ("School play", 3, "18:00", "19:30", "Max", None),
        ],
        "birthdays": [("Max", "Max", 25, None), ("Grandpa Lou", None, 6, 1949)],
        "meals": [(0, "Taco night", None), (1, "Mac and cheese", None), (2, None, "leftovers"),
                  (4, None, "Eating out")],
    },
}  # fmt: skip


def _fill_planning(hh, region: str) -> None:
    import datetime as _dt

    from . import events, recipes, recur
    from .util import fold, now_stamp

    spec = PLANNING[region]
    today = hh.today()
    owner = next(m for m in hh.members if m["role"] == "owner")
    by_name = {m["name"]: m for m in hh.members}
    rec = hh.data("recipes")
    titles = {}
    for title, serves, prep, cook, lines, steps, tags in spec["recipes"]:
        fields = {"title": title, "servings": serves, "prep_min": prep, "cook_min": cook, "ingredients": lines,
                  "steps": steps, "tags": tags}  # fmt: skip
        recipe = recipes.build_recipe(hh, fields, owner["id"])
        rec["recipes"].append(recipe)
        titles[title] = recipe["id"]
    hh.touch("recipes")
    cal = hh.data("calendar")
    for title, offset, time, end, who, repeat in spec["events"]:
        day = today + _dt.timedelta(days=offset)
        members = [by_name[n.strip()]["id"] for n in who.split(",")] if who else []
        rrule = recur.from_words(repeat, day) if repeat else None
        if rrule:
            day = recur.next_after(recur.parse(rrule), day, day - _dt.timedelta(days=1)) or day
        kind = events.guess_type(title)
        cal["events"].append({
            "id": hh.next_id("event"), "title": title, "type": kind, "icon": events.guess_icon(title, kind),
            "kind": "event", "date": day.isoformat(), "time": time, "end_time": end, "end_date": None, "location": None,
            "notes": None, "visibility": "household", "members": members, "owner": owner["id"], "reminders": [60],
            "rrule": rrule, "exdates": [], "overrides": {}, "source": "demo", "created_at": now_stamp(),
        })  # fmt: skip
    for name, member, offset, year in spec["birthdays"]:
        day = today + _dt.timedelta(days=offset)
        member_id = by_name[member]["id"] if member else None
        cal["events"].append({
            "id": hh.next_id("event"), "title": f"{name}'s birthday", "type": "birthday", "icon": "🎂",
            "kind": "birthday", "date": day.replace(year=year or day.year).isoformat(), "time": None,
            "end_time": None, "end_date": None, "location": None, "notes": None, "visibility": "household",
            "members": [member_id] if member_id else [], "owner": owner["id"], "reminders": [1440],
            "rrule": f"FREQ=YEARLY;BYMONTH={day.month};BYMONTHDAY={day.day}", "exdates": [], "overrides": {},
            "birthday": {"name": name, "member": member_id, "year": year}, "source": "demo", "created_at": now_stamp(),
        })  # fmt: skip
    hh.touch("calendar")
    plan = hh.data("mealplan")["plan"]
    previous = None
    for offset, title, text in spec["meals"]:
        named = next((i for i, n in enumerate(WEEKDAY_NAMES) if n in fold(f"{title} {text}")), None)
        if named is not None:  # "Saturday pancakes" goes on the coming Saturday, whatever day the demo is made
            offset = (named - today.weekday()) % 7
        day = (today + _dt.timedelta(days=offset)).isoformat()
        meal = "breakfast" if text == "breakfast" else "dinner"
        entry = {"id": hh.next_id("meal"), "recipe": titles.get(title), "text": None, "servings": None,
                 "leftovers_of": None, "added_by": owner["id"], "added_at": now_stamp()}  # fmt: skip
        if text == "leftovers" and previous:
            entry["leftovers_of"] = previous
        elif not title:
            entry["text"] = text
        plan.setdefault(day, {}).setdefault(meal, []).append(entry)
        if title and meal == "dinner":
            previous = entry["id"]
    hh.touch("mealplan")
    pantry = hh.data("shopping")["pantry"]
    for staple in ("salt", "olive oil", "rice", "flour", "sugar"):
        pantry[staple] = {"name": staple, "status": "in", "staple": True, "updated_at": now_stamp()}
    hh.touch("shopping")


DEMO_FILLERS.append(_fill_planning)


# Sample notes and a budget per region (all amounts and names made up).
# Bills: (name, amount, day of month or "q" for quarterly, category). Spending: (category, amount, days ago, by).
HOUSEKEEPING = {
    "CA": {
        "notes": [("Wifi", "Network: Maple-5G. The password is on the router.", True, True, None),
                  ("Sitter instructions", "Bedtime 8pm for Theo and Lily, 9:30 for Zoe. Emergency numbers on the "
                   "fridge.", True, False, "Kids"), ("Camping packing list", None, False, False, "Trips")],
        "budgets": {"Groceries": "1200", "Housing": "2400", "Utilities": "300", "Transport": "400", "Kids": "300",
                    "Eating out": "200", "Fun": "150"},
        "bills": [("Mortgage", "2400", 1, "Housing"), ("Hydro", "141.80", 22, "Utilities"),
                  ("Internet", "85", 5, "Utilities"), ("Car insurance", "162.40", 15, "Transport")],
        "spending": [("Groceries", "254.20", 2, "Ada"), ("Groceries", "198.75", 9, "Marc"),
                     ("Eating out", "64.50", 4, "Marc"), ("Kids", "120", 6, "Ada"), ("Transport", "88.10", 3, "Marc"),
                     ("Fun", "45", 11, "Ada")],
        "goal": ("Cottage week", "2500", 260, ["300", "150"]),
    },
    "GB": {
        "notes": [("Wifi", "Network: Flat2-Fibre. Password on the hub.", True, True, None),
                  ("Bin day", "Black bin Tuesday, recycling every other Thursday.", True, False, "House")],
        "budgets": {"Groceries": "450", "Housing": "1350", "Utilities": "300", "Transport": "120",
                    "Eating out": "150", "Fun": "100"},
        "bills": [("Rent", "1350", 1, "Housing"), ("Council tax", "162", 10, "Utilities"),
                  ("Energy", "118.40", 18, "Utilities")],
        "spending": [("Groceries", "86.30", 1, "Priya"), ("Groceries", "64.15", 6, "Tom"),
                     ("Eating out", "42", 3, "Tom"), ("Transport", "64.80", 8, "Priya")],
        "goal": ("Holiday fund", "1500", 220, ["250", "100"]),
    },
    "AU": {
        "notes": [("Wifi", "Network: SharehouseNet. Password on the fridge door.", True, True, None),
                  ("House rules", "Quiet after 11pm on weeknights. Label your food.", True, False, "House")],
        "budgets": {"Groceries": "600", "Utilities": "300", "Fun": "100"},
        "bills": [("Internet", "75", 12, "Utilities"), ("Power", "214.60", "q", "Utilities")],
        "spending": [("Groceries", "132.40", 2, "Jess"), ("Groceries", "98.20", 7, "Sam"),
                     ("Fun", "36", 5, "Kai")],
        "goal": ("New couch", "900", 120, ["150", "150", "100"]),
    },
    "US": {
        "notes": [("Wifi", "Network: RiveraHome. Password on the router.", True, True, None),
                  ("Sitter instructions", "Max: bedtime 7:30, no screens after dinner. Ruby: homework first.", True,
                   False, "Kids")],
        "budgets": {"Groceries": "700", "Housing": "1650", "Utilities": "180", "Kids": "250", "Transport": "300"},
        "bills": [("Rent", "1650", 1, "Housing"), ("Electric", "96.40", 20, "Utilities"),
                  ("Phone", "65", 8, "Utilities")],
        "spending": [("Groceries", "143.27", 2, "Dana"), ("Kids", "85", 5, "Dana"), ("Transport", "52.10", 4, "Dana")],
        "goal": ("Emergency fund", "3000", 300, ["200", "200"]),
    },
}  # fmt: skip


def _fill_housekeeping(hh, region: str) -> None:
    import datetime as _dt

    from . import budget, recur
    from .util import now_stamp

    spec = HOUSEKEEPING[region]
    today = hh.today()
    owner = next(m for m in hh.members if m["role"] == "owner")
    by_name = {m["name"]: m for m in hh.members}
    notes = hh.data("notes")["notes"]
    for title, body, pinned, sensitive, folder in spec["notes"]:
        checklist = [{"text": t, "done": False} for t in ("tent", "sleeping bags", "torch", "first-aid kit")] \
            if body is None else []  # fmt: skip
        notes.append({"id": hh.next_id("note"), "title": title, "body": body, "checklist": checklist, "photos": [],
                      "folder": folder, "tags": [], "pinned": pinned, "visibility": "shared", "sensitive": sensitive,
                      "author": owner["id"], "created_at": now_stamp()})  # fmt: skip
    hh.touch("notes")
    budget.add_default_categories(hh)  # setup made them already: this only fills any gap
    data = hh.data("budget")
    for cat in data["categories"]:
        cat["monthly"] = spec["budgets"].get(cat["name"], cat.get("monthly"))
    cats = {c["name"]: c["id"] for c in data["categories"]}
    for name, amount, day, category in spec["bills"]:
        if day == "q":
            start = today + _dt.timedelta(days=24)
            rrule = recur.from_words("every 3 months", start)
        else:
            start = today.replace(day=day) if day >= today.day else (today.replace(day=1) + _dt.timedelta(days=32)
                                                                      ).replace(day=day)  # fmt: skip
            rrule = recur.from_words(f"monthly on the {day}th", start)
        data["bills"].append({"id": hh.next_id("bill"), "name": name, "amount": amount, "category": cats[category],
                              "rrule": rrule, "start": start.isoformat(), "remind_minutes": [4320], "calendar": True,
                              "autopay": name in ("Mortgage", "Internet", "Phone"), "paid": {},
                              "created_by": owner["id"], "created_at": now_stamp()})  # fmt: skip
    for category, amount, days_ago, who in spec["spending"]:
        for months_back in (0, 1, 2):
            when = today - _dt.timedelta(days=days_ago + 30 * months_back)
            value = (budget.Decimal(amount) * budget.Decimal(("1.00", "0.92", "1.07")[months_back])).quantize(
                budget.Decimal("0.01"))  # fmt: skip
            data["expenses"].append({"id": hh.next_id("expense"), "date": when.isoformat(), "amount": str(value),
                                     "category": cats[category], "spent_by": by_name[who]["id"], "note": None,
                                     "receipt": None, "created_by": owner["id"], "created_at": now_stamp()})  # fmt: skip
    name, target, days, saved = spec["goal"]
    data["goals"].append({"id": hh.next_id("goal"), "name": name, "target": target,
                          "deadline": (today + _dt.timedelta(days=days)).isoformat(),
                          "contributions": [{"date": (today - _dt.timedelta(days=20 * i)).isoformat(), "amount": a,
                                             "by": owner["id"], "note": None} for i, a in enumerate(saved)],
                          "created_at": now_stamp()})  # fmt: skip
    hh.touch("budget")


DEMO_FILLERS.append(_fill_housekeeping)
