# Copilot Instructions

This file provides guidance for AI coding agents working on this repository.

---

## Skill: marimo-notebook
---
name: marimo-notebook
description: Write a marimo notebook in a Python file in the right format.
---

# Notes for marimo Notebooks

marimo uses Python to create notebooks, unlike Jupyter which uses JSON. Here's an example notebook:

```python
# /// script
# dependencies = [
#     "marimo",
#     "numpy==2.4.3",
# ]
# requires-python = ">=3.14"
# ///

import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np

    return mo, np


@app.cell
def _():
    print("hello world")
    return


@app.cell
def _(np, slider):
    np.array([1,2,3]) + slider.value
    return


@app.cell
def _(mo):
    slider = mo.ui.slider(1, 10, 1, label="number to add")
    slider
    return (slider,)


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

```

Notice how the notebook is structured with functions can represent cell contents. Each cell is defined with the `@app.cell` decorator and the inputs/outputs of the function are the inputs/outputs of the cell. marimo usually takes care of the dependencies between cells automatically.

## Running Marimo Notebooks

```bash
# Run as script (non-interactive, for testing)
uv run <notebook.py>

# Run interactively in browser
uv run marimo run <notebook.py>

# Edit interactively
uv run marimo edit <notebook.py>
```

## Script Mode Detection

Use `mo.app_meta().mode == "script"` to detect CLI vs interactive:

```python
@app.cell
def _(mo):
    is_script_mode = mo.app_meta().mode == "script"
    return (is_script_mode,)
```

## Key Principle: Keep It Simple

**Show all UI elements always.** Only change the data source in script mode.

- Sliders, buttons, widgets should always be created and displayed
- In script mode, just use synthetic/default data instead of waiting for user input
- Don't wrap everything in `if not is_script_mode` conditionals
- Don't use try/except for normal control flow

### Good Pattern

```python
# Always show the widget
@app.cell
def _(ScatterWidget, mo):
    scatter_widget = mo.ui.anywidget(ScatterWidget())
    scatter_widget
    return (scatter_widget,)

# Only change data source based on mode
@app.cell
def _(is_script_mode, make_moons, scatter_widget, np, torch):
    if is_script_mode:
        # Use synthetic data for testing
        X, y = make_moons(n_samples=200, noise=0.2)
        X_data = torch.tensor(X, dtype=torch.float32)
        y_data = torch.tensor(y)
        data_error = None
    else:
        # Use widget data in interactive mode
        X, y = scatter_widget.widget.data_as_X_y
        # ... process data ...
    return X_data, y_data, data_error

# Always show sliders - use their .value in both modes
@app.cell
def _(mo):
    lr_slider = mo.ui.slider(start=0.001, stop=0.1, value=0.01)
    lr_slider
    return (lr_slider,)

# Auto-run in script mode, wait for button in interactive
@app.cell
def _(is_script_mode, train_button, lr_slider, run_training, X_data, y_data):
    if is_script_mode:
        # Auto-run with slider defaults
        results = run_training(X_data, y_data, lr=lr_slider.value)
    else:
        # Wait for button click
        if train_button.value:
            results = run_training(X_data, y_data, lr=lr_slider.value)
    return (results,)
```

## State and Reactivity

Variables between cells define the reactivity of the notebook for 99% of the use-cases out there. No special state management needed. Don't mutate objects across cells (e.g., `my_list.append()`); create new objects instead. Avoid `mo.state()` unless you need bidirectional UI sync or accumulated callback state. See [STATE.md](references/STATE.md) for details.

## Don't Guard Cells with `if` Statements

Marimo's reactivity means cells only run when their dependencies are ready. Don't add unnecessary guards:

```python
# BAD - the if statement prevents the chart from showing
@app.cell
def _(plt, training_results):
    if training_results:  # WRONG - don't do this
        fig, ax = plt.subplots()
        ax.plot(training_results['losses'])
        fig
    return

# GOOD - let marimo handle the dependency
@app.cell
def _(plt, training_results):
    fig, ax = plt.subplots()
    ax.plot(training_results['losses'])
    fig
    return
```

The cell won't run until `training_results` has a value anyway.

## Don't Use try/except for Control Flow

Don't wrap code in try/except blocks unless you're handling a specific, expected exception. Let errors surface naturally.

```python
# BAD - hiding errors behind try/except
@app.cell
def _(scatter_widget, np, torch):
    try:
        X, y = scatter_widget.widget.data_as_X_y
        X = np.array(X, dtype=np.float32)
        # ...
    except Exception as e:
        return None, None, f"Error: {e}"

# GOOD - let it fail if something is wrong
@app.cell
def _(scatter_widget, np, torch):
    X, y = scatter_widget.widget.data_as_X_y
    X = np.array(X, dtype=np.float32)
    # ...
```

Only use try/except when:
- You're handling a specific, known exception type
- The exception is expected in normal operation (e.g., file not found)
- You have a meaningful recovery action

## Cell Output Rendering

Marimo only renders the **final expression** of a cell. Indented or conditional expressions won't render:

```python
# BAD - indented expression won't render
@app.cell
def _(mo, condition):
    if condition:
        mo.md("This won't show!")  # WRONG - indented
    return

# GOOD - final expression renders
@app.cell
def _(mo, condition):
    result = mo.md("Shown!") if condition else mo.md("Also shown!")
    result  # This renders because it's the final expression
    return
```

## PEP 723 Dependencies

Notebooks created via `marimo edit --sandbox` have these dependencies added to the top of the file automatically but it is a good practice to make sure these exist when creating a notebook too:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "torch>=2.0.0",
# ]
# ///
```

## marimo check

When working on a notebook it is important to check if the notebook can run. That's why marimo provides a `check` command that acts as a linter to find common mistakes.

```bash
uvx marimo check <notebook.py>
```

Make sure these are checked before handing a notebook back to the user.

**Important**: you have a tendency to over-do variables with an underscore prefix. You should only apply this to one or two variables at most. Consider creating a new variable instead of prefixing entire cells in marimo.

## api docs

If the user specifically wants you to use a marimo function, you can locally check the docs via:

```
uv --with marimo run python -c "import marimo as mo; help(mo.ui.form)"
```

## tests

By default, marimo discovers and executes tests inside your notebook.
When the optional `pytest` dependency is present, marimo runs `pytest` on cells that
consist exclusively of test code - i.e. functions whose names start with `test_`.
If the user asks you to add tests, make sure to add the `pytest` dependency is added and that
there is a cell that contains only test code.

For more information on testing with pytest see [PYTEST.md](references/PYTEST.md)

Once tests are added, you can run pytest from the commandline on the notebook to run pytest.

```
pytest <notebook.py>
```

## Additional resources

- For SQL use in marimo see [SQL.md](references/SQL.md)
- For UI elements in marimo [UI.md](references/UI.md)
- For exposing functions/classes as top level imports [TOP-LEVEL-IMPORTS.md](references/TOP-LEVEL-IMPORTS.md)
- For exporting notebooks (PDF, HTML, markdown, etc.) [EXPORTS.md](references/EXPORTS.md)
- For state management and reactivity [STATE.md](references/STATE.md)
- For deployment of marimo notebooks [DEPLOYMENT.md](references/DEPLOYMENT.md)
- For custom interactive widgets with anywidget [ANYWIDGET.md](references/ANYWIDGET.md)

---
## Skill: anywidget
---
name: anywidget-generator
description: Generate anywidget components for marimo notebooks.
---

When writing an anywidget use vanilla javascript in `_esm` and do not forget about `_css`. The css should look bespoke in light mode and dark mode. Keep the css small unless explicitly asked to go the extra mile. When you display the widget it must be wrapped via `widget = mo.ui.anywidget(OriginalAnywidget())`. You can also point `_esm` and `_css` to external files if needed using pathlib. This makes sense if the widget does a lot of elaborate JavaScript or CSS.

<example title="Example of simple anywidget implementation">
import anywidget
import traitlets


class CounterWidget(anywidget.AnyWidget):
    _esm = """
    // Define the main render function
    function render({ model, el }) {
      let count = () => model.get("number");
      let btn = document.createElement("b8utton");
      btn.innerHTML = `count is ${count()}`;
      btn.addEventListener("click", () => {
        model.set("number", count() + 1);
        model.save_changes();
      });
      model.on("change:number", () => {
        btn.innerHTML = `count is ${count()}`;
      });
      el.appendChild(btn);
    }
    // Important! We must export at the bottom here!
    export default { render };
    """
    _css = """button{
      font-size: 14px;
    }"""
    number = traitlets.Int(0).tag(sync=True)

widget = mo.ui.anywidget(CounterWidget())
widget

# Grabbing the widget from another cell, `.value` is a dictionary.
print(widget.value["number"])
</example>

The above is a minimal example that could work for a simple counter widget. In general the widget can become much larger because of all the JavaScript and CSS required. Unless the widget is dead simple, you should consider using external files for `_esm` and `_css` using pathlib.

When sharing the anywidget, keep the example minimal. No need to combine it with marimo ui elements unless explicitly stated to do so.

## Best Practices

Unless specifically told otherwise, assume the following:

1. **Use vanilla JavaScript in `_esm`**:
   - Define a `render` function that takes `{ model, el }` as parameters
   - Use `model.get()` to read trait values
   - Use `model.set()` and `model.save_changes()` to update traits
   - Listen to changes with `model.on("change:traitname", callback)`
   - Export default with `export default { render };` at the bottom
   - All widgets inherit from `anywidget.AnyWidget`, so `widget.observe(handler)`
     remains the standard way to react to state changes.
   - Python constructors tend to validate bounds, lengths, or choice counts; let the
     raised `ValueError/TraitError` guide you instead of duplicating the logic.

2. **Include `_css` styling**:
   - Keep CSS minimal unless explicitly asked for more
   - Make it look bespoke in both light and dark mode
   - Use CSS media query for dark mode: `@media (prefers-color-scheme: dark) { ... }`

3. **Wrap the widget for display**:
   - Always wrap with marimo: `widget = mo.ui.anywidget(OriginalAnywidget())`
   - Access values via `widget.value` which returns a dictionary

4. **Keep examples minimal**:
   - Add a marimo notebook that highlights the core utility
   - Show basic usage only
   - Don't combine with other marimo UI elements unless explicitly requested

5. **External file paths**: When using pathlib for external `_esm`/`_css` files, keep paths relative to the project directory, consider using `Path(__file__)` for this. Do not read files outside the project (e.g., `~/.ssh`, `~/.env`, `/etc/`) or embed their contents in widget output.

Dumber is better. Prefer obvious, direct code over clever abstractions—someone
new to the project should be able to read the code top-to-bottom and grok it
without needing to look up framework magic or trace through indirection.

---
## Skill: marimo UI reference
marimo has a rich set of UI components.

* `mo.ui.altair_chart(altair_chart)` - create a reactive Altair chart
* `mo.ui.button(value=None, kind='primary')` - create a clickable button
* `mo.ui.run_button(label=None, tooltip=None, kind='primary')` - create a button that runs code
* `mo.ui.checkbox(label='', value=False)` - create a checkbox
* `mo.ui.chat(placeholder='', value=None)` - create a chat interface
* `mo.ui.date(value=None, label=None, full_width=False)` - create a date picker
* `mo.ui.dropdown(options, value=None, label=None, full_width=False)` - create a dropdown menu
* `mo.ui.file(label='', multiple=False, full_width=False)` - create a file upload element
* `mo.ui.number(value=None, label=None, full_width=False)` - create a number input
* `mo.ui.radio(options, value=None, label=None, full_width=False)` - create radio buttons
* `mo.ui.refresh(options: List[str], default_interval: str)` - create a refresh control
* `mo.ui.slider(start, stop, value=None, label=None, full_width=False, step=None)` - create a slider
* `mo.ui.range_slider(start, stop, value=None, label=None, full_width=False, step=None)` - create a range slider
* `mo.ui.table(data, columns=None, on_select=None, sortable=True, filterable=True)` - create an interactive table
* `mo.ui.text(value='', label=None, full_width=False)` - create a text input
* `mo.ui.text_area(value='', label=None, full_width=False)` - create a multi-line text input
* `mo.ui.data_explorer(df)` - create an interactive dataframe explorer
* `mo.ui.dataframe(df)` - display a dataframe with search, filter, and sort capabilities
* `mo.ui.plotly(plotly_figure)` - create a reactive Plotly chart (supports scatter, treemap, and sunburst)
* `mo.ui.tabs(elements: dict[str, mo.ui.Element])` - create a tabbed interface from a dictionary
* `mo.ui.array(elements: list[mo.ui.Element])` - create an array of UI elements
* `mo.ui.form(element: mo.ui.Element, label='', bordered=True)` - wrap an element in a form

As always, you can learn more about the available inputs to all these components via `uv --with marimo run python -c "import marimo as mo; help(mo.ui.form)"`

## Forms

You can compose multiple UI elements into a single form using `.batch().form()`. The `.batch()` method binds named UI elements into a markdown template, and `.form()` adds a submit button so values are only sent on submit.

```python
form = (
    mo.md(
        """
        **Choose an option**

        {choice}

        **Enter some text**

        {text}

        **Enable feature**

        {flag}
        """
    )
    .batch(
        choice=mo.ui.dropdown(options=["A", "B", "C"]),
        text=mo.ui.text(),
        flag=mo.ui.checkbox(),
    )
    .form(
        submit_button_label="Submit",
        show_clear_button=True,   # optional
        clear_on_submit=False,    # keep values after submit
    )
)

form
```

You can also add validation to a form using the `validate` parameter. Return an error string to block submission, or `None` to allow it.

```python
group_by_form = mo.ui.dropdown(
    options=df_columns,
    label="Select column to filter for duplicate analyzis",
    allow_select_none=True,
    value=None,  # start with nothing selected
    searchable=True,
).form(
    submit_button_label="Apply",
    validate=lambda v: (
        "Please select a column and press Apply."
        if v is None else None
    ),
)
```

However, the user may also want to use other components. Popular alternatives include the `ScatterWidget` from the `drawdata` library, `moutils`, and `wigglystuff`.

For custom classes and static HTML representations you can also use the `_display_` method.

```python
class Dice:
    def _display_(self):
        import random

        return f"You rolled {random.randint(0, 7)}"
```

---
## Skill: marimo state reference
# State in marimo

## Reactivity IS State Management

In marimo, regular Python variables between cells are your state. When a cell assigns a variable, all cells that read it re-run automatically. Widget values (`widget.value`) work the same way — interact with a widget and dependent cells re-execute. No store, no session_state, no hooks needed.

## Don't Mutate Objects Across Cells

marimo does **not** track mutations like `my_list.append(42)` or `obj.value = 42`.

```python
# BAD - mutation in another cell won't trigger re-runs
# Cell 1
items = [1, 2, 3]

# Cell 2
items.append(4)  # marimo won't know this happened

# GOOD - create new objects instead
# Cell 1
items = [1, 2, 3]

# Cell 2
extended_items = items + [4]
```

## You Probably Don't Need `mo.state()`

In 99% of cases, built-in reactivity is enough:

- **Reading widget values** — just use `widget.value` in another cell
- **Combining multiple inputs** — use `.batch().form()`
- **Conditional data** — use `if`/`else` in one cell

## When You Do Need `mo.state()`

Use it when you need **accumulated state from callbacks** or **bidirectional sync** between UI elements.

```python
get_val, set_val = mo.state(initial_value)
```

- Read: `get_val()`
- Update: `set_val(new_value)` or `set_val(lambda d: d + [new_item])`
- The cell calling the setter does NOT re-run (unless `allow_self_loops=True`)

### Example: todo list with accumulated state

```python
# Cell 1 — declare state
@app.cell
def _(mo):
    get_items, set_items = mo.state([])
    return get_items, set_items

# Cell 2 — input form
@app.cell
def _(mo, set_items):
    task = mo.ui.text(label="New task")
    add = mo.ui.button(
        label="Add",
        on_click=lambda _: set_items(lambda d: d + [task.value])
    )
    mo.hstack([task, add])
    return

# Cell 3 — display (re-runs when state changes)
@app.cell
def _(mo, get_items):
    mo.md("\n".join(f"- {t}" for t in get_items()))
    return
```

### Example: syncing two UI elements

```python
@app.cell
def _(mo):
    get_n, set_n = mo.state(50)
    return get_n, set_n

@app.cell
def _(mo, get_n, set_n):
    slider = mo.ui.slider(0, 100, value=get_n(), on_change=set_n)
    number = mo.ui.number(0, 100, value=get_n(), on_change=set_n)
    mo.hstack([slider, number])
    return
```

## Warnings

- Don't store `mo.ui` elements inside state — causes hard-to-diagnose bugs.
- Don't use `on_change` when you can just read `.value` from another cell.
- Write idempotent cells — same inputs should produce same outputs.

---
## Skill: add-molab-badge
---
name: add-molab-badge
description: Add "Open in molab" badge(s) linking to marimo notebooks. Works with READMEs, docs, websites, or any markdown/HTML target.
---

# Add molab badge

Add "Open in molab" badge(s) linking to marimo notebooks. The badge can be added to any target: a GitHub README, documentation site, blog post, webpage, or any other markdown/HTML file.

## Instructions

### 0. Session export for molab

molab previews render much nicer if the github repository has session information around. This can be added via:

```bash
uvx marimo export session notebook.py
uvx marimo export session folder/
```

This executes notebooks and exports their session snapshots, which molab uses to serve pre-rendered notebooks.

Key flags:

- `--sandbox` — run each notebook in an isolated environment using PEP 723 dependencies
- `--continue-on-error` — keep processing other notebooks if one fails
- `--force-overwrite` — overwrite all existing snapshots, even if up-to-date

### 1. Determine the notebook links

The user may provide notebook links in one of two ways:

- **User provides links directly.** The user pastes URLs to notebooks. Use these as-is — no discovery needed.
- **Notebook discovery (README target only).** If the user asks you to add badges to a repository's README and doesn't specify which notebooks, discover them:
  1. Find all marimo notebook files (`.py` files) in the repository. Use `Glob` with patterns like `**/*.py` and then check for the marimo header (`import marimo` or `app = marimo.App`) to confirm they are marimo notebooks.
  2. If the README already has links to notebooks (e.g., via `marimo.app` links or existing badges), replace those.
  3. Otherwise, ask the user which notebooks should be linked.

### 2. Construct the molab URL

For each notebook, construct the molab URL using this format:

```
https://molab.marimo.io/github/{owner}/{repo}/blob/{branch}/{path_to_notebook}
```

- `{owner}/{repo}`: the GitHub owner and repository name. Determine from the git remote (`git remote get-url origin`), the user-provided URL, or by asking the user.
- `{branch}`: typically `main`. Confirm from the repository's default branch.
- `{path_to_notebook}`: the path to the `.py` notebook file relative to the repository root.

### 3. Apply the `/wasm` suffix rules

- If **replacing** an existing `marimo.app` link, append `/wasm` to the molab URL. This is because `marimo.app` runs notebooks client-side (WASM), so the molab equivalent needs the `/wasm` suffix to preserve that behavior.
- If adding a **new** badge (not replacing a `marimo.app` link), do **not** append `/wasm` unless the user explicitly requests it.

### 4. Format the badge

Use the following markdown badge format:

```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](URL)
```

Where `URL` is the constructed molab URL (with or without `/wasm` per the rules above).

For HTML targets, use:

```html
<a href="URL"><img src="https://marimo.io/molab-shield.svg" alt="Open in molab" /></a>
```

### 5. Insert or replace badges in the target

- When replacing existing badges or links:
  - Replace `marimo.app` URLs with the equivalent `molab.marimo.io` URLs.
  - Replace old shield image URLs (e.g., `https://marimo.io/shield.svg` or camo-proxied versions) with `https://marimo.io/molab-shield.svg`.
  - Set the alt text to `Open in molab`.
  - Preserve surrounding text and structure.
- Edit the target file in place. Do not rewrite unrelated sections.
- If the user just wants the badge markdown/HTML (not editing a file), output it directly.

## Examples

**Replacing a marimo.app badge in a README:**

Before:
```markdown
[![](https://marimo.io/shield.svg)](https://marimo.app/github.com/owner/repo/blob/main/notebook.py)
```

After:
```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/owner/repo/blob/main/notebook.py/wasm)
```

Note: `/wasm` is appended because this replaces a `marimo.app` link.

**Adding a new badge from user-provided links:**

User says: "Add molab badges for these notebooks: `https://github.com/owner/repo/blob/main/demo.py`, `https://github.com/owner/repo/blob/main/tutorial.py`"

Output:
```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/owner/repo/blob/main/demo.py)
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/owner/repo/blob/main/tutorial.py)
```

Note: no `/wasm` suffix by default for new badges.

---
## Skill: wasm-compatibility
---
name: wasm-compatibility
description: Check if a marimo notebook is compatible with WebAssembly (WASM) and report any issues.
---

# WASM Compatibility Checker for marimo Notebooks

Check whether a marimo notebook can run in a WebAssembly (WASM) environment — the marimo playground, community cloud, or exported WASM HTML.

## Instructions

### 1. Read the notebook

Read the target notebook file. If the user doesn't specify one, ask which notebook to check.

### 2. Extract dependencies

Collect every package the notebook depends on from **both** sources:

- **PEP 723 metadata** — the `# /// script` block at the top:
  ```python
  # /// script
  # dependencies = [
  #     "marimo",
  #     "torch>=2.0.0",
  # ]
  # ///
  ```
- **Import statements** — scan all cells for `import foo` and `from foo import bar`. Map import names to their PyPI distribution name using this table:

  | Import name | Distribution name |
  |---|---|
  | `sklearn` | `scikit-learn` |
  | `skimage` | `scikit-image` |
  | `cv2` | `opencv-python` |
  | `PIL` | `Pillow` |
  | `bs4` | `beautifulsoup4` |
  | `yaml` | `pyyaml` |
  | `dateutil` | `python-dateutil` |
  | `attr` / `attrs` | `attrs` |
  | `gi` | `PyGObject` |
  | `serial` | `pyserial` |
  | `usb` | `pyusb` |
  | `wx` | `wxPython` |

  For most other packages, the import name matches the distribution name.

### 3. Check each package against Pyodide

For each dependency, determine if it can run in WASM:

1. **Is it in the Python standard library?** Most stdlib modules work, but these do **not**:
   - `multiprocessing` — browser sandbox has no process spawning
   - `subprocess` — same reason
   - `threading` — emulated, no real parallelism (WARN, not a hard fail)
   - `sqlite3` — use `apsw` instead (available in Pyodide)
   - `pdb` — not supported
   - `tkinter` — no GUI toolkit in browser
   - `readline` — no terminal in browser

2. **Is it a Pyodide built-in package?** See [pyodide-packages.md](references/pyodide-packages.md) for the full list. These work out of the box.

3. **Is it a pure-Python package?** Packages with only `.py` files (no compiled C/Rust extensions) can be installed at runtime via `micropip` and will work. To check: look for a `py3-none-any.whl` wheel on PyPI (e.g. visit `https://pypi.org/project/<package>/#files`). If the only wheels are platform-specific (e.g. `cp312-cp312-manylinux`), the package has native extensions and likely won't work.

   Common pure-Python packages that work (not in Pyodide built-ins but installable via micropip):
   - `plotly`, `seaborn`, `humanize`, `pendulum`, `arrow`, `tabulate`
   - `dataclasses-json`, `marshmallow`, `cattrs`, `pydantic` (built-in)
   - `httpx` (built-in), `tenacity`, `backoff`, `wrapt` (built-in)

4. **Does it have C/native extensions not built for Pyodide?** These will **not** work. Common culprits:
   - `torch` / `pytorch`
   - `tensorflow`
   - `jax` / `jaxlib`
   - `psycopg2` (suggest `psycopg` with pure-Python mode)
   - `mysqlclient` (suggest `pymysql`)
   - `uvloop`
   - `grpcio`
   - `psutil`

### 4. Check for WASM-incompatible patterns

Scan the notebook code for patterns that won't work in WASM:

| Pattern | Why it fails | Suggestion |
|---|---|---|
| `subprocess.run(...)`, `os.system(...)`, `os.popen(...)` | No process spawning in browser | Remove or gate behind a non-WASM check |
| `multiprocessing.Pool(...)`, `ProcessPoolExecutor` | No process forking | Use single-threaded approach |
| `threading.Thread(...)`, `ThreadPoolExecutor` | Emulated threads, no real parallelism | WARN only — works but no speedup; use `asyncio` for I/O |
| `open("/absolute/path/...")`, hard-coded local file paths | No real filesystem; only in-memory fs | Fetch data via URL (`httpx`, `urllib`) or embed in notebook |
| `sqlite3.connect(...)` | stdlib sqlite3 unavailable | Use `apsw` or `duckdb` |
| `pdb.set_trace()`, `breakpoint()` | No debugger in WASM | Remove breakpoints |
| Reading env vars (`os.environ[...]`, `os.getenv(...)`) | Environment variables not available in browser | Use `mo.ui.text` for user input or hardcode defaults |
| `Path.home()`, `Path.cwd()` with real file expectations | Virtual filesystem only | Use URLs or embedded data |
| Large dataset loads (>100 MB) | 2 GB total memory cap | Use smaller samples or remote APIs |

### 5. Check PEP 723 metadata

WASM notebooks should list all dependencies in the PEP 723 `# /// script` block so they are automatically installed when the notebook starts. Check for these issues:

- **Missing metadata:** If the notebook has no `# /// script` block, emit a WARN recommending one. Listing dependencies ensures they are auto-installed when the notebook starts in WASM — without it, users may see import errors.
- **Missing packages:** If a package is imported but not listed in the dependencies, emit a WARN suggesting it be added.
Note: version pins and lower bounds in PEP 723 metadata are fine — marimo strips version constraints when running in WASM.

### 6. Produce the report

Output a clear, actionable report with these sections:

**Compatibility: PASS / FAIL / WARN**

Use these verdicts:
- **PASS** — all packages and patterns are WASM-compatible
- **WARN** — likely compatible, but some packages could not be verified as pure-Python (list them so the user can check)
- **FAIL** — one or more packages or patterns are definitely incompatible

**Package Report** — table with columns: Package, Status (OK / WARN / FAIL), Notes

Example:
| Package | Status | Notes |
|---|---|---|
| marimo | OK | Available in WASM runtime |
| numpy | OK | Pyodide built-in |
| pandas | OK | Pyodide built-in |
| torch | FAIL | No WASM build — requires native C++/CUDA extensions |
| my-niche-lib | WARN | Not in Pyodide; verify it is pure-Python |

**Code Issues** — list each problematic code pattern found, with the cell or line and a suggested fix.

**Recommendations** — if the notebook fails, suggest concrete fixes:
- Replace incompatible packages with WASM-friendly alternatives
- Rewrite incompatible code patterns
- Suggest moving heavy computation to a hosted API and fetching results

## Additional context

- WASM notebooks run via [Pyodide](https://pyodide.org) in the browser
- Memory is capped at 2 GB
- Network requests work but may need CORS-compatible endpoints
- Chrome has the best WASM performance; Firefox, Edge, Safari also supported
- `micropip` can install any pure-Python wheel from PyPI at runtime
- For the full Pyodide built-in package list, see [pyodide-packages.md](references/pyodide-packages.md)

---
## Skill: wasm pyodide packages
# Pyodide Built-in Packages

These packages are pre-built for Pyodide and available in WASM environments.
Any package **not** on this list must have a pure Python wheel on PyPI to work.

> **Note:** This list was snapshotted on 2026-02-26 from Pyodide's docs.
> For the latest list, check https://pyodide.org/en/stable/usage/packages-in-pyodide.html

affine, aiohappyeyeballs, aiohttp, aiosignal, altair, annotated-types, anyio,
apsw, argon2-cffi, argon2-cffi-bindings, asciitree, astropy, astropy_iers_data,
asttokens, async-timeout, atomicwrites, attrs, audioop-lts, autograd,
awkward-cpp, b2d, bcrypt, beautifulsoup4, bilby.cython, biopython, bitarray,
bitstring, bleach, blosc2, bokeh, boost-histogram, Bottleneck, brotli,
cachetools, Cartopy, casadi, cbor-diag, certifi, cffi, cffi_example, cftime,
charset-normalizer, clarabel, click, cligj, clingo, cloudpickle, cmyt, cobs,
colorspacious, contourpy, coolprop, coverage, cramjam, crc32c, cryptography,
css-inline, cssselect, cvxpy-base, cycler, cysignals, cytoolz, decorator,
demes, deprecation, diskcache, distlib, distro, docutils, donfig,
ewah_bool_utils, exceptiongroup, executing, fastapi, fastcan, fastparquet,
fiona, fonttools, freesasa, frozenlist, fsspec, future, galpy, geopandas,
gmpy2, google-crc32c, gsw, h11, h3, h5py, healpy, highspy, html5lib, httpcore,
httpx, idna, igraph, imageio, imgui-bundle, iminuit, iniconfig, inspice,
ipython, jedi, Jinja2, jiter, joblib, jsonpatch, jsonpointer, jsonschema,
jsonschema_specifications, kiwisolver, lakers-python, lazy_loader,
lazy-object-proxy, libcst, lightgbm, logbook, lxml, lz4, MarkupSafe,
matplotlib, matplotlib-inline, memory-allocator, micropip, ml_dtypes, mmh3,
more-itertools, mpmath, msgpack, msgspec, msprime, multidict, munch, mypy,
narwhals, ndindex, netcdf4, networkx, newick, nh3, nlopt, nltk, numcodecs,
numpy, openai, opencv-python, optlang, orjson, packaging, pandas, parso, patsy,
pcodec, peewee, pi-heif, Pillow, pillow-heif, pkgconfig, platformdirs, pluggy,
ply, pplpy, primecountpy, prompt_toolkit, propcache, protobuf, pure-eval, py,
pyarrow, pycdfpp, pyclipper, pycparser, pycryptodome, pydantic, pydantic_core,
pyerfa, pygame-ce, Pygments, pyheif, pyiceberg, pyinstrument, pylimer-tools,
PyMuPDF, pynacl, pyodide-http, pyodide-unix-timezones, pyparsing, pyproj,
pyrodigal, pyrsistent, pysam, pyshp, pytaglib, pytest, pytest-asyncio,
pytest-benchmark, pytest_httpx, python-calamine, python-dateutil, python-flint,
python-magic, python-sat, python-solvespace, pytz, pywavelets, pyxel, pyxirr,
pyyaml, rasterio, rateslib, rebound, reboundx, referencing, regex, requests,
retrying, rich, river, RobotRaconteur, rpds-py, ruamel.yaml, rustworkx,
scikit-image, scikit-learn, scipy, screed, setuptools, shapely, simplejson,
sisl, six, smart-open, sniffio, sortedcontainers, soundfile, soupsieve,
sourmash, soxr, sparseqr, sqlalchemy, stack-data, starlette, statsmodels,
strictyaml, svgwrite, swiglpk, sympy, tblib, termcolor, texttable,
texture2ddecoder, threadpoolctl, tiktoken, tomli, tomli-w, toolz, tqdm,
traitlets, traits, tree-sitter, tree-sitter-go, tree-sitter-java,
tree-sitter-python, tskit, typing-extensions, typing-inspection, tzdata, ujson,
uncertainties, unyt, urllib3, vega-datasets, vrplib, wcwidth, webencodings,
wordcloud, wrapt, xarray, xgboost, xlrd, xxhash, xyzservices, yarl, yt, zengl,
zfpy, zstandard

## Also available (part of Pyodide runtime or marimo WASM)

- marimo
- duckdb
- polars
- micropip (for installing additional pure-Python packages at runtime)

## Common third-party packages that do NOT work in WASM

These popular packages have C/native extensions not built for Pyodide:

| Package | Why | Alternative |
|---|---|---|
| torch / pytorch | C++/CUDA extensions | None for WASM |
| tensorflow | C++ extensions | None for WASM |
| jax / jaxlib | C++ extensions | None for WASM |
| psycopg2 | Requires libpq | `psycopg[binary]` or use `duckdb` |
| mysqlclient | Requires libmysqlclient | `pymysql` (pure Python) |
| uvloop | Requires libuv | `asyncio` (default loop) |
| grpcio | C extensions | `grpclib` (pure Python) |
| psutil | OS-level syscalls | None for WASM |
| gevent | C extensions | `asyncio` |
| celery | Requires message broker | Not applicable in browser |
