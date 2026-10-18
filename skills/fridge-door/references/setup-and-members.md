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
at most three things, in one message if you can:

1. **Who lives there?** The person setting it up first. Kids and teens get "(kid)" or "(teen)", or
   an age in brackets, which only picks the role and isn't stored.
2. **The country** (a code like CA or a name like Canada). It sets the currency, time zone, week
   start, date and time format, units and paper size.
3. **A name for the household** (optional; the default is "<owner>'s home").

```bash
fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid), Mateo (15)" --country MX
fridge setup --members "Jo" --country GB                    # someone living alone
fridge setup --name "Flat 4" --members "Kai, Jess, Sam" --country AU --timezone Australia/Perth
```

- The first person is the owner unless someone is marked "(owner)". The owner must be an adult, and
  becomes the household's direct-chat speaker.
- If the country has several time zones and the person is outside the main one, pass `--timezone`
  (an IANA name such as America/Vancouver). Ask only if they mentioned a city or region.
- Setup makes the shared "Household Tasks" and "Groceries" lists, a private "My Tasks" list for
  each adult, and the usual budget categories.
- Afterwards, repeat the `summary`, then offer what's in `next`: the morning Today summary,
  registering a group chat if the household uses one with you, and registering each other adult's
  own one-to-one chat (below).

To try things out first, use the demo in its own folder: `fridge --home /tmp/fridge-door-demo demo
--region GB`. The regions are CA (a family of five), GB (a couple), AU (three flatmates) and US (a
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
| `sensitive_notes_in_groups` | `yes` needs the owner's own words (`ask_owner`) |
| `reminders_outside_chat` | `yes` needs the owner's own words (`ask_owner`) |

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
fridge member access Mateo --role adult         # a new role resets access to that role's preset
fridge member access Luis --reset
```

- `member add --name ... --role ...` (owner) adds someone. Colours come from a palette unless
  `--color` picks one.
- `member edit` changes a name, colour, quiet hours (`"22:30-06:30"`, `none` or `default`) or the
  Today sections (`events,tasks,dinner,lists,birthdays,bills,notices` or `all`). Members may edit
  themselves; the owner may edit anyone.
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

In a one-to-one chat with the owner nothing needs setting up: they're the direct-chat speaker
(`fridge who speaker <name>` changes it). Everything else is registered once by the owner.

**A group chat** (a family or flat chat the agent is part of):

1. `fridge who chat <chat-id> --type group --minors yes|no`. The chat id is whatever your platform
   calls that conversation; use the same one every time. If you don't know whether anyone under 18
   is in it, the toolkit asks the owner (`ask_owner`).
2. Link each adult once: `fridge who link <chat-id> --participant <their handle> --member <name>`.
   The first link of each person asks the owner to confirm they're 18 or older; pass the owner's
   words with `--owner-confirmed` only if they said yes (an answer that reads as a no, or says
   they're under 18, is refused). A kid's or teen's handle is noted instead of linked (above).
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

Someone can belong to several households (their own home and a parent's, for example).
`fridge household add --name "Grandma's" --members "Ana (owner), Grandma Rosa" --country PT` adds one
and makes it active; `household list` and `household switch <name>` move between them, and
`--household <name>` runs one command in another household. A registered chat always belongs to one
household.

## Removing, exporting and deleting

- **Removing a member** (`member remove <name>`) erases their profile, stars, personal list,
  private events, notes and printouts, and their chat links, and takes them off shared tasks and
  events. If it was their turn on a chore, it passes to the next person (the `changes` say which).
  It asks the owner first (`ask_owner`); pass the owner's exact words with `--owner-confirmed` only
  if they said yes. Old records show "Former member".
- **Export** (`fridge export`, owner, direct chat) zips the household's data into its exports
  folder. Other members' private events, notes, personal lists and notices stay out of it, as they
  do everywhere else. Offer it before big changes.
- **Deleting the household** (`household delete`, owner, direct chat) erases everything after the
  owner's own confirmation. It can't be undone; suggest an export first.
- Finished chores, deleted lists and the activity log clear themselves after `retention_days`.
