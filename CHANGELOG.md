# Changelog

## 1.0.1 (2026-10-18)

Fixes from an independent review of 1.0.0.

- **Only a clear yes counts.** A question for the owner comes with a code, and the command runs only with the
  owner's exact words and that code, when the words are a clear yes ("yes", "confirm", "go ahead"). Any no
  anywhere ("absolutely not", "I said no"), and anything vague, conditional or emoji ("ok", "sure", "yes but
  later", "👍"), is refused.
- **Adults only, checked properly.** The 18-or-older answer refuses any age under 18 in digits or words, teen and
  school words, and "almost 18", and making a kid or teen an adult asks the same question.
- **The README is honest about installs.** It leads with what works today, marks the Grok Bot, Cursor and Grok
  Build listings as coming soon, and says how updates arrive.
- **Deletes can be undone.** Deleted tasks, events, notes, recipes and budget items wait in a bin for 90 days
  (`fridge bin show`, `fridge bin restore`), with the same privacy they had before.
- **Reminders are opt-in.** Each adult turns their own on; nobody can do it for them.
- **The owner's own chat.** Setup can register it (`--chat`): from then on every message names its chat, and an
  unregistered chat is refused, so no other chat can act as the owner.
- **Time zones.** Setup asks which province, state or city in a country with several zones. Without a time zone
  list (Python on Windows), commands refuse with the fix (`pip install tzdata`) instead of using UTC, and a time
  the clocks skip gets a warning.
- **Kids.** Group chats with kids in them show only chores, and a note naming a child next to health or school
  details must be sensitive or private.
- **Households and chores.** Only the owner adds or switches households, as their owner; undoing a repeating chore
  takes back the next one it made; printouts and calendar files go in a folder for the chat they're made in.
- **The demo** needs its own folder (`--home`), takes `--timezone`, and always has something on today.
- **Smaller fixes.** List delete and restore take the name either way; `household delete --dry-run`; no
  duplicate birthdays; "1,234.56" is read; every country's name works in setup; recipe imports drop the page's
  image link; the no-network test also catches dynamic code and other programs.
- 380 automated tests on Python 3.9, 3.11 and 3.13.

## 1.0.0 (2026-10-17)

First release.

- Households for one person or eight: an owner, adults, and kids and teens who take part through their parents
  (a first name or nickname, a colour, chores and stars). Per-person access to each module, several households,
  and group chats that show only what everyone present may see.
- Setup in one step from who lives there and the country, which sets the currency, time zone, week start, date
  and time format, units and paper size.
- A morning Today summary: events, tasks due, tonight's dinner, lists to shop, birthdays, bills and anything new.
- Calendar: timed, all-day and multi-day events, who they're for, household / members-only / private
  visibility, reminders, repeats with one-off changes and skipped dates, birthdays, busy evenings, meal and bill
  layers, and .ics import and export across time zones.
- To-dos and chores: personal and shared lists, assigning with notices, due dates, priorities, subtasks, photos,
  repeats, chores that take turns, and stars for kids.
- Grocery and shopping lists sorted into aisles (with names from different countries), per-store aisle order,
  amounts said first or last, items said together ("eggs and bread") split apart, crossing off by any of an
  item's words, one-step re-adding, suggestions, and sharing as a message, a file or a printout.
- Recipes from a saved page, a photo or by hand; exact scaling with fractions; cook mode; sending ingredients to
  the list with a pantry check, merging amounts only within metric or US units.
- A weekly meal planner that avoids long cooks on busy evenings, treats leftovers as a meal, and keeps the week's
  grocery list in step when meals change, without touching crossed-off or hand-added items or asking again for
  what was already bought.
- Notes with checklists, folders, tags and pins; private notes; sensitive notes kept out of group chats and
  printouts.
- A manual household budget: categories, spending (including from a receipt photo, confirmed first), recurring
  bills, savings goals, month and trend reports, exact money in any currency.
- Reminders worked out for the agent to pass on: worded when sent, held through quiet hours (or sent just before
  them when the thing comes first), only in chats that may show them, and never repeated.
- Printables: a one-page weekly fridge sheet, month and week calendars, shopping checklists, recipe cards and a
  budget report, as PDF (built-in engine, no dependencies) and HTML.
- Standard-library Python 3.9+, local files only, no network calls, 333 automated tests and a built-in self-test.
  Demo households for Canada, the UK, Australia and the US.
