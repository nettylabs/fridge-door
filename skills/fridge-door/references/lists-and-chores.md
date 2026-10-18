# Lists and chores

Contents:
- [Grocery and shopping lists](#grocery-and-shopping-lists)
- [Aisles and stores](#aisles-and-stores)
- [Sharing a list](#sharing-a-list)
- [To-dos](#to-dos)
- [Chores, rotation and stars](#chores-rotation-and-stars)
- [Notices when someone gets a task](#notices-when-someone-gets-a-task)
- [The bin](#the-bin)

## Grocery and shopping lists

A household starts with one grocery list, "Groceries". More lists can be grocery lists (food,
household basics) or shopping lists (hardware, a warehouse club, gifts), each optionally tied to a
store. Kids may see the grocery list but not shopping lists, which is why there are two kinds.

| They say | Run |
|---|---|
| "Add milk, eggs and 2 loaves of bread" | `fridge shop add "milk, eggs and 2 loaves of bread"` |
| "Add nails to the hardware list" | `fridge shop add nails --list Hardware` |
| "What's on the list?" | `fridge shop show` (grouped by aisle, in the store's order) |
| "Got the milk and eggs" | `fridge shop cross milk eggs` (finds "semi-skimmed milk" too) |
| "Oops, not the eggs" | `fridge shop uncross eggs` |
| "We need milk and eggs again" | `fridge shop readd milk eggs` (with the quantities they had last time) |
| "Take kale off" | `fridge shop remove kale` (gone, not crossed off) |
| "Start the list fresh" | `fridge shop clear` (drops the crossed-off items) |
| "Use the same list again" | `fridge shop uncross --all` |
| "Make it 2 litres" | `fridge shop item milk --qty "2 litres"` |
| "New list for the warehouse club" | `fridge shop new --name "Warehouse run" --kind shopping --store "<store>"` |

- Pass items the way people say them. An amount can come first or last ("2 pints of milk", "500g
  mince", "bread x2"). Commas separate items. "and" splits two everyday grocery items ("eggs and
  bread" is two), while names that belong together stay whole ("mac and cheese"), and so does
  anything it doesn't know ("sandpaper and glue": add those as two items). `--qty` and `--note` work
  for a single item.
- Items already on the list aren't added twice: one with no amount takes the new amount, one with an
  amount keeps it (the summary says so), and a crossed-off one comes back. Use `--again` only when
  they really want a second line.
- Crossing off, uncrossing, removing and re-adding find items by their words: "milk" finds
  "semi-skimmed milk". When two items match ("oat milk" and "almond milk"), the toolkit answers
  `ambiguous`; ask which.
- Crossing off records the purchase: that powers "bought often" suggestions (`fridge shop suggest
  mi`) and, for items the pantry tracks (`fridge pantry show`), marks them as in stock, which
  recipes and the meal planner use.
- Deleted lists can be restored for the retention period (`shop lists --deleted`, `shop restore`).
- Every change is saved at once, so two people shopping the same list stay in step. When someone
  says they're at the shop, show the list and cross things off as they report them.

## Aisles and stores

Items file themselves into aisles (Produce, Bakery, Deli, Meat, Seafood, Dairy, Frozen, Pantry,
Canned, Condiments, Snacks, Beverages, Household, Personal Care, Baby, Pet, then Other). Names from
different countries work: courgette and zucchini, coriander and cilantro, mince and ground beef.

- **Wrong aisle?** `fridge shop item "oat milk" --aisle Dairy`. The household's correction is
  remembered for next time. Renaming an item (`shop item ... --name`) files it again.
- **The store's own order:** `fridge shop aisles --order "Bakery,Produce,Dairy"` puts those first,
  and adds any the list doesn't have yet; `--add`, `--rename ... --to`, `--move ...
  --before/--after/--first` and `--delete` adjust single aisles. Every list starts with the usual
  aisles and keeps its own order, so a list tied to a store matches that store. Items waiting in
  Other move to a new aisle that fits them.

## Sharing a list

- **As a message:** `fridge shop share` returns tidy `text` with tick boxes to paste into a chat.
- **As a file:** `fridge shop share --file` also saves a .txt file to send.
- **On paper:** `fridge print list` makes a printable checklist by aisle (see
  [today-reminders-printables.md](today-reminders-printables.md)).

Sending the list to someone outside the current chat needs the person's OK for that message.

## To-dos

Every adult has a private "My Tasks" list; "Household Tasks" is shared. Custom shared lists (Garden,
Moving house) get an emoji and colour: `fridge todo list-new --name Garden --icon 🌱`.

| They say | Run |
|---|---|
| "Remind me to book the dentist by Friday" | `fridge todo add "Book the dentist" --mine --due friday` |
| "Luis, fix the gate this weekend, it's urgent" | `fridge todo add "Fix the gate" --assign Luis --due "this weekend" --priority high` |
| "What's on my list?" | `fridge todo show --mine` |
| "What's overdue?" | `fridge todo show --due overdue` |
| "Done with the gate" | `fridge todo done "Fix the gate"` |
| "Wipe the mirror is part of cleaning the bathroom" | `fridge todo add "Wipe the mirror" --parent "Clean the bathroom"` |
| "Move it to Monday" | `fridge todo edit "Fix the gate" --due monday` |
| "That wasn't done after all" | `fridge todo undo "Fix the gate"` (a repeating chore's next one goes too, unless it was changed) |
| "Delete the gate task" | `fridge todo delete "Fix the gate"` (it goes to [the bin](#the-bin)) |

- Due dates take words ("today", "friday", "next week", "+3", "Nov 5") or a date written the
  household's way; the toolkit works out the real date with the household's week start.
- Tasks can have notes, a priority (low, medium, high), one level of subtasks, and photos saved as
  file paths (`fridge todo photo <task> --add <path>`).
- Personal lists are private: they never show in a group chat or to anyone else.
- Repeats: `--repeat daily | weekdays | "weekly on mon,thu" | "every 2 weeks" | fortnightly |
  "every other tuesday" | monthly | "monthly on the 2nd monday"`, with `--until <date>` or `--times
  N`. A repeat that could mean two things ("every second tuesday") or names no days ("twice a
  week") is refused with `bad_repeat`: ask the question in its `hint`.
- With no due date, a repeating task starts on its first matching day ("weekly on tue" added on a
  Monday is due tomorrow).
- Ticking off a repeating task makes the next one, once: the next due day after the one it was due,
  but never before the day it was ticked off. Catching up yesterday's daily chore today leaves
  today's still to do.
- `todo undo` finds the task by name among the lists the person can see.

## Chores, rotation and stars

Chores are tasks on a shared list, usually repeating and often taking turns:

```bash
fridge todo add "Take out the bins" --repeat "weekly on mon" --rotate "Theo, Lily, Zoe"
fridge todo add "Clean the bathroom" --repeat weekly --assign Kai
fridge todo done "Take out the bins" --by Theo     # Theo gets a star; next week it's Lily's turn
fridge todo chores                                 # whose turn it is each day this week, with stars
fridge todo chores --member Theo
```

- `--rotate` hands each new turn to the next person, in order. `todo chores` works the turns out
  ahead, day by day; chores nobody is on show under "Anyone". When someone leaves the household,
  their turn passes to the next person.
- In a group chat with kids in it, to-dos are only chores: tasks a kid or teen is on (assigned or
  taking turns), and repeating ones nobody is on. A parent's own chat still has everything.
- `--by <who did it>` records who actually did it. A kid or teen gets a star; an adult just gets the
  credit. Ticking off the same chore twice by name is refused ("already done today"), so a second
  "Theo did the bins" doesn't skip someone's turn; the next turn's id is in the hint if they really
  meant to do it early.
- Kids see their chores on the printable fridge sheet (`fridge print week`), with tick boxes and
  their stars.

## Notices when someone gets a task

Assigning a task to another adult leaves them a notice, and so does a chore turn passing to them
("Your turn: Bathroom, due Tue 10 Nov"). Nothing is sent anywhere:

- In a group chat where they're present, tell them there and then.
- Otherwise they hear the next time they talk to you: every reply to them carries
  `pending_notices` and a `notices_hint`. Run `fridge notices list` in their direct chat and tell
  them. In a group chat, only say that they have news waiting.
- Never message someone outside the chat about a task unless the owner says so for that message.
- Kids and teens don't get notices: their chores show on the fridge sheet and in `fridge today --for
  <kid>` for a parent.

## The bin

Deleting a task (with its subtasks), event, note, recipe, expense, bill, savings goal or budget
category puts it in the bin for the household's retention period (90 days unless the owner changes
it). The reply says so and carries an `undo` command.

- "What did I delete?" → `fridge bin show`: what this person may see, newest first, and until when.
- "Bring back the dentist appointment" → `fridge bin restore Dentist` (add `--kind event` if two
  things match; an expense goes by its id, such as X12). `--dry-run` previews it.
- A restore puts things back with their links (a bill's paid mark, a category's bills). It refuses a
  name that's been reused since (rename that one first), and says so when a task's list or an
  expense's category is gone: the task goes to Household Tasks, the expense under Other.
- Someone else's private event, note or personal task stays theirs in the bin, nothing from it shows
  in a group chat with kids in it, and removing a member clears their private things from it.
- Deleted lists have their own restore: `fridge shop restore` and `fridge todo list-restore`.
