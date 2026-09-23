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

👉 **Pagina per iniziare: https://pezzaliapp.github.io/pc-check/**
(riconosce il tuo sistema e ti mostra cosa fare)

Alla fine si apre nel browser un report HTML salvato nella tua cartella utente (`pc-check-report-DATA.html`).

## Avvio con un solo comando

**Windows** — apri *PowerShell* (tasto Start, scrivi "PowerShell") e incolla:

```powershell
irm https://raw.githubusercontent.com/pezzaliapp/pc-check/main/run.ps1 | iex
```

**macOS / Linux** — apri il *Terminale* e incolla:

```bash
curl -fsSL https://raw.githubusercontent.com/pezzaliapp/pc-check/main/run.sh | bash
```

Il comando scarica l'ultima versione, prepara un ambiente Python separato in `~/.pc-check` (non tocca il resto del sistema) e avvia il controllo.
Se Python manca, su Windows ti propone di installarlo gratis con winget; su Mac e Linux ti dice il comando da usare.

### Senza Python: eseguibili pronti

Nella pagina **Releases** trovi i file pronti:
- **Windows**: [pc-check-windows.exe](https://github.com/pezzaliapp/pc-check/releases/latest/download/pc-check-windows.exe) — se compare "Windows ha protetto il PC", clicca *Ulteriori informazioni* > *Esegui comunque*.
- **Mac Apple Silicon**: [pc-check-macos.zip](https://github.com/pezzaliapp/pc-check/releases/latest/download/pc-check-macos.zip) — apri lo zip, clic destro sul file > *Apri*; se viene bloccato: Impostazioni di Sistema > Privacy e sicurezza > *Apri comunque*. Sui Mac Intel usa il comando del Terminale.
- **Linux**: [pc-check-linux.zip](https://github.com/pezzaliapp/pc-check/releases/latest/download/pc-check-linux.zip) — estrai ed esegui `./pc-check-linux`.

I file non sono firmati (la firma digitale è a pagamento), per questo il sistema chiede conferma al primo avvio.

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
`& ([scriptblock]::Create((irm https://raw.githubusercontent.com/pezzaliapp/pc-check/main/run.ps1))) --fast`

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

## Aggiornare il programma

Modifica `pc_check.py` su GitHub: chi usa il comando del Terminale / PowerShell riceve subito la nuova versione.
Per aggiornare anche gli eseguibili crea una nuova Release con un tag più alto (es. `v1.0.1`).

Licenza: MIT.
