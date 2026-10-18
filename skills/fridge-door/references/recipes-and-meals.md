# Recipes and the meal planner

Contents:
- [Adding recipes](#adding-recipes)
- [Using a recipe](#using-a-recipe)
- [Recipe to grocery list](#recipe-to-grocery-list)
- [The pantry](#the-pantry)
- [Planning the week](#planning-the-week)
- [The week's grocery list](#the-weeks-grocery-list)

## Adding recipes

**From a link.** The toolkit never goes online. Fetch the page with your own web tool, save it to a
file, then:

```bash
fridge recipe import /workspace/pages/chili.html --url https://example.com/chili
```

It reads the page's recipe data (most recipe sites have it). If it answers `no_recipe_data`, read the
page yourself and add the recipe from a spec as below, then ask the person to check it. A recipe that
looks already saved is refused; `--again` saves it anyway.

**From a photo of a recipe card or cookbook page.** Read it yourself, write down anything you're not
sure of in `unclear`, and save it as a spec (a JSON file path or inline JSON):

```bash
fridge recipe add --spec card.json --source photo --photo /workspace/photos/card.jpg
```

```json
{"title": "Gran's scones", "servings": 8, "prep_min": 15, "cook_min": 12,
 "ingredients": ["2 cups flour", "1 tbsp baking powder", "1/2 cup butter", "3/4 cup milk"],
 "steps": ["Rub the butter into the flour.", "Stir in the milk.", "Bake at 220°C for 12 minutes."],
 "tags": ["baking"], "unclear": ["the oven temperature looks like 220°C or 200°C"]}
```

The result's `ask` lists what to check. Put it to the person, fix any line with `recipe edit <title>
--set-ingredient "3=1/2 cup cold butter"`, then mark it checked with `recipe edit <title> --checked`.

**By hand:** `fridge recipe add --title "Pancakes" --servings 4 --ingredient "1 1/2 cups flour"
--ingredient "2 eggs" --step "Whisk everything" --tag breakfast` (repeat `--ingredient` and `--step`).

Ingredient lines are read the way people write them: "1 1/2 cups flour", "1½ cups milk", "2-3 cloves
garlic, minced", "1 (14 oz) can tomatoes", "200g butter", "salt to taste". Amounts stay exact
fractions.

## Using a recipe

- **Find one:** `fridge recipe list` (`--tag dinner`, `--search chicken`, `--quick` for 30 minutes or
  less).
- **Scale it:** `fridge recipe show Chili --servings 6` (servings are a whole number from 1 to 100).
  Every amount is worked out exactly, then shown the way a cook would say it: "2 1/2 tbsp", "5 cloves
  garlic", rounded to a kitchen fraction.
- **Cook mode:** `fridge recipe cook Chili` lists what to get ready; then `--next`, `--back`,
  `--step N`, and `--stop --done` at the end (which notes it was cooked today). Read one step at a time
  and wait for "next". Naming the recipe again with `--next` carries on where they were, and `fridge
  recipe cook` alone shows the current step. A recipe with no steps saved just lists what to get
  ready.
- **A recipe card to print:** `fridge print recipe Chili --servings 6`.
- **Change it:** `recipe edit` (title, servings, times, `--add-ingredient`, `--set-ingredient
  "N=..."`, `--remove-ingredient N`, `--add-step`, tags, notes, photo).
- **Delete it:** `recipe delete` puts it in the bin for the retention period (`fridge bin restore
  <title>`; see [lists-and-chores.md](lists-and-chores.md#the-bin)).

## Recipe to grocery list

Always review first:

```bash
fridge recipe to-list Chili --servings 6 --dry-run
```

Show the person the result's `text`. It sorts the ingredients into:
- **added**, rounded up to what you'd buy (whole onions and cans, the next 5 g or ml, the next
  quarter cup);
- **merged** into a line a recipe or meal already put on the list (2 cups + 1 cup = 3 cups);
- **already on the list** because someone added it by hand: its amount is theirs and stays as it is;
- **skipped** because the pantry has them;
- **check at home**: staples whose stock isn't known, "to taste" items, and spoonfuls and pinches
  (nobody buys 2 tbsp of oil).

The `summary` counts the lines exactly as they'll be saved. Then run it without `--dry-run`, leaving
out anything they say they have (`--skip "salt, cumin"`; words match, so "beef" leaves out "ground
beef", and anything that matched nothing is named in the summary). Amounts only combine within
metric or within US units, and weight never combines with volume; a grocery line can show both
("500 g + 2 cups") rather than guess. Canned goods go to the Canned aisle, and cooking words
("minced", "beaten") stay off the list.

## The pantry

The pantry is what the household usually has in, so lists don't ask for it every time.

```bash
fridge pantry set "rice, flour, olive oil" --status in --staple
fridge pantry set milk --status out
fridge pantry show
```

- Crossing an item off a grocery list marks it as in, if the pantry tracks it.
- Staples are things kept all the time; when one's stock isn't known, it goes on the check-at-home
  pile instead of the list.
- `--forget` removes an item from the pantry.

## Planning the week

```bash
fridge meal plan monday --recipe Chili --servings 6
fridge meal plan tuesday --leftovers-of monday
fridge meal plan friday --text "Eating out"
fridge meal plan saturday --meal lunch --recipe Pancakes
fridge meal week                     # the week, busy evenings marked
```

- **Busy nights:** a recipe taking 45 minutes or more isn't planned on an evening the calendar fills
  (events between 17:00 and 19:30). The toolkit refuses with `busy_night` and suggests quick recipes;
  offer one of those or another night, and use `--anyway` only if the person says so.
  `fridge meal nights` shows the week's busy evenings.
- **Leftovers** are a real slot: the Today summary asks whether they're still good rather than
  assuming.
- **Swap or clear a meal:** `fridge meal swap wednesday --recipe "Fish tacos"`, `fridge meal remove
  wednesday`. If leftovers were planned from the old meal, they now come from the new one, and the
  summary asks the person to check there'll be enough.
- `--servings` is a whole number from 1 to 100.
- **Ideas:** `fridge meal ideas` suggests meals from the household's own recipes and pantry. They're
  suggestions: ask which one they want before planning it.
- Planned meals can show on the calendar: `fridge cal week --layers meals`.

## The week's grocery list

```bash
fridge meal to-list --dry-run          # review: added, merged, pantry skipped, check at home
fridge meal to-list                    # make it (or refresh it)
fridge meal to-list --week "next week" --skip "rice, salt"
```

- Show the `text` from the dry run, ask "Add these to Groceries?", then run it.
- Once the week's list is made, planning, swapping or removing a meal changes the list by that meal's
  share only, and the summary says what was added, changed or taken off. Crossed-off items and items
  someone added by hand are never touched.
- What was already bought for the week's meals counts, whichever meal it was for: swapping meals
  after the shop adds only what's still missing.
- Seeing the recipes is needed to make the list, and in a group chat everyone present must be able to
  see them.
