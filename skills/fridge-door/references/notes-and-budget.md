# Notes and the budget

Contents:
- [Notes](#notes)
- [Private and sensitive notes](#private-and-sensitive-notes)
- [The budget: who and how](#the-budget-who-and-how)
- [Spending and receipts](#spending-and-receipts)
- [Bills](#bills)
- [How are we doing?](#how-are-we-doing)
- [Savings goals](#savings-goals)

## Notes

| They say | Run |
|---|---|
| "Save the wifi password: Maple-5G, password on the router" | `fridge note add "Wifi" --body "Network: Maple-5G, password on the router" --pin --sensitive` |
| "Notes for the sitter" | `fridge note add "Sitter instructions" --body "Bedtime 8pm" --folder Kids --pin` |
| "Packing list for camping: tent, sleeping bags" | `fridge note add "Camping packing list" --item tent --item "sleeping bags" --tag trips` |
| "Packed the tent" | `fridge note check "Camping packing list" tent` (by number or words) |
| "Add the torch" | `fridge note edit "Camping packing list" --add-item torch` |
| "Add that she's allergic to peanuts" | `fridge note edit "Sitter instructions" --append "Allergic to peanuts"` |
| "What's the wifi?" | `fridge note show Wifi` |

- `note list` shows pinned notes first; filter with `--folder`, `--tag`, `--pinned` or `--search`.
- A new note with the same title as one they can see is refused (`exists`): change that one
  instead, or pick another title.
- Photos are saved file paths (`--photo`, `edit --add-photo`), never uploaded anywhere.
- Pinned shared notes (not sensitive) appear at the bottom of the printable fridge sheet, where
  everyone at home can read them, kids included. Don't pin what the kids shouldn't see.

## Private and sensitive notes

- **Private** (`--private`): only whoever wrote it ever sees it, and never in a group chat. Only the
  author changes a note between private and shared.
- **Sensitive** (`--sensitive`): door codes, the wifi password, account numbers. Members with notes
  access see it in a direct chat. It stays out of group chats unless the owner turned on
  `sensitive_notes_in_groups`, and it's never printed. In a group, `note list` says how many sensitive
  notes it left out, and asking for one answers `hidden_in_group`; offer to show it in a direct
  chat.
- Suggest `--sensitive` whenever a note holds a code, password or account detail. Don't keep
  passwords for online accounts; suggest a password manager for those.
- Never write a child's details (school, health, surname, location) into a note. If a shared note
  names a kid next to health words (an allergy, an inhaler), the result has a `hint` to mark it
  sensitive: offer that, since the sitter's notes may need the allergy, but groups and the fridge
  sheet don't.

## The budget: who and how

The budget is manual (no bank connections) and for adults by default: teens and kids have no budget
access, and it never shows in a group chat where anyone present can't see it, kids included.

- Amounts come from the person. Pass them as plain numbers with a dot for decimals ("54.20",
  "1500"). The toolkit refuses "1,500" and "1.234,50", which mean different things in different
  countries; ask which they meant, then pass it plainly.
- Money is exact: the household's currency, with the right number of decimals (none for yen, three
  for Kuwaiti dinar), shown the way the toolkit prints it ("$1,234.50 CAD", "1.234,50 €"). More
  decimals than the currency has ("12.999") are refused with `bad_number`.
- You keep the household's records; you don't give investment, tax or financial advice. Saying
  "Groceries is $66 over this month" is fine; telling them what to do with their money isn't.

Categories:

```bash
fridge budget categories                              # setup made Groceries, Housing, Utilities ... (no budgets yet)
fridge budget category-edit Groceries --monthly 800
fridge budget category-defaults                       # adds back any of the usual ones that were deleted
fridge budget category-add "Pets" --monthly 120 --icon 🐾
fridge budget category-delete Fun --move-to Other      # a category in use needs --move-to
```

## Spending and receipts

```bash
fridge budget spend 54.20 --category Groceries
fridge budget spend 38 --category "Eating out" --by Luis --note "Pizza night"
fridge budget expenses --month 2026-09 --category Groceries
fridge budget expense-edit X4 --amount 45.10              # or expense-delete X4; both take --dry-run
```

`--date` leans to the past, since spending has already happened: "friday" means the Friday just
gone, and a date in the future is refused (`future_date`).

**From a receipt photo:** read the store, date and total yourself, pick the likely category, then
preview:

```bash
fridge budget spend 87.43 --category Groceries --date 2026-10-17 --note "Corner market" \
  --receipt /workspace/receipts/oct17.jpg --dry-run
```

Show the preview ("$87.43 CAD at Corner market on 17 Oct, Groceries. Log it?") and log it without
`--dry-run` only after they say yes. The receipt stays a file path on the computer.

## Bills

```bash
fridge budget bill-add Rent --amount 1800 --due 2026-11-01 --repeat monthly --category Housing
fridge budget bill-add "Car insurance" --amount 640 --due 2027-03-15 --repeat yearly --remind 2w
fridge budget bill-add "Phone plan" --amount 45 --due 2026-11-05 --repeat monthly --times 24
fridge budget bills                     # coming up (and anything overdue)
fridge budget bill-paid Rent            # records the expense and moves to the next due date
fridge budget bill-paid Hydro --amount 142.37 --by Luis
fridge budget bill-edit Rent --due 2026-11-03 --dry-run    # moves the schedule; later dates follow
```

- `--until <date>` or `--times N` sets when a bill stops; `bill-edit --no-repeat` stops one
  repeating.
- Bills remind 3 days before by default (`--remind`), in a person's own chat only, and show on the
  calendar (`--no-calendar` to hide). Marking one `--autopay` keeps the reminder but notes it pays
  itself; an autopay bill is never called overdue, and `bills` asks for it to be recorded once it's
  gone out.
- Recording the same bill paid twice for the same due date is caught ("already recorded"). When the
  oldest unpaid one is more than a week away, `bill-paid` answers `not_due_yet`: it was probably
  recorded already (perhaps by someone else). Pass `--due` from the hint only if it really was paid
  early.
- The Today summary lists bills due in the next week for members who can see the budget.

## How are we doing?

| They ask | Run |
|---|---|
| "How are we doing this month?" | `fridge budget month` (spent against the categories with a budget and what's left, spending in categories without one listed apart, and anything over) |
| "Last month?" | `fridge budget month "last month"` or `fridge budget month 2026-09` |
| "Spending over the last 6 months" | `fridge budget trend --months 6` |
| "A report I can keep" | `fridge print budget` (a private PDF with charts; direct chat only, never for the fridge) |

Reply with the toolkit's `summary` and the categories that are over or close to their budget.

## Savings goals

```bash
fridge budget goal-add "Holiday fund" --target 3000 --by 2027-07-01
fridge budget goal-save "Holiday fund" 150 --by Luis      # a negative amount takes money out
fridge budget goals                                       # progress, and how much a month is still needed
```

A goal can't go below zero.
