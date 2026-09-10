-- In-game labels follow UCP's game-language provider, never the launcher locale.
local M={}
local de={
 ['Statistics']='Statistik',
 ['Replay statistics are unavailable.']='Keine Statistik für diese Aufnahme verfügbar.',
 ['F3: replay information']='F3: Replay-Informationen',
 ['UCP framework: %s']='UCP-Framework: %s', ['Active packs:']='Aktive Pakete:',
 ['%d exact extension versions verified']='%d genaue Erweiterungsversionen geprüft',
 ['Watch replay']='Replay ansehen',
 ['Replay unavailable']='Replay nicht verfügbar',
 ['Restart mission']='Mission neu starten',
 ['Checks matching']='Prüfwerte stimmen überein',
 ['Replay: %d / %d ticks']='Wiedergabe: %d / %d Ticks',
 ['Playback failed.']='Wiedergabe fehlgeschlagen.',
 ['Checking replay data...']='Aufnahme wird geprüft...',
 ['Checking recorded settings...']='Aufgezeichnete Einstellungen werden geprüft...',
 ['Checking starting state...']='Startzustand wird geprüft...',
 ['Replay preparation cancelled.']='Vorbereitung abgebrochen.',
 ['Automatic recording: on']='Automatische Aufnahme: ein',
 ['Automatic recording: off']='Automatische Aufnahme: aus',
 ['Pause replay']='Wiedergabe pausieren', ['Resume replay']='Wiedergabe fortsetzen',
 ['Return to replay']='Zur Wiedergabe', ['Speed: %d']='Tempo: %d',
 ['View player %d...']='Spieler %d ansehen...',
 ['Saved on this PC. Open Replays in single-player after the match.']='Auf diesem PC gespeichert. Danach Replays im Einzelspieler öffnen.',
 ['Open Replays in single-player to watch this match.']='Zum Ansehen Replays im Einzelspieler öffnen.',
 ['Recordings are saved separately on each PC.']='Jeder PC speichert seine eigene Aufnahme.',
 ['Playback ended before an unavailable recovery segment.']='Wiedergabe vor einem fehlenden Wiederherstellungsabschnitt beendet.',
 ['Required UCP framework: %s']='Benötigtes UCP-Framework: %s',
 ['Missing or unreadable: %s %s']='Fehlt oder ist nicht lesbar: %s %s',
 ['The recorded UCP framework is required.']='Das UCP-Framework der Aufnahme wird benötigt.',
 ['Required: %s %s']='Benötigt: %s %s',
 [' (+%d more)']=' (+%d weitere)',
 ['Install these exact versions using the UCP launcher or their original releases.']='Diese genauen Versionen über den UCP-Launcher oder ihre ursprünglichen Releases installieren.',
 ['If a required version is no longer available, this replay cannot be played here. Newer versions are not substituted.']='Ist eine benötigte Version nicht mehr verfügbar, kann diese Aufnahme hier nicht abgespielt werden. Neuere Versionen werden nicht als Ersatz verwendet.',
 ['Your normal settings have not been changed.']='Die normalen Einstellungen wurden nicht verändert.',
 ['Save capture as...']='Mitschnitt benennen',
 ['Named copy saved: %s']='Benannter Zwischenstand gespeichert: %s',
 ['Capture stopped: %s']='Mitschnitt abgebrochen: %s',
 ['Existing capture files are preserved.']='Vorhandene Aufzeichnungsdateien bleiben erhalten.',
 ['Start state unavailable; see capture.json for details.']='Startzustand fehlt; Details stehen in capture.json.',
 ['Multiplayer capture: tick %d; %d commands']='Mehrspieler-Mitschnitt: Tick %d; %d Befehle',
 ['Automatic capture continues until you leave the match.']='Der Mitschnitt läuft bis zum Verlassen des Spiels weiter.',
 ['Saved on this PC. Offline playback is not available yet.']='Auf diesem PC gespeichert. Offline-Wiedergabe fehlt noch.',
 ['Multiplayer capture saved: %s']='Mehrspieler-Mitschnitt gespeichert: %s',
 ['Waiting for the multiplayer match.']='Warte auf den Beginn der Mehrspieler-Partie.',
 ['Replays']='Replays', ['Recorded Skirmishes']='Aufgezeichnete Gefechte',
 ['Auto: on']='Auto: ein', ['Auto: off']='Auto: aus',
 ['Play']='Abspielen', ['Back']='Zurück', ['Close']='Schließen', ['Cancel']='Abbrechen',
 ['Save name']='Speichern', ['Save replay']='Replay speichern',
 ['Rename replay...']='Umbenennen', ['Remove']='Entfernen', ['Remove replay?']='Aufnahme entfernen?',
 ['Remove this recording from the library?']='Diese Aufnahme aus der Liste entfernen?',
 ['The files are kept in ucp/replays/removed.']='Die Dateien bleiben unter ucp/replays/removed erhalten.',
 ['Replay removed.']='Aufnahme entfernt.', ['Replay name saved.']='Name gespeichert.',
 ['Saved: %s']='Gespeichert: %s', ['%d recordings']='%d Aufnahmen',
 ['%s  |  %d ticks  |  %s']='%s  |  %d Ticks  |  %s',
 ['Full match']='Ganzes Spiel', ['Snapshot']='Zwischenstand', ['Failed']='Fehlgeschlagen',
 ['Incomplete']='Unvollständig', ['Recording']='Aufnahme läuft',
 ['Choose a recording.']='Aufnahme auswählen.',
 ['Choose a completed recording']='Eine vollständige Aufnahme auswählen',
 ['New Skirmishes are recorded automatically when enabled.']='Bei Auto: ein werden neue Gefechte automatisch aufgezeichnet.',
 ['Ready to play with your current settings.']='Mit den aktuellen Einstellungen abspielbar.',
 ['Install the recorded extension and framework versions to play.']='Zum Abspielen die aufgezeichneten Erweiterungsversionen installieren.',
 ['Play will queue a restart with the recorded settings.']='Abspielen bereitet einen Neustart mit den gespeicherten Einstellungen vor.',
 ['Restart queued. Exit the game to reopen with recorded settings.']='Neustart vorbereitet. Das Spiel beenden, um die Einstellungen zu laden.',
 ['Enter: play   F2: rename   Delete: remove']='Enter: abspielen   F2: umbenennen   Entf: entfernen',
 ['Replay controls']='Wiedergabe', ['Replay status']='Aufnahmestatus',
 ['Replay failed - details']='Aufnahmefehler', ['View player']='Spieler ansehen',
 ['Player %d']='Spieler %d', ['Viewing: player %d']='Ansicht: Spieler %d',
 ['Recorded player']='Aufgezeichneter Spieler', ['View']='Ansehen',
 ['Select a player to inspect their reports.']='Spieler auswählen, um dessen Berichte anzusehen.',
 ['Viewing does not change recorded actions.']='Die Ansicht verändert keine aufgezeichneten Aktionen.',
 ['Playback finished.']='Wiedergabe abgeschlossen.', ['Playback paused.']='Wiedergabe pausiert.',
 ['Playback running.']='Wiedergabe läuft.',
 ['%d / %d ticks; %d / %d commands']='%d / %d Ticks; %d / %d Befehle',
 ['Playback failed. Leave the mission to return to the library.']='Wiedergabe fehlgeschlagen. Mission beenden, um zur Liste zurückzukehren.',
 ['Recording stopped. This match is no longer being recorded.']='Aufnahme abgebrochen. Dieses Spiel wird nicht mehr aufgezeichnet.',
 ['Resume the game to continue playing normally.']='Spiel fortsetzen, um normal weiterzuspielen.',
 ['Automatic recording continues until you leave the match.']='Die Aufnahme läuft bis zum Verlassen des Spiels weiter.',
 ['Multiplayer replay recording is not available.']='Mehrspieler-Wiederholungen sind noch nicht verfügbar.',
 ['Test capture is disabled for this launch.']='Die Testaufzeichnung ist für diesen Start deaktiviert.',
 ['Test capture stopped: %s']='Testaufzeichnung abgebrochen: %s',
 ['Multiplayer replay playback is not available.']='Mehrspieler-Wiedergabe ist noch nicht verfügbar.',
 ['match exit']='Spielende',
 ['Test capture active: tick %d / %s']='Testaufzeichnung läuft: Tick %d / %s',
 ['%d commands; %d uncovered network events.']='%d Befehle; %d nicht abgedeckte Netzwerkereignisse.',
 ['Saved automatically. This is not a playable replay.']='Automatisch gespeichert. Noch keine abspielbare Aufnahme.',
 ['Test capture saved at tick %s.']='Testaufzeichnung bei Tick %s gespeichert.',
 ['Incomplete test capture saved at tick %s.']='Unvollständige Testaufzeichnung bei Tick %s gespeichert.',
 ['Capture ended; further actions are not being saved.']='Aufzeichnung beendet; weitere Aktionen werden nicht gespeichert.',
 ['This is not a playable multiplayer replay.']='Diese Mehrspieler-Aufnahme ist noch nicht abspielbar.',
 ['Waiting for multiplayer test capture at tick %d.']='Warte auf Testaufzeichnung ab Tick %d.',
 ['Waiting for multiplayer test capture.']='Warte auf Mehrspieler-Testaufzeichnung.',
 ['Replay %s. Leave the mission to return to the library.']='Aufnahmestatus: %s. Mission beenden, um zur Liste zurückzukehren.',
 ['Selected: %s']='Ausgewählt: %s', ['Page %d / %d']='Seite %d / %d',
}
local aliases={english='en',american='en',german='de',french='fr',russian='ru',
 hungarian='hu',turkish='tr',chinese='zh',spanish='es',persian='fa',farsi='fa',italian='it',polish='pl',ch='zh'}
M.supported={'en','de','fr','ru','hu','tr','zh','es','fa','it','pl'}
local supported={}; for _,language in ipairs(M.supported) do supported[language]=true end
local function normalize(value)
 if type(value)~='string' then return end
 value=value:lower():gsub('_','-'):match('^%s*(.-)%s*$')
 local language=aliases[value] or value:match('^([a-z]+)%-') or value
 language=aliases[language] or language
 return supported[language] and language or nil
end
local contextReader
-- The renderer supplies the loaded TextManager, not an executable-language
-- guess. Before CR.TEX loads, the game provider may legitimately return nil.
function M.bind(readContext) contextReader=readContext end
function M.context()
 local provider=(rawget(_G,'data') or {}).version
 if type(provider)~='table' or type(provider.getGameLanguage)~='function' then provider=rawget(_G,'version') end
 local language
 if type(provider)=='table' and type(provider.getGameLanguage)=='function' then
  local ok,value=pcall(provider.getGameLanguage); if ok then language=normalize(value) end
 end
 if contextReader then
  local ok,marker,codepage=pcall(contextReader)
  if ok and type(codepage)=='number' and codepage>0 then
   return normalize(marker) or language or 'en',codepage
  end
 end
 return language or 'en',1252 -- original bitmap fallback until TextManager is ready
end
function M.language() local language=M.context(); return language end
M.translations=setmetatable({de=de},{__index=function(self,language)
 if not supported[language] or language=='en' then return end
 local catalog=require('code/locale-'..language); rawset(self,language,catalog); return catalog
end})
local encoding=require('code/text-encoding')
local cache,count={},0
local function encoded(text,codepage)
 if not text:find('[\128-\255]') then return text end
 local key=codepage..':'..text
 if cache[key]~=nil then return cache[key] or nil end
 local ok,value=pcall(encoding.encode,text,codepage)
 if count>=256 then cache={}; count=0 end
 cache[key]=ok and value or false; count=count+1
 return ok and value or nil
end
function M.text(key,...)
 local language,codepage=M.context()
 local catalog=M.translations[language]
 local value=catalog and catalog[key] or key
 -- A translated installation must supply fonts and a matching codepage. If
 -- conversion cannot represent a label, show its English source, not mojibake.
 if not encoded(value,codepage) then value=key end
 return select('#',...)>0 and string.format(value,...) or value
end
local function native(text,codepage)
 return encoded(text,codepage) or (text:gsub('[\128-\255]+','?'))
end
function M.native(text)
 local _,codepage=M.context()
 return native(tostring(text),codepage)
end
function M.fit(text,limit,measure,width)
 local _,codepage=M.context()
 text=tostring(text):gsub('[\r\n%z]',' ')
 return encoding.fit(text,function(value) return native(value,codepage) end,limit,measure,width)
end
return M
