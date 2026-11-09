# Survey Plot: Coordinates to AutoCAD Survey Plan

A Python script that turns a list of Easting/Northing coordinates into a finished survey plan in AutoCAD. Paste the coordinates, answer a few prompts, and the script draws and labels the plan for you, including an optional access road, a coordinates table and an A4 plan frame.

**Author:** Francis Otia
**Contact:** +2348161965054 | francisotia@gmail.com
**Website:** https://francisotia.github.io

---

## What it does

From one list of coordinates the script:

- Opens AutoCAD for you if it is closed, and opens a **new drawing** for every job.
- Sets the drawing up for survey work: units in **meters**, direction **North** (clockwise), angles in **degrees/minutes/seconds**, and a point style of a **square with a point in the middle**.
- Plots the boundary and labels every line with its **bearing** and **distance**, the **plot area**, and the coordinates of the **westernmost point**.
- Puts every element on its own layer (see [Layers](#layers)).
- Finishes the whole survey plan first. Only then does it offer the optional extras:
  1. **Access road** along a boundary line you choose.
  2. **Coordinates table** (STATION, EASTING(m), NORTHING(m)).
  3. **Frame**: an A4 portrait sheet with border, title block, plan number box, scale bar, north arrow and a cross-hair at the westernmost point.
- Lets you plot another job straight after, with each job in its own drawing.

## Requirements

- Windows (the script talks to AutoCAD through COM)
- AutoCAD installed (developed and tested with AutoCAD 2021)
- [Python 3](https://python.org). Tick **Add Python to PATH** during installation.
- The `pyautocad` package:

```
pip install pyautocad
```

## Folder contents

```
survey_plot/
├── fo_survey_autoplot_v3.py     # the program
├── test coordinates 1.csv       # sample coordinates for testing
├── test coordinates 2.csv       # sample coordinates for testing
└── README.md
```

## How to run

1. Open `fo_survey_autoplot_v3.py` in IDLE (**Ctrl+O**) and press **F5** (Run > Run Module). You can also run it from Command Prompt:
   ```
   python fo_survey_autoplot_v3.py
   ```
2. Enter the **font height** for the plan labels, or press Enter for the default of `1.3`.
3. **Paste the coordinates**, one point per line, **Easting before Northing**.
   - Copy them from Excel (tab-separated). Spaces, commas and semicolons also work, so you can copy straight from a CSV opened in Excel or a text editor.
   - A header row such as `Easting Northing` is skipped automatically.
   - A repeated point, or a closing point that repeats the first one, is removed automatically.
   - At least 3 different points are needed.
4. After pasting, press **Enter**, then finish the input:
   - **Command Prompt:** `Ctrl+Z`, then Enter
   - **IDLE / Linux / Mac:** `Ctrl+D`
5. Wait for AutoCAD. The survey plan is drawn and zoomed into view.
6. Answer the optional prompts (road, table, frame). Press **0 or Enter** to skip any of them.
7. At the end, press **1** to plot another job, or **0 / Enter** to finish. Earlier drawings stay open in AutoCAD.

### Trying it with the sample files

The program reads pasted text, not a file path. To use a sample file, open `test coordinates 1.csv` (or `2`), copy the Easting and Northing columns, and paste them when the program asks for coordinates.

## The optional prompts

### 1. Road
You are shown every boundary line (PT 1 to PT 2, PT 2 to PT 3, and so on) with its length. Enter the number of the line the road runs along, or press Enter for no road. The road is drawn **outside** the plot as a white broken (`HIDDEN2`) line, and labelled **ACCESS ROAD** with the words spread along the road.

### 2. Coordinates table
Press `1` to add a table with the columns **STATION**, **EASTING(m)** and **NORTHING(m)**.

- The table starts from the **westernmost point**, because jobs are georeferenced from there. If PT3 is the westernmost point, the rows run PT3, PT4, PT1, PT2.
- It uses the font height you entered.
- Headings and station names are white (they print black). The easting and northing values are red.
- It is placed to the right of the plan, clear of the road and labels.

### 3. Frame
Press `1` to add the frame, then type the plan scale (for example `500` for 1/500) or press Enter for the **best fit**.

- The sheet is A4 portrait. It has a border, title block, plan number box, scale bar, north arrow and a cross-hair at the westernmost point.
- The scale and the position of the sheet are worked out from the **boundary only**. The road, labels and table are not counted, so if they stick out of the border, choose a larger scale number.
- The plan must fit on the sheet at the scale you type. If it does not, the program tells you the smallest scale that fits.
- The scale bar parts are 10 m at 1/500 and grow in proportion at other scales (20 m at 1/1000, 5 m at 1/250).
- Placeholder texts such as `***/****/ 2026`, `[STATE]` and `[PLACEHOLDER SURVEYOR]` are meant to be edited in AutoCAD. The scale, origin, area and today's date are filled in for you.
- Frame text is 2.6 mm tall on paper, which is a font height of 1.3 at 1/500.

**To print:** A4 portrait, plot area = Window around the border, and plot scale `1 mm = 0.5 drawing units` for 1/500 (`1 mm = 1 unit` for 1/1000).

## Layers

| Layer | What goes on it |
|---|---|
| `boundary` | The plot boundary lines |
| `brg_dist_labels` | Bearing and distance text |
| `vertex_points` | The survey points |
| `road_line` | The road lines |
| `road_labels` | The ACCESS ROAD label |
| `coord_labels` | Coordinates of the westernmost point |
| `coord_table` | The coordinates table |
| `frame` | Frame lines: border, title block, scale bar, north arrow |
| `frame_labels` | All frame texts |
| `others` | Anything else, such as the area label |

## Settings you can change

Near the top of the script there is a settings section. Some of the most useful values:

| Setting | Purpose |
|---|---|
| `UTM_ZONE` | Shown on the frame as `ORIGIN= UTM ZONE 32N`. Change it if your job is in another zone. |
| `ROAD_WIDTH`, `ROAD_EXTENSION` | Road width and how far it runs past each end of the line (meters). |
| `ROAD_LABEL` | The road label wording. |
| `AUTO_SCALES` | The standard scales the frame's "best fit" chooses from. |
| `DEGREE_SYMBOL` | Use `"%%d"` if your font does not show the degree sign. |
| `POINT_STYLE`, `POINT_SIZE` | Point appearance (`64` = square with a point in the middle). |

## Troubleshooting

- **`pyautocad is not installed`:** run `pip install pyautocad` in Command Prompt.
- **AutoCAD is slow to start:** the script waits up to 3 minutes for it. Wait for the message "AutoCAD is ready."
- **An error appears:** read the message, fix the input if needed, and press `1` at the end to try again.
- **Frame says the plan does not fit:** use a larger scale number, such as 1000 instead of 500.

---

Built by Francis Otia.
