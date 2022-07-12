<!--
 Copyright (c) 2022 MillenniumEarl
 
 This software is released under the MIT License.
 https://opensource.org/licenses/MIT
-->

# Pixel Game Maker Translator

This script deals with translating and optimizing the data, contained in the `project.json` file, of a game developed with [Pixel Game Maker MV](https://tkool.jp/act/en/index.html).

To function correctly, the file must be legible, that is, that it is decrypt. For this, please refer to the following link on [F95Zone](https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwjj3Myr1vP4AhVFXvEDHcmODIcQFnoECBoQAQ&url=https%3A%2F%2Ff95zone.to%2Fthreads%2Fpixel-game-maker-mv-extractor.105950%2F&usg=AOvVaw3bguItkoSn-u3_3s_LLRrK) (courtesy of @xj47).

The script is completely automatic but it is still possible to extract the location strings for manual modification.

## Quick-start

This script uses [Python 3.x](https://www.python.org/downloads/) and modules in the requirements.txt file. These modules can be installed with the command `pip install -r path/on/disk/to/requirements.txt`.

Place the script in the same directory of the (decrypted) `project.json` and run it.

**Warning**: This script overwrites the file, so make sure to create a backup copy!

## Command-line Arguments

It is possible to have information on the various argoments using the command `python PGMTranslator.py -h`

| Argument  |     Type      |  Description |
|-----------|---------------|--------------|
|    `-p`     |    `string`     | Path to the `project.json` file. If not specified, the file is sought in the current folder  |
|    `-fl`    | `string/locale` | Code of strings from which to translate (eg zh_CN). Default is `auto`, it automatically select the first available language |
|    `-tl`    | `string/locale` | Code of strings to translate (eg en_US)  |
|    `-s`     |    `boolean`    | Avoid the translation of a string that has already been translated for the language specified in `-tl` |
|    `-e`    |    `string`     | Export the part of JSON files containing the strings to be localized in the specified path. Useful for manually changing the strings|
|    `-i`     |    `string`     | Import the part of JSON containing the localized strings (previously exported with the parameter `-e`)| from the specified path
|    `-o`     |    `boolean`    | Optimize the JSON file by removing indections and spaces, reducing its size and speeding up subsequent operations. It can take many minutes and at least 1 GB of free RAM |
