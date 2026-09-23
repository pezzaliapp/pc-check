# PC Check

Controllo gratuito dello stato di salute del computer per **Windows, macOS e Linux**.
Un comando, circa un minuto, e ottieni un report con punteggio da 0 a 100 e l'elenco di cosa sistemare.

## Cosa controlla

- **Sistema**: modello, sistema operativo, da quanto tempo è acceso
- **CPU**: modello, core, frequenza, utilizzo, test di velocità single e multi-core
- **RAM**: totale, occupata, moduli installati (tipo, velocità, produttore), test di velocità
- **Scheda grafica**: modello, memoria video, driver, risoluzione (più temperatura e uso se NVIDIA)
- **Dischi**: spazio usato e libero per ogni partizione, tipo (SSD / HDD), stato di salute, velocità di lettura e scrittura
- **Spazio occupato**: le cartelle più pesanti nella tua cartella utente e i file temporanei
- **Batteria**: carica, usura (capacità rispetto a quando era nuova), cicli
- **Temperature e ventole** (su Linux)
- **Rete**: connessioni attive, Internet e DNS
- **Programmi in esecuzione**: quelli che usano più RAM e più CPU
- **Programmi all'avvio**
- **Sicurezza**: antivirus, firewall, aggiornamenti, cifratura disco (dove disponibile)

Alla fine si apre nel browser un report HTML salvato nella tua cartella utente (`pc-check-report-DATA.html`).

## Avvio con un solo comando

**Windows** — apri *PowerShell* (tasto Start, scrivi "PowerShell") e incolla:

```powershell
irm https://raw.githubusercontent.com/TUO-UTENTE/pc-check/main/run.ps1 | iex
```

**macOS / Linux** — apri il *Terminale* e incolla:

```bash
curl -fsSL https://raw.githubusercontent.com/TUO-UTENTE/pc-check/main/run.sh | bash
```

Il comando scarica l'ultima versione, prepara un ambiente Python separato in `~/.pc-check` (non tocca il resto del sistema) e avvia il controllo.
Se Python manca, su Windows ti propone di installarlo gratis con winget; su Mac e Linux ti dice il comando da usare.

### Senza Python: eseguibili pronti

Nella pagina **Releases** del repository trovi i file pronti da scaricare e aprire con doppio clic:
`pc-check-windows.exe`, `pc-check-macos-apple-silicon`, `pc-check-macos-intel`, `pc-check-linux`.

Non essendo firmati (la firma costa), al primo avvio:
- **Windows**: se compare "Windows ha protetto il PC", clicca *Ulteriori informazioni* > *Esegui comunque*.
- **macOS**: nel Terminale `chmod +x pc-check-macos-*` poi clic destro sul file > *Apri*.
- **Linux**: `chmod +x pc-check-linux && ./pc-check-linux`

## Opzioni

| Opzione | Effetto |
|---|---|
| `--fast` | salta test di velocità e scansione cartelle (circa 15 secondi) |
| `--no-bench` | salta solo i test di velocità |
| `--no-scan` | salta solo la scansione delle cartelle |
| `--scan-seconds 90` | tempo massimo per la scansione cartelle (default 40) |
| `--no-browser` | non apre il report |
| `--out report.html` | dove salvare il report |
| `--json dati.json` | salva anche i dati grezzi |

Esempi: `curl -fsSL .../run.sh | bash -s -- --fast` oppure, su Windows,
`& ([scriptblock]::Create((irm https://raw.githubusercontent.com/TUO-UTENTE/pc-check/main/run.ps1))) --fast`

Per dati più completi (moduli RAM e salute SMART su Linux, dettagli dischi su Windows) esegui come amministratore / con `sudo`.

## Privacy e costi

- Tutto viene analizzato **sul tuo computer**. Nessun dato viene inviato.
- Le uniche connessioni in rete sono: il download dello script da GitHub, della libreria `psutil` da PyPI, e un test di raggiungibilità di Internet (1.1.1.1).
- **Costo zero**: repository pubblico GitHub gratuito, GitHub Actions gratuito per i repository pubblici, Python e psutil open source.
- Il test del disco scrive un file temporaneo da 256 MB e lo cancella subito.

## Limiti noti

- Windows e macOS non espongono le temperature senza programmi esterni (gratis: HWiNFO / LibreHardwareMonitor su Windows, `sudo powermetrics` su Mac).
- I test di velocità sono indicativi: utili per confrontare lo stesso computer nel tempo. Su Windows la lettura disco può risultare gonfiata dalla cache.
- Su macOS la scansione delle cartelle può far comparire richieste di permesso per Documenti, Scrivania, Foto: puoi rifiutare, i valori saranno solo parziali.

## Pubblicarlo sul tuo GitHub

1. Crea un repository **pubblico** chiamato `pc-check`.
2. Carica tutti i file di questa cartella (inclusa `.github/workflows/build.yml`).
3. In `run.sh`, `run.ps1` e in questo README sostituisci `TUO-UTENTE` con il tuo nome utente GitHub.
4. Per creare gli eseguibili: scheda **Releases** > *Draft a new release* > tag `v1.0.0` > *Publish*. Dopo qualche minuto gli eseguibili compaiono nella release.

Licenza: MIT.
