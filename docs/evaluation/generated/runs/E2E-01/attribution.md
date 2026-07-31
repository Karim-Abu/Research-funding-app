# E2E-01 — Fehlschlag und Ursachenzuordnung

Lauf: 6 gezielte Specs, **9 passed / 1 failed** (50 s).

Fehlgeschlagen: `e2e/golden-path.spec.ts:221`
```
await expect(openRow.getByText("Freigegeben")).toBeVisible({ timeout: 20_000 })
```

## Kontrollierter Vergleich (durchgeführt, nicht vermutet)

| Stand der Datei `components/research/query-approval-list.tsx` | Build | golden-path |
|---|---|---|
| Working-Tree-Fassung (UI-Bereinigung vom 25.07., nicht committet) | neu gebaut | **FAIL** |
| `git checkout --` Originalfassung (= Commit `8416914`) | neu gebaut | **PASS** (9.5 s) — Protokoll `golden-path_original-component.log` |
| Working-Tree-Fassung wiederhergestellt | neu gebaut | (Ausgangszustand wiederhergestellt) |

Der Working Tree wurde danach exakt wiederhergestellt: unverändert 34 geänderte
Dateien wie in [[EVALUATION_BASELINE]] §2.

## Ursache

Playwright vergleicht bei `getByText("…")` **case-insensitiv** als Teilstring.
Die Originalfassung rendert in jeder freigegebenen Zeile den Text
`Firewall: freigegeben`. Die Assertion `getByText("Freigegeben")` traf damit
faktisch diesen **Firewall-Hinweis** — nicht das Status-Badge.

Die UI-Bereinigung blendet den Firewall-Zusatz im `allow`-Fall aus (redundant zum
Badge). Damit entfällt der Teilstring, auf den die Assertion tatsächlich
angesprungen ist, und der Test läuft in den Timeout.

## Einordnung

- **Regression durch die nicht committete UI-Bereinigung**, nicht durch den
  Commit-Stand `8416914`.
- Die Vitest-Suite (631 Tests) blieb grün — der Fehler war **nur** über
  Playwright sichtbar. Die UI-Bereinigung wurde seinerzeit ohne Playwright-Lauf
  abgenommen; genau diese Lücke hat ihn durchgelassen.
- Der Test ist zusätzlich fragil: er prüft einen Status über einen Fliesstext,
  der zufällig denselben Wortstamm trägt, statt über das Badge oder ein
  `data-testid`.

**Nicht behoben** — dieser Lauf repariert nichts. Empfehlung als eigener
Arbeitsschritt (P0 vor einem Merge der UI-Bereinigung): Assertion auf das Badge
bzw. eine `data-testid` umstellen, oder den Firewall-Hinweis im `allow`-Fall
beibehalten.
