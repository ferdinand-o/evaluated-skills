# Ressourcen modellieren

Bevor ein Pfad entsteht, steht die Frage: Was ist hier eigentlich eine Ressource? Die meisten
Preset-Verstöße (Verben in Pfaden, RPC-artige Endpunkte) sind keine Namensfehler, sondern ein
Zeichen, dass das Ressourcenmodell schief liegt.

## Ressourcen schneiden

Eine Ressource ist etwas, das einen eigenen Lebenszyklus hat: anlegen, lesen, ändern, löschen
(nicht jede Ressource braucht alle vier, aber sie ist als Konzept eigenständig). Test: Kann
man sinnvoll sagen „zeig mir *dieses eine* X" mit einer stabilen ID? Wenn ja, ist X eine
Ressource. Wenn die Antwort „das ist nur ein Ausschnitt von Y" lautet, ist es keine eigene
Ressource, sondern eine Filterung oder Projektion von Y (`GET /orders?status=pending`, nicht
`GET /pending-orders`).

Gegenbeispiel für Übermodellierung: Nicht jedes Substantiv im Fachvokabular braucht einen
eigenen Pfad. „Bestellbestätigung" ist meist kein eigenes Ding mit eigenem Lebenszyklus,
sondern ein Zustand oder eine abgeleitete Darstellung von `Order` — `GET
/orders/{id}/confirmation` nur, wenn sie wirklich unabhängig abrufbar/löschbar ist, sonst ein
Feld auf `Order`.

## Beziehungen

- **Eigentümerschaft (1:n, Kind existiert nicht ohne Eltern):** verschachtelter Pfad,
  `/orders/{id}/items`. Das Kind hat keine sinnvolle Existenz außerhalb des Elternteils.
- **Referenz (m:n oder unabhängiger Lebenszyklus):** flacher Pfad plus Fremdschlüssel-Feld,
  `/orders/{id}` mit `customer_id`-Feld, nicht `/customers/{id}/orders/{id}`. Ein Kunde
  existiert unabhängig von seinen Bestellungen.
- **Verschachtelung nie tiefer als zwei Ebenen.** `/accounts/{id}/orders/{id}/items/{id}` zwingt
  Clients, drei IDs mitzuführen, obwohl `item_id` allein meist schon eindeutig ist. Ab der
  dritten Ebene: flach machen, IDs sind global eindeutig genug (`/items/{id}`), der Kontext
  kommt aus dem Item selbst (`order_id`-Feld).

## Aktionen vs. Ressourcen

Die meisten "Verb-Wünsche" lösen sich, wenn man fragt: Ändert das den *Zustand* einer
bestehenden Ressource, oder passiert etwas mit *Nebenwirkung*, das kein Zustandsfeld ist?

- **Zustandsänderung → PATCH auf die Ressource.** „Bestellung stornieren" klingt nach Aktion,
  ist aber meist `PATCH /orders/{id}` mit `{"status": "cancelled"}` — kein neuer Pfad nötig.
- **Echte Aktion mit Nebenwirkung → Ausnahme-Pfad `/{ressource}/{id}/{aktion}`.** Eine
  E-Mail verschicken, eine Zahlung anstoßen, einen Export starten — das sind Ereignisse, keine
  reinen Feldänderungen. Hier ist `POST /orders/{id}/resend-confirmation` gerechtfertigt und in
  `naming.verb_exceptions` vorgesehen. Faustregel: Wenn der „Verb-Pfad" nur ein PATCH mit
  Statuswechsel imitiert, ist es keine Ausnahme — es ist ein PATCH, das sich vor der
  Modellierungsarbeit drückt.
- **Sammlung von Nebenwirkungen auf mehreren Ressourcen → eigener Batch-Endpunkt**, nicht
  eine Schleife von Einzelaktionen im Client. `POST /orders/batch-cancel` mit einer ID-Liste,
  wenn das ein echter, atomarer Anwendungsfall ist — nicht vorsorglich für jede Aktion.

## Wann eine neue Top-Level-Ressource statt eines Aktions-Pfads

Wenn das „Ereignis" selbst abfragbar, listbar oder historisiert werden soll (wer hat wann
storniert, mit welchem Grund), ist es keine Aktion mehr, sondern eine eigene Ressource:
`POST /orders/{id}/cancellations` legt eine `Cancellation` an, statt nur einen Statuswechsel
auszulösen. Das Signal: Sobald du fragst „brauche ich dafür eine Liste/Historie", ist es eine
Ressource, keine Aktion.
