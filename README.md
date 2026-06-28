i use Google Sheets to order groceries. i enter the quantity next to an item and sort the list and this is sent to the WhatsApp chat of the delivery contact.

the problem: since i'm on my laptop and unless WhatsApp web is already logged in, the next easiest method is to copy it onto a Google Keep note and access it from my phone. however, Google Keep handles the tabs that come automatically from Google Sheets very poorly – the whole list becomes a mess of lines and is unreadable.

naturally, i decided to vibe code a python program to fix the formatting so i don't have to wait 30 seconds for WhatsApp web to load. i only need to Ctrl+C Ctrl+V (technically Cmd+C Cmd+V) into the program, and the formatted list will automatically copy to my clipboard.

if anyone else needs to use this, what you need is a grocery list in this format:
````
   		Date:	:	<date>
		*Address*		: <address>
		<any extra delivery notes>	
		
				
```				
1	|	<item>	-	<quantity>	#
2	|	<item>	-	<quantity>	#
3	|	<item>	-	<quantity>	#
4	|	<item>	-	<quantity>	#
```
````
which will be formatted into:
````
Date: <date>
*Address*: : <address>
<any extra delivery notes>

```
1 | <item> - <quantity> #
2 | <item> - <quantity> #
3 | <item> - <quantity> #
4 | <item> - <quantity> #
```
````

i've tested this on my Mac and it should work on other OS. optionally, you can install `pyperclip` for automatically getting the formatted list onto your clipboard.

## how to use it:

### setup (one-time)

````
  pip install pyperclip
````

1. run the script:
````
   python3 fix_grocery_list.py
````
2. copy your list from Google Sheets (or a messy Keep version, or even an already-formatted list)
3. paste it into the terminal
4. type `END` or `end` on its own line and press Enter
5. the cleaned list is printed in the terminal **and** copied to your clipboard automatically. now you just need to paste it into Keep, WhatsApp, or wherever you need

## expected input format

for the header to be cleaned properly, one of these general formats should be followed 
1. directly from Google Sheets (same as in the intro section):
````
   		Date:	:	<date>
		*Address*		: <address>
		<any extra delivery notes>	
		
				
```				
1	|	<item>	-	<quantity>	#
2	|	<item>	-	<quantity>	#
3	|	<item>	-	<quantity>	#
4	|	<item>	-	<quantity>	#
5 | #
```
````

2. mangled text from somewhere:
````
Date:
:
<date>
*Address*
:
<address>

<any extra delivery notes>


```


1
|
<item>
-
<quantity>
#
2
|
<item>
-
<quantity>
#
3
|
```
````

3. actually formatted list that you accidentally inputted again:
````
Date: <date>
*Address*: : <address>
<any extra delivery notes>

```
1 | <item> - <quantity> #
2 | <item> - <quantity> #
3 | <item> - <quantity> #
4 | <item> - <quantity> #
```
````
the number of items can be whatever you like. if any extra row(s) of item(s) are there, the script will automatically drop them from the final list.

## notes

- this was built for my own use, so it assumes the `Slno | item - quantity #` item format and a `Date` / `*Address*` header. if you want to use this and your sheet uses a different layout, the parsing logic will need adjusting
- if clipboard copying ever fails (e.g. missing `pyperclip`), the script still prints the cleaned output in the terminal so you can copy it manually from that

that's it. thanks for reading.
