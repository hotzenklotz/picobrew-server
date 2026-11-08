# FAQ

## How do I update a recipe?
Re-upload the recipe through the web frontend again to update it. Make sure the recipe file has the same name. Alternatively, you can just replace the file in the `recipes` directory. Recipes are always evaluated just in time. Nothing is cached or saved in some database.

## Not all my recipes are synced
Only recipes containing a full mashing program are synced. If you uploaded a recipe through the web frontend it will tell you whether it found a valid mashing program. You can also check the recipe library. Recipes without a valid schedule will have a highlighted exclamation mark (!) next to their name.
All recipes export from the www.picobrew.com should just work.

On a technial note: Your BeerXML file must contain a `<PROGRAM>`tag.`
```
<PROGRAM>
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
</PROGRAM>
```

## I have a BeerXML file from somewhere else than www.picobrew.com
You can manually update any BeerXML file to be PicoBrew Server compatible by adding the mashing schedule with a text editor. Add a <PROGRAM>` tag - as described above - to the recipe.

## Where can I find a session log
Open **Brew history** in the web interface. It lists every brew and cleaning session; a running session is highlighted at the top. Each session page shows a temperature chart with the machine's steps, a step table, any reset reports, and a CSV download of every reading. While the machine is brewing, the page updates live.

Sessions are stored in one SQLite database, `sessions/brew_sessions.sqlite3`, inside the data directory (`--data-dir` or `PICOBREW_DATA_DIR`, by default the server's working directory). Device error/reset reports are stored in the same database without changing the recovery state of the brew log. Session logs and error reports written as JSON files by earlier versions are imported automatically on first start; the JSON files are left in place. Machine and indexed sensor registrations from `firstSetup` are stored in `machines`. Keep both directories with your data.

The machine logs its four temperature sensors about once a minute, as whole degrees Fahrenheit: channel 2 is the wort, 1 is heat 1, 3 is the control board and 4 is heat 2 (the backup heat sensor). The history pages show these values in °F as received.

## Which account do I select during machine setup?

The local server presents a single account named `PicoBrew Server`. It has a stable identifier and shares the uploaded recipe library across all connected machines. The server's firmware check reports no available update because it does not distribute application firmware images.
