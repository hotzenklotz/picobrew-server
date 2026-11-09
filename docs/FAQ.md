# FAQ

## How do I update or delete a recipe?
To change the brewing steps, open the recipe in the **Recipes** library and choose **Edit machine program** (or **Add machine program**). The editor writes the steps back into the recipe's BeerXML file.

For any other change, replace the file in the `recipes` directory inside the data directory. Recipes are read from these files every time they are needed; nothing is cached or kept in a separate database. Uploading a file with the same name as an existing recipe is rejected, so re-uploading does not overwrite it. To delete a recipe, delete its file from the `recipes` directory.

## Not all my recipes are synced
Only recipes containing a full mashing program are synced. When you import a recipe through the web interface, the review page shows whether it found a machine program and lets you add or edit one. In the recipe library, recipes without a program are marked **Missing machine program**.

All recipes exported from the recipe editor at www.picobrew.com should just work.

On a technical note: your BeerXML file must contain a `<ZYMATIC>` tag inside the recipe to be synced:
```
<ZYMATIC>
    <NAME />
    <MASH_TEMP>100</MASH_TEMP>
    <MASH_TIME>90</MASH_TIME>
    <BOIL_TEMP>207</BOIL_TEMP>
    <BOIL_TIME>60</BOIL_TIME>
    <STEP>
        <NAME>Heat Water</NAME>
        <TEMP>152</TEMP>
        <TIME>0</TIME>
        <LOCATION>0</LOCATION>
        <DRAIN>0</DRAIN>
    </STEP>
    <STEP>
        <NAME>Mash</NAME>
        <TEMP>152</TEMP>
        <TIME>60</TIME>
        <LOCATION>1</LOCATION>
        <DRAIN>5</DRAIN>
    </STEP>
</ZYMATIC>
```

## I have a BeerXML file from somewhere else than www.picobrew.com
You can manually update any BeerXML file to be PicoBrew Server compatible by adding the mashing schedule with a text editor. Add a `<ZYMATIC>` tag, as shown above, to the recipe, or import the file and use **Add program** in the web interface.

## Where can I find a session log
Open **Brew history** in the web interface. It lists every brew and cleaning session; a running session is highlighted at the top. Each session page shows a temperature chart with the machine's steps, a step table, any reset reports, and a CSV download of every reading. While the machine is brewing, the page updates live.

Sessions are stored in one SQLite database, `sessions/brew_sessions.sqlite3`, inside the data directory (`--data-dir` or `PICOBREW_DATA_DIR`, by default the server's working directory). Device error/reset reports are stored in the same database without changing the recovery state of the brew log. Session logs and error reports written as JSON files by earlier versions are imported automatically on first start; the JSON files are left in place. Machine and indexed sensor registrations from `firstSetup` are stored in `machines`. Keep both directories with your data.

The machine logs its four temperature sensors about once a minute, as whole degrees Fahrenheit: channel 2 is the wort, 1 is heat 1, 3 is the control board and 4 is heat 2 (the backup heat sensor). The history pages show these values in °F as received.

## Which account do I select during machine setup?

The local server presents a single account named `PicoBrew Server`. It has a stable identifier and shares the uploaded recipe library across all connected machines. The server's firmware check reports no available update because it does not distribute application firmware images.
