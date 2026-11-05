# My Geocache Finds

A personal web app that turns your Geocaching.com **My Finds** Pocket Query
into caching days you can explore on a map:

- **Day Replay**: replay any caching day, find by find, on a map, with your logs
- **Browse by Date** and **Browse by Location**: by year and month, or country,
  province or state and town
- **Trips**: name a date range and see its caching days together
- **Favourites**: star the days, trips and caches you like best
- **My Places**: name your own areas (a park, a cabin, a neighbourhood) so
  day titles use them

It runs entirely on your own computer. Your finds, trips and notes stay in
the app's folder and are never sent anywhere. The only thing it fetches from
the internet is the map itself (from OpenStreetMap).

It works on **Windows, macOS and Linux**.

---

## What you need

- **Python 3.9 or newer.** No other software or add-ons are needed, except one
  small package on Windows (step 1).
- **A web browser**: Chrome, Edge, Firefox or Safari.
- **A Geocaching.com Premium membership**, to get your My Finds Pocket Query.
- **About 600 MB of free disk space** if you want town names in day titles
  (optional, step 5).

---

## 1. Install Python

### Windows 10 or 11

1. Download Python from <https://www.python.org/downloads/> and run the installer.
   If it shows a checkbox **Add python.exe to PATH**, tick it.
2. Open **Terminal** (or Command Prompt) from the Start menu and check it worked:
   ```
   py --version
   ```
   You should see something like `Python 3.13.1`.
3. Install the time zone data, which Windows doesn't include:
   ```
   py -m pip install tzdata
   ```
   Without it the app still works, but it can't tell what time it was where
   each cache is, so a find logged late in the evening can land on the next day.

On Windows the command is **`py`**. Wherever the app or these instructions
say `python3`, type `py` instead.

### macOS

Recent Macs may already have Python. In **Terminal** (Applications ▸ Utilities) type:
```
python3 --version
```
If it isn't there, or is older than 3.9, install it from
<https://www.python.org/downloads/>.

### Linux

Almost every Linux distribution already has Python 3. Check with:
```
python3 --version
```
If it's missing, install it with your package manager, for example
`sudo apt install python3` (Ubuntu, Debian) or `sudo dnf install python3` (Fedora).

---

## 2. Get the app

The app is kept on **GitHub**, a website where people share software. You
don't need a GitHub account or any GitHub know-how. You download the app as
one zip file, the same way you'd download any file, and unzip it into a folder.

### Download the zip file

1. Go to the app's page on GitHub:
   **<https://github.com/GrantsTracks2121/My_Geocache_Finds>**
   (If you're reading this on GitHub, you're already there: scroll back to
   the top of the page.)
2. Above the list of files, click the green **Code** button.

   ![The green Code button, above the list of files](docs/images/github-code-button.png)

3. A menu opens. Click **Download ZIP** at the bottom of it. You can ignore
   everything else in the menu.

   ![The Code menu, with Download ZIP at the bottom](docs/images/github-download-zip.png)

4. Your browser saves a file named **My_Geocache_Finds-main.zip**, usually in
   your **Downloads** folder.

### Unzip it into a folder

The zip file holds one folder, **My_Geocache_Finds-main**. That folder is the
app. Put it somewhere you'll find it again, such as your **Documents** folder.
Everything the app saves (your trips, favourites and so on) goes in this
folder too.

**Windows 10 or 11**

1. Open **File Explorer** and go to your **Downloads** folder.
2. Right-click **My_Geocache_Finds-main.zip** and choose **Extract All…**
3. In the window that opens, click **Browse…**, choose your **Documents**
   folder, and click **Select Folder**.
4. Click **Extract**. The folder **My_Geocache_Finds-main** is now in Documents.

**macOS**

1. Open **Finder** and go to your **Downloads** folder.
2. Double-click **My_Geocache_Finds-main.zip**. A folder named
   **My_Geocache_Finds-main** appears next to it. (Safari sometimes does this
   for you, so the folder may already be there.)
3. Drag the **My_Geocache_Finds-main** folder into your **Documents** folder.

**Linux**

1. Open your file manager and go to your **Downloads** folder.
2. Right-click **My_Geocache_Finds-main.zip** and choose **Extract Here**.
3. Move the **My_Geocache_Finds-main** folder into your **Documents** folder.

Or, in a terminal: `unzip ~/Downloads/My_Geocache_Finds-main.zip -d ~/Documents`

**Check:** open the **My_Geocache_Finds-main** folder. You should see files
such as `serve.py`, `index.html` and `README.md` straight away. If instead you
see another folder with the same name, open that one: that's the app's folder.

You can rename the folder if you like, for example to **My Geocache Finds**.

### If you use git

You can clone the app instead of downloading the zip:
```
git clone https://github.com/GrantsTracks2121/My_Geocache_Finds.git
```

---

## 3. Start the app

Open a terminal **in the app's folder**:

- **Windows 11:** in File Explorer, open the folder, right-click an empty space
  and choose **Open in Terminal**.
- **macOS:** in Finder, right-click the folder and choose
  **Services ▸ New Terminal at Folder**. Or type `cd ` in Terminal, drag the
  folder onto the window and press Return.
- **Linux:** most file managers have **Open in Terminal** on the right-click
  menu. Or `cd` to the folder.

Then start the app:

| Windows | macOS and Linux |
|---|---|
| `py serve.py` | `python3 serve.py` |

You'll see `Serving this folder at http://localhost:8002/`. Open
**<http://localhost:8002/>** in your web browser. That's the Dashboard.

Leave the terminal window open while you use the app. To stop it, click in
the terminal and press **Control-C**. Next time, just run the same command
again.

Only your own computer can open the app. Nobody else on your network or the
internet can reach it.

---

## 4. Load your finds

1. On Geocaching.com, go to **Pocket Queries** (<https://www.geocaching.com/pocket/>).
2. Under **My Finds**, click **Add to Queue**. Geocaching.com prepares it in a
   few minutes to an hour, and you can run it once every three days.
3. On the **Pocket Queries Ready for Download** tab, download the .zip file.
4. Drag the .zip file onto the **My Finds Pocket Query** box at the bottom of
   the Dashboard, or click the box to choose the file. There's no need to unzip it.

The app reads every find and builds your caching days. This takes about half a
minute. Do the same whenever you want to bring it up to date with your newest
finds.

---

## 5. Optional: town names in day titles

Without this step, day titles show only the province or state, such as
"Alberta". With it, they name the towns, such as "Devon & near Edmonton, Alberta",
and each find's local time zone comes from the nearest town.

In the terminal, in the app's folder (stop the app with Control-C first, or
open a second terminal):

| Windows | macOS and Linux |
|---|---|
| `py build_places.py` | `python3 build_places.py` |

This downloads the GeoNames list of the world's towns (about 400 MB) and builds
a lookup file from it. It only needs to be done once. Then load your My Finds
file again (step 4) so the titles use the town names.

### Canada only: city and county limits

For finds in Canada, the app can use Statistics Canada's municipal boundaries
so a cache is credited to the town it is really in. For example, a cache in
Sherwood Park is credited to Sherwood Park, not to nearby Edmonton.
The file has to be downloaded by hand:

1. Download **lcsd000b21a_e.zip** (Census subdivisions, Shapefile, about 160 MB):
   <https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000b21a_e.zip>
2. Put it in the `boundaries` folder inside the app's folder (create the folder
   if it isn't there). Don't unzip it.
3. Run `py build_boundaries.py` (Windows) or `python3 build_boundaries.py`
   (macOS, Linux), then load your My Finds file again.

---

## What stays on your computer

Everything you add is saved in the app's folder:

| File or folder | What it holds |
|---|---|
| `*.gpx` | your My Finds Pocket Query |
| `data/days.js` | your caching days, built from it |
| `trips.json` | your trips |
| `favorites.json` | your starred days, trips and caches |
| `places.json` | your My Places |
| `settings.json` | your Dashboard settings |
| `profile/` | your Dashboard picture and background |

To back up your data, copy these. To move the app to a new folder or computer,
copy the whole folder.

---

## Troubleshooting

**"py" or "python3" is not recognized.**
Python isn't installed, or wasn't added to PATH. Run the Python installer
again and tick **Add python.exe to PATH** (Windows), then open a new terminal.

**A yellow bar says "this isn't serve.py".**
The pages were opened some other way, for example by double-clicking
`index.html`. Start the app with `py serve.py` or `python3 serve.py` and open
<http://localhost:8002/>.

**"Address already in use" when starting.**
The app is already running in another terminal window, or something else is
using port 8002. Use the running copy, or start it on another port with
`py serve.py 8003` and open <http://localhost:8003/>.

**After loading finds, the terminal says there's no time zone data.**
On Windows, run `py -m pip install tzdata`, then load your My Finds file again.

**The map is blank.**
The map comes from OpenStreetMap, so it needs an internet connection.
Everything else works offline.

---

## Known limits

- Day titles leave out **Canada** as the "home" country, and name every other
  country. This is fixed in `build_days.py` (`HOME_COUNTRY`) for now.
- The **Alberta Brass Cap Cache** (GC43F3) support is specific to the app's
  author's finds. It has no effect on anyone else's data.

---

## Credits

- Maps © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors
- Place names: [GeoNames](https://www.geonames.org), CC BY 4.0
- Canadian boundaries: Statistics Canada, 2021 Census Boundary Files,
  Statistics Canada Open Licence
- Cache type icons: [c:geo](https://github.com/cgeo/cgeo), Apache License 2.0
- [Leaflet](https://leafletjs.com) (BSD 2-Clause),
  [marked](https://github.com/markedjs/marked) (MIT),
  [DOMPurify](https://github.com/cure53/DOMPurify) (Apache 2.0 / MPL 2.0)

Geocaching and Pocket Queries are trademarks of Groundspeak, Inc. This app is
not made by or connected with Geocaching.com.

## License

© 2026 Grant S. Wilson. Released under the [MIT License](LICENSE).
