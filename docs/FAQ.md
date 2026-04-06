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
So far session logs are stored in the `sessions` directory in the server root. An interactive graph in the web frontend end is planned for the future.