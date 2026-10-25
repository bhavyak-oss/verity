Verity

Run it as a real website (not a file:// address)
  Mac:      double-click start.command
            (if it does not open, use Terminal: cd into this folder and run  python3 server.py)
  Windows:  double-click start.bat
  Terminal: python3 server.py

The terminal then shows two addresses, for example:
  http://localhost:8000          on this computer
  http://192.168.1.23:8000       on phones and other devices on the same Wi-Fi
Open either one in a browser. Pages: / (home) and /app (the notes app).

Want no port number in the address (like http://192.168.1.23)?
  sudo python3 server.py 80

Your address is your computer's own network IP, so it will not be 192.168.4.1
unless your computer really has that IP. The terminal prints the right one.

Files (12 files in total)
  index.html      landing page          app.html       notes app
  css/style.css   notes app styles      css/site.css   landing page styles (incl. its motion layer)
  js/app.js       editor logic          js/words.js    English word list for autocorrect
                                        (from the open-source Hunspell en_US dictionary)
  js/keys.js      your Groq keys        server.py      the web server, YouTube helpers and price lookup
  requirements.txt, start.bat (Windows), start.command (Mac)
  The favicon is embedded in the two HTML pages (no assets folder).
  server.py has three sections: 1. YouTube helpers, 2. Price lookup, 3. Web server.

To put it on the public internet, upload the folder to a static host
(GitHub Pages, Netlify, Cloudflare Pages) or any web server.
Notes are saved in the visitor's browser, separately for each address
(localhost and the Wi-Fi IP keep separate notes).

Starred notes
  Press the star button in a note's toolbar (or use the three-dot menu in the note list > Star). Starred notes show a
  gold star in the list and on the home screen, and appear under "Starred" in the sidebar. You can also drag a note
  onto "Starred". Starring does not change the note's "last edited" time.

Recycle bin
  Deleting a note (Delete note, or the three-dot menu > Move to Recycle bin, or dragging it onto "Recycle bin") moves it
  to the Recycle bin instead of erasing it. A toast offers Undo for a few seconds.
  Open "Recycle bin" in the sidebar, tap a note, then choose Restore or Delete forever. "Empty bin" removes everything.
  Notes are removed for good after 30 days (TRASH_DAYS in js/app.js). A restored note goes back to its folder (or to
  Unfiled if that folder was deleted). Photos, audio and files of binned notes are kept until the note is removed for good.

Share a note
  Press Share in the toolbar (or three-dot menu > Share). You get:
    Save as PDF    (main option) opens the browser's print window with the note laid out for paper; choose
                   "Save as PDF" there and send the file. Works offline.
    Copy link      a link that contains the note itself (compressed, after #share=). Nothing is uploaded and no server
                   is needed. Whoever opens it sees a read-only copy and can press "Save a copy to my notes".
    Share...       the phone/computer share sheet (only shown where the browser supports it).
    Copy text      the note as plain text.
    Download .html a single self-contained web page of the note, to send as a file.
  The link is a snapshot: later edits are not sent, share again to send a new version. Photos, audio, video and files
  are NOT included (they live only in your browser); YouTube cards become links. Very long notes may be too big for
  a link; use Download or Copy text for those.
  The link uses the address you opened Verity with. On http://localhost it only works on your own computer, so open
  Verity through the Wi-Fi address printed by server.py (or host it on a website) before sharing with other people.
  Security: a received link is rebuilt from an allow-list of simple formatting (headings, lists, bold, links, etc.),
  so scripts, images and styles inside a link are dropped.

AI typing assistance and writing tools (Groq)
  Keys and model: open js/keys.js and list your Groq keys (from https://console.groq.com/keys) in the VERITY_KEYS array.
  Nothing is asked for on the website. The model is always openai/gpt-oss-120b. Verity tries the keys in order; if one
  says rate limit / limit exceeded / quota, that key rests for a minute (or as long as Groq asks) and the next key is
  used automatically. Only keep keys in that file on your own computer or private network: anyone who can open the
  site can read it. "AI settings" (the gear icon) only has the on/off switch and a "Test connection" button.
  5. Typing assistance works without a key and needs no setup:
     - Autocorrect: when you finish a word (space or punctuation) and it is not a real word,
       Verity swaps in the closest match (keyboard-aware, e.g. teh -> the, recieve -> receive).
       Press Backspace right away to restore what you typed (that word is then left alone from now on),
       or use Ctrl/Cmd+Z. Names, ALL-CAPS, camelCase, URLs and words you use twice in your notes are left alone.
     - Prediction: as you type, the rest of the word appears as grey text at the cursor. Press Tab to fill it,
       Escape to hide it. If the half-typed word is already misspelled it shows "-> closest word"; Tab swaps it in.
  6. With a key in js/keys.js, the model can also refine the grey suggestion using the surrounding sentence.
  7. Select text in the editor (optional), then use Fix text, Improve, or Summarize.

Translate selected text
  Select any text in a note (even one word). A "Translate" button appears above the selection. Press it, pick the
  language in the box that opens (Hindi, Hinglish, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Punjabi,
  Kannada, Malayalam, Urdu, Spanish, French, German, Portuguese, Italian, Russian, Arabic, Chinese, Japanese,
  Korean) and press Translate (or Enter). The selected text is replaced by its translation. Press Undo in the toast
  within a few seconds to get the original back, or use Ctrl/Cmd+Z. The source language is detected automatically,
  and your last language choice is remembered. Hinglish = Hindi written in Roman letters.
  Uses your Groq keys from js/keys.js (same as the other AI tools), up to 12,000 characters at a time.
  It is hidden when AI features are switched off in AI settings.

Fact check (YouTube link, written text, or text highlighted in a note)
  One tool, three ways in. All of them open the same Fact check panel:
    1. YouTube link       the Fact check button, or the Fact check button on a YouTube card in a note.
                          Paste a link in the "YouTube link" tab and Verity checks what is said in the video.
    2. Write or paste     the Fact check button > "Write or paste text" tab. Type or paste up to 30,000 characters.
    3. Highlight in notes Select a sentence or more (20+ characters) in any note and press the "Fact check"
                          button that appears above the selection (or use the Fact check button).
  The panel lists each factual claim with a True / False / Subjective verdict, plus a short summary and counts.
  "Add to note" lets you tick what to add (heading, summary, true / subjective / false claims) and whether it goes
  directly under the video / highlighted passage or into a new note. "New check" starts another one.
  Uses your keys from js/keys.js. Text checks work from any way of hosting Verity; they need no Python server.
  YouTube extras (YouTube cards only): "Check title relevance" and "Overview & transcript" (full transcript with
  timestamps, can be added to a note). Results are cached in the browser, so reopening something costs nothing.
  Setup for YouTube videos (once, on the computer that runs server.py):
    pip install -r requirements.txt            (installs youtube-transcript-api)
    optional: pip install sentence-transformers   for embedding-based relevance. Without it, relevance is judged
              by the Groq model.
  Videos need the python3 server.py way of running Verity: browsers cannot fetch YouTube transcripts themselves.
  The model is openai/gpt-oss-120b. Fact checks are AI-generated
  and the model has no live web access: verify anything important.
  Long inputs are checked in 2,000-word parts with a 45 second pause between parts to respect Groq's rate limits,
  so a 1-hour video takes a few minutes. Short text finishes in seconds.

Dictation (the Dictate button in the note toolbar)
  Press Dictate, speak, and Verity types what you say into the note at the cursor. Press Stop (on the button or in the
  red bar at the bottom) when you are done. Choose the language you will speak in from the box next to the button:
  English (India), Hindi, Hinglish or Tamil.
  Hinglish = Hindi + English mixed, written in Roman letters ("mujhe kal office jaana hai"). Browsers have no Hinglish
  recogniser, so Verity listens in Hindi and converts the result to Roman letters itself. Spellings are a best guess
  (Hinglish has no fixed spelling), so give the text a quick read. Voice punctuation commands are English only. Your choice is remembered. Changing it while dictating restarts in the new language.
  English only: say "full stop", "comma", "question mark", "new line" or "new paragraph" to type punctuation / a line break.
  Needs Chrome, Edge or Safari (Firefox has no speech recognition), an internet connection (the browser sends audio to its
  speech service) and microphone permission. It works on https sites and on http://localhost, but a plain http://192.168...
  address will be blocked by the browser. Dictation stops by itself if you open another note or leave the editor.

Sourcing advisor (the Sourcing advisor button)
  Type a product (for example "smart watch") and how many units you will build. The AI lists the parts needed to
  build one unit, then the Verity server looks up REAL store listings for every part and shows up to 4 sellers per
  part (in stock first, then lowest price) with live price, stock, listing title and a direct buy link, plus the
  cost per unit and for your whole batch. Nothing is simulated: a part with no live listing is shown as an
  "AI estimate" and links to the stores' search pages so you can check it yourself.
  Where the prices come from (the price lookup section of server.py, standard library only):
    1. Free public storefront APIs of Robu.in, Robocraze, ThinkRobotics, Quartz Components and Probots (no key).
    2. Google Shopping India if you set SERPER_API_KEY (environment variable) before starting the server.
    3. Otherwise, if a Groq key is available (GROQ_API_KEY in the environment, or the keys in js/keys.js) and a
       part still has fewer than 3 sellers, Groq's web-search model (groq/compound-mini) reads live store pages.
  Needs python3 server.py (the browser cannot read store prices itself). If the server cannot be reached the
  panel still lists the parts with AI estimates and store search links, and says why.
  Test which stores answer from your network:  http://localhost:8000/api/storetest?q=arduino uno
  Each part shows its cost and share of the total; "Compare all sellers" shows every seller with price, cost for
  the quantity and stock. Prices change often: open the listing and confirm before you buy.
  Keep the plan:
    CSV: best picks   one row per part (spec, qty, best seller + link, stock, price, price type, line cost, batch
                      cost, share of total, why) with totals at the bottom.
    CSV: all quotes   one row per part per seller. Both open in Excel, Google Sheets and Numbers.
    Add to note       choose Summary (short list), Table (one row per part), or Table + all quotes (adds a
                      seller comparison for every part), then "Add to this note" or "Save as new note".
                      "+ Add this part to my note" under any part adds just that part with its seller table.
  Part lists come from the AI (keys from js/keys.js); the store prices come from the server.

Home: knowledge map (click the Verity logo, or open Verity; it is the first screen)
  Every folder and note is drawn as a map: "All notes" in the middle, folders around it, notes around their folder.
    Click a note       opens it straight away.
    Click a folder     folds or unfolds its notes.
    Drag anything      to move it; a folder takes its notes with it. Positions are remembered in this browser.
    Drag a note onto a folder   files it there (same as moving it in the sidebar); drop on Unfiled to un-file it.
    Drag the background to pan; Ctrl/Cmd + scroll (or pinch) or the + / - buttons to zoom; Fit re-centres;
    Reset puts everything back in its default place; Full screen gives the map the whole window (Esc exits).
    "Find on the map" dims everything except matching notes and their folders.
  Keyboard: Tab to a note or folder, then Enter.

How people find the AI tools (no hunting through menus)
  - Home screen: Fact check and Sourcing advisor cards with one-click examples.
  - AI tools sit directly in the toolbar (Fact check, Sourcing advisor), with a "New" tag on Sourcing advisor until first used.
  - Type "/" anywhere in a note: a menu of every AI tool appears (keep typing to filter, arrows + Enter to pick).
  - Smart nudges: after you pause typing, a small suggestion may appear, e.g. "Planning to build something?" ->
    Sourcing advisor, a YouTube card -> Fact check, a note with statistics -> Fact check, a long note -> Summarize.
    Each nudge shows once per note, at most one every 90 seconds, hides itself after 16 seconds, and never appears
    when AI features are turned off.
  - Highlight text: the Fact check button appears above the selection.

Study: quiz and flashcards (the Study button in the toolbar)
  Choose what to study at the top of the panel: This note, Pick notes (tick any notes), or Folders (tick one or more
  folders; Unfiled counts as a folder). Several notes or folders become one combined deck with questions spread across
  all of them; "Add more cards" re-reads the folders, so notes added later are included. Each deck keeps its own
  schedule and shows under "Your other decks".
  One AI call turns a note (or just the text you highlighted) into a study set of questions, each with the
  right answer, three believable wrong answers and a one-line explanation. The same cards give you two ways to practise:
    Flashcards  Tap to flip, then say "Missed it" or "Got it" (keys: Space, 1, 2). Spaced repetition: missed cards come back
                in minutes; cards you know come back after 1, 3, 7 and 16 days. Only cards that are due are shown.
    Quiz        Up to 10 multiple-choice questions with instant feedback and explanations. Wrong answers go straight back
                into your flashcards, so a quiz also teaches the deck.
  Where you will see it: a red number on the Study button and a card on the home screen show how many cards are due
  today across all notes ("Review now" starts a mixed session). Highlight text in a note and tap "Flashcards" to add
  3 cards without leaving the page. "Add more cards" extends a deck without repeating questions. Type / and choose
  Quiz & flashcards, or tap the nudge that appears on longer notes.
  Cards are stored in this browser only (key verity-study). Reviewing works even with AI turned off; making cards needs
  your keys in js/keys.js. Questions are AI-written from your note, so skim them for mistakes.

Themes
  Click the half-moon icon at the top of the sidebar to pick one of five themes:
  Daylight (bright), Midnight (dark), Paper (warm sepia), Forest (deep green) and Sunset (plum and coral).
  Your choice is remembered in this browser. Until you pick one, Verity follows your device's light or dark setting.
  Animations respect the "reduce motion" setting of your device.

Knowledge map (Home screen)
  Your folders and notes as a map you can pan (drag the background), zoom (+ / - or Ctrl + scroll) and rearrange.
  Folders
    - Click a folder to MINIMISE it into a stacked bubble (hover it to peek at what is inside); click again to unfold.
    - Press the round arrow on a folder to MAXIMISE it into a board: every note in it opens as a readable card laid out
      in a grid, and the camera flies to it. Press the arrow again to go back to the map.
    - "Fold all" / "Unfold all" does every folder at once.
  Notes (shown on the map itself, no need to leave it)
    - Click a note label to expand it into a card with its formatted text, star button, age and word count.
      Scroll inside the card to read more. Press "-" on the card to shrink it back.
    - Double-click a note (or press "Open") to edit it in the editor.
    - Drag a note onto a folder, or anywhere on a maximised board, to file it there.
    - Overlapping items glide apart automatically. "Tidy" does it for the whole map.
  Connections
    - "Links" draws dashed lines between notes that share distinctive ideas or mention each other's titles.
      Hover a note to light up what it is connected to; cards list related notes, and clicking one flies you to it.
  Search
    - Type in "Find on the map" to dim everything else, then press Enter to fly to the first match.
  Zoomed far out, note labels shrink into coloured dots so even a large map stays readable.
  Layout, folded folders, open cards and the Links setting are remembered in this browser.

Photos, audio, video and YouTube
  Use the Media menu in the toolbar (or paste an image, or drag files into the note).
  Files are stored in this browser (IndexedDB), not uploaded anywhere, so they stay on this device and address.
  Paste a YouTube link, or use Media > YouTube link: Verity recognises it, shows a card with the video's
  title (fetched from YouTube's oEmbed service, needs internet) and plays it in place when you click it.

AI privacy and security
  Keys live in js/keys.js, not in the browser. The selected text or note content
  is sent to Groq when you use an AI action. Do not put real keys in js/keys.js for
  a public/shared deployment or on a device other people can access. For those cases, use
  a private backend proxy that stores the key outside the browser.

Landing page (index.html)
  The three AI tools (Fact check, Sourcing advisor, Study) are in the very first screen under the headline, as large
  cards, so visitors see them without scrolling. Each whole card is a link that opens the tool in the app.
  The editor preview moved just below. On phones the cards become compact and all three still fit on screen.

Sidebar
  The notes sidebar can be hidden to give you the whole screen: press the panel icon at the top of the sidebar, or
  Ctrl+\ (Cmd+\ on Mac). A small button at the top-left brings it back. Verity remembers your choice. On phones the
  notes list is already its own screen, so the button is not shown there.

Turn text into notes
  This is now a quiet row below the three AI tools on the home screen. Tap it (or "AI notes" in the sidebar, or
  app.html#ai) to open the paste box. It is closed by default so Fact check, Sourcing advisor and Study stay in front.

Dashboard (the home screen) and landing page (index.html)
  Command bar     One box on the home screen. Paste a YouTube link or a claim (Fact check), name a product
                  (Sourcing advisor), or type "study Biology" / a note title (Study). The three chips under it show what
                  Verity will do; Enter runs the highlighted one. Long pasted text can also be saved as a note and studied.
  Live tool cards Fact check shows your last result (true / false / opinion bar) with "Reopen this result";
                  Sourcing shows your last plan and its biggest costs with "Reopen this plan"; Study shows a mastery ring,
                  your day streak, a 14-day activity strip and "Up next". Numbers at the top: notes, cards due, claims checked, streak.
                  These are remembered in this browser (verity-fc-hist, verity-src-hist, verity-study-log).
  Note actions    Under "Pick up where you left off", each note has one-tap buttons: fact check it, find parts for
                  its title, or make flashcards from it.
  Sidebar         Check / Source / Study shortcuts under New note, with the due-cards badge.
  index.html      Landing page with an auto-playing demo of the command bar and working mini-demos of all three tools.

Assistant (v33): talk to your notes (Groq)
  Open it with the "Assistant" button (bottom right), Ctrl/Cmd+J, or just type a command in the dashboard box, for
  example "rename my Biology note to Cell Biology", "add a note called Weekly plan", "delete my empty notes",
  "move my unfiled notes into folders", "fix typos in this note". Commands that name notes/folders open the
  Assistant automatically (the highlighted "Do it with the assistant" chip); everything else routes as before.
  What it can do (Groq function calling, model openai/gpt-oss-120b, same keys as the rest of Verity):
    notes     list / search, read, create, append, insert after a heading or paragraph, find & replace, delete a
              line, rewrite, rename, duplicate, move to a folder, star / unstar, delete (to the Recycle bin),
              restore, open
    folders   create, rename, delete (notes are kept and become Unfiled)
    tools     start Fact check, Sourcing advisor and Study (flashcards / quiz) for a note, folder or topic
  Safety: deleting only moves notes to the Recycle bin (never permanent, and "empty bin" is not available to the
  AI). Each request that changes something gets an "Undo these changes" button. A rewrite is refused on notes that
  contain photos, audio, video or files (it would lose them); the AI uses small edits there instead. For large
  deletions it is told to list what it will touch and ask first. It sees the note you have open ("this note").
  The conversation is kept only in the open page (not saved). Notes you ask about are sent to Groq like other AI actions.
  Code: search for "Verity Assistant" in js/app.js (ASST_TOOLS lists the tools, ASST_EXEC runs them).

Sources for each claim (Fact check)
  After the claims are checked, Verity looks up sources for every true / false claim (subjective ones are skipped) with
  a live web search: Groq Compound (groq/compound-mini, then groq/compound), and if your key cannot use those, gpt-oss-120b with Groq browser search (SRC_MODELS in js/app.js). Each claim shows up to
  3 links, tagged supports / contradicts / related. Only links the search really returned are kept, so the AI cannot make
  up a URL; if nothing was found the claim says "No sources found". Up to 24 claims are looked up per check (SRC_MAX).
  "Find sources for N claims" retries the ones that are missing. "Add to note" includes the source links.
  Needs a Groq key that can use the Compound models; if it cannot, the claims still appear and you get a message.
  The verdicts themselves are still the model's judgement and are not changed by the sources: open them to confirm.

Home screen AI cards (v35)
  Click anywhere on the Fact check, Sourcing advisor or Study block to open that tool. The buttons, the product box and the
  example chips inside a card still do their own thing, and you can still select text in a card without opening it.
  The round arrow at the top right of each card does the same and works with the keyboard (Tab, Enter).

Folders: minimise and maximise (v36)
  Click "FOLDERS" (the arrow beside it) in the sidebar to minimise the whole folder list; click again to maximise it.
  While it is minimised a one-line bar shows the folder you are in (click it to open the list). The choice is remembered
  in this browser. Dragging a note automatically opens the list so you can drop it on a folder.

Lower Groq token use (v37)
Autocomplete asks the AI only from 3 letters, waits 800 ms, sends less text and uses low reasoning.
The command bar sends only your 60 newest note titles and waits 1.2 s. The assistant uses low reasoning,
at most 6 steps and shorter history. Run verityUsage() in the browser console to see tokens used per model.


AI USAGE LIMITS (v82)
---------------------
Open AI settings: pick a usage limit (Strict / Moderate / Relaxed / No limit) and switch single AI features on or off.
Moderate = 15 requests per minute, 300 requests and about 250k tokens per day. Automatic features (inline word
suggestions, Lens routing) are OFF by default and have a tighter cap. "Reset today" clears the counter.
Server side (price search): VERITY_GROQ_HOURLY=40 caps Groq web-search calls per hour, VERITY_WEB_PARTS=6 limits how
many parts per list may use it, VERITY_GROQ_WEB=0 turns it off completely.
