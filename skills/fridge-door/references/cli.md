# Command reference

Generated from `fridge <command> --help`. Run that for the same text at any time.

Who is talking goes with every command: `--chat <chat-id> --from <participant>` in a registered group chat, `--chat <chat-id>` in an adult's own registered one-to-one chat (once any one-to-one chat is registered, every command and routine needs `--chat`), and neither only on a platform without chat ids, as the household's direct-chat speaker. `--as <adult member>` is only for when the platform itself says who is writing, and is refused in group chats and in someone's own chat. `--home <folder>` picks the data folder and `--household <name>` the household. These work before or after the command, so they are left out of the sections below. Every command prints JSON; errors print `{"ok": false, "error", "hint", "code"}` and exit with code 1 (2 for a mistyped command); an `ask_owner` field is a question only the household owner may answer.

```text
usage: fridge [-h] [--version] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
              [--from PARTICIPANT]
              {setup,doctor,export,household,selftest,demo,member,who,shop,todo,notices,today,cal,recipe,pantry,meal,note,budget,bin,remind,ics,print}
              ...

Fridge Door: a household organizer for any household in any country. Shared calendar, to-dos and chores, grocery lists, recipes, meal plans, notes and a budget.

positional arguments:
  {setup,doctor,export,household,selftest,demo,member,who,shop,todo,notices,today,cal,recipe,pantry,meal,note,budget,bin,remind,ics,print}
    setup               Set up the first household in one step: its name, who's in it and the country
                        (everything else defaults).
    doctor              Show the setup status and what's missing.
    export              Zip this household's data into the exports folder (owner, direct chat).
    household           Households: add, list, switch, show, rename, settings, delete.
    selftest            Run the built-in checks.
    demo                Create a sample household in an empty folder (use --home): CA family of five, GB
                        couple, AU share house, US single parent.
    member              Members: list, show, add, edit, access, stars, remove.
    who                 Who's talking: link chats and adult participants to members (owner).
    shop                Shopping and grocery lists: items by aisle, cross off, re-add, suggestions, share.
    todo                To-dos and chores: lists, tasks, assigning, repeats, rotation, stars.
    notices             Notices waiting for the person talking (e.g. tasks someone assigned them).
    today               The Today summary: today's events, tasks due, tonight's dinner, lists to shop,
                        birthdays, bills and new notices, in the member's chosen sections. Run it first
                        thing each day.
    cal                 The household calendar: events, repeats, birthdays, views, busy evenings.
    recipe              Recipes: add (by hand, from a saved page or a photo), show, scale, cook, to a list.
    pantry              The pantry: what's in, low or out, and staples to check before shopping.
    meal                The meal plan: plan the week, keep the grocery list in step, busy nights, ideas.
    note                Notes: shared or private, checklists, folders and tags, pinned notes, sensitive
                        notes.
    budget              The household budget: categories, expenses, bills, savings goals, month reports.
    bin                 Deleted tasks, events, notes, recipes and budget items, kept for the retention
                        period.
    remind              Reminders for events, birthdays and bills, respecting quiet hours.
    ics                 Calendar files (.ics): export to Google, Apple or Outlook, or import from them.
    print               Printables: fridge sheet, calendar, shopping checklist, recipe card, budget report.

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit

who's talking (any command):
  --home HOME           Data folder
  --household HOUSEHOLD
                        Which household (name or id); default: the active one
  --as MEMBER           Run as this adult member (name or id)
  --chat CHAT           The chat the message came from (registered with: who chat)
  --from PARTICIPANT    Who sent it, in that chat

Examples:
  fridge doctor
  fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid)" --country MX
  fridge --home /tmp/fridge-demo demo --region CA
  fridge member list
  fridge who am-i --chat family-group --from @ana

Who's talking: --as <adult member>, or --chat <chat-id> --from <participant> once the chat is linked; with
neither, the household's direct-chat speaker. These options work before or after the command.
Data folder: --home, else $FRIDGE_HOME, else /workspace/fridge-door (if /workspace exists), else ~/fridge-door.
Every command prints JSON: {"ok": true, "summary": ...} or {"ok": false, "error", "hint", "code"}; an
"ask_owner" field is a question only the household owner may answer.
```

## setup

```text
usage: fridge setup [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                    [--from PARTICIPANT] [--name NAME] --members MEMBERS --country COUNTRY
                    [--currency CURRENCY] [--timezone TIMEZONE] [--week-start WEEK_START]
                    [--date-format DATE_FORMAT] [--time-format TIME_FORMAT] [--units UNITS] [--paper PAPER]
                    [--dry-run]

Set up the first household in one step: its name, who's in it and the country (everything else defaults).

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           The household name, e.g. "The Garcias" (default: "<owner>'s home")
  --members MEMBERS     Who lives there: "Ana, Luis, Sofia (kid), Mateo (15)"
  --country COUNTRY     Country code or name, e.g. CA or Canada
  --currency CURRENCY   3-letter currency code (default: the country's)
  --timezone TIMEZONE   IANA time zone, e.g. America/Vancouver (default: the country's main one)
  --week-start WEEK_START
                        monday ... sunday (default: the country's)
  --date-format DATE_FORMAT
                        e.g. DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD
  --time-format TIME_FORMAT
                        24h or 12h
  --units UNITS         metric or us
  --paper PAPER         a4 or letter
  --dry-run             Show what would be set up without saving

Examples:
  fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid), Mateo (teen)" --country MX
  fridge setup --members "Jo" --country GB
  fridge setup --name "Flat 4" --members "Kai, Jess, Sam" --country AU --timezone Australia/Perth
```

## doctor

```text
usage: fridge doctor [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]

Show the setup status and what's missing.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge doctor
```

## export

```text
usage: fridge export [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]

Zip this household's data into the exports folder (owner, direct chat).

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge export
```

## household

```text
usage: fridge household [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT]
                        {add,list,switch,show,rename,settings,delete} ...

Households: add, list, switch, show, rename, settings, delete.

positional arguments:
  {add,list,switch,show,rename,settings,delete}
    add                 Add another household (e.g. an extended family's) and make it the active one.
    list                List the households in this data folder (direct chat).
    switch              Make another household the active one (direct chat).
    show                Show the household's settings and members.
    rename              Rename the household (owner).
    settings            Show the settings, or change them with --set key=value (owner).
    delete              Delete this household and everything in it (owner, direct chat, needs the owner's
                        words).

optional arguments:
  -h, --help            show this help message and exit
```

### household add

```text
usage: fridge household add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] [--name NAME] --members MEMBERS --country COUNTRY
                            [--currency CURRENCY] [--timezone TIMEZONE] [--week-start WEEK_START]
                            [--date-format DATE_FORMAT] [--time-format TIME_FORMAT] [--units UNITS]
                            [--paper PAPER] [--dry-run]

Add another household (e.g. an extended family's) and make it the active one.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           The household name, e.g. "The Garcias" (default: "<owner>'s home")
  --members MEMBERS     Who lives there: "Ana, Luis, Sofia (kid), Mateo (15)"
  --country COUNTRY     Country code or name, e.g. CA or Canada
  --currency CURRENCY   3-letter currency code (default: the country's)
  --timezone TIMEZONE   IANA time zone, e.g. America/Vancouver (default: the country's main one)
  --week-start WEEK_START
                        monday ... sunday (default: the country's)
  --date-format DATE_FORMAT
                        e.g. DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD
  --time-format TIME_FORMAT
                        24h or 12h
  --units UNITS         metric or us
  --paper PAPER         a4 or letter
  --dry-run             Show what would be set up without saving

Examples:
  fridge household add --name "Grandma's" --members "Ana (owner), Grandma Rosa, Uncle Leo" --country PT
```

### household list

```text
usage: fridge household list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                             [--from PARTICIPANT]

List the households in this data folder (direct chat).

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge household list
```

### household switch

```text
usage: fridge household switch [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT]
                               name

Make another household the active one (direct chat).

positional arguments:
  name                  Household name or id

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge household switch "Grandma's"
```

### household show

```text
usage: fridge household show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                             [--from PARTICIPANT]

Show the household's settings and members.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge household show
```

### household rename

```text
usage: fridge household rename [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT] --to TO

Rename the household (owner).

optional arguments:
  -h, --help            show this help message and exit
  --to TO               The new name

Examples:
  fridge household rename --to "The Garcia-Lopez home"
```

### household settings

```text
usage: fridge household settings [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                 [--from PARTICIPANT] [--set SET] [--owner-confirmed OWNER_CONFIRMED]
                                 [--confirm CONFIRM] [--dry-run]

Show the settings, or change them with --set key=value (owner).

optional arguments:
  -h, --help            show this help message and exit
  --set SET             key=value; repeat for more. Keys: country, currency, timezone, week_start,
                        date_format, time_format, units, paper, currency_display, retention_days,
                        quiet_hours, sensitive_notes_in_groups, reminders_outside_chat
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words, for settings that need their OK
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run

Examples:
  fridge household settings
  fridge household settings --set week_start=monday --set units=us
  fridge household settings --set quiet_hours="22:00-07:00"
  fridge household settings --set reminders_outside_chat=yes --owner-confirmed "yes, allow it" --confirm 1c5e2a0-8d41f2-3f9b27d41c
```

### household delete

```text
usage: fridge household delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT] [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM]
                               [--dry-run]

Delete this household and everything in it (owner, direct chat, needs the owner's words).

optional arguments:
  -h, --help            show this help message and exit
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words confirming the deletion
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run             Say what would be deleted (no owner's yes needed)

Examples:
  fridge household delete
  fridge household delete --owner-confirmed "yes, delete it" --confirm 1c5e2a0-8d41f2-3f9b27d41c
```

## selftest

```text
usage: fridge selftest [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT]

Run the built-in checks.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge selftest
```

## demo

```text
usage: fridge demo [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                   [--from PARTICIPANT] [--region {AU,CA,GB,US}] [--force] [--timezone TIMEZONE]

Create a sample household in an empty folder (use --home): CA family of five, GB couple, AU share house, US single parent.

optional arguments:
  -h, --help            show this help message and exit
  --region {AU,CA,GB,US}
                        Which sample household (default CA)
  --force               Add the demo household even if the folder has data
  --timezone TIMEZONE   The person's own time zone (IANA name), so the demo's day matches theirs

Examples:
  fridge --home /tmp/fridge-demo demo
  fridge --home /tmp/fridge-demo-uk demo --region GB
```

## member

```text
usage: fridge member [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]
                     {list,show,add,edit,access,stars,remove} ...

Members: list, show, add, edit, access, stars, remove.

positional arguments:
  {list,show,add,edit,access,stars,remove}
    list                List the household's members with their role, colour and stars.
    show                Show one member.
    add                 Add a member (owner). Kids and teens get only a first name or nickname, a colour and
                        stars.
    edit                Change a member's name, colour, quiet hours or Today sections (yourself, or anyone
                        if you're the owner).
    access              Show or change a member's role and per-module access (owner). A new role resets
                        access to its preset.
    stars               Show the kids' and teens' stars, or give/take some (adults): --add 1, --add -1.
    remove              Remove a member and erase their details (owner, needs the owner's own words).

optional arguments:
  -h, --help            show this help message and exit
```

### member list

```text
usage: fridge member list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--detail]

List the household's members with their role, colour and stars.

optional arguments:
  -h, --help            show this help message and exit
  --detail              Include access levels, quiet hours and Today sections

Examples:
  fridge member list
  fridge member list --detail
```

### member show

```text
usage: fridge member show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT]
                          member

Show one member.

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge member show Sofia
```

### member add

```text
usage: fridge member add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] --name NAME [--role {owner,adult,teen,kid}] [--color COLOR]
                         [--quiet-hours QUIET_HOURS] [--dry-run]

Add a member (owner). Kids and teens get only a first name or nickname, a colour and stars.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           First name, or a nickname; "Max (15)" makes a teen (the age isn't stored)
  --role {owner,adult,teen,kid}
                        owner, adult, teen or kid (default: adult)
  --color COLOR         A palette colour name or #RRGGBB (default: the next unused one)
  --quiet-hours QUIET_HOURS
                        Adults: e.g. "22:00-07:00", or none
  --dry-run

Examples:
  fridge member add --name "Grandma Rosa" --role adult
  fridge member add --name Mia --role kid --color pink
```

### member edit

```text
usage: fridge member edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--name NAME] [--color COLOR] [--quiet-hours QUIET_HOURS]
                          [--today-sections TODAY_SECTIONS] [--reminders {on,off}] [--dry-run]
                          member

Change a member's name, colour, quiet hours or Today sections (yourself, or anyone if you're the owner).

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --color COLOR
  --quiet-hours QUIET_HOURS
                        "HH:MM-HH:MM", none, or default (the household's)
  --today-sections TODAY_SECTIONS
                        Comma list from: events, tasks, dinner, lists, birthdays, bills, notices; or all
  --reminders {on,off}  on: they'd like reminders (only they can say so); off
  --dry-run

Examples:
  fridge member edit Ana --color teal
  fridge member edit Ana --quiet-hours "22:30-06:30"
  fridge member edit Luis --today-sections events,tasks,dinner
```

### member access

```text
usage: fridge member access [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] [--role {owner,adult,teen,kid}] [--set SET] [--reset]
                            [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM] [--dry-run]
                            member

Show or change a member's role and per-module access (owner). A new role resets access to its preset.

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit
  --role {owner,adult,teen,kid}
  --set SET             module=level (none, view or edit); repeat for more
  --reset               Back to the role's preset
  --owner-confirmed OWNER_CONFIRMED
                        Making a kid or teen an adult: the owner's own words that they're 18+
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run

Examples:
  fridge member access Mateo
  fridge member access Mateo --role teen
  fridge member access Sofia --set grocery=edit --set calendar=view
  fridge member access Luis --reset
  fridge member access Zoe --role adult --owner-confirmed "yes, Zoe is 19" --confirm 1c5e2a0-8d41f2-3f9b27d41c
```

### member stars

```text
usage: fridge member stars [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--add ADD] [--dry-run]
                           [member]

Show the kids' and teens' stars, or give/take some (adults): --add 1, --add -1.

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit
  --add ADD             Stars to add (negative to take away)
  --dry-run

Examples:
  fridge member stars
  fridge member stars Mia --add 1
```

### member remove

```text
usage: fridge member remove [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM]
                            [--dry-run]
                            member

Remove a member and erase their details (owner, needs the owner's own words).

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words confirming the removal
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run

Examples:
  fridge member remove "Uncle Leo"
  fridge member remove "Uncle Leo" --owner-confirmed "yes, remove Uncle Leo" --confirm 1c5e2a0-8d41f2-3f9b27d41c
```

## who

```text
usage: fridge who [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                  [--from PARTICIPANT]
                  {chat,link,unlink,forget-chat,speaker,show,am-i} ...

Who's talking: link chats and adult participants to members (owner).

positional arguments:
  {chat,link,unlink,forget-chat,speaker,show,am-i}
    chat                Register a chat with this household (owner). Group chats must say whether anyone
                        under 18 is in them.
    link                Link a group-chat participant to an adult member (owner). The first link asks the
                        owner to confirm 18+. A kid's or teen's handle is noted instead: they're recognised,
                        never act, and the chat counts as having kids in it.
    unlink              Unlink a participant from a group chat (owner).
    forget-chat         Remove a chat from this household (owner).
    speaker             Choose who's talking in direct chats for this household (owner).
    show                Show the linked chats, their participants and the direct-chat speaker.
    am-i                Say which member and household this message runs as, and who will see the reply.

optional arguments:
  -h, --help            show this help message and exit
```

### who chat

```text
usage: fridge who chat [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] --type {group,direct} [--minors MINORS] [--member MEMBER]
                       [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM] [--dry-run]
                       chat_id

Register a chat with this household (owner). Group chats must say whether anyone under 18 is in them.

positional arguments:
  chat_id               The chat's id, as the platform gives it

optional arguments:
  -h, --help            show this help message and exit
  --type {group,direct}
  --minors MINORS       yes or no: is anyone under 18 in this group chat?
  --member MEMBER       For a direct chat: whose chat it is (default: you)
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words confirming that person is 18 or older
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run             Show what would happen without saving

Examples:
  fridge who chat family-group --type group --minors yes
  fridge who chat jo-dm --type direct --member Jo
  fridge who chat jo-dm --type direct --member Jo --owner-confirmed "yes, Jo is 34" --confirm 1c5e2a0-8d41f2-3f9b27d41c
```

### who link

```text
usage: fridge who link [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] --participant PARTICIPANT --member MEMBER
                       [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM] [--dry-run]
                       chat_id

Link a group-chat participant to an adult member (owner). The first link asks the owner to confirm 18+. A kid's or teen's handle is noted instead: they're recognised, never act, and the chat counts as having kids in it.

positional arguments:
  chat_id

optional arguments:
  -h, --help            show this help message and exit
  --participant PARTICIPANT
                        Their handle or id in that chat
  --member MEMBER       The member (name or id)
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words confirming the person is 18 or older
  --confirm CONFIRM     The code that came with the owner's question (confirm)
  --dry-run

Examples:
  fridge who link family-group --participant @sam --member Sam
  fridge who link family-group --participant @sam --member Sam --owner-confirmed "yes, Sam is 42" --confirm 1c5e2a0-8d41f2-3f9b27d41c
  fridge who link family-group --participant @arjun --member Arjun
```

### who unlink

```text
usage: fridge who unlink [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] --participant PARTICIPANT
                         chat_id

Unlink a participant from a group chat (owner).

positional arguments:
  chat_id

optional arguments:
  -h, --help            show this help message and exit
  --participant PARTICIPANT

Examples:
  fridge who unlink family-group --participant @sam
```

### who forget-chat

```text
usage: fridge who forget-chat [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                              [--from PARTICIPANT]
                              chat_id

Remove a chat from this household (owner).

positional arguments:
  chat_id

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge who forget-chat family-group
```

### who speaker

```text
usage: fridge who speaker [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--owner-confirmed OWNER_CONFIRMED] [--confirm CONFIRM]
                          member

Choose who's talking in direct chats for this household (owner).

positional arguments:
  member

optional arguments:
  -h, --help            show this help message and exit
  --owner-confirmed OWNER_CONFIRMED
                        The owner's own words confirming that person is 18 or older
  --confirm CONFIRM     The code that came with the owner's question (confirm)

Examples:
  fridge who speaker Ana
```

### who show

```text
usage: fridge who show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT]
                       [chat_id]

Show the linked chats, their participants and the direct-chat speaker.

positional arguments:
  chat_id

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge who show
  fridge who show family-group
```

### who am-i

```text
usage: fridge who am-i [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT]

Say which member and household this message runs as, and who will see the reply.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge who am-i
  fridge who am-i --chat family-group --from @ana
```

## shop

```text
usage: fridge shop [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                   [--from PARTICIPANT]
                   {lists,new,edit,delete,restore,add,show,cross,uncross,readd,remove,clear,item,suggest,aisles,share}
                   ...

Shopping and grocery lists: items by aisle, cross off, re-add, suggestions, share.

positional arguments:
  {lists,new,edit,delete,restore,add,show,cross,uncross,readd,remove,clear,item,suggest,aisles,share}
    lists               Show the shopping and grocery lists with how many items are left.
    new                 Make a list (grocery or shopping), optionally for a store.
    edit                Rename a list or change its store, icon or colour.
    delete              Delete a list (restorable for the retention period).
    restore             Bring back a deleted list.
    add                 Add items ("milk x2" sets a quantity). Items file themselves into aisles; items
                        already there aren't added twice, and crossed-off ones come back with their
                        quantity.
    show                Show a list grouped by aisle, in the store's order.
    cross               Cross items off (they drop to the crossed-off section).
    uncross             Put crossed-off items back on the list (--all to reuse it).
    readd               Re-add items in one step, each with the quantity it had last time.
    remove              Take items off the list (not the same as crossing off).
    clear               Clear the crossed-off items (or --everything).
    item                Change an item's name, quantity, note or aisle. A new aisle is remembered for next
                        time.
    suggest             Suggestions while typing: what the household buys often, then common items.
    aisles              Show or change a list's aisle order: add, rename, move, delete, or set the whole
                        order.
    share               The list as a tidy message with tick boxes, or a .txt file with --file.

optional arguments:
  -h, --help            show this help message and exit
```

### shop lists

```text
usage: fridge shop lists [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--deleted]

Show the shopping and grocery lists with how many items are left.

optional arguments:
  -h, --help            show this help message and exit
  --deleted             Show deleted lists that can still be restored

Examples:
  fridge shop lists
  fridge shop lists --deleted
```

### shop new

```text
usage: fridge shop new [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] --name NAME [--kind KIND] [--store STORE] [--icon ICON]
                       [--color COLOR] [--dry-run]

Make a list (grocery or shopping), optionally for a store.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --kind KIND           grocery (default) or shopping
  --store STORE
  --icon ICON           An emoji
  --color COLOR         A palette colour name or #RRGGBB
  --dry-run

Examples:
  fridge shop new --name "Warehouse run" --kind shopping --store "Northside Warehouse Club"
  fridge shop new --name "Hardware" --kind shopping --icon 🔨
```

### shop edit

```text
usage: fridge shop edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--list LIST] [--name NAME] [--store STORE] [--icon ICON]
                        [--color COLOR] [--dry-run]

Rename a list or change its store, icon or colour.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --name NAME
  --store STORE         The store ("" to clear it)
  --icon ICON
  --color COLOR
  --dry-run

Examples:
  fridge shop edit --list Hardware --store "Hammer & Nail"
```

### shop delete

```text
usage: fridge shop delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--list LIST]
                          [name]

Delete a list (restorable for the retention period).

positional arguments:
  name                  The list

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           The list (the same as giving its name)

Examples:
  fridge shop delete Hardware
  fridge shop delete --list Hardware
```

### shop restore

```text
usage: fridge shop restore [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--list LIST]
                           [name]

Bring back a deleted list.

positional arguments:
  name                  The deleted list

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           The deleted list (the same as giving its name)

Examples:
  fridge shop restore Hardware
  fridge shop restore --list Hardware
```

### shop add

```text
usage: fridge shop add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--list LIST] [--qty QTY] [--note NOTE] [--aisle AISLE]
                       [--again] [--dry-run]
                       items [items ...]

Add items ("milk x2" sets a quantity). Items file themselves into aisles; items already there aren't added twice, and crossed-off ones come back with their quantity.

positional arguments:
  items                 Items; "x2" at the end sets the quantity; commas separate items

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --qty QTY             Quantity for a single item, e.g. "2 lbs"
  --note NOTE           A note for a single item
  --aisle AISLE         Put it in this aisle instead of the automatic one
  --again               Add another line even if it's already on the list
  --dry-run

Examples:
  fridge shop add "milk x2" eggs bread
  fridge shop add "nails" --list Hardware --note "2 inch"
  fridge shop add "oat milk" --aisle Dairy
```

### shop show

```text
usage: fridge shop show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--list LIST] [--crossed]

Show a list grouped by aisle, in the store's order.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --crossed             List the crossed-off items too

Examples:
  fridge shop show
  fridge shop show --list Hardware --crossed
```

### shop cross

```text
usage: fridge shop cross [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--list LIST]
                         [items ...]

Cross items off (they drop to the crossed-off section).

positional arguments:
  items

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)

Examples:
  fridge shop cross milk eggs
  fridge shop cross I12 --list Hardware
```

### shop uncross

```text
usage: fridge shop uncross [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--list LIST] [--all]
                           [items ...]

Put crossed-off items back on the list (--all to reuse it).

positional arguments:
  items

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --all                 Uncross everything (reuse the list)

Examples:
  fridge shop uncross milk eggs
  fridge shop uncross --all
```

### shop readd

```text
usage: fridge shop readd [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--list LIST]
                         items [items ...]

Re-add items in one step, each with the quantity it had last time.

positional arguments:
  items

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)

Examples:
  fridge shop readd milk
  fridge shop readd milk bananas
```

### shop remove

```text
usage: fridge shop remove [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--list LIST]
                          items [items ...]

Take items off the list (not the same as crossing off).

positional arguments:
  items

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)

Examples:
  fridge shop remove kale
```

### shop clear

```text
usage: fridge shop clear [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--list LIST] [--everything]

Clear the crossed-off items (or --everything).

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --everything          Remove every item, crossed off or not

Examples:
  fridge shop clear
```

### shop item

```text
usage: fridge shop item [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--list LIST] [--name NAME] [--qty QTY] [--note NOTE]
                        [--aisle AISLE] [--dry-run]
                        item

Change an item's name, quantity, note or aisle. A new aisle is remembered for next time.

positional arguments:
  item

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --name NAME
  --qty QTY             "" clears it
  --note NOTE           "" clears it
  --aisle AISLE         An aisle on this list, or Other
  --dry-run

Examples:
  fridge shop item milk --qty "2 litres"
  fridge shop item "oat milk" --aisle Dairy
```

### shop suggest

```text
usage: fridge shop suggest [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--list LIST]
                           text

Suggestions while typing: what the household buys often, then common items.

positional arguments:
  text

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)

Examples:
  fridge shop suggest mi
```

### shop aisles

```text
usage: fridge shop aisles [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--list LIST] [--add ADD] [--rename RENAME] [--to TO]
                          [--move MOVE] [--first] [--before BEFORE] [--after AFTER] [--delete DELETE]
                          [--order ORDER] [--dry-run]

Show or change a list's aisle order: add, rename, move, delete, or set the whole order.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --add ADD             A new aisle name
  --rename RENAME       The aisle to rename (with --to)
  --to TO               The new name
  --move MOVE           The aisle to move (with --first, --before, --after; default: last)
  --first
  --before BEFORE
  --after AFTER
  --delete DELETE       The aisle to delete (its items move to Other)
  --order ORDER         Comma list: these aisles first, in this order
  --dry-run

Examples:
  fridge shop aisles
  fridge shop aisles --add "Bulk" --before Pantry
  fridge shop aisles --move Frozen --after Beverages
  fridge shop aisles --order "Bakery,Produce,Dairy"
  fridge shop aisles --rename Deli --to "Deli & Cheese"
```

### shop share

```text
usage: fridge shop share [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--list LIST] [--file]

The list as a tidy message with tick boxes, or a .txt file with --file.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (name or id; default: the household's grocery list)
  --file                Also save it as a text file to send

Examples:
  fridge shop share
  fridge shop share --list Hardware --file
```

## todo

```text
usage: fridge todo [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                   [--from PARTICIPANT]
                   {lists,list-new,list-edit,list-delete,list-restore,add,show,task,done,undo,edit,assign,delete,photo,chores}
                   ...

To-dos and chores: lists, tasks, assigning, repeats, rotation, stars.

positional arguments:
  {lists,list-new,list-edit,list-delete,list-restore,add,show,task,done,undo,edit,assign,delete,photo,chores}
    lists               Show the to-do lists you can see (your own list first).
    list-new            Make a shared to-do list with an emoji and colour.
    list-edit           Rename a to-do list or change its emoji or colour.
    list-delete         Delete a custom to-do list (restorable).
    list-restore        Bring back a deleted to-do list.
    add                 Add a task. Assigning someone else leaves them a notice; --rotate turns a repeating
                        chore between people.
    show                Show open tasks by list (overdue first), with today's finished ones counted.
    task                Show one task with its subtasks.
    done                Tick tasks off. --by <kid> gives the kid who did it a star; a repeating task makes
                        its next one.
    undo                Re-open a finished task (and take back its star).
    edit                Change a task: title, notes, list, due date, priority, assignee, repeat or rotation.
    assign              Give a task to someone (they get a notice; kids see it on the fridge sheet).
    delete              Delete a task and its subtasks.
    photo               Attach a saved photo to a task (kept as a file path), or remove one.
    chores              Everyone's chores for the coming week, with the kids' stars.

optional arguments:
  -h, --help            show this help message and exit
```

### todo lists

```text
usage: fridge todo lists [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT]

Show the to-do lists you can see (your own list first).

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo lists
```

### todo list-new

```text
usage: fridge todo list-new [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] --name NAME [--icon ICON] [--color COLOR] [--dry-run]

Make a shared to-do list with an emoji and colour.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --icon ICON
  --color COLOR
  --dry-run

Examples:
  fridge todo list-new --name "Garden" --icon 🌱 --color green
```

### todo list-edit

```text
usage: fridge todo list-edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                             [--from PARTICIPANT] [--name NAME] [--icon ICON] [--color COLOR]
                             list

Rename a to-do list or change its emoji or colour.

positional arguments:
  list

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --icon ICON
  --color COLOR

Examples:
  fridge todo list-edit Garden --icon 🌻
```

### todo list-delete

```text
usage: fridge todo list-delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT]
                               list

Delete a custom to-do list (restorable).

positional arguments:
  list

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo list-delete Garden
```

### todo list-restore

```text
usage: fridge todo list-restore [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                [--from PARTICIPANT]
                                list

Bring back a deleted to-do list.

positional arguments:
  list

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo list-restore Garden
```

### todo add

```text
usage: fridge todo add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--list LIST] [--mine] [--due DUE] [--priority PRIORITY]
                       [--assign ASSIGN] [--notes NOTES] [--repeat REPEAT] [--until UNTIL] [--times TIMES]
                       [--rotate ROTATE] [--parent PARENT] [--dry-run]
                       title

Add a task. Assigning someone else leaves them a notice; --rotate turns a repeating chore between people.

positional arguments:
  title

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (default: "Household Tasks")
  --mine                Put it on your own private My Tasks list
  --due DUE             today, tomorrow, friday, next week, +3, 2026-11-02 ...
  --priority PRIORITY   none, low, medium or high
  --assign ASSIGN       Who it's for (a member)
  --notes NOTES
  --repeat REPEAT       e.g. daily, weekdays, "weekly on mon,thu", "every 2 weeks", monthly
  --until UNTIL         Last date for the repeat
  --times TIMES         How many times in all
  --rotate ROTATE       People who take turns, in order: "Theo, Lily, Zoe"
  --parent PARENT       Make it a subtask of this task (one level only)
  --dry-run

Examples:
  fridge todo add "Book the dentist" --mine --due friday
  fridge todo add "Fix the gate" --assign Luis --due "this weekend" --priority high
  fridge todo add "Take out the bins" --repeat "weekly on mon" --rotate "Theo, Lily, Zoe"
  fridge todo add "Wipe the mirror" --parent "Clean the bathroom"
```

### todo show

```text
usage: fridge todo show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--list LIST] [--mine] [--assignee ASSIGNEE]
                        [--due {today,overdue,week}] [--done]

Show open tasks by list (overdue first), with today's finished ones counted.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST
  --mine
  --assignee ASSIGNEE   Only this person's tasks
  --due {today,overdue,week}
  --done                List the tasks finished in the last 24 hours

Examples:
  fridge todo show
  fridge todo show --mine
  fridge todo show --assignee Luis --due week
  fridge todo show --list Garden --done
```

### todo task

```text
usage: fridge todo task [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT]
                        task

Show one task with its subtasks.

positional arguments:
  task

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo task "Fix the gate"
```

### todo done

```text
usage: fridge todo done [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--by BY] [--dry-run]
                        tasks [tasks ...]

Tick tasks off. --by <kid> gives the kid who did it a star; a repeating task makes its next one.

positional arguments:
  tasks

optional arguments:
  -h, --help            show this help message and exit
  --by BY               Who actually did it (a kid or teen gets a star)
  --dry-run

Examples:
  fridge todo done "Fix the gate"
  fridge todo done "Take out the bins" --by Theo
  fridge todo done T4 T7
```

### todo undo

```text
usage: fridge todo undo [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT]
                        task

Re-open a finished task (and take back its star).

positional arguments:
  task

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo undo "Fix the gate"
```

### todo edit

```text
usage: fridge todo edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--title TITLE] [--notes NOTES] [--list LIST] [--due DUE]
                        [--no-due] [--priority PRIORITY] [--assign ASSIGN] [--unassign] [--repeat REPEAT]
                        [--until UNTIL] [--times TIMES] [--no-repeat] [--rotate ROTATE] [--no-rotate]
                        [--dry-run]
                        task

Change a task: title, notes, list, due date, priority, assignee, repeat or rotation.

positional arguments:
  task

optional arguments:
  -h, --help            show this help message and exit
  --title TITLE
  --notes NOTES
  --list LIST
  --due DUE
  --no-due
  --priority PRIORITY
  --assign ASSIGN
  --unassign
  --repeat REPEAT
  --until UNTIL
  --times TIMES
  --no-repeat
  --rotate ROTATE
  --no-rotate
  --dry-run

Examples:
  fridge todo edit "Fix the gate" --due tomorrow
  fridge todo edit T9 --repeat "every 2 weeks" --rotate "Kai, Jess, Sam"
  fridge todo edit T3 --no-due
```

### todo assign

```text
usage: fridge todo assign [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--dry-run]
                          task member

Give a task to someone (they get a notice; kids see it on the fridge sheet).

positional arguments:
  task
  member

optional arguments:
  -h, --help            show this help message and exit
  --dry-run

Examples:
  fridge todo assign "Fix the gate" Luis
```

### todo delete

```text
usage: fridge todo delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT]
                          task

Delete a task and its subtasks.

positional arguments:
  task

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge todo delete "Fix the gate"
```

### todo photo

```text
usage: fridge todo photo [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--add ADD] [--remove REMOVE]
                         task

Attach a saved photo to a task (kept as a file path), or remove one.

positional arguments:
  task

optional arguments:
  -h, --help            show this help message and exit
  --add ADD             Path of a saved photo
  --remove REMOVE       Path to remove

Examples:
  fridge todo photo "Fix the gate" --add /workspace/photos/gate.jpg
```

### todo chores

```text
usage: fridge todo chores [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--member MEMBER]

Everyone's chores for the coming week, with the kids' stars.

optional arguments:
  -h, --help            show this help message and exit
  --member MEMBER

Examples:
  fridge todo chores
  fridge todo chores --member Theo
```

## notices

```text
usage: fridge notices [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                      [--from PARTICIPANT]
                      {list,clear} ...

Notices waiting for the person talking (e.g. tasks someone assigned them).

positional arguments:
  {list,clear}
    list                Show the person's new notices and mark them as delivered (--keep to leave them new).
    clear               Delete the person's delivered notices.

optional arguments:
  -h, --help            show this help message and exit
```

### notices list

```text
usage: fridge notices list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--all] [--keep]

Show the person's new notices and mark them as delivered (--keep to leave them new).

optional arguments:
  -h, --help            show this help message and exit
  --all                 Include ones already delivered
  --keep                Don't mark them as delivered

Examples:
  fridge notices list
  fridge notices list --all
```

### notices clear

```text
usage: fridge notices clear [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT]

Delete the person's delivered notices.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge notices clear
```

## today

```text
usage: fridge today [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                    [--from PARTICIPANT] [--for MEMBER] [--date DATE] [--peek]

The Today summary: today's events, tasks due, tonight's dinner, lists to shop, birthdays, bills and new notices, in the member's chosen sections. Run it first thing each day.

optional arguments:
  -h, --help            show this help message and exit
  --for MEMBER          Someone else's day (e.g. a kid's chores)
  --date DATE           Another day (default today)
  --peek                Don't mark the notices shown as delivered

Examples:
  fridge today
  fridge today --for Theo
  fridge today --date tomorrow
  fridge today --chat family --from @ana
```

## cal

```text
usage: fridge cal [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                  [--from PARTICIPANT]
                  {add,agenda,day,week,month,show,edit,skip,delete,birthday,birthdays,busy} ...

The household calendar: events, repeats, birthdays, views, busy evenings.

positional arguments:
  {add,agenda,day,week,month,show,edit,skip,delete,birthday,birthdays,busy}
    add                 Add an event: all day, or with a time; who it's for; visibility; reminders; repeats.
    agenda              The next days, in order (default 7).
    day                 One day.
    week                The week containing a date.
    month               A whole month.
    show                One event with its repeat and next dates.
    edit                Change an event, or with --on just one date of a repeating event.
    skip                Skip one date of a repeating event (--undo to bring it back).
    delete              Delete an event (all repeats), or end a repeating one from a date.
    birthday            Add a birthday (or --anniversary) that repeats every year. For kids, day and month
                        only.
    birthdays           Birthdays and anniversaries coming up.
    busy                Busy evenings (events around dinner time), for planning meals.

optional arguments:
  -h, --help            show this help message and exit
```

### cal add

```text
usage: fridge cal add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                      [--from PARTICIPANT] [--date DATE] [--time TIME] [--end END] [--minutes MINUTES]
                      [--until-date UNTIL_DATE] [--location LOCATION] [--type TYPE] [--for WHO] [--only]
                      [--private] [--visibility VISIBILITY] [--remind REMIND] [--repeat REPEAT]
                      [--until UNTIL] [--times TIMES] [--notes NOTES] [--dry-run]
                      title

Add an event: all day, or with a time; who it's for; visibility; reminders; repeats.

positional arguments:
  title

optional arguments:
  -h, --help            show this help message and exit
  --date DATE           today, friday, next week, 2026-11-02 ... (default today)
  --time TIME           Start time; leave out for all day
  --end END             End time
  --minutes MINUTES     Length in minutes (instead of --end)
  --until-date UNTIL_DATE
                        Last day of a multi-day event
  --location LOCATION
  --type TYPE           appointment, school, sports, health, social, work, travel, ... (guessed)
  --for WHO             Who it's for: "Theo, Lily"
  --only                Only the people in --for (and you) can see it
  --private             Only you can see it, and never in a group chat
  --visibility VISIBILITY
                        household, members or private
  --remind REMIND       Reminders before the start: "30m, 1d"
  --repeat REPEAT       daily, weekly, every 2 weeks, monthly on the 2nd tuesday, yearly ...
  --until UNTIL
  --times TIMES
  --notes NOTES
  --dry-run

Examples:
  fridge cal add "Dentist" --date friday --time 15:30 --minutes 45 --for Theo --remind 1d,1h
  fridge cal add "Soccer practice" --date tuesday --time 17:30 --end 19:00 --for Lily --repeat weekly
  fridge cal add "Camping trip" --date 2026-11-06 --until-date 2026-11-08
  fridge cal add "Surprise party planning" --date saturday --time 20:00 --for "Ana, Luis" --only
```

### cal agenda

```text
usage: fridge cal agenda [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--days DAYS] [--from-date START] [--for WHO]
                         [--layers LAYERS]

The next days, in order (default 7).

optional arguments:
  -h, --help            show this help message and exit
  --days DAYS
  --from-date START     Start from this date
  --for WHO             Only events involving this member
  --layers LAYERS       Extra layers, comma list: meals, bills

Examples:
  fridge cal agenda --days 14 --for Lily
```

### cal day

```text
usage: fridge cal day [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                      [--from PARTICIPANT] [--for WHO] [--layers LAYERS]
                      [date]

One day.

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit
  --for WHO             Only events involving this member
  --layers LAYERS       Extra layers, comma list: meals, bills

Examples:
  fridge cal day tomorrow
```

### cal week

```text
usage: fridge cal week [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--for WHO] [--layers LAYERS]
                       [date]

The week containing a date.

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit
  --for WHO             Only events involving this member
  --layers LAYERS       Extra layers, comma list: meals, bills

Examples:
  fridge cal week --layers meals
```

### cal month

```text
usage: fridge cal month [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--for WHO] [--layers LAYERS]
                        [month]

A whole month.

positional arguments:
  month                 YYYY-MM (default this month)

optional arguments:
  -h, --help            show this help message and exit
  --for WHO             Only events involving this member
  --layers LAYERS       Extra layers, comma list: meals, bills

Examples:
  fridge cal month 2026-11
```

### cal show

```text
usage: fridge cal show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT]
                       event

One event with its repeat and next dates.

positional arguments:
  event

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge cal show "Soccer practice"
```

### cal edit

```text
usage: fridge cal edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--on ON] [--title TITLE] [--date DATE] [--time TIME]
                       [--end END] [--all-day] [--location LOCATION] [--for WHO] [--remind REMIND]
                       [--notes NOTES] [--visibility VISIBILITY] [--type TYPE] [--repeat REPEAT]
                       [--no-repeat] [--dry-run]
                       event

Change an event, or with --on just one date of a repeating event.

positional arguments:
  event

optional arguments:
  -h, --help            show this help message and exit
  --on ON               Only this date of a repeating event
  --title TITLE
  --date DATE
  --time TIME
  --end END
  --all-day
  --location LOCATION
  --for WHO
  --remind REMIND
  --notes NOTES
  --visibility VISIBILITY
  --type TYPE
  --repeat REPEAT
  --no-repeat
  --dry-run

Examples:
  fridge cal edit "Soccer practice" --on 2026-10-27 --time 18:00
  fridge cal edit Dentist --date monday
```

### cal skip

```text
usage: fridge cal skip [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] --on ON [--undo] [--dry-run]
                       event

Skip one date of a repeating event (--undo to bring it back).

positional arguments:
  event

optional arguments:
  -h, --help            show this help message and exit
  --on ON
  --undo
  --dry-run

Examples:
  fridge cal skip "Soccer practice" --on 2026-10-27
```

### cal delete

```text
usage: fridge cal delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--from-date START]
                         event

Delete an event (all repeats), or end a repeating one from a date.

positional arguments:
  event

optional arguments:
  -h, --help            show this help message and exit
  --from-date START     Start from this date

Examples:
  fridge cal delete Dentist
  fridge cal delete "Soccer practice" --from-date 2026-12-01
```

### cal birthday

```text
usage: fridge cal birthday [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--name NAME] [--member MEMBER] --date DATE [--anniversary]
                           [--dry-run]

Add a birthday (or --anniversary) that repeats every year. For kids, day and month only.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --member MEMBER       A household member (their name is used)
  --date DATE
  --anniversary
  --dry-run

Examples:
  fridge cal birthday --name "Grandma Rosa" --date 1948-03-14
  fridge cal birthday --member Theo --date "14 March"
  fridge cal birthday --name "Our anniversary" --date 2012-06-02 --anniversary
```

### cal birthdays

```text
usage: fridge cal birthdays [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] [--days DAYS]

Birthdays and anniversaries coming up.

optional arguments:
  -h, --help            show this help message and exit
  --days DAYS

Examples:
  fridge cal birthdays --days 30
```

### cal busy

```text
usage: fridge cal busy [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--from-date START] [--days DAYS]

Busy evenings (events around dinner time), for planning meals.

optional arguments:
  -h, --help            show this help message and exit
  --from-date START     Start from this date
  --days DAYS

Examples:
  fridge cal busy
```

## recipe

```text
usage: fridge recipe [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]
                     {add,import,list,show,edit,delete,to-list,cook,cooked} ...

Recipes: add (by hand, from a saved page or a photo), show, scale, cook, to a list.

positional arguments:
  {add,import,list,show,edit,delete,to-list,cook,cooked}
    add                 Save a recipe by hand, or from structured data (--spec) the agent read from a photo
                        of a recipe card.
    import              Read a recipe from a web page the agent saved (schema.org Recipe data). No network.
    list                List recipes, by tag, search words or quick ones.
    show                Show a recipe, scaled with --servings.
    edit                Change a recipe: title, servings, times, ingredients (add, set N=..., remove N),
                        steps, tags, notes.
    delete              Delete a recipe.
    to-list             Send a recipe's ingredients to a grocery list. Run with --dry-run first to review:
                        pantry items are skipped, unknown staples and "to taste" items go to a check-at-home
                        pile, duplicates merge.
    cook                Cook mode, one step at a time: start with a recipe, then --next, --back, --step N,
                        or --stop (--done).
    cooked              Note that a recipe was cooked today (helps meal ideas).

optional arguments:
  -h, --help            show this help message and exit
```

### recipe add

```text
usage: fridge recipe add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--title TITLE] [--servings SERVINGS] [--prep PREP]
                         [--cook COOK] [--ingredient INGREDIENT] [--step STEP] [--tag TAG] [--notes NOTES]
                         [--photo PHOTO] [--unclear UNCLEAR] [--spec SPEC] [--source {manual,photo}]
                         [--dry-run]

Save a recipe by hand, or from structured data (--spec) the agent read from a photo of a recipe card.

optional arguments:
  -h, --help            show this help message and exit
  --title TITLE
  --servings SERVINGS
  --prep PREP           Prep time, e.g. 15 or 1h15m
  --cook COOK           Cook time
  --ingredient INGREDIENT
                        One ingredient line; repeat
  --step STEP           One step; repeat
  --tag TAG
  --notes NOTES
  --photo PHOTO         Path of a saved photo
  --unclear UNCLEAR     Something the person must confirm (photo imports)
  --spec SPEC           JSON: title, servings, ingredients, steps, tags, prep_min, cook_min, unclear
  --source {manual,photo}
  --dry-run

Examples:
  fridge recipe add --title "Pancakes" --servings 4 --ingredient "1 1/2 cups flour" --ingredient "2 eggs" --step "Whisk everything" --tag breakfast
  fridge recipe add --spec card.json --source photo --photo /workspace/photos/card.jpg
```

### recipe import

```text
usage: fridge recipe import [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT] [--url URL] [--again] [--dry-run]
                            page

Read a recipe from a web page the agent saved (schema.org Recipe data). No network.

positional arguments:
  page                  Path of the saved page

optional arguments:
  -h, --help            show this help message and exit
  --url URL             Where the page came from
  --again               Save it even if it looks like one already saved
  --dry-run

Examples:
  fridge recipe import /workspace/pages/chili.html --url https://example.com/chili
```

### recipe list

```text
usage: fridge recipe list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--tag TAG] [--search SEARCH] [--quick]

List recipes, by tag, search words or quick ones.

optional arguments:
  -h, --help            show this help message and exit
  --tag TAG
  --search SEARCH
  --quick               30 minutes or less

Examples:
  fridge recipe list
  fridge recipe list --tag dinner --quick
  fridge recipe list --search chicken
```

### recipe show

```text
usage: fridge recipe show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--servings SERVINGS]
                          recipe

Show a recipe, scaled with --servings.

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit
  --servings SERVINGS

Examples:
  fridge recipe show Chili --servings 6
```

### recipe edit

```text
usage: fridge recipe edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--title TITLE] [--servings SERVINGS] [--prep PREP]
                          [--cook COOK] [--add-ingredient ADD_INGREDIENT] [--set-ingredient SET_INGREDIENT]
                          [--remove-ingredient REMOVE_INGREDIENT] [--add-step ADD_STEP] [--tag TAG]
                          [--untag UNTAG] [--notes NOTES] [--photo PHOTO] [--checked] [--dry-run]
                          recipe

Change a recipe: title, servings, times, ingredients (add, set N=..., remove N), steps, tags, notes.

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit
  --title TITLE
  --servings SERVINGS
  --prep PREP
  --cook COOK
  --add-ingredient ADD_INGREDIENT
  --set-ingredient SET_INGREDIENT
                        N=new line
  --remove-ingredient REMOVE_INGREDIENT
                        Ingredient number
  --add-step ADD_STEP
  --tag TAG
  --untag UNTAG
  --notes NOTES
  --photo PHOTO
  --checked             The person has checked the unclear bits
  --dry-run

Examples:
  fridge recipe edit Chili --servings 6
  fridge recipe edit Chili --set-ingredient "3=2 tsp cumin"
  fridge recipe edit Pancakes --checked
```

### recipe delete

```text
usage: fridge recipe delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT]
                            recipe

Delete a recipe.

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge recipe delete Chili
```

### recipe to-list

```text
usage: fridge recipe to-list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                             [--from PARTICIPANT] [--list LIST] [--servings SERVINGS] [--skip SKIP]
                             [--dry-run]
                             recipe

Send a recipe's ingredients to a grocery list. Run with --dry-run first to review: pantry items are skipped, unknown staples and "to taste" items go to a check-at-home pile, duplicates merge.

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit
  --list LIST           Which list (default: the household's grocery list)
  --servings SERVINGS
  --skip SKIP           Items to leave out (comma list)
  --dry-run

Examples:
  fridge recipe to-list Chili --dry-run
  fridge recipe to-list Chili --servings 6 --skip "salt, cumin"
```

### recipe cook

```text
usage: fridge recipe cook [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--servings SERVINGS] [--next] [--back] [--step STEP]
                          [--stop] [--done]
                          [recipe]

Cook mode, one step at a time: start with a recipe, then --next, --back, --step N, or --stop (--done).

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit
  --servings SERVINGS
  --next
  --back
  --step STEP
  --stop
  --done                With --stop: note that it was cooked today

Examples:
  fridge recipe cook Chili
  fridge recipe cook --next
  fridge recipe cook --stop --done
```

### recipe cooked

```text
usage: fridge recipe cooked [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                            [--from PARTICIPANT]
                            recipe

Note that a recipe was cooked today (helps meal ideas).

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge recipe cooked Chili
```

## pantry

```text
usage: fridge pantry [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]
                     {show,set} ...

The pantry: what's in, low or out, and staples to check before shopping.

positional arguments:
  {show,set}
    show                Show what the pantry knows.
    set                 Mark items in, low or out, mark staples (things usually kept), or forget items.

optional arguments:
  -h, --help            show this help message and exit
```

### pantry show

```text
usage: fridge pantry show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT]

Show what the pantry knows.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge pantry show
```

### pantry set

```text
usage: fridge pantry set [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--status {in,low,out}] [--staple] [--not-staple] [--forget]
                         items [items ...]

Mark items in, low or out, mark staples (things usually kept), or forget items.

positional arguments:
  items

optional arguments:
  -h, --help            show this help message and exit
  --status {in,low,out}
  --staple
  --not-staple
  --forget

Examples:
  fridge pantry set "rice, flour, olive oil" --status in --staple
  fridge pantry set milk --status out
  fridge pantry set kale --forget
```

## meal

```text
usage: fridge meal [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                   [--from PARTICIPANT]
                   {plan,swap,remove,week,to-list,nights,ideas} ...

The meal plan: plan the week, keep the grocery list in step, busy nights, ideas.

positional arguments:
  {plan,swap,remove,week,to-list,nights,ideas}
    plan                Plan a meal: a recipe, quick text, or leftovers of an earlier meal. A long cook on a
                        busy evening is refused unless --anyway. If the week's list was made, it's updated
                        by this meal's share only.
    swap                Replace a planned meal (the grocery list changes by the difference only).
    remove              Clear a planned meal (its share comes off the week's list, crossed-off items stay).
    week                The week's meals (busy evenings marked).
    to-list             Make (or refresh) the week's grocery list from the plan: merged amounts, pantry
                        items skipped, unknown staples to check at home. Use --dry-run to review first.
    nights              Which evenings are busy this week, and any long cook planned on one.
    ideas               Meal ideas from your own recipes and pantry (suggestions to confirm).

optional arguments:
  -h, --help            show this help message and exit
```

### meal plan

```text
usage: fridge meal plan [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--meal MEAL] [--recipe RECIPE] [--text TEXT]
                        [--leftovers-of LEFTOVERS_OF] [--servings SERVINGS] [--replace] [--anyway]
                        [--dry-run]
                        date

Plan a meal: a recipe, quick text, or leftovers of an earlier meal. A long cook on a busy evening is refused unless --anyway. If the week's list was made, it's updated by this meal's share only.

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit
  --meal MEAL           breakfast, lunch, dinner (default) or snack
  --recipe RECIPE
  --text TEXT
  --leftovers-of LEFTOVERS_OF
                        The day whose meal this is leftovers of
  --servings SERVINGS
  --replace             Replace what's planned for that meal
  --anyway              Plan a long cook on a busy evening anyway
  --dry-run

Examples:
  fridge meal plan monday --recipe Chili --servings 6
  fridge meal plan friday --text "Eating out"
  fridge meal plan tuesday --leftovers-of monday
  fridge meal plan saturday --meal lunch --recipe Pancakes
```

### meal swap

```text
usage: fridge meal swap [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--meal MEAL] [--recipe RECIPE] [--text TEXT]
                        [--servings SERVINGS] [--anyway] [--dry-run]
                        date

Replace a planned meal (the grocery list changes by the difference only).

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit
  --meal MEAL
  --recipe RECIPE
  --text TEXT
  --servings SERVINGS
  --anyway
  --dry-run

Examples:
  fridge meal swap wednesday --recipe "Fish tacos"
```

### meal remove

```text
usage: fridge meal remove [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--meal MEAL] [--entry ENTRY]
                          [date]

Clear a planned meal (its share comes off the week's list, crossed-off items stay).

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit
  --meal MEAL
  --entry ENTRY         A planned meal's id

Examples:
  fridge meal remove wednesday
  fridge meal remove --entry P4
```

### meal week

```text
usage: fridge meal week [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT]
                        [date]

The week's meals (busy evenings marked).

positional arguments:
  date

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge meal week
  fridge meal week "next week"
```

### meal to-list

```text
usage: fridge meal to-list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--week WEEK] [--list LIST] [--skip SKIP] [--dry-run]

Make (or refresh) the week's grocery list from the plan: merged amounts, pantry items skipped, unknown staples to check at home. Use --dry-run to review first.

optional arguments:
  -h, --help            show this help message and exit
  --week WEEK           Any day in the week (default this week)
  --list LIST           Which list (default: the household's grocery list)
  --skip SKIP           Items to leave out (comma list)
  --dry-run

Examples:
  fridge meal to-list --dry-run
  fridge meal to-list --week "next week" --skip "rice, salt"
```

### meal nights

```text
usage: fridge meal nights [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--week WEEK]

Which evenings are busy this week, and any long cook planned on one.

optional arguments:
  -h, --help            show this help message and exit
  --week WEEK

Examples:
  fridge meal nights
```

### meal ideas

```text
usage: fridge meal ideas [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--date DATE]

Meal ideas from your own recipes and pantry (suggestions to confirm).

optional arguments:
  -h, --help            show this help message and exit
  --date DATE

Examples:
  fridge meal ideas
  fridge meal ideas --date thursday
```

## note

```text
usage: fridge note [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                   [--from PARTICIPANT]
                   {add,list,show,edit,check,delete} ...

Notes: shared or private, checklists, folders and tags, pinned notes, sensitive notes.

positional arguments:
  {add,list,show,edit,check,delete}
    add                 Save a note. --sensitive keeps it out of group chats and printouts; --private keeps
                        it to yourself.
    list                List notes (pinned first), by folder, tag or search words.
    show                Show one note.
    edit                Change a note: title, text (or --append), folder, tags, pin, sensitive,
                        private/shared, items, photos.
    check               Tick checklist items by number or words (--undo to untick).
    delete              Delete a note.

optional arguments:
  -h, --help            show this help message and exit
```

### note add

```text
usage: fridge note add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--body BODY] [--item ITEM] [--photo PHOTO] [--folder FOLDER]
                       [--tag TAG] [--pin] [--private] [--sensitive] [--dry-run]
                       title

Save a note. --sensitive keeps it out of group chats and printouts; --private keeps it to yourself.

positional arguments:
  title

optional arguments:
  -h, --help            show this help message and exit
  --body BODY
  --item ITEM           A checklist item; repeat
  --photo PHOTO         Path of a saved photo; repeat
  --folder FOLDER
  --tag TAG
  --pin
  --private
  --sensitive
  --dry-run

Examples:
  fridge note add "Wifi" --body "Network: Maple-5G" --pin --sensitive
  fridge note add "Sitter instructions" --body "Bedtime 8pm" --folder Kids --pin
  fridge note add "Camping packing list" --item tent --item "sleeping bags" --tag trips
```

### note list

```text
usage: fridge note list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--folder FOLDER] [--tag TAG] [--pinned] [--search SEARCH]

List notes (pinned first), by folder, tag or search words.

optional arguments:
  -h, --help            show this help message and exit
  --folder FOLDER
  --tag TAG
  --pinned
  --search SEARCH

Examples:
  fridge note list
  fridge note list --folder Kids
  fridge note list --search wifi
```

### note show

```text
usage: fridge note show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT]
                        note

Show one note.

positional arguments:
  note

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge note show Wifi
```

### note edit

```text
usage: fridge note edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                        [--from PARTICIPANT] [--title TITLE] [--body BODY] [--append APPEND]
                        [--folder FOLDER] [--tag TAG] [--untag UNTAG] [--pin] [--unpin] [--sensitive]
                        [--not-sensitive] [--private] [--shared] [--add-item ADD_ITEM]
                        [--add-photo ADD_PHOTO] [--dry-run]
                        note

Change a note: title, text (or --append), folder, tags, pin, sensitive, private/shared, items, photos.

positional arguments:
  note

optional arguments:
  -h, --help            show this help message and exit
  --title TITLE
  --body BODY
  --append APPEND
  --folder FOLDER
  --tag TAG
  --untag UNTAG
  --pin
  --unpin
  --sensitive
  --not-sensitive
  --private
  --shared
  --add-item ADD_ITEM
  --add-photo ADD_PHOTO
  --dry-run

Examples:
  fridge note edit Wifi --body "Network: Maple-5G, password on the router"
  fridge note edit "Sitter instructions" --append "Allergic to peanuts"
  fridge note edit "Packing list" --add-item torch
```

### note check

```text
usage: fridge note check [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--undo]
                         note items [items ...]

Tick checklist items by number or words (--undo to untick).

positional arguments:
  note
  items

optional arguments:
  -h, --help            show this help message and exit
  --undo

Examples:
  fridge note check "Packing list" 1 tent
```

### note delete

```text
usage: fridge note delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT]
                          note

Delete a note.

positional arguments:
  note

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge note delete "Old wifi"
```

## budget

```text
usage: fridge budget [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]
                     {categories,category-add,category-defaults,category-edit,category-delete,spend,expenses,expense-edit,expense-delete,month,trend,bill-add,bills,bill-paid,bill-edit,bill-delete,goal-add,goal-save,goals,goal-delete}
                     ...

The household budget: categories, expenses, bills, savings goals, month reports.

positional arguments:
  {categories,category-add,category-defaults,category-edit,category-delete,spend,expenses,expense-edit,expense-delete,month,trend,bill-add,bills,bill-paid,bill-edit,bill-delete,goal-add,goal-save,goals,goal-delete}
    categories          Categories with this month's spending against their budgets.
    category-add        Add a category, optionally with a monthly budget.
    category-defaults   Add the usual categories (Groceries, Housing, Utilities ...), with no budgets yet.
    category-edit       Rename a category, set its monthly budget (or none), or change its icon.
    category-delete     Delete a category (move its expenses with --move-to).
    spend               Log an expense. From a receipt photo: read it, run with --dry-run, check with the
                        person, then log it.
    expenses            List expenses for a month, by category or person.
    expense-edit        Change an expense.
    expense-delete      Delete an expense.
    month               The month at a glance: spent vs budget per category.
    trend               Spending month by month.
    bill-add            Add a recurring bill with its due date (reminded 3 days before by default, shown on
                        the calendar).
    bills               Bills coming up (and any overdue).
    bill-paid           Record a bill as paid (logs the expense).
    bill-edit           Change a bill.
    bill-delete         Delete a bill.
    goal-add            Start a shared savings goal.
    goal-save           Put money towards a goal (negative to take some out).
    goals               Savings goals with progress.
    goal-delete         Delete a goal.

optional arguments:
  -h, --help            show this help message and exit
```

### budget categories

```text
usage: fridge budget categories [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                [--from PARTICIPANT] [--month MONTH]

Categories with this month's spending against their budgets.

optional arguments:
  -h, --help            show this help message and exit
  --month MONTH

Examples:
  fridge budget categories
  fridge budget categories --month "last month"
```

### budget category-add

```text
usage: fridge budget category-add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                  [--from PARTICIPANT] [--monthly MONTHLY] [--icon ICON] [--dry-run]
                                  name

Add a category, optionally with a monthly budget.

positional arguments:
  name

optional arguments:
  -h, --help            show this help message and exit
  --monthly MONTHLY     Monthly budget
  --icon ICON
  --dry-run

Examples:
  fridge budget category-add "Pets" --monthly 120 --icon 🐾
```

### budget category-defaults

```text
usage: fridge budget category-defaults [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER]
                                       [--chat CHAT] [--from PARTICIPANT]

Add the usual categories (Groceries, Housing, Utilities ...), with no budgets yet.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge budget category-defaults
```

### budget category-edit

```text
usage: fridge budget category-edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                   [--from PARTICIPANT] [--name NAME] [--monthly MONTHLY] [--icon ICON]
                                   category

Rename a category, set its monthly budget (or none), or change its icon.

positional arguments:
  category

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --monthly MONTHLY
  --icon ICON

Examples:
  fridge budget category-edit Groceries --monthly 800
```

### budget category-delete

```text
usage: fridge budget category-delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                     [--from PARTICIPANT] [--move-to MOVE_TO]
                                     category

Delete a category (move its expenses with --move-to).

positional arguments:
  category

optional arguments:
  -h, --help            show this help message and exit
  --move-to MOVE_TO

Examples:
  fridge budget category-delete Fun --move-to Other
```

### budget spend

```text
usage: fridge budget spend [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] --category CATEGORY [--by BY] [--date DATE] [--note NOTE]
                           [--receipt RECEIPT] [--dry-run]
                           amount

Log an expense. From a receipt photo: read it, run with --dry-run, check with the person, then log it.

positional arguments:
  amount

optional arguments:
  -h, --help            show this help message and exit
  --category CATEGORY
  --by BY               Who spent it (default: you)
  --date DATE
  --note NOTE
  --receipt RECEIPT     Path of a saved receipt photo
  --dry-run

Examples:
  fridge budget spend 54.20 --category Groceries
  fridge budget spend 38 --category "Eating out" --by Luis --note "Pizza night" --receipt /workspace/receipts/pizza.jpg --dry-run
```

### budget expenses

```text
usage: fridge budget expenses [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                              [--from PARTICIPANT] [--month MONTH] [--category CATEGORY] [--by BY]

List expenses for a month, by category or person.

optional arguments:
  -h, --help            show this help message and exit
  --month MONTH
  --category CATEGORY
  --by BY

Examples:
  fridge budget expenses
  fridge budget expenses --month 2026-09 --category Groceries
```

### budget expense-edit

```text
usage: fridge budget expense-edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                  [--from PARTICIPANT] [--amount AMOUNT] [--category CATEGORY] [--date DATE]
                                  [--note NOTE] [--by BY] [--dry-run]
                                  expense

Change an expense.

positional arguments:
  expense

optional arguments:
  -h, --help            show this help message and exit
  --amount AMOUNT
  --category CATEGORY
  --date DATE
  --note NOTE
  --by BY
  --dry-run

Examples:
  fridge budget expense-edit X4 --amount 45.10
```

### budget expense-delete

```text
usage: fridge budget expense-delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                    [--from PARTICIPANT] [--dry-run]
                                    expense

Delete an expense.

positional arguments:
  expense

optional arguments:
  -h, --help            show this help message and exit
  --dry-run

Examples:
  fridge budget expense-delete X4
```

### budget month

```text
usage: fridge budget month [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT]
                           [month]

The month at a glance: spent vs budget per category.

positional arguments:
  month

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge budget month
  fridge budget month 2026-09
```

### budget trend

```text
usage: fridge budget trend [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--months MONTHS]

Spending month by month.

optional arguments:
  -h, --help            show this help message and exit
  --months MONTHS

Examples:
  fridge budget trend --months 6
```

### budget bill-add

```text
usage: fridge budget bill-add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                              [--from PARTICIPANT] [--amount AMOUNT] --due DUE [--repeat REPEAT]
                              [--until UNTIL] [--times TIMES] [--category CATEGORY] [--remind REMIND]
                              [--no-calendar] [--autopay] [--dry-run]
                              name

Add a recurring bill with its due date (reminded 3 days before by default, shown on the calendar).

positional arguments:
  name

optional arguments:
  -h, --help            show this help message and exit
  --amount AMOUNT
  --due DUE             The first due date
  --repeat REPEAT       monthly, every 3 months, yearly ... (leave out for a one-off)
  --until UNTIL         The last due date, for a bill that stops
  --times TIMES         How many payments in all
  --category CATEGORY
  --remind REMIND       How long before: "3d", "1w" (default 3d)
  --no-calendar         Don't show it on the calendar
  --autopay
  --dry-run

Examples:
  fridge budget bill-add Rent --amount 1800 --due 2026-11-01 --repeat monthly --category Housing
  fridge budget bill-add "Car insurance" --amount 640 --due 2027-03-15 --repeat yearly --remind 2w
```

### budget bills

```text
usage: fridge budget bills [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--days DAYS]

Bills coming up (and any overdue).

optional arguments:
  -h, --help            show this help message and exit
  --days DAYS

Examples:
  fridge budget bills --days 31
```

### budget bill-paid

```text
usage: fridge budget bill-paid [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT] [--due DUE] [--amount AMOUNT] [--date DATE] [--by BY]
                               [--dry-run]
                               bill

Record a bill as paid (logs the expense).

positional arguments:
  bill

optional arguments:
  -h, --help            show this help message and exit
  --due DUE             Which due date (default: the oldest unpaid, if it's due within a week)
  --amount AMOUNT       If it differs from the usual amount
  --date DATE           When it was paid (default today)
  --by BY               Who paid it (default: you)
  --dry-run

Examples:
  fridge budget bill-paid Rent
  fridge budget bill-paid Hydro --amount 142.37
```

### budget bill-edit

```text
usage: fridge budget bill-edit [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT] [--name NAME] [--amount AMOUNT] [--category CATEGORY]
                               [--remind REMIND] [--calendar CALENDAR] [--autopay AUTOPAY] [--due DUE]
                               [--until UNTIL] [--no-repeat] [--dry-run]
                               bill

Change a bill.

positional arguments:
  bill

optional arguments:
  -h, --help            show this help message and exit
  --name NAME
  --amount AMOUNT
  --category CATEGORY
  --remind REMIND
  --calendar CALENDAR   yes or no
  --autopay AUTOPAY     yes or no
  --due DUE             Move the next due date (later ones follow)
  --until UNTIL         The last due date, for a bill that stops
  --no-repeat           Stop it repeating
  --dry-run

Examples:
  fridge budget bill-edit Rent --amount 1850
```

### budget bill-delete

```text
usage: fridge budget bill-delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                 [--from PARTICIPANT]
                                 bill

Delete a bill.

positional arguments:
  bill

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge budget bill-delete Gym
```

### budget goal-add

```text
usage: fridge budget goal-add [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                              [--from PARTICIPANT] --target TARGET [--by DEADLINE] [--dry-run]
                              name

Start a shared savings goal.

positional arguments:
  name

optional arguments:
  -h, --help            show this help message and exit
  --target TARGET
  --by DEADLINE         Target date
  --dry-run

Examples:
  fridge budget goal-add "Holiday fund" --target 3000 --by 2027-07-01
```

### budget goal-save

```text
usage: fridge budget goal-save [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                               [--from PARTICIPANT] [--by BY] [--note NOTE] [--dry-run]
                               goal amount

Put money towards a goal (negative to take some out).

positional arguments:
  goal
  amount

optional arguments:
  -h, --help            show this help message and exit
  --by BY               Who put it in (default: you)
  --note NOTE
  --dry-run

Examples:
  fridge budget goal-save "Holiday fund" 150 --by Luis
```

### budget goals

```text
usage: fridge budget goals [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT]

Savings goals with progress.

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge budget goals
```

### budget goal-delete

```text
usage: fridge budget goal-delete [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                                 [--from PARTICIPANT]
                                 goal

Delete a goal.

positional arguments:
  goal

optional arguments:
  -h, --help            show this help message and exit

Examples:
  fridge budget goal-delete "Holiday fund"
```

## bin

```text
usage: fridge bin [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                  [--from PARTICIPANT]
                  {show,restore} ...

Deleted tasks, events, notes, recipes and budget items, kept for the retention period.

positional arguments:
  {show,restore}
    show                What's in the bin that you may see, newest first, and until when.
    restore             Put something deleted back where it was (by its name, or its id for an expense).

optional arguments:
  -h, --help            show this help message and exit
```

### bin show

```text
usage: fridge bin show [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                       [--from PARTICIPANT] [--kind {task,event,note,recipe,expense,bill,goal,category}]

What's in the bin that you may see, newest first, and until when.

optional arguments:
  -h, --help            show this help message and exit
  --kind {task,event,note,recipe,expense,bill,goal,category}

Examples:
  fridge bin show
  fridge bin show --kind event
```

### bin restore

```text
usage: fridge bin restore [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                          [--from PARTICIPANT] [--kind {task,event,note,recipe,expense,bill,goal,category}]
                          [--dry-run]
                          item

Put something deleted back where it was (by its name, or its id for an expense).

positional arguments:
  item                  What to restore: its name, or an id such as X12

optional arguments:
  -h, --help            show this help message and exit
  --kind {task,event,note,recipe,expense,bill,goal,category}
  --dry-run

Examples:
  fridge bin restore "Fix the gate"
  fridge bin restore X12
  fridge bin restore Dentist --kind event
```

## remind

```text
usage: fridge remind [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                     [--from PARTICIPANT]
                     {due} ...

Reminders for events, birthdays and bills, respecting quiet hours.

positional arguments:
  {due}
    due                 What to remind people of right now (owner; --mine for your own). Run it on a
                        schedule, e.g. every 15 minutes. Held reminders come back after quiet hours; nothing
                        is repeated.

optional arguments:
  -h, --help            show this help message and exit
```

### remind due

```text
usage: fridge remind due [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--mine] [--peek]

What to remind people of right now (owner; --mine for your own). Run it on a schedule, e.g. every 15 minutes. Held reminders come back after quiet hours; nothing is repeated.

optional arguments:
  -h, --help            show this help message and exit
  --mine                Only reminders for the person talking
  --peek                Show without marking them as sent

Examples:
  fridge remind due
  fridge remind due --mine
  fridge remind due --peek
```

## ics

```text
usage: fridge ics [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                  [--from PARTICIPANT]
                  {export,import} ...

Calendar files (.ics): export to Google, Apple or Outlook, or import from them.

positional arguments:
  {export,import}
    export              Save the calendar (what you may see) as an .ics file.
    import              Import events from an .ics file. Re-importing the same file updates its events
                        instead of duplicating.

optional arguments:
  -h, --help            show this help message and exit
```

### ics export

```text
usage: fridge ics export [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--for WHO] [--file FILE]

Save the calendar (what you may see) as an .ics file.

optional arguments:
  -h, --help            show this help message and exit
  --for WHO             Only events involving this member
  --file FILE           File name (saved in the household's output folder)

Examples:
  fridge ics export
  fridge ics export --for Lily --file lily
```

### ics import

```text
usage: fridge ics import [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--for WHO] [--private] [--dry-run]
                         file

Import events from an .ics file. Re-importing the same file updates its events instead of duplicating.

positional arguments:
  file

optional arguments:
  -h, --help            show this help message and exit
  --for WHO             Who the events are for
  --private             Import them as your private events
  --dry-run

Examples:
  fridge ics import /workspace/downloads/school-term.ics --for "Theo, Lily"
  fridge ics import work.ics --private --dry-run
```

## print

```text
usage: fridge print [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                    [--from PARTICIPANT]
                    {week,calendar,list,recipe,budget} ...

Printables: fridge sheet, calendar, shopping checklist, recipe card, budget report.

positional arguments:
  {week,calendar,list,recipe,budget}
    week                The one-page "this week" fridge sheet: household events, dinners, chores with tick
                        boxes, kids' stars and pinned notes (nothing private).
    calendar            A month (or --week) calendar in member colours; --for one member; --mine adds your
                        own private events (direct chat).
    list                A shopping checklist with tick boxes, by aisle.
    recipe              A recipe card (scaled with --servings).
    budget              The month's budget report with charts (private).

optional arguments:
  -h, --help            show this help message and exit
```

### print week

```text
usage: fridge print week [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--date DATE] [--format {pdf,html,both}]

The one-page "this week" fridge sheet: household events, dinners, chores with tick boxes, kids' stars and pinned notes (nothing private).

optional arguments:
  -h, --help            show this help message and exit
  --date DATE           Any day in the week (default this week)
  --format {pdf,html,both}
                        pdf (default), html or both

Examples:
  fridge print week
  fridge print week --date "next week" --format both
```

### print calendar

```text
usage: fridge print calendar [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                             [--from PARTICIPANT] [--month MONTH] [--week WEEK] [--for WHO] [--mine]
                             [--format {pdf,html,both}]

A month (or --week) calendar in member colours; --for one member; --mine adds your own private events (direct chat).

optional arguments:
  -h, --help            show this help message and exit
  --month MONTH         YYYY-MM (default this month)
  --week WEEK           Print a week instead (any day in it)
  --for WHO
  --mine
  --format {pdf,html,both}
                        pdf (default), html or both

Examples:
  fridge print calendar
  fridge print calendar --month 2026-11 --for Lily
  fridge print calendar --week tomorrow
```

### print list

```text
usage: fridge print list [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                         [--from PARTICIPANT] [--list LIST] [--format {pdf,html,both}]

A shopping checklist with tick boxes, by aisle.

optional arguments:
  -h, --help            show this help message and exit
  --list LIST
  --format {pdf,html,both}
                        pdf (default), html or both

Examples:
  fridge print list
  fridge print list --list Hardware
```

### print recipe

```text
usage: fridge print recipe [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--servings SERVINGS] [--format {pdf,html,both}]
                           recipe

A recipe card (scaled with --servings).

positional arguments:
  recipe

optional arguments:
  -h, --help            show this help message and exit
  --servings SERVINGS
  --format {pdf,html,both}
                        pdf (default), html or both

Examples:
  fridge print recipe Chili --servings 6
```

### print budget

```text
usage: fridge print budget [-h] [--home HOME] [--household HOUSEHOLD] [--as MEMBER] [--chat CHAT]
                           [--from PARTICIPANT] [--month MONTH] [--format {pdf,html,both}]

The month's budget report with charts (private).

optional arguments:
  -h, --help            show this help message and exit
  --month MONTH
  --format {pdf,html,both}
                        pdf (default), html or both

Examples:
  fridge print budget
  fridge print budget --month 2026-09
```
