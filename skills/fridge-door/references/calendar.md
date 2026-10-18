# Calendar

Contents:
- [Adding events](#adding-events)
- [Who sees an event](#who-sees-an-event)
- [Repeats, one-off changes and skips](#repeats-one-off-changes-and-skips)
- [Looking ahead](#looking-ahead)
- [Birthdays and anniversaries](#birthdays-and-anniversaries)
- [Calendar files (.ics)](#calendar-files-ics)

## Adding events

| They say | Run |
|---|---|
| "Dentist Friday at 3:30 for Theo, 45 minutes, remind me the day before" | `fridge cal add "Dentist" --date friday --time 15:30 --minutes 45 --for Theo --remind 1d` |
| "Lily has soccer Tuesdays 5:30 to 7" | `fridge cal add "Soccer practice" --date tuesday --time 17:30 --end 19:00 --for Lily --repeat weekly` |
| "We're camping 6 to 8 November" | `fridge cal add "Camping trip" --date 2026-11-06 --until-date 2026-11-08` |
| "Parent-teacher night next Thursday at 7, school hall" | `fridge cal add "Parent-teacher night" --date "next thursday" --time 19:00 --location "School hall"` |

- Leave out `--time` for an all-day event. Times are in the household's time zone. In a household
  on the 12-hour clock, a time like "4:30" is refused with `ambiguous_time`: ask whether it's
  morning or afternoon, then pass "4:30pm" or "16:30". Two-digit hours ("10:00") are read as the
  24-hour clock.
- Dates take words ("today", "friday", "next week", "Nov 5", "5 November") or a date written the
  household's way; the toolkit works out the real date. Read the date back in the reply so the
  person can catch a mix-up.
- An event over several days shows on each of them ("day 2 of 3"), for up to a year.
- The type and its icon (appointment, school, sports with the sport's own icon, health, social,
  work, travel, chores like bin night...) are guessed from the title; `--type` sets one.
- `--remind "30m, 1d"` adds reminders before the start. They reach adults only (a kid's event, or
  one for adults who never talk with you, reminds the adult who added it), through your reminder
  routine
  ([today-reminders-printables.md](today-reminders-printables.md)).
- `--dry-run` shows the event without saving it.

## Who sees an event

| Visibility | How | Who sees it |
|---|---|---|
| household (default) | | Everyone with calendar access |
| selected members | `--for "Ana, Luis" --only` | Those people and whoever made it, and only in chats where everyone present is one of them |
| private | `--private` | Only whoever made it, and never in a group chat |

- Only the person who made an event can change who sees it. Anyone with calendar edit access can
  change the details of a household event; someone else's private event can't be seen or changed.
- In a group chat the toolkit leaves out what anyone present may not see, and in a group chat with
  kids present the calendar isn't shown at all. Offer a direct chat when it says `hidden_in_group`.
- Printouts carry only household events. In a direct chat, `print calendar --mine` adds the events
  only that person can see.

## Repeats, one-off changes and skips

- Repeats: `--repeat daily | weekdays | weekly | "every 2 weeks" | monthly | "monthly on the 2nd
  tuesday" | yearly`, with `--until <date>` or `--times N`. Monthly on the 31st falls on the last day
  of shorter months; yearly on 29 February falls on the 28th in other years.
- **One date only:** `fridge cal edit "Soccer practice" --on 2026-10-27 --time 18:00` moves just that
  one; without `--on`, the change applies to every date. A new start time without a new `--end`
  keeps the length (a 5:30 to 7:00 practice moved to 6:30 ends at 8:00).
- **Skip one date:** `fridge cal skip "Soccer practice" --on 2026-10-27` (`--undo` brings it back;
  `--dry-run` previews it).
- **Stop repeating from a date:** `fridge cal delete "Soccer practice" --from-date 2026-12-01`.
  `cal delete <event>` alone removes every repeat; confirm first when it repeats. A deleted event
  goes to the bin for the retention period (`fridge bin restore <title>`; see
  [lists-and-chores.md](lists-and-chores.md#the-bin)).

## Looking ahead

| They ask | Run |
|---|---|
| "What's on this week?" | `fridge cal week` |
| "What's on tomorrow?" | `fridge cal day tomorrow` |
| "Next two weeks for Lily" | `fridge cal agenda --days 14 --for Lily` |
| "November at a glance" | `fridge cal month 2026-11` |
| "Show dinners and bills too" | add `--layers meals,bills` |
| "Which nights are busy?" | `fridge cal busy` (something on between 17:00 and 19:30, including evenings out that run past midnight; for meal planning) |
| "Tell me about soccer" | `fridge cal show "Soccer practice"` (its repeat and next dates) |

Each result has a `text` ready for the chat. The bills layer only appears for people who may see the
budget.

## Birthdays and anniversaries

```bash
fridge cal birthday --name "Grandma Rosa" --date 1948-03-14
fridge cal birthday --member Theo --date "14 March"          # kids and teens: day and month only
fridge cal birthday --name "Our anniversary" --date 2012-06-02 --anniversary
fridge cal birthdays --days 30
```

They repeat every year by themselves, show in the Today summary in the two weeks before, and remind
every adult except the person whose birthday it is the day before. For a kid or teen only the day
and month are kept, even if a year is given. `cal birthdays` lists only the ones added this way, not
events that mention a birthday in the title.

## Calendar files (.ics)

**Export** (to add the household calendar to Google, Apple or Outlook): `fridge ics export`
(`--for Lily` for one person's events, `--file <name>` for the file name). It holds only what the
person asking may see, with time zones, repeats, skipped and moved dates and reminders. It's saved
in that person's own folder (a group chat's in the group's), so one person's file never overwrites
another's. Send them the file from `file`; their calendar app opens it.

**Import** (a school term, a sports schedule, someone's work calendar): save the file they sent,
then:

```bash
fridge ics import <path> --dry-run                      # what would come in
fridge ics import <path> --for "Theo, Lily"             # tag who the events are for
fridge ics import <path> --private                      # as the person's own private events
```

- Times convert to the household's time zone, including Outlook's Windows time zone names. A time
  zone the toolkit doesn't know is read as the household's, with a warning: pass the `warnings` on
  so the person checks those times. Repeats, skipped dates, moved dates and reminders come across;
  cancelled events are left out, and an event over a year long is cut to one (with a warning).
- Importing the same file again updates its events instead of duplicating them, but only events the
  person could change by hand. Only what the file changed since the last import changes here, so
  edits made in Fridge Door (a note, a new time) stay. An event cancelled in the file is removed.
  Who sees an event never changes on re-import, and a private import never writes into someone
  else's event.
- A file this household exported earlier is recognised: its events are reported as already in the
  calendar.
- The toolkit never fetches a calendar from the internet. If the person gives a link, download the
  file with your own tools first, then import it.
