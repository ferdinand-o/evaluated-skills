# Delphi: Prüfliste für den Reviewer

Referenz für den Hauptagenten. Sie geht zusammen mit dem Paketblock an jeden Reviewer, wenn
das Paket Delphi-Dateien (`.pas`, `.dpr`, `.dpk`) enthält ([review-brief.md](review-brief.md)).
Der Reviewer spielt jeden Punkt an den geänderten Zeilen durch: zuerst die **Frage**, dann
die **Eingabe**, also den kleinen Ablauf, der zeigt, ob die Stelle bricht.

Was der Sammler für Delphi liefert, steht in [counterparts.md](counterparts.md), Abschnitte
[Delphi](counterparts.md#delphi) (Auflösung, Kopf mit Default-Werten, `deklariert:`, `wirft:`)
und [Besitz bei Delphi](counterparts.md#besitz-bei-delphi) (Klassendeklaration,
`inherited Create(…)`, `Besitz (RTL)`). Das wird hier nicht wiederholt; die Punkte unten sagen
nur, wonach man in diesen Zeilen schaut.

| Gruppe | Punkte |
| --- | --- |
| Besitz und Freigabe | `try/finally`, Owner, `Extract` gegen `OwnsObjects`, Besitzübergabe an Antwort-Objekte |
| Werte | 1-basierte Strings, Record-Kopien aus `TryGetValue`, `TDateTime` in Tagen, UTC gegen Ortszeit |
| Lebensdauer und Fehler | Interface-Referenzzählung gemischt mit Objektreferenzen, verschluckte Exceptions |

## Besitz und Freigabe

Ein Leck oder eine doppelte Freigabe zeigt sich selten im Diff. Frage immer: Wer legt das
Objekt an, wer gibt es frei, und stimmt das auf **jedem** Weg aus der Routine, auch bei einer
Exception?

### `try/finally`

- **Frage:** Steht zwischen `Create` und dem Ende der Routine etwas, das wirft, ohne dass ein
  `finally` das Objekt freigibt? Liegt `Create` vor dem `try`, nicht darin?
- **Eingabe:**

  ```pascal
  procedure LoadPrices(const AName: string);
  var List: TStringList; Index: TPriceIndex;
  begin
    List := TStringList.Create;
    Index := TPriceIndex.Create;      // wirft, wenn der Speicher knapp ist
    try
      List.LoadFromFile(AName);       // wirft, wenn die Datei fehlt
      Index.Fill(List);
    finally
      List.Free;
      Index.Free;
    end;
  end;
  ```

  Spiele zwei Fälle durch: `TPriceIndex.Create` wirft, dann ist `List` verloren, weil das
  `try` erst danach beginnt. Und `List.Free` wirft: `Index` wird nicht mehr erreicht. Richtig
  ist ein `try/finally` je Objekt, das unmittelbar nach seinem `Create` beginnt.

### Owner

- **Frage:** Wer besitzt das Objekt nach dieser Zeile: der Aufrufer, das Feld einer Klasse
  (Destruktor), ein `TComponent`-Owner oder eine besitzende Liste? Gibt jemand zweiten Besitz
  frei oder niemand?
- **Eingabe:**

  ```pascal
  Inv := TInvoice.Create(Lines);      // speichert Lines in FLines, ~TInvoice ruft FLines.Free
  try
    Inv.Print;
  finally
    Inv.Free;
    Lines.Free;                       // Lines gehört seit Create dem Invoice
  end;
  ```

  Der Destruktor von `TInvoice` hat `Lines` schon freigegeben, die letzte Zeile ist eine
  doppelte Freigabe. Gegenprobe: Öffne den Destruktor von `TInvoice`. Gibt er `FLines` nicht
  frei, ist `Lines.Free` richtig, und ein fehlendes `Free` wäre der Fund.

### `Extract` gegen `OwnsObjects`

- **Frage:** Ist der Container besitzend (`inherited Create(True)`, `Ownerships` mit
  `doOwnsKeys` oder `doOwnsValues`, oder der Besitz-Default der RTL im Block), und wechselt die
  Stelle zwischen den freigebenden Aufrufen (`Remove`, `Delete`, `Clear`) und den
  herausnehmenden (`Extract`, `ExtractPair`)? Bei `OwnsObjects` gleich wahr gibt eine Liste mit
  `Remove`, `Delete` und `Clear` das Element frei, mit `Extract` nicht. `TObjectDictionary`
  besitzt nur, was `Ownerships` nennt, und gibt es bei `Remove` und `Clear` frei, bei
  `ExtractPair` nicht.
- **Eingabe:**

  ```pascal
  // FCache: TObjectDictionary<string, TReport>, Create([doOwnsValues])
  Pair := FCache.ExtractPair(Key);    // vorher: FCache.Remove(Key)
  Outbox.Add(Pair.Value);             // Outbox.Add speichert nur, es gibt nichts frei
  ```

  Mit `Remove` war der Bericht nach der Zeile zerstört. Mit `ExtractPair` lebt er weiter und
  gehört jetzt niemandem: Wer ruft `Pair.Value.Free`, wenn `Outbox` es nicht tut? Umgekehrt:
  Bleibt nach dem Wechsel auf `Remove` ein `Free` auf dem Wert stehen, ist es eine doppelte
  Freigabe. Gegenprobe: Ohne `doOwnsValues` gibt auch `Remove` nichts frei, dann ändert der
  Wechsel am Besitz nichts.

### Besitzübergabe an Antwort-Objekte

- **Frage:** Wird ein Objekt (Stream, Liste, Daten-Objekt) an eine Antwort, einen Container
  oder einen Setter wie `SetContentStream` übergeben? Übernimmt der Empfänger den Besitz, und
  gibt der Aufrufer es danach trotzdem frei, auch im `except`-Pfad? Die Klassendeklaration und
  `inherited Create(…)` im Block sagen, wer besitzt.
- **Eingabe:**

  ```pascal
  Stream := TMemoryStream.Create;
  try
    Stream.LoadFromFile(Path);
    Reply.SetContentStream(Stream);   // Reply übernimmt und gibt beim Senden frei
  finally
    Stream.Free;                      // gibt den Stream vor dem Senden frei
  end;
  ```

  Übernimmt `Reply` den Besitz, sendet es später einen zerstörten Stream (oder gibt ihn ein
  zweites Mal frei). Übernimmt es nicht, ist das `Free` zu früh, wenn gesendet wird, nachdem
  die Routine zurück ist. Spiele auch den Fall durch, dass `LoadFromFile` wirft: Hier geht
  der Besitz noch nicht über, das `finally` ist dann richtig.

## 1-basierte Strings

- **Frage:** Wird ein `string` mit 0 oder mit 1 als erstem Index angesprochen, und stimmt das
  mit der Funktion daneben überein? `S[…]`, `Copy`, `Pos`, `Delete`, `Insert` zählen ab 1;
  `string`-Helfer (`Substring`, `IndexOf`), `TStringBuilder` und die Standard-Eigenschaft
  `TStringList.Strings[…]` (geschrieben auch `List[i]`) zählen ab 0. `{$ZEROBASEDSTRINGS}` dreht das für `S[…]`.
- **Eingabe:**

  ```pascal
  P := Pos(':', Line);                // 1-basiert, 0 wenn nicht gefunden
  Key := Line.Substring(0, P);        // Substring ist 0-basiert
  Val := Line.Substring(P);           // gedacht: hinter dem Doppelpunkt
  ```

  Für `Line = 'mode:fast'` ist `P` = 5. `Substring(0, 5)` ergibt `'mode:'` statt `'mode'`, und
  `Substring(5)` ergibt `'fast'` nur zufällig richtig. Fehlt der Doppelpunkt, ist `P` = 0 und
  `Substring(0, 0)` ist leer, ohne Fehler.

## Record-Kopien aus `TryGetValue`

- **Frage:** Ist der Elementtyp ein `record`, und wird die Kopie, die `TryGetValue` oder
  `Items[…]` liefert, verändert, als wäre es das Original? Wird sie zurückgeschrieben?
- **Eingabe:**

  ```pascal
  if Counts.TryGetValue(Key, Stat) then
    Inc(Stat.Hits)                    // Stat ist eine Kopie
  else
    Counts.Add(Key, TStat.Create(1));
  ```

  Beim zweiten Aufruf mit demselben `Key` bleibt `Hits` im Dictionary 1. Es fehlt
  `Counts[Key] := Stat;`. Gleiches gilt für `for var R in List do R.Done := True` über eine
  `TList<TRec>`.

## `TDateTime` in Tagen

- **Frage:** Rechnet die Stelle mit einem `TDateTime` oder einer Differenz davon, als stünde
  die Zahl für Sekunden oder Millisekunden? Ganze Zahlen sind Tage, der Bruchteil die
  Tageszeit. Wird ein Gleitkommawert mit `=` verglichen?
- **Eingabe:**

  ```pascal
  Deadline := Now + Timeout;          // Timeout = 30, gedacht als Sekunden
  if Now - Started > Limit then       // Limit = 5000, gedacht als Millisekunden
  ```

  `Now + 30` liegt 30 Tage in der Zukunft. `Now - Started > 5000` wird erst nach rund 13,7
  Jahren wahr. Richtig sind `IncSecond(Now, Timeout)` und `MilliSecondsBetween(Now,
  Started) > Limit`. Zwei Zeitpunkte vergleicht man mit `SameDateTime`, nicht mit `=`.

## UTC gegen Ortszeit

- **Frage:** In welcher Zeitzone liegen die beiden Seiten einer Rechnung oder eines
  Vergleichs: `Now` (Ortszeit), UTC aus `TTimeZone.Local.ToUniversalTime(Now)` oder
  `TDateTime.NowUTC` (beide `System.DateUtils`), ein gespeicherter Wert aus der Datenbank oder
  einem Token? Wird zwischen den Zonen
  umgerechnet, und liegt die Stelle über eine Sommerzeitgrenze?
- **Eingabe:**

  ```pascal
  Expires := IncHour(Now, 1);                       // Ortszeit, in die Datei geschrieben
  ...
  if Expires < TTimeZone.Local.ToUniversalTime(Now) then
    raise ETokenExpired.Create;
  ```

  Ortszeit ist UTC−5, es ist 12:00. `Expires` = 13:00 Ortszeit. Die Gegenseite ist 17:00 UTC.
  `13:00 < 17:00` ist wahr: Das Token ist sofort abgelaufen. Bei UTC+2 wäre es 10:00 UTC, und
  das Token bliebe drei Stunden statt einer gültig.

## Interface-Referenzzählung gemischt mit Objektreferenzen

- **Frage:** Wird dieselbe Instanz einer Klasse mit Referenzzählung (`TInterfacedObject`) über
  eine Objektvariable **und** eine Interface-Variable gehalten? Dann zerstört der Zähler die
  Instanz, sobald die letzte Interface-Referenz geht, auch wenn die Objektvariable sie noch
  nutzt. Wann das ist, entscheidet oft eine Referenz, die im Code nicht steht: Das Ergebnis
  von `Obj as IIntf` (ebenso eine Interface-Rückgabe, die keiner Variablen zugewiesen wird)
  hält der Compiler in einer versteckten Temporären. Sie gibt ihre Referenz erst im Epilog der
  umschließenden Routine ab, also an deren `end`, nicht nach dem Aufruf.
- **Eingabe:**

  ```pascal
  procedure TJobs.Start;              // FWorker: TWorker (Objektreferenz)
  begin
    FWorker := TWorker.Create;        // Zähler 0
    Run(FWorker as IWorker);          // versteckte Temporäre: Zähler 1
    FWorker.Reset;                    // geht noch, die Temporäre lebt bis zum Epilog
  end;                                // Epilog: Temporäre gibt ab, Zähler 0, Instanz zerstört

  procedure TJobs.Stop;
  begin
    FWorker.Reset;                    // Instanz seit dem Ende von Start zerstört
    FWorker.Free;                     // zweite Freigabe
  end;
  ```

  Innerhalb von `Start` geht alles gut, auch die Zeile nach `Run`. Freigegeben wird die
  Instanz im Epilog von `Start`. Was danach kommt, scheitert: `Stop` ruft eine Methode auf
  freigegebenem Speicher auf, und `FWorker.Free` gibt ein zweites Mal frei. Spiele daher den
  Weg über das Ende der Routine hinaus durch: Feld, Liste, Rückgabewert. Richtig ist eine
  einzige Art: durchgängig Interface-Variablen, oder eine Klasse, die nicht mitzählt, oder die
  Objektreferenz hält zusätzlich eine eigene Interface-Referenz.

## Verschluckte Exceptions

- **Frage:** Fängt ein `except` die Exception und läuft dann so weiter, als wäre nichts
  geschehen (leerer Block, nur Log, `on E: Exception do` ohne `raise`)? Fängt es mehr Typen
  als vorher? Welche Typen nennt `wirft:` im Block für die Aufrufe im `try`?
- **Eingabe:**

  ```pascal
  try
    Conn.Commit;
  except
    on E: Exception do Log(E.Message);
  end;
  Result := True;                     // Aufrufer löscht daraufhin die Quelldaten
  ```

  Spiele `Conn.Commit` mit einer Exception durch: Die Meldung steht im Log, `Result` ist
  `True`, die Quelldaten werden gelöscht, obwohl nichts gespeichert wurde. Ein
  `raise;` am Ende des `except`-Blocks oder `Result := False` im Handler behebt es. Prüfe
  auch das Gegenstück: Wurde ein bisher spezifisches `on E: EDBError` zu `on E: Exception`
  verbreitert, fängt es jetzt auch `EAccessViolation` und `EOutOfMemory`.
