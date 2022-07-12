# Standard imports
import argparse
import json
from os import path
from shutil import copy
from sys import exit
import tempfile

# Third-party modules imports
from colorama import Fore, Style
from tqdm import tqdm, contrib
import translators as ts

### Utils functions ###
def iso_from_locale(locale: str):
  separator_index = -1
  if '-' in locale:
    separator_index = locale.index('-')
  elif '_' in locale:
    separator_index = locale.index('_')

  return locale[:separator_index] if separator_index != -1 else locale

def message(t: str, text: str):
  # Detect and select the appropriate prefix (info/error)
  prefix = f"{Fore.RED}[Error]{Style.RESET_ALL}" if t == "error" else f"{Fore.GREEN}[Info]{Style.RESET_ALL}"

  # Print the message
  print(f"{prefix} {text}")

def is_slice_in_list(slice, list):
  '''
  Check if a 'slice' array is contained in the array 'list'.
  
  Credits to: https://stackoverflow.com/a/20789669
  '''
  len_s = len(slice) #so we don't recompute length of s on every iteration
  return any(slice == list[i:len_s+i] for i in range(len(list) - len_s+1))

### Json/stream related functions ###
def find_couple_brackets_end(file, open_bracket='[', close_bracket=']', reset=True) -> int:
  '''
  Given a JSON file already open as a text, and positioned the cursor
  in the position of the opening bracket concerned, identifies the
  corresponding closing bracket.
  '''
  # Save the start position in the file
  start = file.tell()

  # We know that it ends with `close_bracket` so we move the cursor to the next position (+1)
  file.read(1)  # With text files we cannot use f.seek(1, 1)
  # and declare a variable (1 because an open bracket is what we skipped)
  brackets_open = 1
  # Now we iterate the file searching for '[' or ']' with the rule
  # - Found `open_bracket` -> brackets_open + 1
  # - Found `close_bracket` -> brackets_open - 1
  # Until square_bracket_open = 0
  while brackets_open != 0:
    char = file.read(1)
    if char == open_bracket: brackets_open += 1
    elif char == close_bracket: brackets_open -= 1

  # We have reached the end of the array!
  cursor_end_array = file.tell()

  # Return to the original position
  if reset:
    file.seek(start)

  # Return the position of the closing bracket
  return cursor_end_array

def stream_search(path: str, pattern: str, start = 0) -> int:
  # To be able to move to a file to taste it is necessary to read it through bytes,
  # since however there are different languages and codes, there is the risk of
  # reading a character in half. For example, if we read a file with Chinese characters:
  #
  # "game 素" = b'game \xe7\xb4\xa0'
  #
  # If we read 6 bytes we will get b'game \xe7 'in which the last character does not make sense.
  #
  # We must then translate what we read and which we compare in the same language,
  # or in the decimal representation of the bytes in UTF-8:
  #
  # 1. From string to bytes: str.encode("game 素") -> b'game \xe7\xb4\xa0'
  # 2. From bytes to decimal rapresentation: b'game \xe7\xb4\xa0' -> [103, 97, 109, 101, 32, 231, 180, 160]

  # Convert pattern from string to dec array
  DEC_ARRAY_PATTERN = [i for i in str.encode(pattern)]

  # Define constants and variables
  STREAM_LENGTH = len(DEC_ARRAY_PATTERN)
  stream: str = None

  # In order to use 'seek' we need to open the file as binary
  with open(path, 'rb') as f:
    # Find the end position
    f.seek(0, 2)
    end_position = f.tell()
    
    # Set the cursor to the starting position
    f.seek(start)

    # Cycle until we foud a match or the file end
    while f.tell() < end_position:
      # Load stream block and convert it to decimal array
      stream = [i for i in f.read(STREAM_LENGTH)]

      # Find all occourrences of pattern[0] in stream
      occourrences = [i for i, char in enumerate(stream) if char == DEC_ARRAY_PATTERN[0]]
      
      # Check, for all indices, if after the index there are others common letters (decimal bytes)
      for i in occourrences:
        # Extract the subset from the stream
        subset = stream[i:]
        
        # Nope, we didn't find what we were searching
        if not is_slice_in_list(subset, DEC_ARRAY_PATTERN): continue

        # We have found our string!
        if subset == DEC_ARRAY_PATTERN: return f.tell() - STREAM_LENGTH
        # We found a partial match:
        # Find in the file the position of the current index 'i'
        # Process again to find (potentially) the searched string
        else:
            index = f.tell() - len(subset)
            f.seek(index)
            break # Ignore other matches
    return -1

def optimize(project_json_path: str):
  with open(project_json_path, "r+", encoding='utf-8') as f:
    # Deserialize full JSON file
    data = json.load(f)

    # Return to the start
    f.seek(0)

    # Serialize JSON file without indent and separators
    json.dump(data, f, indent=None, separators=(',',':'))

    # Ignore excessive data
    f.truncate()

### Translation related functions ###
def extract_localization(project_json_path: str, file):
  # After making us sure that the file exists, we read it as a stream,
  # so as not to saturate the memory
  with open(project_json_path, "r", encoding='utf-8') as f:
    # Find the start of the "textList" array (opening bracket '[')
    textlist_index = stream_search(project_json_path, 'textList')
    textlist_index = stream_search(project_json_path, '[', textlist_index)

    # We need to find the end of the "textList" array
    f.seek(textlist_index)
    end_texlist_index = find_couple_brackets_end(f)
    
    # Extract that node in the passed file
    with open(file.name, 'w') as fw:
      data = f.read(end_texlist_index - textlist_index)
      js = json.loads(data)
      json.dump(js, fw)

def translate_block(block, index: int, lang_src: str, lang_dest: str, skip=False):
  '''
  Translate a JSON node (block).
  
  Since `block` is passed by reference, it is not necessary to return any results.
  '''
  # Find all the child nodes of the block
  for child in (pbar:=tqdm(block["children"])):
    pbar.set_description(f"Block {index}")
    
    # It can happen in certain cases that the `text` key is not present but 
    # a further list of children.
    # 
    # In this case, the recursive translation of the same is required.
    #
    # Usually, either there is the `text` key or the `children` key is present.
    if not "text" in child:
      if "children" in child: translate_block(child, 1, lang_src, lang_dest, skip)
      continue # Skip this node

    # Obtain the text from the desired locale, if the locale choosen
    # is not available, select the first locale in the list
    dictionary = dict(child["text"].items())
    
    # Avoid empty nodes
    if len(dictionary) == 0: continue
    
    # Skip if the desired language is already present
    if skip and lang_dest in dictionary: continue
    
    default_value = list(dictionary.values())[0]
    value = dictionary.get(lang_src, default_value)
    
    # The translation engine needs the ISO 639-1 code (two letters)
    # or "auto" for automatic language detection
    src = "auto" if lang_src == "auto" else iso_from_locale(lang_src)
    
    # Translate and add the new value to the dict
    # { 'en_US': 'Hello' } -> { 'en_US': 'Hello', 'it_IT': 'Ciao' }
    # Note: if lang_src == lang_dest, the value is overwritten.
    # This is useful when the value stored is not in the correct language
    # { 'en_US': 'Ciao' } -> { 'en_US': 'Hello' }
    try:
      translation = ts.google(value,
                              from_language=src,
                              to_language=iso_from_locale(lang_dest),
                              sleep_seconds=2)
      
      # Update translation in the stream
      child["text"][lang_dest] = translation
    except Exception as e:
      message("error", f"An exception has occurred:\n {e}")
      message("error", "The last translation was not carried out")

def translate_strings(file, lang_src: str, lang_dest: str, skip: bool):
  with open(file.name, "r+", encoding='utf-8') as f:
    # Load ALL the file into memory
    data = json.load(f)
      
    # These are "blocks" of string, usually the first 22 blocks
    # are strings regarding menus, save/load, etc.
    for i, block in contrib.tenumerate(data):
      if not "children" in block: continue # Skip node if no children are in the node
      translate_block(block, i + 1, lang_src, lang_dest, skip)
        
      # Return the cursor to the start of the file
      f.seek(0)
        
      # Save block after translation
      f.write(json.dumps(data))

def add_language_support(project_json_path: str, lang_dest: str):
  with open(project_json_path, "r+", encoding='utf-8') as f:
    # Find the node containing the language data (opening bracket '{')
    gi_index = stream_search(project_json_path, 'gameInformation')
    gi_index = stream_search(project_json_path, '{', gi_index)
    
    # Then we need the closing bracket
    f.seek(gi_index)
    end_gi_index = find_couple_brackets_end(f, open_bracket='{', close_bracket='}')
    
    # Return to `gi_index` and read `end_gi_index - gi_index` characters
    data = f.read(end_gi_index - gi_index)
    js = json.loads(data)

    if not lang_dest in js['language']:
      # Add the support for the translation language
      js['language'].append(lang_dest)
    
      # We need to replace the array but we risk to overwrite other data so we can
      # save the remaining json file, overwrite the data in 'project.json', then
      # append the previously saved data
      temp = tempfile.TemporaryFile(mode='r+', encoding='utf-8')
      temp.write(f.read()) # Read and write the remaining file
      temp.seek(0)

      # Memorize the new language
      f.seek(gi_index)
      f.write(json.dumps(js))
      
      # Now append the previously saved data
      while True:
        # Get next line from file
        line = temp.readline(2048)
    
        # if line is empty
        # end of file is reached
        if not line: break
        
        # Transfer line
        f.write(line)

def add_translation(project_json_path: str, file):
  with open(project_json_path, "r+", encoding='utf-8') as f:
    # Find the start of the "textList" array (opening bracket '[')
    textlist_index = stream_search(project_json_path, 'textList')
    textlist_index = stream_search(project_json_path, '[', textlist_index)

    # We need to find the end of the "textList" array
    # Mantain the position of the array end (reset=False)
    f.seek(textlist_index)
    find_couple_brackets_end(f, reset=False)

    # We need to replace the array with the translation array but we risk to overwrite other data
    # we can save the remaining json file, overwrite the data in 'project.json', append the 
    # previously saved data
    temp = tempfile.TemporaryFile(mode='r+', encoding='utf-8')
    temp.write(f.read()) # Read and write the remaining file
    temp.seek(0)

    # Load the translations
    with open(file.name, 'r', encoding='utf-8') as fo:
      translation_array = json.load(fo)

      # Return to the start of the "textList" array
      f.seek(textlist_index)

      # Write the translated strings
      f.write(json.dumps(translation_array))

    # Now append the previously saved data line by line
    while True:
      # Get next line from file
      line = temp.readline(2048)
  
      # if line is empty
      # end of file is reached
      if not line: break
      
      # Transfer line
      f.write(line)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='''Application for the localization of games developed with Pixel Game Maker.\n\n
                                  To use the program, specify the path of the 'Project.json' file or place this script in its own directory.\n\n
                                  By default the translation language is [Auto] -> [en_US], it is possible to specify the destination language''')
  
  parser.add_argument('-p', '--path', action="store", default=None, help="The path to the file containing the information about the game")
  
  parser.add_argument('-fl', '--from-lang', action="store", default="auto", help="Source language for the translation (Locale: en_US)")
  
  parser.add_argument('-tl', '--to-lang', action="store", default="en_US", help="Destination language for the translation (Locale: en_US)")
  
  parser.add_argument('-s', '--skip', action="store_true",
                      help="Specifies whether to skip the translation in the event that the specified language is already present (useful in case of partial localization)")
  
  parser.add_argument('-e', '--export-localization', action="store", default=None,
                      help="Path to which export localization strings, in the event that it is necessary to process them later and so as not to have to analyze 'Project.json' again")
  
  parser.add_argument('-i', '--import-localization', action="store", default=None, help="Path from which import the localization strings exported previously")
  
  parser.add_argument('-o', '--optimize', action="store_true", default=None,
                      help="Optimize the JSON file to reduce its size and processing time. Requires at least 1 GB of free RAM")
  
  args = vars(parser.parse_args())
  
  # Extract the path, else if no argument is specified, check
  # if the 'project.json' file is in the current directory
  cur_dir_path = path.dirname(path.realpath(__file__))
  project_json_path: str = args["path"] if args["path"] is not None else path.join(cur_dir_path, "project.json")

  message('info', f"Selected 'project.json' path: {project_json_path}")
  message('info', f"Translation: '{args['from_lang']}' -> '{args['to_lang']}'")

  # Check if the file exists on disk
  if not path.exists(project_json_path):
    message('error', "The specified path does not contain the requested file, check that the path is exact")
    exit(1)
    
  # Optimize JSON if required
  if args["optimize"]:
    message('info', 'Optimization of the JSON file, please wait...')
    optimize(project_json_path)
    message('info', 'Optimization done')

  # Create a temporary file where store the localization strings
  localization_file = tempfile.TemporaryFile(delete=False)
  # To avoid reading/writing a ENORMOUS json file, we extract the interested strings in a temporary file
  if args['import_localization'] is None:
    message('info', "Extracting localization strings, it may requires some time, please wait")
    extract_localization(project_json_path, localization_file)
    
    # If the user specified the '-e' option, save the data in the selected path
    if not args['export_localization'] is None and not path.exists(args['export_localization']):
      copy(localization_file.name, args['export_localization'])
      message('info', f"Strings extracted to {args['export_localization']}")

  # The import path does not exists
  elif not path.exists(args['import_localization']):
    message('error', "The import ('-i' argument) path does not exists, check that the path is exact")
    exit(1)
  # Read the data and save it in the temporary file
  else:
    message('info', f"Importing strings from {args['import_localization']}")
    copy(args["import_localization"], localization_file.name)

  message('info', f"Strings extracted to {localization_file.name}")

  # Now we can re-open the file and translate the strings inside
  message('info', "Translating strings, it may require some time, please wait")
  translate_strings(localization_file, args["from_lang"], args["to_lang"], args["skip"])
  message('info', "All strings translated")

  # If we not add the support for the language, we cannot use the localization in-game
  # so we add it and then we write the translated strings into the 'project.json' file
  message('info', "Saving 'project.json', it may require some time, please wait")
  add_language_support(project_json_path, args["to_lang"])
  add_translation(project_json_path, localization_file)
  message('info', "Operation completed, you can now close this window")