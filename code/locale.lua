-- GUI language is passed at launch. Older launchers fall back to the game language.
local M={}
local de={
 ['Replays']='Replays', ['Recorded Skirmishes']='Aufgezeichnete Gefechte',
 ['Auto: on']='Auto: ein', ['Auto: off']='Auto: aus',
 ['Play']='Abspielen', ['Back']='Zurück', ['Close']='Schließen', ['Cancel']='Abbrechen',
 ['Save name']='Speichern', ['Save replay as...']='Aufnahme benennen',
 ['Rename replay...']='Umbenennen', ['Remove']='Entfernen', ['Remove replay?']='Aufnahme entfernen?',
 ['Remove this recording from the library?']='Diese Aufnahme aus der Liste entfernen?',
 ['The files are kept in ucp/replays/removed.']='Die Dateien bleiben unter ucp/replays/removed erhalten.',
 ['Replay removed.']='Aufnahme entfernt.', ['Replay name saved.']='Name gespeichert.',
 ['Type a name. Enter saves; Escape cancels.']='Name eingeben. Enter speichert, Escape bricht ab.',
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
function M.language()
 local lang=os.getenv('UCP_GUI_LANGUAGE')
 if not lang or lang=='' then
  -- UCP's global version is its semantic-version utility. The game-language
  -- provider lives in data.version; the utility must not shadow that provider.
  local v=(rawget(_G,'data') or {}).version
  if type(v)~='table' or type(v.getGameLanguage)~='function' then v=rawget(_G,'version') end
  if type(v)=='table' and type(v.getGameLanguage)=='function' then
   local ok,value=pcall(v.getGameLanguage); if ok then lang=value end
  end
 end
 lang=type(lang)=='string' and lang:lower():gsub('_','-') or 'en'
 return (lang=='german' or lang=='de' or lang:match('^de%-')) and 'de' or 'en'
end
function M.text(key,...)
 local value=M.language()=='de' and de[key] or key
 return select('#',...)>0 and string.format(value or key,...) or value or key
end
-- The original bitmap renderer consumes Windows-1252 bytes, not UTF-8.
-- UI translations remain UTF-8 in source. Replay names are currently ASCII.
local glyphs={['Ä']=196,['Ö']=214,['Ü']=220,['ä']=228,['ö']=246,['ü']=252,['ß']=223}
function M.native(text)
 for glyph,byte in pairs(glyphs) do text=text:gsub(glyph,string.char(byte)) end
 return text
end
M.translations={de=de}
return M
