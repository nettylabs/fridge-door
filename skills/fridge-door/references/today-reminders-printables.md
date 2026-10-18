# Today, reminders and printables

Contents:
- [The Today summary](#the-today-summary)
- [Notices](#notices)
- [Reminders and quiet hours](#reminders-and-quiet-hours)
- [Printables](#printables)
- [The weekly routine](#the-weekly-routine)

## The Today summary

`fridge today` is the morning brief for the person talking: today's events (for a parent, the kids'
too), their tasks due and overdue, tonight's dinner (and whether leftovers are still good), the lists waiting to be shopped,
birthdays in the next two weeks, bills due this week (for members who see the budget) and anything
new for them. Reply with its `text`, trimmed to what matters; skip empty sections.

- `fridge today --date tomorrow` looks ahead.
- `fridge today --for Theo` shows a parent a kid's day (their chores and events).
- Each member picks their sections: `fridge member edit Luis --today-sections events,tasks,dinner`.
- In a group chat it shows only what everyone there may see.
- `--peek` leaves any new notices it shows as unread.

Offer it as a morning routine for each adult who wants it, in their own chat, at the time they
choose.

## Notices

When someone assigns a task to another adult, or a chore turn passes to them, that person gets a
notice. Nothing is sent anywhere: they hear about it the next time they talk to you.

- Any reply to a person with news waiting carries `pending_notices` and a `notices_hint`.
- In their direct chat, run `fridge notices list` (it marks them as delivered) and tell them.
- In a group chat, only say they have news waiting; the details stay for their direct chat.
- `fridge notices clear` deletes their delivered notices.

## Reminders and quiet hours

The toolkit works out reminders; your routine passes them on. It never sends anything itself.

```bash
fridge remind due            # everyone's (owner, direct chat): run every 15 minutes
fridge remind due --mine     # just the person talking
fridge remind due --peek     # look without marking anything as sent
```

The result has:
- **`send`**: pass each one on now, to `to`, with its `text` word for word, in one of the chats its
  `chats` list names, and nowhere else. A chat id is that person's own registered chat, or a group
  chat that may show it (no kids in it, everyone linked may see it, nobody linked is in quiet
  hours). `"direct"` is your one-to-one chat with them, when they're the household's direct-chat
  speaker. Bills and private events never name a group.
- **`held`**: the person is in quiet hours. It comes back by itself once they end (`until`). If it
  has a `note`, the thing starts before then: follow the note.
- **`nowhere`**: people who had a reminder but no chat to get it in. It isn't sent and doesn't come
  back. Suggest the owner registers that person's own chat (`fridge who chat <chat-id> --type
  direct --member <name>`), so the next ones reach them.
- **`dropped`**: the thing has already started, so it isn't sent late.
- **`outside_chat_ok`**: false unless the owner allowed reminders outside the chat platform. While
  it's false, never email or text a reminder.

Reminders go only to adults: a kid's event reminds the adult who added it, and so does an event for
nobody in particular or for adults who never talk with you ("remind me about Marc's dentist"). A
birthday reminds every adult except the person whose birthday it is. Each reminder goes out once, worded when it's sent ("today at 10:00", not "in 12
hours"). One that comes due during the person's quiet hours waits until they end, unless the thing
starts before then: that one goes just before their quiet hours begin. "Hours before" count real
hours, across a clock change; "days before" keep the time of day. Quiet hours come from the member
(`member edit Ana --quiet-hours "22:30-06:30"`) or the household default (9pm to 7am unless the
owner changes it: `household settings --set quiet_hours="22:00-07:00"`).

Without scheduled tasks on your platform, run `fridge remind due --mine` when someone starts a
conversation and mention what's due.

## Printables

| They ask | Run |
|---|---|
| "Print the week for the fridge" | `fridge print week` (or `--date "next week"`) |
| "Print November's calendar" / "just Lily's" | `fridge print calendar --month 2026-11` (`--for Lily`) |
| "A calendar for this week" | `fridge print calendar --week today` |
| "Print the shopping list" | `fridge print list` (`--list Hardware`) |
| "Print the chili recipe for 6" | `fridge print recipe Chili --servings 6` |
| "A budget report" | `fridge print budget` (`--month 2026-09`) |

- Files go to the household's output folder; their paths are in `files`. Send the file in the chat.
  `--format html` makes a web page instead (handy on a phone), and `--format both` makes both.
- The paper size (A4 or Letter) and the date format follow the household's settings.
- **The fridge sheet** is one landscape page: the week's household events, dinners, each member's
  chores day by day with tick boxes (with an "Anyone" row for unassigned ones), the kids' stars and
  pinned notes. Nothing private, sensitive or financial is ever on it, because anyone in the home
  can read it. Pinned notes are on it although a kid's access doesn't include notes: the adults
  choose what to pin.
- **Private printouts** (a calendar with `--mine`, which adds the person's own private events, and
  the budget report) go to that person's own folder, never the shared one, and are deleted if they
  leave the household.
- **The budget report** is private: the toolkit makes it only in a direct chat with an adult who
  sees the budget (`direct_chat_only` in a group). Never suggest putting it on the fridge.
- The built-in PDF covers Western European letters. For other scripts (Greek, Cyrillic, Arabic,
  Chinese...) the toolkit prints through a Chrome, Chromium or Edge already on the computer, offline;
  without one it says so in `notes`, and the HTML version shows everything.

## The weekly routine

Offer this for the evening before the household's week starts:

1. `fridge meal week "next week"`: plan the empty nights with the person (`meal ideas`; busy nights
   are marked).
2. `fridge meal to-list --week "next week" --dry-run`, show the list, then make it.
3. `fridge print week --date "next week"` and send the fridge sheet to print.
4. Optionally `fridge todo chores` to check everyone's chores and rotations for the week.
