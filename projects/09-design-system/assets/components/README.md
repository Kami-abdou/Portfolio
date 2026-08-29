# Drop design system exports here

Anything you put in this folder appears automatically in the component browser
on the design system page. No JSON to edit, no code to change.

    1. export from Figma as PNG
    2. drop the files in this folder
    3. run:  python3 build.py

## Naming drives order and labels

The filename becomes the tab label. A leading number sets the order and is
stripped from the label.

| filename                        | tab label              |
| ------------------------------- | ---------------------- |
| `01-button.png`                 | Button                 |
| `02-input-field.png`            | Input field            |
| `03-toast--how-it-enters.png`   | Toast — how it enters  |
| `04-colour-tokens.png`          | Colour tokens          |
| `05-type-scale.png`             | Type scale             |

- `--` becomes an em dash, for "Component — behaviour" style labels
- hyphens and underscores become spaces
- `.png`, `.jpg` and `.gif` all work

## Motion

Animated **GIF** works and plays inline — the best way to show how something
enters, waits or responds without shipping any code. Export a short loop from
Figma or screen-record the prototype and convert it.

Keep GIFs under ~2 MB each. If one is heavier, say so and it can be converted.

## What to include

Your manager cleared: the components, how they animate or interact, and the
documentation for each. A good set is roughly:

- a few core components, each with its states
- one or two motion loops
- the colour tokens and the type scale
- a documentation page for one component, showing how it is specified

## What must NOT go here

- screenshots of unreleased product UI or roadmap
- anything from the DeepCore repository
- any image containing a Figma share link or access token
