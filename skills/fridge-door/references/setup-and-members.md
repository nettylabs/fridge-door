# Setup, members and chats

Contents:
- [First setup](#first-setup)
- [Settings](#settings)
- [Members, roles and access](#members-roles-and-access)
- [Kids and teens](#kids-and-teens)
- [Chats: who's talking and who's watching](#chats-whos-talking-and-whos-watching)
- [More than one household](#more-than-one-household)
- [Removing, exporting and deleting](#removing-exporting-and-deleting)

## First setup

`fridge doctor` says whether the data folder has a household and what's missing. To set one up, ask
these in one message:

1. **Who lives there?** The person setting it up first. Kids and teens get "(kid)" or "(teen)", or
   an age in brackets, which only picks the role and isn't stored.
2. **The country** (a code like CA or a name like Canada). It sets the currency, time zone, week
   start, date and time format, units and paper size. For a country with several time zones
   (Australia, Brazil, Canada, Chile, Spain, Indonesia, Mexico, Portugal, the US, Russia and
   others), also ask which province, state or city, and pass its zone with `--timezone`. Without
   it, setup answers `needs_timezone` and lists the zones (`zones`): ask, then run it again. For a
   country it has no defaults for, `needs_currency` asks for the currency (and the zone, unless the
   country has only one) in one go. It never quietly runs a household on UTC; `doctor` flags one
   that does.
3. **A name for the household** (optional; the default is "<owner>'s home").

Pass `--chat <this chat's id>` whenever your platform gives chats an id: it registers this
one-to-one chat as the owner's (see "Chats" below).

```bash
fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid), Mateo (15)" --country MX \
  --timezone America/Mexico_City --chat <chat-id>
fridge setup --members "Jo" --country GB                    # someone living alone, in a terminal
fridge setup --name "Flat 4" --members "Kai, Jess, Sam" --country AU --timezone Australia/Perth
```

On a computer with no time zone list (Python on Windows without the tzdata package), setup and every
other command refuse with `no_tz_data`: the fix is `pip install tzdata`, once.

- The first person is the owner unless someone is marked "(owner)". The owner must be an adult, and
  becomes the household's direct-chat speaker.
- Setup makes the shared "Household Tasks" and "Groceries" lists, a private "My Tasks" list for
  each adult, and the usual budget categories.
- Afterwards, repeat the `summary`, then offer what's in `next`: the morning Today summary,
  registering a group chat if the household uses one with you, and registering each other adult's
  own one-to-one chat (below).

To try things out first, use the demo in its own folder (it refuses without `--home`):
`fridge --home /tmp/fridge-door-demo demo --region GB` (add `--timezone <their zone>` so its day
matches theirs). The regions are CA (a family of five), GB (a couple), AU (three flatmates) and US (a
single parent with two kids).

## Settings

`fridge household settings` shows them; the owner changes them with `--set key=value` (repeat for
more):

| Key | Values |
|---|---|
| `country`, `currency`, `timezone` | e.g. `NZ`, `NZD`, `Pacific/Auckland` |
| `week_start` | `monday` ... `sunday` |
| `date_format`, `time_format` | `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM-DD`; `24h` or `12h` |
| `units`, `paper` | `metric` or `us`; `a4` or `letter` |
| `currency_display` | `auto` (the code when a symbol like $ is shared), `always` or `never` |
| `quiet_hours` | the household default, e.g. `22:00-07:00` |
| `retention_days` | how long finished chores, deleted lists and the activity log are kept (default 90) |
| `sensitive_notes_in_groups` | `yes` needs the owner's plain yes (`ask_owner`, then `--owner-confirmed` and `--confirm`), one setting at a time |
| `reminders_outside_chat` | `yes` needs the owner's plain yes, the same way |

**The owner's yes.** Only a plain yes as the whole answer counts: "yes", "yep", "yeah", "confirm",
"go ahead" or "do it", perhaps with "please" and the question's own words ("yes, remove Luis",
"yes, delete it"). Anything else is refused, so ask again: "ok", "sure", an emoji, a question, a
condition or delay ("yes, once we've exported", "yes, next week"), a joke ("yes lol jk") or a yes
naming someone else. Any no is refused as a no. Each `confirm` code works once, for a day, for that
one question.

## Members, roles and access

| Role | Starts with |
|---|---|
| owner | Everything, plus managing members, access, chats and settings. There's always at least one owner. |
| adult | Everything (edit) in every module, budget included. |
| teen | Calendar, recipes, meal plan and notes to view; to-dos and both kinds of lists to edit; no budget. |
| kid | To-dos to edit, the grocery list to view; nothing else. |

Each member has a level (`none`, `view` or `edit`) for each of eight modules: `calendar`, `todos`,
`shopping_lists`, `grocery`, `recipes`, `meal_plan`, `notes` and `budget`. Only the owner changes
them:

```bash
fridge member access Mateo                      # show
fridge member access Luis --set budget=view     # one module
fridge member access Mateo --role adult         # a new role resets access; making a teen an adult asks 18+ first
fridge member access Luis --reset
```

- `member add --name ... --role ...` (owner) adds someone. An age or tag in brackets works as in
  setup (`--name "Max (15)"` adds a teen called Max; the age isn't stored), and names can't hold
  numbers. Colours come from a palette unless `--color` picks one. Kids and teens never get the
  budget, whatever their access says.
- `member edit` changes a name, colour, quiet hours (`"22:30-06:30"`, `none` or `default`), the
  Today sections (`events,tasks,dinner,lists,birthdays,bills,notices` or `all`) or reminders
  (`--reminders on|off`). Members may edit themselves; the owner may edit anyone, except that only
  an adult can turn their own reminders on (they're opt-in: see
  [today-reminders-printables.md](today-reminders-printables.md)).
- When the toolkit refuses with `not_authorized`, say who can do it (the `hint` says), and don't
  look for a way around it.

## Kids and teens

Fridge Door is made for the adults of a household. Kids and teens take part through them.

- **They never chat with you.** Commands never run as them (`minor_cannot_chat`). If a teen is in a
  group chat, note their handle with the same command used for adults (`who link`, below): their
  messages are then recognised, nothing they ask is recorded, and the chat counts as having kids in
  it. If a child seems to be writing, be friendly, ask nothing personal, record nothing, and suggest
  they get a parent.
- **Their profile is minimal:** a first name or nickname, a colour, their chores and a star count.
  The name is one word (hyphenate a double name: "Mary-Jane"); the toolkit refuses surnames, ages
  and numbers with `minor_details`. Never store anything else about a child anywhere, notes
  included.
- **Chores and stars:** an adult ticks a chore off for them with `fridge todo done "Dishes" --by
  Theo`, which gives Theo a star. `fridge member stars Theo --add 1` (or `--add -1`) adjusts by hand.
  Stars are a plain count only adults award: no streaks, badges or messages to the kids.
- **Birthdays:** day and month only for kids (`fridge cal birthday --member Theo --date "14 March"`).
- **Their day:** `fridge today --for Theo` shows a parent what's on for Theo, and the printable
  fridge sheet shows every kid's chores with tick boxes.

## Chats: who's talking and who's watching

**The owner's own one-to-one chat** is registered at setup (`setup --chat <chat-id>`) or later
(`fridge who chat <chat-id> --type direct`). Once any one-to-one chat is registered, every command
in every household of the data folder must say which chat it came from, scheduled routines
included, and a chat nobody registered is refused (`which_chat`, `chat_not_linked`), so no other
chat can act as anyone. Only on a platform without chat ids (a terminal) do commands run without
`--chat`, as the household's direct-chat speaker (`fridge who speaker <name>` changes who that is;
with chat ids it's refused, `uses_chats`, because each chat already says who's talking).
Everything else is registered once by the owner.

**A group chat** (a family or flat chat the agent is part of):

1. `fridge who chat <chat-id> --type group --minors yes|no`. The chat id is whatever your platform
   calls that conversation; use the same one every time. If you don't know whether anyone under 18
   is in it, the toolkit asks the owner (`ask_owner`).
2. Link each adult once: `fridge who link <chat-id> --participant <their handle> --member <name>`.
   The first link of each person asks the owner "Is <name> 18 or older?". Only if they say yes,
   run it again with their exact words in `--owner-confirmed` and the `confirm` code in
   `--confirm`. Only a plain yes counts, perhaps with one age of 18 or over ("yes", "yes, Sam is
   42"). An answer that says or suggests they're under 18 (an age, "teen", a school grade, "almost
   18") is refused, and anything else (a birth year, "18 in May", "a junior") is asked again. A
   kid's or teen's handle is noted instead of linked (above).
3. From then on, every command from that chat carries `--chat <chat-id> --from <handle>`.
   `--as` is refused in group chats, so nobody can act as someone else.

**What a group chat shows:** only what every linked member may see, and nothing private (private
events and notes, personal to-do lists). Sensitive notes stay out unless the owner turned
`sensitive_notes_in_groups` on. When kids are in the chat (`--minors yes`), replies there show only
what a kid may see: chores and the grocery list. For anything else the toolkit answers
`hidden_in_group`; offer to continue in a direct chat. Nothing a child writes in a group chat is
recorded.

**Someone not linked yet** gets `unknown_participant`. Don't record what they ask for; ask the owner
who they are and link them first (adults only).

**Another adult's one-to-one chat:** the owner registers it with `fridge who chat <chat-id> --type
direct --member <name>` (it asks the owner to confirm they're 18 or older, as linking does), and you
pass `--chat <chat-id>` on their commands. Everything from that chat runs as them: `--as` is refused
there. Register it even if they mostly use the group chat: their bill reminders, private reminders
and task notices only ever go to a chat of their own.

`fridge who show` lists the chats, and `fridge who am-i` (with the same options as the command)
says who a message runs as and who will see the reply. Use it whenever you're unsure.

## More than one household

Someone can belong to several households (their own home and a parent's, for example). Only the
owner adds one, listing themselves as its owner:
`fridge household add --name "Grandma's" --members "Ana (owner), Grandma Rosa" --country PT
--timezone Europe/Lisbon` adds one and makes it active. Run from the owner's own chat, it registers
that chat in the new household as theirs too, and the chat's messages go there from then on.

- `household list` (direct chat) shows the households the person asking is in, and who they are in
  each: by their chat where chats have ids, else by their name.
- `household switch <name>` moves this chat to another household it's registered in (anyone, for
  their own chat). Without chat ids, the owner switches the household everything runs in, but only
  to one where direct chats are them too.
- `--household <name>` runs one command in another household without switching (with chat ids, the
  chat must be registered there).
- A group chat, and another adult's chat, belongs to one household.

## Removing, exporting and deleting

- **Removing a member** (`member remove <name>`) erases their profile, stars, personal list,
  private events, notes and printouts (in the bin too), and their chat links, and takes them off
  shared tasks and events. If it was their turn on a chore, it passes to the next person (the `changes` say which).
  It asks the owner first (`ask_owner`); only if they clearly say yes, run it again with their exact
  words in `--owner-confirmed` and the `confirm` code in `--confirm`. Old records show "Former
  member".
- **Export** (`fridge export`, owner, direct chat) zips the household's data into its exports
  folder. Other members' private events, notes, personal lists and notices stay out of it, as they
  do everywhere else. Offer it before big changes.
- **Deleting the household** (`household delete`, owner, direct chat) erases everything after the
  owner's clear yes, given the same way. It can't be undone; suggest an export first.
- Finished chores, deleted lists, the bin (deleted tasks, events, notes, recipes and budget items)
  and the activity log clear themselves after `retention_days`.
