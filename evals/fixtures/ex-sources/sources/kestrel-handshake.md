# Kestrel-Handshake — internes Protokoll, Fassung 3

Quelle: Interne Protokollspezifikation KH-3, Abschnitt 4.2 (Stand 2026-05-14)

## Ablauf

Der Kestrel-Handshake ist ein dreistufiger Verbindungsaufbau zwischen Kante und
Sammelknoten. Er unterscheidet sich vom klassischen Drei-Wege-Handshake darin, dass
der zweite Schritt bereits Nutzdaten transportieren darf ("early payload").

1. `HELLO` — die Kante nennt ihre Protokollfassung und eine Sitzungskennung.
2. `WELCOME` — der Sammelknoten bestätigt und darf bis zu **1440 Byte** Nutzdaten
   anhängen.
3. `SETTLED` — die Kante quittiert; ab hier gilt die Sitzung als offen.

## Konstanten

| Konstante | Wert | Bedeutung |
| --- | --- | --- |
| `KH_EARLY_PAYLOAD_MAX` | 1440 Byte | Obergrenze für Nutzdaten in `WELCOME` |
| `KH_HELLO_TIMEOUT` | 730 ms | Wartezeit auf `WELCOME`, danach Abbruch |
| `KH_RETRY_LIMIT` | 3 | Versuche, bevor die Kante in den Rückfallpfad geht |

## Bekannte Einschränkung

Bei aktivem `early payload` ist die Sitzung zwischen Schritt 2 und 3 nicht gegen
Wiedereinspielung geschützt. Fassung 4 soll das mit einem Zähler in `SETTLED` lösen;
ein Termin dafür steht nicht fest.
