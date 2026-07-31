<!--
Plantilla de notas de release BILINGÜES. Copia esto, edita los "..." y úsalo:

  gh release create vX.Y.Z <archivos...> -R np3ir/tiddl-elvigilante-gui \
    --title "tiddl GUI X.Y.Z" --notes-file RELEASE_NOTES_TEMPLATE.md

(o `gh release edit vX.Y.Z --notes-file RELEASE_NOTES_TEMPLATE.md` para una ya publicada).
Siempre inglés primero, luego español, separados por una línea `---`.
-->

**English** · Español abajo

<!-- Qué cambió (una lista corta) -->
- ...
- ...

**Downloads:** Windows installer (`.exe`), Linux x64 (`.tar.gz`), macOS DMG (Apple Silicon).

- **Windows:** SmartScreen will warn (unsigned installer) → **More info → Run anyway**.
- **macOS:** unsigned app; if you see *"is damaged and can't be opened"*:
  ```
  chmod -R u+w "/Applications/tiddl-gui.app"
  xattr -cr "/Applications/tiddl-gui.app"
  ```
- **Linux:** extract and install ffmpeg (`sudo apt install ffmpeg`).

---

**Español**

<!-- Qué cambió (misma lista, traducida) -->
- ...
- ...

**Descargas:** instalador de Windows (`.exe`), Linux x64 (`.tar.gz`), DMG de macOS (Apple Silicon).

- **Windows:** SmartScreen te advertirá (instalador sin firmar) → **Más información → Ejecutar de todas formas**.
- **macOS:** app sin firmar; si ves *"is damaged and can't be opened"*:
  ```
  chmod -R u+w "/Applications/tiddl-gui.app"
  xattr -cr "/Applications/tiddl-gui.app"
  ```
- **Linux:** descomprime e instala ffmpeg (`sudo apt install ffmpeg`).
