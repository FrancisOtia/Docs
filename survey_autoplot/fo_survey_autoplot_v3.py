"""
Survey plan plotter for AutoCAD (fo_survey_autoplot v3: adds the frame and the frame labels).

Plots a survey polygon from Easting/Northing coordinates, then labels each line
with its bearing and distance, the plot area, and the westernmost coordinates.
Straight after plotting, it offers a menu of boundary lines so a simple road can be
drawn along one of them. The road is labelled "ACCESS ROAD".

New in v3:
  - After the road and the coordinates table you can press 1 to add the frame: an A4 portrait sheet
    at the scale you choose (or the best fit for the survey plan alone), with the border, title block,
    plan number box, scale bar, north arrow and a cross-hair at the westernmost point.
  - The frame lines are on the layer "frame". All the frame texts (placeholders such as ***/****/ 2026,
    [STATE] and [PLACEHOLDER SURVEYOR], plus the scale, origin, area and today's date) are on the
    layer "frame_labels", so they are easy to find and edit in AutoCAD.
  - Everything else works exactly as in fo_survey_autoplot_v2.

Carried over from fo_survey_autoplot_v2:
  - The point style is now a square with a point in the middle (PDMODE 64).
  - The whole survey plan (perimeter, points, bearings, distances, area, coordinates) is
    plotted and zoomed into view BEFORE the optional road prompt appears.
  - Every element goes on its own layer: boundary, brg_dist_labels, vertex_points,
    road_line, road_labels, coord_labels, frame (empty for now) and others.

  - After the road prompt there is a second optional prompt: press 1 to add a coordinates
    table (STATION, EASTING(m), NORTHING(m)) to the drawing, on the coord_table layer. The
    table starts from the westernmost point (e.g. PT3, PT4, PT1, PT2).

Carried over from the versions before that:
  - AutoCAD does not have to be open: the program starts it if needed.
  - Every job opens a NEW drawing from the default AutoCAD template and sets units to
    meters, direction to North, angles to degrees/minutes/seconds and the point style.
  - At the end you can press 1 to plot another job. Earlier drawings stay open.

Author: Francis Otia
"""
import datetime
import math
import os
import re
import sys
import time
import traceback

try:
    from pyautocad import Autocad, APoint
except ImportError:
    sys.exit("pyautocad is not installed. Open Command Prompt and run: pip install pyautocad")


INSTRUCTIONS = """\
This program plots a survey plan in AutoCAD and labels it, using the coordinates as input.
Author: Francis Otia
Contact: +2348161965054 | francisotia@gmail.com
GitHub: https://francisotia.github.io

SETUP (one time)
1. Install Python from https://python.org and tick 'Add Python to PATH' during installation.
2. Open Command Prompt and run:  pip install pyautocad
   (needs an internet connection; documentation: https://pyautocad.readthedocs.io)

BEFORE EACH RUN
You do not need to open AutoCAD. If it is closed, the program starts it for you (this can take
a minute). For every job the program opens a NEW drawing from the default AutoCAD template and
sets: units to meters, direction to North (clockwise), angles to degrees/minutes/seconds, and
the point style to a square with a point in the middle (size 1, absolute units). It also creates
the layers (boundary, brg_dist_labels, vertex_points, road_line, road_labels, coord_labels, frame,
frame_labels, others). Then it plots the job in that drawing.

RUN
Open this file in IDLE (Ctrl+O), press F5 (or Run > Run Module) and follow the prompts.
If you get an error, read the message, then run again (or press 1 at the end to try again).

ROAD
The road is optional. The survey plan is fully plotted first and left ready in AutoCAD; only
then are you shown every boundary line (PT 1 to PT 2, PT 2 to PT 3,
and so on). Pick the one the road runs along, or press Enter for no road. The road is drawn
outside the plot, in white with the HIDDEN2 line type, and labelled ACCESS ROAD.

COORDINATES TABLE
After the road prompt you are asked whether to paste the coordinates list in AutoCAD. Press 0 or
Enter to skip, or 1 to add a table with the columns STATION, EASTING(m) and NORTHING(m). The
table uses the font height you entered, sits on the coord_table layer, and starts from the
westernmost point, so if PT3 is the westernmost the order is PT3, PT4, PT1, PT2. Headings and
station names stay white (default colour); the easting and northing values are red.

FRAME
The frame is optional and comes last, after the road and the coordinates table. Press 1 to add it, then
type the plan scale (for example 500 for 1/500) or just press Enter for the best fit. The program draws
an A4 portrait sheet around the survey plan: the border, title block, plan number box, scale bar, north
arrow and a cross-hair (a cross with four equal arms) at the westernmost point. The scale and the
position of the sheet are worked out from the survey plan (the boundary) ONLY. The road, the labels and
the coordinates table are not counted, so if they stick out of the border, use a larger scale number.
The lines go on the layer frame. All the texts go on the layer frame_labels: placeholders such as
***/****/ 2026, [STATE] and [PLACEHOLDER SURVEYOR] (edit them in AutoCAD), plus the scale, origin, area
and today's date. The surveyor's name is the only bold text. Each part of the scale bar is 10 m at 1/500
and grows in proportion at other scales (20 m at 1/1000, 5 m at 1/250).
The frame text is 2.6 mm tall on paper, which is a font height of 1.3 at 1/500. To print: A4 portrait,
plot area = Window around the border, plot scale 1 mm = 0.5 drawing units for 1/500 (1 mm = 1 unit for 1/1000).

MORE THAN ONE JOB
At the end, press 0 (or just press Enter) to end the program, or press 1 to plot another job.
Each job gets its own new drawing and the earlier drawings stay open in AutoCAD.
"""

# ----------------------------------------------------------------------------
# Settings (change these to tune the look of the plan)
# ----------------------------------------------------------------------------
DEGREE_SYMBOL = "\u00b0"   # use "%%d" instead if your font does not show the degree sign
LINE_COLOR = 1             # AutoCAD colour index: 1 = red
AREA_COLOR = 1             # red
COORD_COLOR = 5            # blue

LABEL_OFFSET = 0.9         # distance from line to text centre, in font heights
COORD_GAP = 1.5            # gap between westernmost point and its labels, in font heights

# Road settings
ROAD_WIDTH = 6.10          # how far the road's far edge sits outside the boundary line, in meters
ROAD_EXTENSION = 15.0      # how far the road lines run past each end of the boundary line, in meters
ROAD_COLOR = 7             # colour 7 = white on the black screen, prints black
ROAD_LINETYPE = "HIDDEN2"  # broken line
ROAD_LINETYPE_SCALE = 1.0  # raise or lower if the dashes look too long or too short
ROAD_LABEL = "ACCESS ROAD" # default road label words; the spaces between them are worked out from the road length
ROAD_LABEL_FILL = 0.75     # fraction of the road length the spaced label may use (keep below ~0.9)
ROAD_LABEL_COLOR = 7       # same white as the road

# Coordinates table settings
TABLE_HEADERS = ("STATION", "EASTING(m)", "NORTHING(m)")
TABLE_TEXT_COLOR = 7       # headings and station names: white (prints black)
TABLE_VALUE_COLOR = 1      # easting and northing values: red
TABLE_GAP = 8.0            # gap between the plan (and road) and the table, in font heights
TABLE_ROW_FACTOR = 2.2     # row height, in font heights
TABLE_MARGIN_FACTOR = 0.5  # cell margin, in font heights
TABLE_CHAR_FACTOR = 0.95   # assumed width of one character, in font heights

# Frame settings. Sizes and positions are in millimetres ON PAPER: A4 portrait, origin = bottom-left
# corner of the sheet. The scale you choose turns them into meters in the drawing.
FRAME_GRID_COLOR = 5       # blue: north arrow and the cross-hair at the westernmost point
FRAME_AREA_COLOR = 1       # red: the area in the title block
UTM_ZONE = "32N"           # shown as "ORIGIN= UTM ZONE 32N"; change it if your job is in another zone
NORTH_LABEL = "UN"         # the small text on the north arrow, as in the example sheet
BOLD_FONT = "Times New Roman"   # typeface of the one bold text, the surveyor's name (as in the example sheet)
BOLD_FONT_PITCH_FAMILY = 18     # 18 = serif typeface; use 34 if you change BOLD_FONT to a sans-serif such as Arial
BOLD_STYLE_NAME = "fo_bold"     # name of the bold text style that is created in the drawing
AUTO_SCALES = (500, 1000, 1250, 2000, 2500, 5000, 10000)   # "best fit" picks the first one that fits

FRAME_BORDER = (5.0, 6.0, 205.0, 291.0)                     # x1, y1, x2, y2
TITLE_BLOCK_TOP = 56.5                                      # top edge of the title block along the bottom
TITLE_COL_1, TITLE_COL_2 = 67.5, 123.5                      # the two vertical lines of the title block
LEFT_SPLIT_Y, RIGHT_SPLIT_Y = 32.0, 28.0                    # horizontal dividers in the left and right cells
PLAN_BOX = (58.5, 279.5, 105.0, 291.0)                      # plan number box, hanging from the top border
DRAW_REGION = (13.0, 64.0, 197.0, 224.0)                    # where the survey plan (boundary) is placed

TEXT_STD = 2.6             # frame text heights on paper, mm
TEXT_SMALL = 2.0
TEXT_SCALE = 2.4
TEXT_BIG = 3.0
TEXT_PLAN = 2.75
TEXT_NAME = 2.8

TITLE_CENTER_X = 167.1     # the title text block at the top right is centred on this line
TITLE_TOP_Y = 287.9        # height of its first line
TITLE_LINE_GAP = 4.36      # distance between its lines
FRAME_TITLE_LINES = (      # placeholder wording, edit in AutoCAD (or here)
    "PLAN SHEWING LANDED PROPERTY",
    "OF",
    "*" * 27,
    "AT",
    '"' + "*" * 20 + '"',
    "*" * 23,
    "*" * 22,
    "*" * 18,
    "[STATE] STATE, NIGERIA",
)
SCALE_BAR_CENTER_X = 167.9
SCALE_BAR_Y = 238.9
SCALE_BAR_REF_SCALE = 500  # at this scale each part of the scale bar is SCALE_BAR_REF_STEP meters long ...
SCALE_BAR_REF_STEP = 10.0  # ... and at any other scale it grows in proportion: 1/1000 -> 20 m, 1/250 -> 5 m
NORTH_TOP_Y, NORTH_BOTTOM_Y, NORTH_CIRCLE_Y = 273.7, 224.9, 253.2
GRID_STUB_SIDE = 20.0      # length of the grid lines running in from the left and right borders, mm on paper
GRID_STUB_BOTTOM = 17.5    # length of the grid line running up from the title block, mm on paper
CROSSHAIR_ARM = 4.0        # length of each of the four equal arms of the cross-hair, mm on paper

# AutoCAD drawing settings, applied to every new drawing
TEMPLATE_FALLBACKS = ("acad.dwt", "acadiso.dwt")  # used if no default template is set in AutoCAD
UNITS_METERS = 6           # INSUNITS: 6 = meters
ANGLE_UNITS_DMS = 1        # AUNITS: 1 = degrees/minutes/seconds
ANGLE_PRECISION = 4        # AUPREC: 4 = angles shown down to seconds
ANGLE_CLOCKWISE = True     # ANGDIR: True = clockwise (survey bearings), False = AutoCAD's anticlockwise
POINT_STYLE = 64           # PDMODE: 64 = square with a point (dot) in the middle
POINT_SIZE = 1.0           # PDSIZE: positive = absolute size, in drawing units (meters)
AUTOCAD_START_TIMEOUT = 180  # seconds to wait for AutoCAD to start

# Layers: (name, colour index). Each element of the drawing goes on its own layer.
LAYER_BOUNDARY = "boundary"
LAYER_BRG_DIST = "brg_dist_labels"
LAYER_POINTS = "vertex_points"
LAYER_ROAD_LINE = "road_line"
LAYER_ROAD_LABELS = "road_labels"
LAYER_COORDS = "coord_labels"
LAYER_FRAME = "frame"          # the frame lines: border, title block, scale bar, north arrow
LAYER_FRAME_LABELS = "frame_labels"   # every text of the frame
LAYER_OTHERS = "others"        # anything else, e.g. the area label
LAYER_TABLE = "coord_table"    # the optional coordinates table
LAYERS = [
    (LAYER_BOUNDARY, LINE_COLOR),
    (LAYER_BRG_DIST, 7),
    (LAYER_POINTS, 7),
    (LAYER_ROAD_LINE, ROAD_COLOR),
    (LAYER_ROAD_LABELS, ROAD_LABEL_COLOR),
    (LAYER_COORDS, COORD_COLOR),
    (LAYER_FRAME, 7),
    (LAYER_FRAME_LABELS, 7),
    (LAYER_OTHERS, AREA_COLOR),
    (LAYER_TABLE, 7),
]

# Bearing text is spread along the line. These widths are deliberately generous so the
# text under-fills the line rather than overflowing it. Raise BEARING_FILL (max ~0.9)
# to spread the bearing wider, lower it to spread less.
BEARING_FILL = 0.75        # fraction of the line length the bearing text may use
CHAR_WIDTH = 0.85          # assumed width of a digit/symbol, in font heights
SPACE_WIDTH = 0.65         # assumed width of a space, in font heights

# AutoCAD text alignment codes (AcAlignment enumeration)
AC_ALIGN_MIDDLE_LEFT = 9
AC_ALIGN_MIDDLE_CENTER = 10
AC_ALIGN_MIDDLE_RIGHT = 11

_EPS = 1e-6


# ----------------------------------------------------------------------------
# Input
# ----------------------------------------------------------------------------
def ask_font_height(default=1.3):
    """Ask for the text height; Enter accepts the default."""
    while True:
        raw = ask(f"Please enter the font height, e.g. {default} (press Enter for {default}):\n ")
        if raw is None:  # console could not be read, so use the default
            return default
        raw = raw.strip()
        if not raw:
            return default
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
        print("Please enter a number greater than 0.")


def parse_points(raw_text):
    """Turn pasted 'Easting<TAB>Northing' lines into a list of (e, n) tuples."""
    points = []
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[\t ,;]+", line) if p]
        try:
            values = [float(p) for p in parts]
        except ValueError:
            if not points:  # a header row such as "Easting  Northing"
                print(f"Skipped header row: {line!r}")
                continue
            raise ValueError(f"Line {line_no} is not numeric: {line!r}")
        if len(values) != 2:
            raise ValueError(
                f"Line {line_no} must have exactly 2 numbers (Easting, Northing): {line!r}")
        points.append((values[0], values[1]))
    return points


def clean_points(points):
    """Drop repeated points and a closing point that repeats the first one."""
    def same(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-9

    cleaned = []
    for p in points:
        if not cleaned or not same(p, cleaned[-1]):
            cleaned.append(p)
    if len(cleaned) > 1 and same(cleaned[0], cleaned[-1]):
        cleaned.pop()
    if len(cleaned) < 3:
        raise ValueError("At least 3 different points are needed to form a plot.")
    removed = len(points) - len(cleaned)
    if removed:
        print(f"Removed {removed} repeated point(s).")
    return cleaned


def read_points():
    """Read pasted coordinates from the console."""
    print("Paste coordinates from Excel: tab-separated, one point per line, Easting before Northing.")
    print("After pasting, press ENTER, then CTRL+D (IDLE, Linux, Mac) "
          "or CTRL+Z and ENTER (Windows Command Prompt).")
    return clean_points(parse_points(sys.stdin.read()))


# ----------------------------------------------------------------------------
# Survey maths (no AutoCAD needed)
# ----------------------------------------------------------------------------
def bearing_dms(dx, dy):
    """Whole-bearing from north, clockwise, rounded to the nearest minute.

    Returns (degrees, minutes). Rounding is done on total minutes, so 359 deg 59.6 min
    becomes 0 deg 0 min instead of '360 deg 00 min'.
    """
    bearing = math.degrees(math.atan2(dx, dy)) % 360.0
    total_minutes = int(round(bearing * 60)) % (360 * 60)
    return total_minutes // 60, total_minutes % 60


def text_rotation(dx, dy):
    """AutoCAD text rotation (radians, counter-clockwise from east) for a line.

    The text runs along the line and is always readable: the angle is kept in the
    range (-90, +90] degrees, so text is never upside down.
    """
    deg = math.degrees(math.atan2(dy, dx))      # direction of the line, (-180, 180]
    if deg > 90 + _EPS:
        deg -= 180
    elif deg <= -90 + _EPS:
        deg += 180
    return math.radians(deg)


def polygon_signed_area(points):
    """Shoelace area, positive if the points run anticlockwise, negative if clockwise.

    Coordinates are shifted first so large UTM values keep their precision.
    """
    x0, y0 = points[0]
    shifted = [(x - x0, y - y0) for x, y in points]
    total = 0.0
    for (xa, ya), (xb, yb) in zip(shifted, shifted[1:] + shifted[:1]):
        total += xa * yb - xb * ya
    return total / 2.0


def polygon_area(points):
    return abs(polygon_signed_area(points))


def outward_unit_normal(points, index):
    """Unit vector at right angles to the line starting at points[index], pointing OUT of the plot.

    The interior is on the left of each line for an anticlockwise polygon and on the
    right for a clockwise one, so the outward side comes from the polygon's direction.
    """
    p1, p2 = points[index], points[(index + 1) % len(points)]
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    side = -1.0 if polygon_signed_area(points) > 0 else 1.0
    return side * -dy / length, side * dx / length


def road_lines(points, index, width=ROAD_WIDTH, extension=ROAD_EXTENSION):
    """Coordinates of a simple road along the boundary line that starts at points[index].

    Returns three lines, each as ((x1, y1), (x2, y2)):
      1. the road's far edge: the boundary line offset `width` meters outward, then
         lengthened by `extension` meters at both ends
      2. the boundary line extended `extension` meters beyond its first point
      3. the boundary line extended `extension` meters beyond its second point
    Lines 2 and 3 stop exactly at the boundary points (the extended line is broken there),
    so the red boundary line itself is left untouched.
    """
    (x1, y1), (x2, y2) = points[index], points[(index + 1) % len(points)]
    length = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length          # along the boundary line
    ox, oy = outward_unit_normal(points, index)               # away from the plot

    far_edge = ((x1 - ux * extension + ox * width, y1 - uy * extension + oy * width),
                (x2 + ux * extension + ox * width, y2 + uy * extension + oy * width))
    before_first = ((x1 - ux * extension, y1 - uy * extension), (x1, y1))
    after_second = ((x2, y2), (x2 + ux * extension, y2 + uy * extension))
    return [far_edge, before_first, after_second]


def polygon_label_point(points):
    """A point inside the polygon near its centroid, for placing the area label."""
    x0, y0 = points[0]
    pts = [(x - x0, y - y0) for x, y in points]
    nxt = pts[1:] + pts[:1]

    a2 = cx = cy = 0.0
    for (xa, ya), (xb, yb) in zip(pts, nxt):
        cross = xa * yb - xb * ya
        a2 += cross
        cx += (xa + xb) * cross
        cy += (ya + yb) * cross
    if abs(a2) < 1e-12:  # degenerate polygon: fall back to the plain average
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
    else:
        cx /= 3.0 * a2
        cy /= 3.0 * a2

    # Horizontal scan through the centroid. If the centroid falls outside the polygon
    # (L or U shapes), use the middle of the longest stretch that is inside.
    xs = []
    for (xa, ya), (xb, yb) in zip(pts, nxt):
        if (ya <= cy < yb) or (yb <= cy < ya):
            xs.append(xa + (cy - ya) * (xb - xa) / (yb - ya))
    xs.sort()
    spans = list(zip(xs[0::2], xs[1::2]))
    for a, b in spans:
        if a <= cx <= b:
            return x0 + cx, y0 + cy
    if spans:
        a, b = max(spans, key=lambda s: s[1] - s[0])
        return x0 + (a + b) / 2.0, y0 + cy
    return x0 + cx, y0 + cy


def build_bearing_text(deg, minute, line_length, height):
    """e.g. 045 deg, spaces, 30' - spaced to under-fill the line, never overflow it."""
    head = f"{deg:02d}{DEGREE_SYMBOL}"
    tail = f"{minute:02d}'"
    fixed_width = 7 * CHAR_WIDTH * height      # worst case: 3 digits, symbol, 2 digits, tick
    room = BEARING_FILL * line_length - fixed_width
    spaces = max(int(room / (SPACE_WIDTH * height)), 1)
    return head + " " * spaces + tail


# ----------------------------------------------------------------------------
# AutoCAD drawing
# ----------------------------------------------------------------------------
def com_retry(action, what, timeout=60.0, delay=1.0):
    """Run action(). While AutoCAD is still starting or busy, wait and try again."""
    deadline = time.time() + timeout
    while True:
        try:
            return action()
        except Exception as err:
            if time.time() >= deadline:
                raise RuntimeError(f"AutoCAD did not respond ({what}): {err}")
            time.sleep(delay)


def autocad_alive(acad):
    """True if this AutoCAD connection still works (the user may have closed AutoCAD)."""
    try:
        acad.app.Documents.Count
        return True
    except Exception:
        return False


def start_autocad():
    """Attach to a running AutoCAD, or start one. Returns (acad, started_by_us)."""
    try:
        acad = Autocad(create_if_not_exists=False)
        acad.app.Documents.Count          # fails if AutoCAD is not running
        return acad, False
    except Exception:
        pass

    print("AutoCAD is not open, so starting it now. This can take a minute, please wait...")

    def create():
        acad = Autocad(create_if_not_exists=True)
        acad.app.Documents.Count          # fails until AutoCAD is ready
        return acad

    acad = com_retry(create, "starting AutoCAD - check that it is installed",
                     timeout=AUTOCAD_START_TIMEOUT, delay=2.0)
    print("AutoCAD is ready.")
    return acad, True


def template_candidates(app):
    """Existing template files to try, best first: AutoCAD's default (QNEW) template, then acad.dwt."""
    found = []
    try:
        qnew = app.Preferences.Files.QNewTemplateFile
        if qnew and os.path.isfile(qnew):
            found.append(qnew)
    except Exception:
        pass
    try:
        folders = [f.strip() for f in str(app.Preferences.Files.TemplateDwgPath).split(";") if f.strip()]
    except Exception:
        folders = []
    for name in TEMPLATE_FALLBACKS:
        for folder in folders:
            path = os.path.join(folder, name)
            if os.path.isfile(path) and path not in found:
                found.append(path)
    return found


def open_template_drawing(app):
    """Open a new drawing from the default AutoCAD template and return it."""
    for path in template_candidates(app):
        try:
            doc = com_retry(lambda p=path: app.Documents.Add(p), "opening the template")
            print(f"New drawing opened from template: {path}")
            return doc
        except RuntimeError:
            continue
    doc = com_retry(lambda: app.Documents.Add(), "opening a new drawing")
    print("New drawing opened from AutoCAD's default template.")
    return doc


def set_north_base_angle(doc):
    """Direction = North: base angle 90 degrees (AutoCAD wants radians for ANGBASE)."""
    north = math.pi / 2
    doc.SetVariable("ANGBASE", north)
    try:
        if abs(float(doc.GetVariable("ANGBASE")) - north) > 1e-6:
            doc.SetVariable("ANGBASE", 90.0)   # in case this AutoCAD takes degrees
    except Exception:
        pass


def apply_drawing_settings(doc):
    """Units = meters, direction = North, angles = deg/min/sec, point style = absolute size."""
    settings = [
        ("INSUNITS", UNITS_METERS),
        ("AUNITS", ANGLE_UNITS_DMS),
        ("AUPREC", ANGLE_PRECISION),
        ("ANGDIR", 1 if ANGLE_CLOCKWISE else 0),
        ("PDMODE", POINT_STYLE),
        ("PDSIZE", POINT_SIZE),
    ]
    for name, value in settings:
        try:
            com_retry(lambda n=name, v=value: doc.SetVariable(n, v), f"setting {name}", timeout=10)
        except RuntimeError as err:
            print(f"Warning: could not set {name}. {err}")
    try:
        com_retry(lambda: set_north_base_angle(doc), "setting ANGBASE", timeout=10)
    except RuntimeError as err:
        print(f"Warning: could not set the direction to North. {err}")
    print("Drawing settings applied: meters, North, degrees/minutes/seconds, "
          f"point style {POINT_STYLE} (square with a point in the middle) size {POINT_SIZE:g} (absolute).")


def close_blank_startup_drawing(app, keep):
    """After starting AutoCAD ourselves, close its untouched blank 'Drawing1' so it is not left over."""
    try:
        keep_name = keep.Name
        for i in range(app.Documents.Count - 1, -1, -1):
            other = app.Documents.Item(i)
            if other.Name == keep_name:
                continue
            if other.Name.lower().startswith("drawing") and other.Saved and other.ModelSpace.Count == 0:
                other.Close(False)
        keep.Activate()
    except Exception:
        pass


def make_layer(doc, name, color):
    """Create one layer (or reuse it if it exists) and set its colour."""
    try:
        layer = doc.Layers.Item(name)
    except Exception:
        layer = doc.Layers.Add(name)
    layer.Color = color


def create_layers(doc):
    """Create the drawing's layers and give each its colour.

    AutoCAD sometimes answers 'Call was rejected by callee' while it is busy, so every
    layer is retried until AutoCAD accepts it.
    """
    for name, color in LAYERS:
        try:
            com_retry(lambda n=name, c=color: make_layer(doc, n, c),
                      f"creating layer {name}", timeout=30, delay=0.5)
        except RuntimeError as err:
            print(f"Warning: could not create layer {name}. {err}")
    print("Layers ready: " + ", ".join(name for name, _ in LAYERS))


def get_model_space(app, doc):
    """Return (document, model space) of the new drawing once AutoCAD is really ready.

    Right after a drawing is created AutoCAD may hand out a model-space object that does not
    know its methods yet (that caused "AttributeError: AddPoint"), so keep asking until it does.
    """
    def fetch():
        last = None
        for source in (lambda: app.ActiveDocument, lambda: doc):
            try:
                candidate = source()
                ms = candidate.ModelSpace
                ms.AddPoint            # fails until the drawing is ready to be drawn on
                ms.AddLine
                ms.AddText
                return candidate, ms
            except Exception as err:
                last = err
        raise last

    return com_retry(fetch, "opening model space", timeout=60, delay=1.0)


def connect_autocad(acad=None):
    """Make sure AutoCAD is running, open a NEW drawing from the default template, set it up.

    Pass the connection from the previous job (or None). Returns (acad, doc, model_space).
    Earlier drawings are left open.
    """
    started_now = False
    if acad is None or not autocad_alive(acad):
        acad, started_now = start_autocad()
    app = acad.app
    doc = open_template_drawing(app)
    com_retry(lambda: doc.Activate(), "activating the new drawing", timeout=20)
    doc, ms = get_model_space(app, doc)
    apply_drawing_settings(doc)
    create_layers(doc)
    if started_now:
        close_blank_startup_drawing(app, doc)
    return acad, doc, ms


def set_layer(obj, layer):
    """Put an AutoCAD object on the named layer, retrying while AutoCAD is busy."""
    try:
        com_retry(lambda: setattr(obj, "Layer", layer), f"setting layer {layer}",
                  timeout=15, delay=0.3)
    except RuntimeError:
        print(f"Warning: could not put an object on layer {layer}.")


def add_text(ms, text, x, y, height, rotation=0.0, color=None, align=AC_ALIGN_MIDDLE_CENTER,
             layer=LAYER_OTHERS):
    """Add single-line text anchored at (x, y) by its alignment point, then rotate it.

    Because the anchor is the text's own centre (or right end), rotating it keeps it
    exactly where it was placed, whatever the text length or font height.
    """
    obj = ms.AddText(text, APoint(x, y), height)
    obj.Alignment = align                         # set the alignment BEFORE its point
    obj.TextAlignmentPoint = APoint(x, y)
    obj.Rotation = rotation
    set_layer(obj, layer)
    if color is not None:
        obj.Color = color
    return obj


def draw_polygon(ms, points):
    """Draw the survey points and the closed ring of red lines."""
    for x, y in points:
        point = ms.AddPoint(APoint(x, y))
        set_layer(point, LAYER_POINTS)
    count = len(points)
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        line = ms.AddLine(APoint(a[0], a[1]), APoint(b[0], b[1]))
        set_layer(line, LAYER_BOUNDARY)
        line.Color = LINE_COLOR


def label_lines(ms, points, height):
    """Bearing OUTSIDE each line, distance INSIDE it, both parallel to the line."""
    count = len(points)
    offset = LABEL_OFFSET * height
    for i in range(count):
        p1, p2 = points[i], points[(i + 1) % count]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy)
        deg, minute = bearing_dms(dx, dy)
        rotation = text_rotation(dx, dy)

        out_x, out_y = outward_unit_normal(points, i)
        mid_x, mid_y = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0

        bearing_text = build_bearing_text(deg, minute, length, height)
        distance_text = f"{length:.2f}m"
        add_text(ms, bearing_text, mid_x + out_x * offset, mid_y + out_y * offset, height, rotation,
                 layer=LAYER_BRG_DIST)
        add_text(ms, distance_text, mid_x - out_x * offset, mid_y - out_y * offset, height, rotation,
                 layer=LAYER_BRG_DIST)

        print(f"Line {i + 1} - Angle: {deg:02d}{DEGREE_SYMBOL} {minute:02d}', Distance: {distance_text}")


def area_text(points):
    """The area wording, used on the plan and again in the frame."""
    return f"AREA = {polygon_area(points):.3f} SQ. MTRS"


def label_area(ms, points, height):
    """Area text at the middle of the plot."""
    text = area_text(points)
    x, y = polygon_label_point(points)
    add_text(ms, text, x, y, height, color=AREA_COLOR, layer=LAYER_OTHERS)
    print(text)


def westernmost_labels(points):
    """(easting, northing, northing text, easting text) of the westernmost point."""
    easting, northing = min(points, key=lambda p: p[0])
    return easting, northing, f"{northing:.4f}m.N", f"{easting:.4f}m.E"


def label_westernmost_point(ms, points, height):
    """Northing and Easting of the westernmost point, written to its left."""
    easting, northing, northing_str, easting_str = westernmost_labels(points)
    x = easting - COORD_GAP * height
    gap = LABEL_OFFSET * height
    add_text(ms, northing_str, x, northing + gap, height, color=COORD_COLOR, align=AC_ALIGN_MIDDLE_RIGHT,
             layer=LAYER_COORDS)
    add_text(ms, easting_str, x, northing - gap, height, color=COORD_COLOR, align=AC_ALIGN_MIDDLE_RIGHT,
             layer=LAYER_COORDS)
    print(f"Westernmost point inserted: {northing_str}, {easting_str}")


def plot_survey(ms, points, height):
    """Draw and label the whole plan."""
    draw_polygon(ms, points)
    label_lines(ms, points, height)
    label_area(ms, points, height)
    label_westernmost_point(ms, points, height)


# ----------------------------------------------------------------------------
# Road
# ----------------------------------------------------------------------------
def ask(prompt):
    """input() that still works after the pasted coordinates were read to end-of-file.

    Returns None if the console cannot be read any more.
    """
    try:
        return input(prompt)
    except EOFError:
        pass
    try:  # the Windows console keeps its end-of-file mark, so re-open the console and retry
        sys.stdin = open("CONIN$" if os.name == "nt" else "/dev/tty")
        return input(prompt)
    except Exception:
        return None


def ask_road_choice(points):
    """List every boundary line and ask which one the road runs along.

    Returns the index of the chosen line (0 = PT 1 to PT 2), or None for no road.
    """
    count = len(points)
    print("\nROAD OPTIONS (optional - the survey plan above is already plotted in AutoCAD)")
    print("  0 - No road, skip this (or just press Enter)")
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        print(f"  {i + 1} - PT {i + 1} to PT {(i + 1) % count + 1}   ({length:.2f}m)")

    while True:
        raw = ask(f"Enter the option number for the road (0-{count}): ")
        if raw is None:
            print("Could not read your road choice, so the road step was skipped.")
            return None
        raw = raw.strip()
        if raw in ("", "0"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw) - 1
        print(f"Please enter a number from 0 to {count}.")


def ensure_linetype(doc, name):
    """Make sure the line type is loaded in the drawing. Returns True if it is available."""
    try:
        doc.Linetypes.Item(name)
        return True
    except Exception:
        pass
    for lin_file in ("acadiso.lin", "acad.lin"):
        try:
            doc.Linetypes.Load(name, lin_file)
            return True
        except Exception:
            continue
    return False


def road_label_position(points, index, height, width=ROAD_WIDTH):
    """Where the road label goes: middle of the boundary line, in the middle of the road.

    It is pushed outward only if needed, so it never sits on top of the bearing text.
    """
    p1, p2 = points[index], points[(index + 1) % len(points)]
    ox, oy = outward_unit_normal(points, index)
    mid_x, mid_y = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    distance = max(width / 2.0, (LABEL_OFFSET + 1.0) * height)
    return mid_x + ox * distance, mid_y + oy * distance


def draw_road(ms, doc, points, index):
    """Draw the road lines in white with a broken (HIDDEN2) line type."""
    linetype_ready = ensure_linetype(doc, ROAD_LINETYPE)
    if not linetype_ready:
        print(f"Warning: could not load the {ROAD_LINETYPE} line type, so the road is drawn with a solid line.")
    for a, b in road_lines(points, index):
        line = ms.AddLine(APoint(a[0], a[1]), APoint(b[0], b[1]))
        set_layer(line, LAYER_ROAD_LINE)
        line.Color = ROAD_COLOR
        if linetype_ready:
            try:
                line.Linetype = ROAD_LINETYPE
                line.LinetypeScale = ROAD_LINETYPE_SCALE
            except Exception:
                print(f"Warning: could not apply the {ROAD_LINETYPE} line type to a road line.")


def road_label_text(road_length, height):
    """ROAD_LABEL with the gaps between its words widened to spread along the road, never beyond it."""
    words = ROAD_LABEL.split()
    if len(words) < 2:
        return ROAD_LABEL
    letters_width = sum(len(w) for w in words) * CHAR_WIDTH * height
    room = ROAD_LABEL_FILL * road_length - letters_width
    spaces = max(int(room / (SPACE_WIDTH * height * (len(words) - 1))), 1)
    return (" " * spaces).join(words)


def label_road(ms, points, index, height):
    """Write the default road label (ROAD_LABEL) inside the road, parallel to it."""
    p1, p2 = points[index], points[(index + 1) % len(points)]
    x, y = road_label_position(points, index, height)
    road_length = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) + 2 * ROAD_EXTENSION
    add_text(ms, road_label_text(road_length, height), x, y, height,
             text_rotation(p2[0] - p1[0], p2[1] - p1[1]),
             color=ROAD_LABEL_COLOR, layer=LAYER_ROAD_LABELS)


def road_step(ms, doc, points, height):
    """Ask for the road and draw it. Runs straight after plotting, before any other prompt."""
    index = ask_road_choice(points)
    if index is None:
        print("No road added.")
        return
    draw_road(ms, doc, points, index)
    label_road(ms, points, index, height)
    count = len(points)
    print(f"Road added along PT {index + 1} to PT {(index + 1) % count + 1}: "
          f"{ROAD_WIDTH:.2f}m wide, running {ROAD_EXTENSION:g}m past each end, labelled {ROAD_LABEL}.")


def table_start_order(points):
    """Station numbers (0-based) starting from the westernmost point, then continuing in order.

    If PT3 is the westernmost of 4 points the result is [2, 3, 0, 1], i.e. PT3, PT4, PT1, PT2.
    """
    count = len(points)
    first = min(range(count), key=lambda i: points[i][0])
    return [(first + k) % count for k in range(count)]


def make_color(doc, index):
    """An AutoCAD colour object (ACI index) for table cells, or None if it cannot be made."""
    app = doc.Application
    versions = []
    try:
        versions.append(str(app.Version).split(".")[0])
    except Exception:
        pass
    versions += ["24", "23", "22", "25", "21", "20"]
    for ver in versions:
        try:
            color = app.GetInterfaceObject(f"AutoCAD.AcCmColor.{ver}")
            color.ColorIndex = index
            return color
        except Exception:
            continue
    return None


def add_coord_table(ms, doc, points, height):
    """Add the STATION / EASTING(m) / NORTHING(m) table, starting from the westernmost point."""
    order = table_start_order(points)
    count = len(order)
    rows_wanted = count + 1                                   # heading row + one row per point

    def call(fn, what):
        return com_retry(fn, what, timeout=20, delay=0.5)

    cells = [[TABLE_HEADERS[0], TABLE_HEADERS[1], TABLE_HEADERS[2]]]
    for i in order:
        cells.append([f"PT{i + 1}", f"{points[i][0]:.4f}", f"{points[i][1]:.4f}"])

    row_h = TABLE_ROW_FACTOR * height
    margin = TABLE_MARGIN_FACTOR * height
    col_w = [max(len(r[c]) for r in cells) * TABLE_CHAR_FACTOR * height + 2 * margin for c in range(3)]

    gap = TABLE_GAP * height + ROAD_EXTENSION + ROAD_WIDTH     # clear of the road and the labels
    x = max(p[0] for p in points) + gap
    y = max(p[1] for p in points)

    table = call(lambda: ms.AddTable(APoint(x, y), rows_wanted + 1, 3, row_h, col_w[0]), "adding the table")
    set_layer(table, LAYER_TABLE)

    # No title row: the first row is the heading row (STATION, EASTING(m), NORTHING(m)).
    try:
        call(lambda: setattr(table, "TitleSuppressed", True), "removing the table title row")
    except RuntimeError:
        pass
    offset = max(int(call(lambda: table.Rows, "reading the table rows")) - rows_wanted, 0)

    for setting in ("HorzCellMargin", "VertCellMargin"):
        try:
            call(lambda n=setting: setattr(table, n, margin), f"setting {setting}")
        except RuntimeError:
            pass
    for row_type in (1, 2, 4):                                # data, title and heading rows
        try:
            call(lambda r=row_type: table.SetTextHeight(r, height), "setting the table text height")
            call(lambda r=row_type: table.SetAlignment(r, 5), "centering the table text")  # 5 = middle centre
        except RuntimeError:
            print("Warning: could not set the table text height/alignment for one row type.")
    for r in range(rows_wanted):
        call(lambda r=r: table.SetRowHeight(r + offset, row_h), "setting a row height")
    for c in range(3):
        call(lambda c=c: table.SetColumnWidth(c, col_w[c]), "setting a column width")

    white, red = make_color(doc, TABLE_TEXT_COLOR), make_color(doc, TABLE_VALUE_COLOR)
    if white is None or red is None:
        print("Warning: could not set the table text colours; the default colours are used.")
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            call(lambda r=r, c=c, t=text: table.SetCellValue(r + offset, c, t), "writing a table cell")
            colour = red if (r > 0 and c > 0) else white
            if colour is not None:
                try:
                    call(lambda r=r, c=c, k=colour: table.SetCellContentColor(r + offset, c, k),
                         "colouring a table cell")
                except RuntimeError:
                    pass
    print(f"Coordinates table added on layer {LAYER_TABLE}, starting from PT{order[0] + 1} "
          f"(westernmost): " + ", ".join(f"PT{i + 1}" for i in order))


def ask_table_choice():
    """Ask whether to paste the coordinates list in AutoCAD. True = add the table."""
    print("\nDo you want to paste the coordinates list in AutoCAD?")
    print("  0 or press Enter to skip")
    print("  Press 1 to add the coordinates list")
    while True:
        raw = ask("Your choice: ")
        if raw is None:
            print("Could not read your choice, so the coordinates table was skipped.")
            return False
        raw = raw.strip()
        if raw in ("", "0"):
            return False
        if raw == "1":
            return True
        print("Please press 0 (or Enter) to skip, or 1 to add the coordinates list.")


def table_step(ms, doc, points, height):
    """Optional coordinates table. Runs after the road prompt."""
    if not ask_table_choice():
        print("No coordinates table added.")
        return
    try:
        add_coord_table(ms, doc, points, height)
    except RuntimeError as err:
        print(f"Could not add the coordinates table: {err}")


# ----------------------------------------------------------------------------
# Frame (an A4 portrait sheet drawn around everything, with its labels)
# ----------------------------------------------------------------------------
def ensure_bold_style(doc):
    """Create (or reuse) the bold text style used for the surveyor's name. Returns its name, or None if it cannot be made."""
    def make():
        try:
            style = doc.TextStyles.Item(BOLD_STYLE_NAME)
        except Exception:
            style = doc.TextStyles.Add(BOLD_STYLE_NAME)
        style.SetFont(BOLD_FONT, True, False, 0, BOLD_FONT_PITCH_FAMILY)    # bold, not italic
        return BOLD_STYLE_NAME

    try:
        return com_retry(make, "creating the bold text style", timeout=15, delay=0.5)
    except RuntimeError as err:
        print(f"Warning: could not make the bold text style, so the surveyor's name stays regular. {err}")
        return None


class Sheet:
    """The A4 sheet. Positions and sizes are in millimetres ON PAPER, measured from the sheet's
    bottom-left corner. The scale turns them into meters in the drawing.

    Lines and arcs go on the frame layer; every text goes on the frame_labels layer.
    """

    def __init__(self, ms, origin_x, origin_y, scale, bold_style=None):
        self.ms = ms
        self.bold_style = bold_style       # name of the bold text style, or None (then nothing is bold)
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.scale = scale
        self.k = scale / 1000.0            # meters in the drawing for every millimetre on paper

    def to_model(self, x_mm, y_mm):
        return self.origin_x + x_mm * self.k, self.origin_y + y_mm * self.k

    def to_paper(self, x, y):
        return (x - self.origin_x) / self.k, (y - self.origin_y) / self.k

    def line(self, x1, y1, x2, y2, color=None):
        (ax, ay), (bx, by) = self.to_model(x1, y1), self.to_model(x2, y2)
        obj = com_retry(lambda: self.ms.AddLine(APoint(ax, ay), APoint(bx, by)),
                        "drawing a frame line", timeout=15, delay=0.3)
        set_layer(obj, LAYER_FRAME)
        if color is not None:
            obj.Color = color
        return obj

    def rectangle(self, x1, y1, x2, y2):
        self.line(x1, y1, x2, y1)
        self.line(x2, y1, x2, y2)
        self.line(x2, y2, x1, y2)
        self.line(x1, y2, x1, y1)

    def arc(self, cx_mm, cy_mm, radius_mm, start_deg, end_deg, color=None):
        cx, cy = self.to_model(cx_mm, cy_mm)
        obj = com_retry(lambda: self.ms.AddArc(APoint(cx, cy), radius_mm * self.k,
                                               math.radians(start_deg), math.radians(end_deg)),
                        "drawing the north arrow", timeout=15, delay=0.3)
        set_layer(obj, LAYER_FRAME)
        if color is not None:
            obj.Color = color
        return obj

    def text(self, string, x_mm, y_mm, height_mm, color=None, align=AC_ALIGN_MIDDLE_CENTER, bold=False):
        x, y = self.to_model(x_mm, y_mm)
        obj = add_text(self.ms, string, x, y, height_mm * self.k, 0.0, color, align,
                       layer=LAYER_FRAME_LABELS)
        if bold and self.bold_style:
            try:
                obj.StyleName = self.bold_style
            except Exception:
                print("Warning: could not make the surveyor's name bold.")
        return obj


def content_bounds(points):
    """(xmin, ymin, xmax, ymax), in meters, of the survey plan (the boundary) only.

    The road, the labels and the coordinates table are NOT counted, so the scale and the position
    of the sheet depend on the boundary alone.
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def sheet_fits(bounds, scale):
    """True if the survey plan fits inside the drawing region of the sheet at this scale."""
    k = scale / 1000.0
    rx1, ry1, rx2, ry2 = DRAW_REGION
    return ((bounds[2] - bounds[0]) <= (rx2 - rx1) * k + 1e-9
            and (bounds[3] - bounds[1]) <= (ry2 - ry1) * k + 1e-9)


def smallest_scale_that_fits(bounds):
    """The smallest whole scale number at which the survey plan fits (500 means 1/500)."""
    rx1, ry1, rx2, ry2 = DRAW_REGION
    needed = max((bounds[2] - bounds[0]) * 1000.0 / (rx2 - rx1),
                 (bounds[3] - bounds[1]) * 1000.0 / (ry2 - ry1))
    return max(int(math.ceil(needed - 1e-9)), 1)


def best_fit_scale(bounds):
    """The first standard scale that fits, or None if even the smallest one is too big."""
    for scale in AUTO_SCALES:
        if sheet_fits(bounds, scale):
            return scale
    return None


def sheet_origin(bounds, scale):
    """Where the sheet's bottom-left corner goes so the survey plan is centred in the drawing region."""
    k = scale / 1000.0
    rx1, ry1, rx2, ry2 = DRAW_REGION
    centre_x, centre_y = (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0
    return centre_x - (rx1 + rx2) / 2.0 * k, centre_y - (ry1 + ry2) / 2.0 * k


def ask_frame_choice():
    """Ask whether to add the frame. True = add it."""
    print("\nDo you want to add the frame (A4 sheet with title block, scale bar and north arrow)?")
    print("  0 or press Enter to skip")
    print("  Press 1 to add the frame")
    while True:
        raw = ask("Your choice: ")
        if raw is None:
            print("Could not read your choice, so the frame was skipped.")
            return False
        raw = raw.strip()
        if raw in ("", "0"):
            return False
        if raw == "1":
            return True
        print("Please press 0 (or Enter) to skip, or 1 to add the frame.")


def ask_frame_scale(bounds):
    """Ask for the plan scale. Enter = best fit. Returns the scale number (500 = 1/500) or None."""
    best = best_fit_scale(bounds)
    if best is None:
        print(f"This plan is too big for an A4 frame even at 1/{AUTO_SCALES[-1]}, so no frame was added.")
        return None
    minimum = smallest_scale_that_fits(bounds)
    while True:
        raw = ask(f"Enter the scale number for the frame, e.g. 500 for 1/500 "
                  f"(press Enter for the best fit, 1/{best}): ")
        if raw is None:
            print("Could not read the scale, so the frame was skipped.")
            return None
        raw = raw.strip().replace(" ", "")
        if raw.startswith("1/"):
            raw = raw[2:]
        if not raw:
            return best
        if raw.isdigit() and int(raw) > 0:
            scale = int(raw)
            if sheet_fits(bounds, scale):
                return scale
            print(f"The survey plan does not fit on the sheet at 1/{scale}. "
                  f"The smallest scale that fits is 1/{minimum}; 1/{best} is the best standard one.")
            continue
        print("Please enter a whole number such as 500, or press Enter.")


def scale_bar_step(scale):
    """Length of one part of the scale bar, in meters: 10 m at 1/500 and (scale / 500) x 10 m at any other scale.

    So the parts are always the same length on paper (20 mm).
    """
    return SCALE_BAR_REF_STEP * scale / SCALE_BAR_REF_SCALE


def draw_scale_bar(sheet, scale):
    """Scale bar of three equal parts: -step, 0, step, 2 x step (e.g. 10m 0 10 20m at 1/500)."""
    step = scale_bar_step(scale)
    segment = step * 1000.0 / scale                       # length of one part on paper, mm
    xs = [SCALE_BAR_CENTER_X + segment * f for f in (-1.5, -0.5, 0.5, 1.5)]
    y0 = SCALE_BAR_Y
    sheet.line(xs[0], y0, xs[3], y0)
    sheet.line(xs[0], y0 + 1.0, xs[3], y0 + 1.0)
    for i, x in enumerate(xs):
        start = y0 if i in (0, 3) else y0 + 1.0           # the two end ticks start on the lower line
        sheet.line(x, start, x, y0 + 4.0)
    number = lambda value: f"{round(value, 2):g}"
    labels = (f"{number(step)}m", "0", number(step), f"{number(2 * step)}m")
    for x, label in zip(xs, labels):
        sheet.text(label, x, y0 + 5.9, TEXT_SCALE)


def draw_north_arrow(sheet, x):
    """Blue north arrow on a vertical line: half arrowhead, open circle, and its small label."""
    sheet.line(x, NORTH_BOTTOM_Y, x, NORTH_TOP_Y, FRAME_GRID_COLOR)
    radius = 2.4
    cx, cy = x - 0.35, NORTH_CIRCLE_Y
    tip = (cx + radius * math.cos(math.radians(146)), cy + radius * math.sin(math.radians(146)))
    sheet.line(x, NORTH_TOP_Y, tip[0], tip[1], FRAME_GRID_COLOR)
    sheet.arc(cx, cy, radius, 212.0, 146.0, FRAME_GRID_COLOR)      # circle left open on the left side
    sheet.text(NORTH_LABEL, x, 234.0, TEXT_PLAN, FRAME_GRID_COLOR)


def draw_crosshair(sheet, west):
    """Blue cross-hair centred on the westernmost point: a cross with four arms of equal length."""
    xw, yw = west
    sheet.line(xw - CROSSHAIR_ARM, yw, xw + CROSSHAIR_ARM, yw, FRAME_GRID_COLOR)
    sheet.line(xw, yw - CROSSHAIR_ARM, xw, yw + CROSSHAIR_ARM, FRAME_GRID_COLOR)


def draw_grid_lines(sheet, west, bounds_mm):
    """Blue lines through the westernmost point, from the frame edges, stopping short of the plan."""
    xw, yw = west
    bx1, by1, bx2, by2 = bounds_mm
    gap = 2.0
    x1, _, x2, _ = FRAME_BORDER
    left_end = min(x1 + GRID_STUB_SIDE, bx1 - gap)
    if left_end - x1 >= gap:
        sheet.line(x1, yw, left_end, yw, FRAME_GRID_COLOR)
    right_start = max(x2 - GRID_STUB_SIDE, bx2 + gap)
    if x2 - right_start >= gap:
        sheet.line(right_start, yw, x2, yw, FRAME_GRID_COLOR)
    low_end = min(TITLE_BLOCK_TOP + GRID_STUB_BOTTOM, by1 - gap)
    if low_end - TITLE_BLOCK_TOP >= gap:
        sheet.line(xw, TITLE_BLOCK_TOP, xw, low_end, FRAME_GRID_COLOR)


def draw_border_and_title_block(sheet):
    """Border, title block along the bottom, and the plan number box hanging from the top border."""
    x1, y1, x2, y2 = FRAME_BORDER
    sheet.rectangle(x1, y1, x2, y2)
    sheet.line(x1, TITLE_BLOCK_TOP, x2, TITLE_BLOCK_TOP)
    sheet.line(TITLE_COL_1, y1, TITLE_COL_1, TITLE_BLOCK_TOP)
    sheet.line(TITLE_COL_2, y1, TITLE_COL_2, TITLE_BLOCK_TOP)
    sheet.line(x1, LEFT_SPLIT_Y, TITLE_COL_1, LEFT_SPLIT_Y)
    sheet.line(TITLE_COL_2, RIGHT_SPLIT_Y, x2, RIGHT_SPLIT_Y)
    bx1, by1, bx2, by2 = PLAN_BOX                          # its top is the border, so only 3 sides
    sheet.line(bx1, by1, bx2, by1)
    sheet.line(bx1, by1, bx1, by2)
    sheet.line(bx2, by1, bx2, by2)


def draw_plan_number_box_labels(sheet, year):
    x = (PLAN_BOX[0] + PLAN_BOX[2]) / 2.0
    sheet.text("PLAN   NO.", x, 288.4, TEXT_PLAN)
    sheet.text(f"***/****/ {year}", x, 282.6, TEXT_PLAN)


def draw_title_block_labels(sheet, year, date_text):
    left_x = (FRAME_BORDER[0] + TITLE_COL_1) / 2.0
    sheet.text("PLAN NO :", left_x, TITLE_BLOCK_TOP - 3.6, TEXT_BIG)
    sheet.text(f"***/****/ {year}", left_x, TITLE_BLOCK_TOP - 13.6, TEXT_BIG)
    sheet.text("DEP NO :", left_x, LEFT_SPLIT_Y - 3.6, TEXT_BIG)
    sheet.text(f"SURV. /REC     / {year}", left_x, LEFT_SPLIT_Y - 13.6, TEXT_BIG)

    left = TITLE_COL_2 + 1.0
    sheet.text("CERTIFIED TRUE COPY OF ORIGINAL PLAN", left, 54.2, TEXT_STD, align=AC_ALIGN_MIDDLE_LEFT)
    sheet.text(f"MADE BY ME ON {date_text}", left, 49.8, TEXT_STD, align=AC_ALIGN_MIDDLE_LEFT)

    right_x = (TITLE_COL_2 + FRAME_BORDER[2]) / 2.0
    sheet.text("SURV. [PLACEHOLDER SURVEYOR]", right_x, 23.5, TEXT_NAME, bold=True)
    sheet.text("[PLACEHOLDER COMPANY NAME]", right_x, 18.7, TEXT_SMALL)
    sheet.text("[PLACEHOLDER ADDRESS]", right_x, 14.8, TEXT_SMALL)
    sheet.text("[STATE] STATE, NIGERIA", right_x, 11.1, TEXT_SMALL)


def draw_title_text(sheet, scale, points):
    """Title lines at the top right, then the scale bar, the origin and the area."""
    lines = FRAME_TITLE_LINES + (f"SCALE 1/{scale}",)
    for i, line in enumerate(lines):
        sheet.text(line, TITLE_CENTER_X, TITLE_TOP_Y - i * TITLE_LINE_GAP, TEXT_STD)
    draw_scale_bar(sheet, scale)
    sheet.text(f"ORIGIN= UTM ZONE {UTM_ZONE}", TITLE_CENTER_X, SCALE_BAR_Y - 3.2, TEXT_STD,
               FRAME_GRID_COLOR)
    sheet.text(area_text(points), TITLE_CENTER_X, SCALE_BAR_Y - 7.5, TEXT_STD, FRAME_AREA_COLOR)


def draw_frame(sheet, points, today):
    """Draw the whole frame on the sheet: lines on layer frame, texts on layer frame_labels."""
    year = today.year
    date_text = today.strftime("%d/%m/%Y")
    draw_border_and_title_block(sheet)
    draw_plan_number_box_labels(sheet, year)
    draw_title_block_labels(sheet, year, date_text)
    draw_title_text(sheet, sheet.scale, points)

    easting, northing, _, _ = westernmost_labels(points)
    xw, yw = sheet.to_paper(easting, northing)
    draw_crosshair(sheet, (xw, yw))
    bounds = content_bounds(points)
    bx1, by1 = sheet.to_paper(bounds[0], bounds[1])
    bx2, by2 = sheet.to_paper(bounds[2], bounds[3])
    draw_grid_lines(sheet, (xw, yw), (bx1, by1, bx2, by2))
    draw_north_arrow(sheet, min(max(xw, 20.0), 120.0))      # keep the arrow clear of the title text


def frame_step(ms, doc, points, height):
    """Optional frame, drawn last. Its scale and position come from the survey plan (boundary) alone.

    Returns the Sheet that was drawn, or None if no frame was added.
    """
    if not ask_frame_choice():
        print("No frame added.")
        return None
    bounds = content_bounds(points)
    scale = ask_frame_scale(bounds)
    if scale is None:
        print("No frame added.")
        return None

    origin_x, origin_y = sheet_origin(bounds, scale)
    sheet = Sheet(ms, origin_x, origin_y, scale, ensure_bold_style(doc))
    try:
        draw_frame(sheet, points, datetime.date.today())
    except Exception:
        print("\nThe frame could not be completed - details below. The plan itself is not affected.")
        traceback.print_exc()
        return None

    print(f"Frame added at 1/{scale}: lines on layer {LAYER_FRAME}, texts on layer {LAYER_FRAME_LABELS}.")
    units = scale / 1000.0
    print("The scale was worked out from the survey plan only (not the road, labels or table).")
    print(f"To print: A4 portrait, plot area = Window around the border, "
          f"plot scale 1 mm = {units:g} drawing unit{'' if units == 1 else 's'}.")
    label_mm = height * 1000.0 / scale
    if abs(label_mm - TEXT_STD) > 0.3 * TEXT_STD:
        print(f"Note: at 1/{scale} your plan labels print {label_mm:.1f} mm tall, but the frame text is "
              f"{TEXT_STD:g} mm. A font height of {TEXT_STD * scale / 1000.0:.2f} would match.")
    return sheet


def zoom_extents(acad, doc):
    try:
        acad.app.ZoomExtents()
    except Exception:
        doc.SendCommand("_ZOOM _EXTENTS\n")


def finish_drawing(acad, doc):
    """Make AutoCAD show everything drawn so far: regenerate, then zoom to the extents."""
    try:
        doc.Regen(1)          # 1 = acActiveViewport
    except Exception:
        pass
    zoom_extents(acad, doc)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def ask_next_action():
    """End-of-job menu. Returns True to plot another job, False to end the program."""
    print("\nPress 0 or just press Enter to end this program")
    print("Press 1 to plot another job")
    while True:
        raw = ask("Your choice: ")
        if raw is None:
            return False
        raw = raw.strip()
        if raw in ("", "0"):
            return False
        if raw == "1":
            return True
        print("Please press 0 (or Enter) to end, or 1 to plot another job.")


def run_job(acad):
    """One job: ask for the inputs, open a new drawing, plot it, add the road, table and frame. Returns the AutoCAD connection."""
    height = ask_font_height()
    points = read_points()
    acad, doc, ms = connect_autocad(acad)     # new drawing from the default template, set up
    plot_survey(ms, points, height)             # perimeter, points, bearings, distances, area, coordinates
    finish_drawing(acad, doc)                   # regenerate + zoom so the plan is ready on screen
    print("\nSurvey plan plotted and ready in AutoCAD.")
    road_step(ms, doc, points, height)          # optional: only now do we prompt for the road
    finish_drawing(acad, doc)                   # zoom again in case a road was added
    table_step(ms, doc, points, height)         # optional: coordinates table, after the road prompt
    finish_drawing(acad, doc)                   # zoom again so the table is included
    frame_step(ms, doc, points, height)         # optional: the frame, last, around the survey plan
    finish_drawing(acad, doc)                   # zoom again so the frame is included
    print("Executed Successfully!")
    return acad


def main():
    print(INSTRUCTIONS)
    acad = None
    job = 0
    while True:
        job += 1
        print(f"\n===== JOB {job} =====")
        try:
            acad = run_job(acad)
        except (ValueError, RuntimeError) as err:
            print(f"\nERROR: {err}")
        except Exception:
            print("\nUNEXPECTED ERROR - details below:")
            traceback.print_exc()
        if not ask_next_action():
            break
    print("Program ended. Your drawings are still open in AutoCAD.")


if __name__ == "__main__":
    main()
