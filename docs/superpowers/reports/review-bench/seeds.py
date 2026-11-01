"""Fehler-Einbauten fuer die drei Test-Repos. Jede Ersetzung muss genau einmal passen."""
import pathlib
import sys

PY_DIFF = [
    # P1: HEADERS ist ein Modul-Dict aus network/utils.py, Range/If-Range bleiben fuer alle Folgeanfragen haengen
    ("P1", "src/pip/_internal/network/download.py",
     "    headers = HEADERS.copy()\n",
     "    headers = HEADERS\n"),
    # P2: der vendorte Resolver wirft TypeError (Gruppe keine Liste) -> Traceback statt InstallationError
    ("P2", "src/pip/_internal/req/req_dependency_group.py",
     "        except (ValueError, TypeError, LookupError) as e:\n",
     "        except (ValueError, LookupError) as e:\n"),
    # P3: packaging liefert () ohne Build-Tag -> Legacy-Regex, group None -> TypeError bei jedem normalen Wheel
    ("P3", "src/pip/_internal/models/wheel.py",
     "        if self._build_tag is not None:\n",
     "        if self._build_tag:\n"),
    # P4: ohne ignore_installed liefern installierte Pakete kein InstallRequirement -> fehlen still im Lockfile
    ("P4", "src/pip/_internal/commands/lock.py",
     "            ignore_installed=True,\n",
     "            ignore_installed=False,\n"),
    # P5: Docstring sagt rechtester Doppelpunkt; partition bricht Windows-Pfade mit Laufwerksbuchstaben
    ("P5", "src/pip/_internal/cli/cmdoptions.py",
     '    path, sep, groupname = value.rpartition(":")\n',
     '    path, sep, groupname = value.partition(":")\n'),
    # P6: Cache-Schluessel ohne hashes -> Ergebnis eines Aufrufs mit anderen Hashes wird wiederverwendet
    ("P6", "src/pip/_internal/index/package_finder.py",
     "            Tuple[str, Optional[specifiers.BaseSpecifier], Optional[Hashes]],\n",
     "            Tuple[str, Optional[specifiers.BaseSpecifier]],\n"),
    ("P6", "src/pip/_internal/index/package_finder.py",
     "        if (project_name, specifier, hashes) in self._best_candidates:\n"
     "            return self._best_candidates[project_name, specifier, hashes]\n",
     "        if (project_name, specifier) in self._best_candidates:\n"
     "            return self._best_candidates[project_name, specifier]\n"),
    ("P6", "src/pip/_internal/index/package_finder.py",
     "        self._best_candidates[project_name, specifier, hashes] = (\n",
     "        self._best_candidates[project_name, specifier] = (\n"),
    ("P6", "src/pip/_internal/index/package_finder.py",
     "        return self._best_candidates[project_name, specifier, hashes]\n",
     "        return self._best_candidates[project_name, specifier]\n"),
]

PY_PATH = [
    # Q1: Root-Scheme-Dateien ohne Pfad-Traversal-Pruefung (Data-Scheme behaelt sie) -> Zip-Slip
    ("Q1", "src/pip/_internal/operations/install/wheel.py",
     "            dest_path = os.path.join(dest, normed_path)\n"
     "            assert_no_path_traversal(dest, dest_path)\n"
     "            return ZipBackedFile(record_path, dest_path, zip_file)\n",
     "            dest_path = os.path.join(dest, normed_path)\n"
     "            return ZipBackedFile(record_path, dest_path, zip_file)\n"),
    # Q2: Hashes() ist leer falsy (utils/hashes.py __bool__); leeres Hashes wirft immer HashMismatch
    ("Q2", "src/pip/_internal/operations/prepare.py",
     "    # If already downloaded, does its hash match?\n"
     '    logger.info("File was already downloaded %s", download_path)\n'
     "    if hashes:\n",
     "    # If already downloaded, does its hash match?\n"
     '    logger.info("File was already downloaded %s", download_path)\n'
     "    if hashes is not None:\n"),
    # Q3: Kommentar-Regex ohne Leerraum-Anker frisst URL-Fragmente (#sha256=, #egg=, #subdirectory=)
    ("Q3", "src/pip/_internal/req/req_file.py",
     'COMMENT_RE = re.compile(r"(^|\\s+)#.*$")\n',
     'COMMENT_RE = re.compile(r"#.*$")\n'),
    # Q4: SpecifierSet.contains schliesst Vorabversionen ohne prereleases=True aus -> falsche Konflikte in pip check
    ("Q4", "src/pip/_internal/operations/check.py",
     "            if not req.specifier.contains(version, prereleases=True):\n",
     "            if not req.specifier.contains(version):\n"),
    # Q5: RECORD verlangt urlsafe-b64 des rohen Digests (PEP 376/427), nicht des Hex-Strings
    ("Q5", "src/pip/_internal/operations/install/wheel.py",
     '    digest = "sha256=" + urlsafe_b64encode(h.digest()).decode("latin1").rstrip("=")\n',
     '    digest = "sha256=" + urlsafe_b64encode(h.hexdigest().encode()).decode("latin1").rstrip("=")\n'),
    # Q6: ohne copy() schreibt hashes() Internet-Hashes in hash_options -> trust_internet=False vertraut ihnen spaeter
    ("Q6", "src/pip/_internal/req/req_install.py",
     "        good_hashes = self.hash_options.copy()\n",
     "        good_hashes = self.hash_options\n"),
]

DL_DIFF = [
    # D1: TRQLAbstractSyntaxTree besitzt seine Knoten (RQL.Parser: inherited Create(true)); Extract gibt den Besitz ab -> Leck je Anfrage
    ("D1", "sources/MVCFramework.RQL.AST2MSSQL.pas",
     "    aRQLAST.Remove(lLimit);\n"
     "    if aRQLAST.TreeContainsToken(tkSort, lSortToken) then\n"
     "      aRQLAST.Remove(lSortToken);\n",
     "    aRQLAST.Extract(lLimit);\n"
     "    if aRQLAST.TreeContainsToken(tkSort, lSortToken) then\n"
     "      aRQLAST.Extract(lSortToken);\n"),
    # D2: Strings sind 1-basiert; lLine[lNameLen] ist das letzte Zeichen des Namens -> Duplikat-Schutz (MVCFramework.pas) auf Indy aus
    ("D2", "sources/MVCFramework.Indy.Request.pas",
     "    if (Length(lLine) > lNameLen) and (lLine[lNameLen + 1] = ':') and\n",
     "    if (Length(lLine) > lNameLen) and (lLine[lNameLen] = ':') and\n"),
    # D3: Groups 1-basiert, Params 0-basiert; Rueckbau entfernt die falschen Schluessel, Params[0] bleibt -> EListError beim naechsten Kandidaten
    ("D3", "sources/MVCFramework.Router.pas",
     "          aParams.Remove(lCacheItem.Params[J - 1].Key);\n",
     "          aParams.Remove(lCacheItem.Params[J].Key);\n"),
    # D4: ParseFrame-Default 0 = kein Limit (WebSocket.pas); MaxPayloadLength wird nie angewandt
    ("D4", "sources/MVCFramework.WebSocket.Server.pas",
     "        LFrame := TMVCWebSocketFrameParser.ParseFrame(LIOHandler, True, FMaxPayloadLength);\n",
     "        LFrame := TMVCWebSocketFrameParser.ParseFrame(LIOHandler, True);\n"),
    # D5: Secure folgt HttpOnly (Default True) -> Session-Cookie auf HTTP nie gespeichert, gegen die Doku der Property
    ("D5", "sources/MVCFramework.Session.pas",
     "  fTimeoutInMinutes := aTimeoutInMinutes;\n"
     "  fSecure := aSecure;\n",
     "  fTimeoutInMinutes := aTimeoutInMinutes;\n"
     "  fSecure := aHttpOnly;\n"),
    # D6: @@IDENTITY sieht die Inserts eines Triggers; SCOPE_IDENTITY nicht -> Refresh liest bei Tabellen mit Trigger die falsche Zeile
    ("D6", "sources/MVCFramework.SQLGenerators.MSSQL.pas",
     "        ' WHERE ' + lPKName + ' = SCOPE_IDENTITY();';\n",
     "        ' WHERE ' + lPKName + ' = @@IDENTITY;';\n"),
]

DL_PATH = [
    # E1: TEntry ist ein Record (Wertkopie aus TryGetValue); ohne Zurueckschreiben bleibt Used False -> Wiederverwendung nie erkannt
    ("E1", "sources/MVCFramework.JWT.RefreshToken.pas",
     "    lOld.Used := True; // keep, so reuse stays detectable\n"
     "    fByHash.AddOrSetValue(lHash, lOld);\n",
     "    lOld.Used := True; // keep, so reuse stays detectable\n"),
    # E2: TDateTime zaehlt Tage; Now + ATTLSeconds macht aus Sekunden Tage
    ("E2", "sources/MVCFramework.JWT.RefreshToken.pas",
     "  lEntry.ExpiresAt := Now + (ATTLSeconds * OneSecond);\n",
     "  lEntry.ExpiresAt := Now + ATTLSeconds;\n"),
    # E3: SetContentStream uebernimmt den Stream; ohne nil gibt finally ihn frei -> Doppelfreigabe bei jeder Anfrage ohne Range
    ("E3", "sources/MVCFramework.Middleware.RangeMedia.pas",
     "      LFileStream := nil; // SetContentStream takes ownership; prevent double-free in finally\n",
     ""),
    # E4: UnixToDateTime(.., True) liefert UTC, Now ist Ortszeit -> abgelaufene Tokens oestlich von UTC stundenlang gueltig
    ("E4", "sources/MVCFramework.Middleware.OIDC.pas",
     "    if UnixToDateTime(lExp, False) + (FLeewaySeconds * OneSecond) <= Now then\n",
     "    if UnixToDateTime(lExp, True) + (FLeewaySeconds * OneSecond) <= Now then\n"),
    # E5: Feld mit Anfuehrungszeichen wird nicht gequotet, EscapeField verdoppelt dann nichts -> kaputtes CSV
    ("E5", "sources/MVCFramework.Serializer.CSV.pas",
     "    if (lCh = FSettings.Delimiter) or\n"
     "       (lCh = FSettings.QuoteChar) or\n",
     "    if (lCh = FSettings.Delimiter) or\n"),
    # E6: Vergleich umgedreht -> Cache gilt als abgelaufen, solange er frisch ist: JWKS-Abruf bei jeder Anfrage
    ("E6", "sources/MVCFramework.OIDC.JWKS.pas",
     "    (SecondsBetween(Now, FLastFetchTime) >= FCacheTTLSeconds);\n",
     "    (SecondsBetween(Now, FLastFetchTime) <= FCacheTTLSeconds);\n"),
]

SETS = {"py-diff": PY_DIFF, "py-path": PY_PATH, "dl-diff": DL_DIFF, "dl-path": DL_PATH}


def apply(name: str, root: str) -> None:
    base = pathlib.Path(root)
    for seed_id, rel, old, new in SETS[name]:
        p = base / rel
        raw = p.read_bytes()
        try:
            text, enc = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, enc = raw.decode("latin-1"), "latin-1"
        crlf = "\r\n" in text
        o, n = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) if crlf else (old, new)
        count = text.count(o)
        if count != 1:
            sys.exit(f"{seed_id} {rel}: {count} Treffer")
        p.write_bytes(text.replace(o, n).encode(enc))
        print(seed_id, rel, "ok")


if __name__ == "__main__":
    apply(sys.argv[1], sys.argv[2])
