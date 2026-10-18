# Security and privacy

## What this plugin does and doesn't do

- **No network access.** The toolkit (`skills/fridge-door/scripts/`) is standard-library Python. It makes no
  network connections, sends no telemetry, checks for no updates, and downloads or runs no remote code. A test
  (`tests/test_no_network.py`) fails if any networking module is ever imported, if any code is loaded
  dynamically, or if any program other than the optional browser printer below is started.
- **No credentials.** It needs no API keys, tokens or accounts, and it never reads environment secrets, SSH keys
  or `.env` files.
- **Local files only.** It reads and writes plain JSON, text, PDF, HTML and .ics files in one data folder
  (`$FRIDGE_HOME`, else `/workspace/fridge-door` when `/workspace` exists, else `~/fridge-door`), files the person
  asks it to import (a saved recipe page, a calendar file), and the system temp folder. Photos and receipt
  pictures are referred to where they were saved, not copied: deleting the household doesn't delete them.
- **One optional subprocess.** For printouts in scripts the built-in PDF fonts can't show (Greek, Cyrillic,
  Arabic, Chinese and others), it can print its own locally generated HTML file with a Chrome, Chromium or Edge
  browser that's already installed, headless, with a throwaway profile and background networking turned off. It
  never installs or downloads a browser, and the page loads nothing from the internet. Without a browser it
  makes the PDF with the built-in fonts and points to the HTML version.
- **No hooks, no MCP servers, no background processes.** The plugin is one skill, four slash commands and the
  toolkit.
- **Nothing leaves without an OK.** The toolkit never sends messages, emails or reminders itself: it works out
  what's due and the agent passes it on in the chat. Reminders outside the chat platform stay off unless the
  household owner turns them on in their own words. The toolkit records spending; it never moves money.

## Who sees what

- Every command runs as one adult member of the household, and the toolkit enforces each member's access
  (none, view or edit) to the calendar, to-dos, lists, recipes, meal plan, notes and budget.
- In a group chat, a reply shows only what everyone linked to that chat may see. Private events, private notes
  and personal to-do lists never appear in a group chat. Sensitive notes don't either, unless the owner allows
  it. When the owner says children are in a group chat, it shows only chores and the grocery list.
- Reminders say which chats each one may go to: a person's own chats, or a group chat with no children in it
  where everyone linked may see it. Bills and private events never go to a group, and a reminder with no such
  chat isn't sent. Task notices are only read out in a person's own chat.
- Reminders are opt-in: an adult gets them only after turning them on in their own chat, and nobody can turn
  them on for someone else.
- Once the owner's own chat is registered, every message must name the chat it came from, and a chat nobody
  registered is refused, so no other chat can act as the owner.
- The owner's export leaves out other members' private events, private notes, personal to-do lists and notices.
- Printouts and calendar files are saved in a folder for the chat they were made in (a person's own folder, or a
  group chat's), so one audience's file never overwrites another's. A person's folder is deleted if they leave
  the household, and a group chat's when the chat is removed.
- Deleted tasks, events, notes, recipes and budget items wait in a bin for the retention period (90 days unless
  the owner changes it), with the same privacy as before: someone's private things stay theirs there, nothing
  from it shows in a group chat with kids in it, the owner's export leaves others' private ones out, and
  removing a member clears theirs.
- Only the owner changes members, roles, access and chat links, and removing a member or deleting the household
  needs the owner's own confirmation. Only a clear yes to that exact question counts: each question comes with a
  code that the yes must be sent back with, and a vague, conditional or negative answer ("ok", "sure", an emoji,
  "yes but later", "absolutely not") is refused.

## Children's data

Fridge Door is for adults; kids and teens take part through their parents.

- Kids and teens never chat with the agent. Only adults can be linked to a chat or have a one-to-one chat
  registered, after the owner's clear yes that they're 18 or older; an answer that mentions an age under 18, a
  school grade or "almost 18" is refused. Making a kid or teen an adult member asks the same question.
- A teen's handle in a group chat can be noted so their messages are recognised and never acted on; that chat
  then shows only chores and the grocery list.
- A shared note that names a kid or teen next to health or school details is refused: it has to be sensitive
  (adults only, in their own chats) or private, so it never reaches a group chat or the fridge sheet.
- A kid or teen is stored as a first name or nickname, a colour, their chores and a star count, with no place
  for anything else. The toolkit takes a one-word name only (no surname), refuses ages and numbers in it, and
  keeps only the day and month of a child's birthday.
- Netty Labs receives no data at all. The household's files stay on the computer where the agent runs. If that's
  a hosted agent (such as Grok Bot), the files and the chats are stored by that service under its own privacy
  policy and age rules; use its controls to delete them. Removing a member or deleting the household in Fridge
  Door erases their records from the data folder.

## Reporting a vulnerability

Please open a private security advisory on this repository (GitHub → Security → Report a vulnerability), or an
issue if it's not sensitive. Don't include household files or anyone's personal details. We aim to respond
within a few business days.
