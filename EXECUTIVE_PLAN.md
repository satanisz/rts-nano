# RTS Nano - Executive Plan (Polska wersja robocza)

Ostatnia aktualizacja: 2026-05-20

Ten plik jest śledzonym planem projektu. Ma utrzymywać wspólny kontekst:
gdzie jesteśmy w repozytorium, jaki jest kierunek architektury, jakie prace są
już wykonane i jakie zadania są następne. Po większych zmianach w kodzie albo
planie należy go aktualizować razem z resztą zmian.

## 1. Cel produktu

RTS Nano ma stać się w pełni funkcjonalną grą RTS na poziomie funkcjonalnym
zbliżonym do WarCraft II. Nie celujemy teraz w zaawansowane animacje ani ciężką
oprawę audiowizualną. Najważniejsze są kompletne mechaniki: ekonomia, produkcja,
budowanie, walka, rozkazy jednostek, warunki zwycięstwa, grywalny interfejs dla
człowieka oraz stabilne API, przez które agent może sterować grą.

Assety mogą być poprawiane osobno. Kod powinien mieć jasne miejsca na lepsze
sprite'y, portrety, ikony i przyszłe paczki assetów, ale ukończenie gameplayu
nie może zależeć od animacji. Symulacja ma być czytelna, deterministyczna i
uruchamialna bez renderowania.

Drugim głównym celem jest środowisko do trenowania sieci neuronowych. Rdzeń gry
musi być lekki, możliwy do uruchamiania w wielu instancjach i dostępny przez
stabilne API. Klient Pygame jest tylko warstwą prezentacji nad tym samym modelem
gry, a nie źródłem prawdy o mechanice.

## 2. Twarde zasady projektowe

1. Gameplay przed animacją.
   Pełne mechaniki mają pierwszeństwo przed płynnością sprite'ów, efektami,
   dźwiękami i ozdobnikami.

2. Symulacja bez zależności od renderera.
   Trening agentów nie może wymagać okna, surface Pygame, sprite'ów ani obsługi
   myszy. Pygame należy do UI/renderingu, nie do core simulation.

3. Lekkość obliczeniowa.
   Rozwiązania muszą skalować się do wielu równoległych instancji. Unikamy
   ciężkich systemów fizyki, domyślnych obserwacji obrazowych, zbędnych pętli
   O(N^2) i pracy wykonywanej co tick bez budżetu.

4. Determinizm.
   Ten sam seed, mapa i sekwencja akcji muszą dawać ten sam wynik. To jest
   krytyczne dla testów, debugowania agentów i porównywania eksperymentów.

5. API-first.
   Każda mechanika gameplayu powinna być dostępna przez jawne akcje, obserwacje
   i snapshoty. Sieć neuronowa nie powinna czytać prywatnego stanu UI ani żywych
   obiektów Pygame.

6. Małe, weryfikowalne kroki.
   Każdy większy etap powinien kończyć się testami headless i minimalnym
   sprawdzeniem grywalności w kliencie Pygame.

## 3. Aktualny stan repozytorium

Projekt jest pakietem Python 3.14.4 zarządzanym przez `uv`/`hatchling`.
Runtime używa `pygame-ce`, importowanego jako `pygame`. Jakość kodu jest
pilnowana przez `ruff`, `ty`, `pytest`, `tox` i `pre-commit`. Końce linii LF są
wymuszane przez `.gitattributes` i `.editorconfig`.

Główne moduły:

- `src/rts_nano/main.py`
  Uruchamia Pygame, tworzy okno, prowadzi pętlę event/update/draw i przekazuje
  input do managera.

- `src/rts_nano/game/manager.py`
  Nadal posiada większość żywego stanu gry: mapę, drużyny, zasoby, jednostki,
  budynki, selekcję, kamerę, HUD, minimapę, menu, pociski, zbieranie i zwycięstwo.
  To nadal główny kandydat do dalszego rozdzielania.

- `src/rts_nano/game/orders.py`
  `OrderSystem` obsługujący zapytania o jednostki/bazy i publiczne rozkazy:
  ruch, cel/atak, żądania produkcji peasantów, anulowanie produkcji i selekcję.

- `src/rts_nano/game/data.py`
  Statyczne dane gameplayu: zasoby, koszty jednostek, czasy produkcji,
  populacja, role budynków i szkic przyszłego rosteru RTS.

- `src/rts_nano/game/production.py`
  Lekki `ProductionSystem` dla kolejek produkcji. Peasant w bazie jest teraz
  opłacany z góry, rezerwuje populację, postępuje w tickach headless i pojawia
  się dopiero po czasie produkcji. Barracks produkuje podstawowe jednostki
  wojskowe. Produkcję można anulować z częściowym zwrotem. Niedokończone
  budynki nie mogą produkować.

- `src/rts_nano/game/construction.py`
  Lekki `ConstructionSystem` dla budowy struktur przez workerów. Obecnie
  obsługuje Barracks i House: koszt, walidację terenu/kolizji, niedokończony
  budynek, postęp budowy, anulowanie z częściowym zwrotem i aktywację po
  ukończeniu.

- `src/rts_nano/actions.py`
  Publiczne DTO akcji: `NoOpAction`, `MoveAction`, `AttackAction`,
  `GatherAction`, `DepositAction`, `BuildAction`, `ConstructAction`,
  `CancelProductionAction`, `SelectAction`, `ActionSpec` i `WorldPoint`.

- `src/rts_nano/action_translation.py`
  `ActionTranslator` tłumaczy publiczne akcje API na wywołania managera i
  systemów rozkazów.

- `src/rts_nano/env.py`
  Cienka fasada `RtsNanoEnv`: `reset`, `step`, `observe`, `available_actions`,
  `action_mask`, `reward` i `close`. To obecny punkt wejścia dla przyszłych
  agentów RL.

- `src/rts_nano/game/observations.py`
  Snapshoty obserwacji i mapowanie ID encji: `Observation`, `EntitySnapshot`,
  `TeamSnapshot`, `ProductionSnapshot` i `EntityIdRegistry`.

- `src/rts_nano/headless.py`
  Wrapper bez renderowania używany przez testy i przyszłą pracę RL.

- `src/rts_nano/game/pathfinding.py`
  Grid A* z zewnętrznym predykatem przechodniości.

- `src/rts_nano/game/rules.py`
  Czyste reguły pomocnicze dla dystansów, obrażeń, bonusów wysokości, clampingu
  i wyszukiwania najbliższych encji.

- `src/rts_nano/game/terrain.py`
  Mapa terenu, wysokości, rampy, woda/blokady i renderowanie terenu.

- `src/rts_nano/map_schema.py`, `src/rts_nano/map_editor.py`,
  `src/rts_nano/validate_map.py`
  Format map JSON, walidacja i edytor map.

- `src/rts_nano/game/assets/entities/`
  Klasy encji: jednostki, budynki, zasoby i wspólne klasy bazowe.

Ostatni znany stan jakości po bieżącym etapie: `ruff`, `ty`, `pytest`, `tox` i
`pre-commit` przechodzą.

## 4. Co już działa

- Podstawowa pętla gry Pygame.
- Ładowanie map JSON i walidacja schematu.
- Edytor map.
- Teren z wodą, rampami, wysokością i blokadami.
- Jednostki: peasant, knight, archer, mage.
- Budynek bazy.
- Zasoby: wood i crystal/cristal.
- Podstawowe zbieranie i deponowanie zasobów.
- Kolejkowana produkcja peasantów w bazie.
- Kolejkowana produkcja knightów i archerów w Barracks.
- Budowanie Barracks przez peasantów: koszt, placement API, walidacja terenu i
  kolizji, niedokończony budynek z progressem oraz aktywacja po ukończeniu.
- Budowanie House przez peasantów i limit populacji liczony z ukończonych
  budynków: Base daje 10, House daje 6.
- Anulowanie niedokończonej budowy z częściowym zwrotem zasobów przez API/env.
- Pierwszy UI placement w Pygame: Peasant ma komendy budowy House/Barracks,
  kliknięcie w świecie stawia budynek, a ghost pokazuje poprawność miejsca.
- Anulowanie produkcji z częściowym zwrotem zasobów.
- Statyczne dane gameplayu dla obecnych jednostek/budynków i najbliższych ról RTS.
- Selekcja jednostek i rozkazy ruchu.
- Podstawowy pathfinding A*.
- Podstawowa walka i celowanie.
- Rozkaz stop przez API/env, managera i hotkey `S`.
- Fog of war w kliencie gry.
- Headless simulation wrapper.
- Wczesne publiczne API agenta przez `RtsNanoEnv`.
- Stanowe maski akcji z powodami odmowy dla integracji agentów.
- Snapshoty obserwacji bez bezpośredniego wystawiania obiektów UI.
- Snapshoty obserwacji zawierają kolejki produkcji i limit populacji.
- Testy dla map, terenu, pathfindingu, headless wrappera, env i danych gry.

## 5. Największe braki względem celu

### 5.1 Ekonomia i produkcja

- Produkcja ma pierwszą implementację kolejek/czasu/anulowania dla peasantów oraz
  podstawowych jednostek z Barracks; Barracks można już zbudować workerem, ale
  nadal trzeba dodać kolejne budynki produkcyjne i wymagania technologiczne.
- Potrzebne są pełniejsze wymagania technologiczne.
- Model populacji jest rozpoczęty: ukończone budynki dodają support, ale nadal
  trzeba dopracować balans, UI i wymagania technologiczne.
- Rekomendacja zasobów: zostać przy `wood` i `cristal`, żeby zachować prostotę i
  lekkość, ale nadać im role podobne do drewna i złota.

### 5.2 Budowanie

- Barracks i House mają pierwszą wersję placementu przez API/env z walidacją
  kosztu, terenu i kolizji.
- Budowa trwa w czasie, ma progress w obserwacji i aktywuje efekty budynku
  dopiero po ukończeniu.
- UI placement jest rozpoczęty, ale nadal brakuje pełnych komunikatów UX, hotkeyów
  budowy, pełnych footprintów i dalszych typów budynków.
- Budynki muszą blokować pathfinding zgodnie ze swoim footprintem.

### 5.3 Rozkazy i zachowanie jednostek

- Rozkaz stop jest zaimplementowany. Nadal potrzebne są: hold position, patrol,
  follow/guard, attack-move, repair/build, gather i return cargo.
- Priorytety muszą być spójne: rozkaz ręczny, autoatak, powrót do pracy,
  path replanning, śmierć celu.
- Projekt potrzebuje modelu `Order`/`Command` zamiast rozproszonych flag.

### 5.4 Walka

- Walka musi być deterministyczna, testowalna i niezależna od efektów wizualnych.
- Potrzebne są typy obrażeń/zasięgów, cooldowny, target acquisition, fog-aware
  targeting, opcjonalny friendly fire i jasne reguły śmierci.
- Pociski mogą zostać wizualne, ale obrażenia nie mogą zależeć od renderingu.

### 5.5 Fog of war i informacje

- Gracz i agenci potrzebują oddzielnych widoków: pełny stan debug, obserwacja
  drużyny i obserwacja ograniczona fogiem.
- Gra powinna wspierać pamięć ostatnio widzianych budynków/terenu.
- Obserwacje RL powinny działać bez obrazów: encje, mapa kafelkowa, zasoby,
  kolejki i maski akcji.

### 5.6 UI dla człowieka

- Potrzebny kompletny command panel dla jednostek i budynków.
- UI potrzebuje produkcji, placementu budynków, komend z minimapy, kosztów,
  postępu produkcji i populacji.
- Grupy kontrolne, wybieranie po typie, double-click lub podstawowe hotkeye
  powinny zostać dodane w praktycznym zakresie.
- UI ma być funkcjonalny i czytelny, nie ciężki wizualnie.

### 5.7 API treningowe

- Kontrakty obserwacji i akcji wymagają formalnego wersjonowania.
- Maski akcji są rozpoczęte, ale trzeba je rozszerzać przy każdej nowej mechanice.
- Potrzebne są scenariusze treningowe, reward functions i benchmarki steps/sec.
- Adaptery Gymnasium lub PettingZoo są użyteczne później, po stabilizacji
  natywnego lekkiego API.

## 6. Docelowa architektura

Gra powinna iść w stronę trzech warstw.

### 6.1 Core simulation

Warstwa bez Pygame, obrazów i UI. Ona posiada prawdziwy stan gry.

Proponowane elementy:

- `GameState`
  Dane świata: mapa, tick, seed, drużyny, encje, zasoby, kolejki, fog i stan
  zwycięstwa. Powinien być łatwy do snapshotowania i testowania.

- `Simulation`
  Fasada wysokiego poziomu: `reset`, `step`, `apply_action`, `observe`,
  `available_actions`, `is_done`.

- Systemy:
  `OrderSystem`, `EconomySystem`, `ProductionSystem`, `ConstructionSystem`,
  `CombatSystem`, `MovementSystem`, `PathingSystem`, `VisionSystem`,
  `VictorySystem`.

- Encje jako dane plus minimalne zachowanie lokalne.
  Reguły przekrojowe powinny trafiać do systemów, a nie powiększać `GameManager`.

### 6.2 Adaptery

- `RtsNanoEnv` dla natywnego API treningowego.
- Przyszłe `GymnasiumRtsNanoEnv` albo `PettingZooRtsNanoEnv`.
- Adapter Pygame dla renderingu i wejścia człowieka.
- Adaptery ładowania map i assetów.

### 6.3 Presentation/UI

- Rysowanie mapy i encji.
- HUD, minimapa, command panel.
- Input myszy/klawiatury tłumaczony na te same DTO akcji, których używają agenci.
- Efekty wizualne tylko jako konsekwencja stanu symulacji.

## 7. API dla sieci neuronowych

Docelowy minimalny kontrakt:

```python
env = RtsNanoEnv(config)
obs = env.reset(seed=123)

while not obs.done:
    mask = env.action_mask(team="Blue")
    action = policy(obs, mask)
    result = env.step(action)
    obs = result.observation
```

Wymagania:

- `reset(seed=...)` gwarantuje deterministyczny start.
- `step(action)` przesuwa grę o jeden tick albo skonfigurowaną liczbę ticków.
- `observe(team_id=...)` powinno zwracać serializowalny snapshot, nie żywe obiekty.
- `available_actions`/`action_mask` opisuje legalne akcje w obecnym stanie.
- ID encji są stabilne w trakcie epizodu.
- Warianty obserwacji mogą obejmować `full_state_debug`, `team_state`,
  `fog_limited` i `spatial_grid`.
- Domyślna obserwacja nie jest obrazem, żeby wiele instancji treningowych było
  tanie.
- Obraz/screenshot może istnieć jako opcjonalny adapter, nie domyślne API.
- Core nie importuje PyTorch, Gymnasium ani PettingZoo; te zależności należą do
  adapterów.

## 8. Performance i skalowanie treningu

Najpierw mierzyć, potem optymalizować. Potrzebne benchmarki:

- headless steps/sec dla jednej instancji,
- headless steps/sec dla wielu instancji w jednym procesie,
- koszt pathfindingu przy wielu jednostkach,
- koszt obserwacji dla full-state i fog-limited,
- pamięć na instancję.

Zasady implementacyjne:

- Renderowanie nigdy nie działa podczas treningu.
- Obserwacje powinny używać danych już policzonych w ticku, jeśli to możliwe.
- Pathfinding powinien dostać budżety, cache albo reuse ścieżek dla grup, gdy
  liczba jednostek wzrośnie.
- Spatial index/grid dodać dopiero, gdy liczba encji uzasadnia koszt.
- Unikać dużych alokacji co tick.
- Symulacja powinna używać fixed timestep.
- Testy performance nie mogą wymagać GPU ani okna.

## 9. Plan prac

### Faza 0 - Jakość

- Utrzymywać zielone `ruff`, `ty`, `pytest`, `tox`, `pre-commit`.
- Aktualizować i commitować `EXECUTIVE_PLAN.md`, gdy zmienia się kierunek albo
  ważny stan repo.
- Przy każdej zmianie gameplayu dodawać test headless.
- Nie mieszać architektury, gameplayu i assetów w jednym dużym commicie.

### Faza 1 - Specyfikacja gameplayu

- Dane gry dla jednostek, budynków, kosztów, czasów, populacji i wymagań:
  rozpoczęte w `game/data.py`.
- Zdefiniować finalne role `wood` i `cristal`.
- Zdefiniować minimalne budynki: baza, populacja/support, produkcja wojsk,
  ulepszenia, wieża.
- Zdefiniować minimalne jednostki: worker, melee, ranged, special/caster,
  ewentualnie siege później.
- Zdefiniować warunki zwycięstwa.
- Zdefiniować scenariusze treningowe.

### Faza 2 - Wyciąganie rdzenia symulacji

- Utworzyć jawny `GameState` albo równoważny kontener bez zależności od UI.
- Przenosić tick/update mechanik do systemów niezależnych od Pygame.
- Zmienić `GameManager` w adapter Pygame nad `Simulation`.
- Ujednolicić ID encji i dostęp przez registry/repository.
- Przenieść victory detection do `VictorySystem`.
- Utrzymywać testy deterministycznego replayu.

### Faza 3 - Ekonomia i produkcja

- Koszty i płatności: rozpoczęte.
- Kolejki produkcji: rozpoczęte dla peasantów.
- Czasy produkcji/progress: rozpoczęte.
- Anulowanie produkcji i częściowy zwrot: rozpoczęte.
- Limit populacji: obecnie globalny, docelowo do rozbudowy.
- Dalej: więcej budynków produkcyjnych, więcej jednostek, wymagania tech.
- Obserwacje powinny dalej pokazywać kolejki, populację i dostępne produkcje.

### Faza 4 - Budowanie budynków

- Placement mode w API i UI.
- Footprinty budynków.
- Walidacja terenu, kolizji, zasobów i fog przy placement.
- Niedokończone budynki z progressem.
- Worker wykonuje budowę w czasie.
- Budynek działa dopiero po ukończeniu.
- Pathfinding i blokady uwzględniają nowe budynki.

### Faza 5 - Rozkazy, ruch i walka

- Ujednolicić model rozkazów.
- Dodać stop, hold, patrol, attack-move, gather-return, build, repair.
- Dodać autoatak z jasnym priorytetem.
- Dodać zachowanie po śmierci celu.
- Dodać lekkie usprawnienia ruchu grupowego.
- Oddzielić wizualne pociski od deterministycznych obrażeń.
- Dodać testy walki bez renderowania.

### Faza 6 - Fog, obserwacje i API treningowe

- Sformalizować wersję schematu obserwacji.
- Rozszerzać action masks przy każdej mechanice.
- Dodać obserwacje: full debug, team, fog-limited, spatial grid.
- Dodać scenariusze treningowe z rewardami.
- Dodać benchmark headless steps/sec.
- Dodać batch runner dla wielu epizodów.
- Gymnasium/PettingZoo dopiero po stabilizacji natywnego API.

### Faza 7 - Pełny UI gry

- Command panel dla wybranych jednostek i budynków.
- Produkcja jednostek z UI.
- Budowa budynków z UI.
- Komendy z minimapy.
- Koszty, populacja, kolejki i cooldowny.
- Komunikaty o braku zasobów, złym miejscu budowy itp.
- Podstawowe skróty klawiaturowe.

### Faza 8 - Mapy, scenariusze i balans

- Kilka map skirmish.
- Małe scenariusze treningowe.
- Metadata map: liczba graczy, start positions, zasoby, victory rules.
- Prosty scripted AI jako baseline.
- Pierwszy balans kosztów i statystyk.

### Faza 9 - Asset hooks i lekki polish

- Uporządkować assety runtime i development.
- Dodać manifest assetów, jeśli liczba plików wzrośnie.
- Dodać fallbacki dla brakujących assetów.
- Nie robić ciężkich animacji wymaganiem symulacji.
- Poprawiać UI/ikony tylko tam, gdzie pomaga to gameplayowi.

## 10. Najbliższy sprint

Status ostatnich zadań:

1. Prosta specyfikacja danych gry.
   Status: zrobione w `src/rts_nano/game/data.py`.

2. `ProductionSystem`.
   Status: zrobione dla kolejek peasantów w bazie.

3. Action masks w `RtsNanoEnv`.
   Status: pierwsza wersja zrobiona, wraz z powodami odmowy.

4. Deterministyczny replay.
   Status: test obejmuje ruch oraz kolejkowaną produkcję.

5. Anulowanie produkcji.
   Status: zrobione dla peasantów w bazie, z częściowym zwrotem zasobów,
   publiczną akcją API, maską akcji, obserwacją i UI command panel.

Następne rekomendowane zadanie:

6. Rozszerzyć produkcję poza peasantów w bazie.
   Status: zrobione dla Barracks, knightów i archerów, z map schema, map editor,
   action masks, obserwacjami i testami headless/env.

7. Budowanie struktur przez workerów.
   Status: zrobione dla Barracks z `ConstructionSystem`, `ConstructAction`,
   action mask, obserwacją progresu oraz testami headless/env.

8. House i model populacji.
   Status: zrobione. `ConstructionSystem` obsługuje House, schema/map editor
   znają `house`, a `population_cap` wynika z ukończonych budynków supportu.

9. Anulowanie budowy z refundem.
   Status: zrobione. `CancelConstructionAction`, action mask i testy headless/env
   obsługują niedokończone budynki.

10. UI placement.
   Status: pierwsza wersja zrobiona. Peasant ma przyciski budowy House/Barracks,
   kliknięcie w świecie odpala placement, a ghost pokazuje poprawność miejsca.

11. Stop order.
   Status: zrobione. `StopAction`, action mask, manager helper i hotkey `S`
   zatrzymują jednostki oraz czyszczą ich bieżące cele.

12. Następne rekomendowane zadanie: uporządkować command panel i hotkeye.
   Dodać skróty budowy, czytelniejsze komunikaty odmowy i bardziej kompletne
   przyciski dla hold/gather/return cargo/attack-move.

## 11. Definition of Done pełnej gry

- Człowiek może rozegrać skirmish lokalnie przeciwko drugiemu człowiekowi albo
  prostemu scripted AI.
- Gra ma jawne warunki zwycięstwa.
- Workerzy zbierają zasoby, budują budynki i wracają do pracy.
- Budynki produkują jednostki w kolejkach z kosztami i czasem.
- Jednostki wspierają standardowy zestaw rozkazów RTS.
- Walka, ruch, fog i ekonomia działają w headless simulation.
- `RtsNanoEnv` pozwala resetować grę, wykonywać akcje, czytać obserwacje, maski,
  rewardy i stan terminalny.
- Symulacja działa bez okna i renderowania.
- Istnieją benchmarki steps/sec i testy deterministyczne.
- `ruff`, `ty`, `pytest`, `tox` i `pre-commit` przechodzą.

## 12. Ryzyka i kontrola

- Ryzyko: `GameManager` znowu urośnie.
  Kontrola: każda nowa mechanika przekrojowa trafia do systemu albo core module.

- Ryzyko: Pygame przecieka do API treningowego.
  Kontrola: testy headless nie mogą wymagać display surface, eventów ani assetów.

- Ryzyko: obserwacje będą zbyt drogie.
  Kontrola: benchmark obserwacji i warianty nieobrazowe jako domyślne.

- Ryzyko: pathfinding będzie bottleneckiem.
  Kontrola: mierzyć, potem cache, budżety, spatial index albo uproszczenia grup.

- Ryzyko: zakres urośnie za szybko.
  Kontrola: każda faza kończy się działającą grą, nawet prostą.

- Ryzyko: API będzie wygodne dla UI, ale niewygodne dla agentów.
  Kontrola: każda nowa mechanika dostaje DTO akcji, obserwację i test env.

## 13. Zasady dla przyszłych sesji i agentów

- Zacznij od przeczytania tego pliku i `ARCHITECTURE.md`.
- Sprawdź `git status` przed zmianami.
- Traktuj `EXECUTIVE_PLAN.md` jako śledzony dokument projektowy.
- Preferuj małe commity z zielonymi testami.
- Przy refaktorach zachowuj kompatybilność publicznego API, chyba że zmiana jest
  celowa i udokumentowana.
- Przy gameplayu zawsze dodawaj test headless.
- Nie dodawaj PyTorch/Gymnasium do core. Integracje przez adaptery.
- Po większej zmianie zaktualizuj plan.

## 14. Podejście agentic, MCP i lokalne modele

Dopuszczalne jest podejście agentic. Główny agent może rozdzielać pracę na małe,
jasno określone zadania i koordynować helperów, jeśli poprawia to tempo albo
utrzymuje kontekst w ryzach.

Dozwolone narzędzia pomocnicze:

- MCP tools i serwery mogą być używane do inspekcji lokalnych zasobów, przeglądarki,
  dokumentacji albo skonfigurowanego kontekstu projektu.
- Lokalne modele Ollama mogą być używane do ograniczonych zadań pomocniczych,
  szczególnie modele Gemma. Dobre zastosowania: streszczenie plików, review małej
  decyzji projektowej, porównanie alternatyw, szkic notatek.
- Wyniki helperów i lokalnych modeli nie są źródłem prawdy. Trzeba je sprawdzić
  względem repozytorium, testów i celów projektu.
- Kod z workflow agentic nadal wymaga normalnego review: przeczytać diff,
  uruchomić właściwe checki i trzymać zakres zmian.
- Narzędzia zewnętrzne nie mogą dodawać ciężkich zależności do core simulation.
  MCP, Ollama, Gemma, Gymnasium, PettingZoo i PyTorch należą poza rdzeń, chyba że
  istnieje wyraźna granica adaptera.

---

# RTS Nano - Executive Plan (English Working Version)

Last updated: 2026-05-20

This file is a tracked project plan. It exists to keep the implementation
direction, repository status, architectural decisions, and next work stages in
one shared place. It should be updated when the project direction, sprint scope,
or important repository state changes.

## 1. Product Goal

RTS Nano should become a fully functional RTS game with a feature level broadly
comparable to WarCraft II, without making animation polish or heavy audiovisual
production the main goal. The priority is complete gameplay functionality:
economy, production, construction, combat, unit orders, victory conditions, a
playable human UI, and a stable API that lets agents control the game.

Assets may be improved separately. The code should provide clear hooks for
better sprites, portraits, icons, and future asset packs, but gameplay delivery
must not depend on advanced animation. The simulation should be readable,
deterministic, and runnable without rendering.

The second core goal is to serve as an environment for training neural networks.
The game core must stay lightweight, easy to run across many instances, and
accessible through a stable API. The Pygame client is only one presentation layer
over the same game model; it must not be the source of truth for gameplay.

## 2. Hard Design Rules

1. Gameplay before animation.
   Complete mechanics take priority over sprite smoothness, effects, sound, and
   visual polish.

2. Simulation without renderer dependency.
   Agent training must not require a window, a Pygame surface, sprites, or mouse
   input. Pygame belongs in the UI/rendering layer, not in the simulation core.

3. Lightweight computation.
   Solutions must scale to many parallel instances. Avoid heavy physics systems,
   expensive image observations as the default API, unnecessary global O(N^2)
   loops, and unbudgeted work every tick.

4. Determinism.
   The same seed, map, and action sequence must produce the same result. This is
   essential for tests, agent debugging, and experiment comparison.

5. API-first.
   Every gameplay mechanic should be accessible through explicit actions,
   observations, and snapshots. A neural network should not need to read private
   UI objects or live Pygame state.

6. Small verified steps.
   Each larger stage should end with headless tests and a minimal playable check
   in the Pygame client.

## 3. Current Repository State

The project is a Python 3.14.4 package managed by `uv`/`hatchling`. Runtime uses
`pygame-ce`, imported as `pygame`. Code quality is enforced with `ruff`, `ty`,
`pytest`, `tox`, and `pre-commit`. LF line endings are enforced by
`.gitattributes` and `.editorconfig`.

Current main modules:

- `src/rts_nano/main.py`
  Starts Pygame, creates the window, runs the event/update/draw loop, and
  forwards input to the manager.

- `src/rts_nano/game/manager.py`
  Still owns most live game state: map, teams, resources, units, buildings,
  selection, camera, HUD, minimap, menu, projectiles, harvesting, and victory
  detection. This is the main candidate for continued decomposition.

- `src/rts_nano/game/orders.py`
  Contains the extracted `OrderSystem`. It handles unit/base queries and public
  orders: movement, target/attack, peasant production requests, and selection.

- `src/rts_nano/game/data.py`
  Static gameplay data for resources, unit costs, production timings,
  population, building roles, and future RTS roster expansion.

- `src/rts_nano/game/production.py`
  Lightweight `ProductionSystem` for base production queues. Peasant production
  now pays cost up front, reserves population through queued jobs, advances in
  headless ticks, and spawns only after the configured production time. Barracks
  can train basic military units. Unfinished buildings cannot produce units.

- `src/rts_nano/game/construction.py`
  Lightweight `ConstructionSystem` for worker-built structures. It currently
  supports Barracks and House construction: cost payment, terrain/collision
  placement validation, unfinished building state, build progress, cancellation
  with a partial refund, and activation on completion.

- `src/rts_nano/actions.py`
  Public action DTOs: `NoOpAction`, `MoveAction`, `AttackAction`, `GatherAction`,
  `DepositAction`, `BuildAction`, `ConstructAction`, `CancelProductionAction`,
  `SelectAction`, `ActionSpec`, and `WorldPoint`.

- `src/rts_nano/action_translation.py`
  `ActionTranslator` converts public API actions into manager/order system
  calls.

- `src/rts_nano/env.py`
  Thin `RtsNanoEnv` facade: `reset`, `step`, `observe`, `available_actions`,
  `action_mask`, `reward`, and `close`. This is the current entry point for
  future RL agents.

- `src/rts_nano/game/observations.py`
  Observation snapshots and entity ID mapping: `Observation`, `EntitySnapshot`,
  `TeamSnapshot`, `ProductionSnapshot`, and `EntityIdRegistry`.

- `src/rts_nano/headless.py`
  No-render wrapper used by tests and future RL work.

- `src/rts_nano/game/pathfinding.py`
  Grid A* pathfinding with an external passability predicate.

- `src/rts_nano/game/rules.py`
  Pure helper rules for distances, damage, height bonuses, clamping, and nearest
  entity selection.

- `src/rts_nano/game/terrain.py`
  Terrain map, height queries, ramps, water/blocking, and terrain rendering.

- `src/rts_nano/map_schema.py`, `src/rts_nano/map_editor.py`,
  `src/rts_nano/validate_map.py`
  JSON map format, validation, and map editor.

- `src/rts_nano/game/assets/entities/`
  Entity classes: units, buildings, resources, and shared base classes.

Last known quality state from the previous implementation session:
`ruff`, `ty`, `pytest`, `tox`, and `pre-commit` passed. Documentation-only
changes do not require the full test suite, but code changes should preserve
this baseline.

## 4. What Already Works

- Basic Pygame game loop.
- JSON map loading and schema validation.
- Map editor.
- Terrain with water, ramps, height, and blocking.
- Units: peasant, knight, archer, mage.
- Base building.
- Resources: wood and crystal.
- Basic harvesting and depositing.
- Basic queued peasant production from the base.
- Basic queued knight and archer production from Barracks.
- Worker construction for Barracks: cost payment, API placement,
  terrain/collision validation, unfinished building progress, and activation on
  completion.
- Worker construction for House and population capacity from completed
  buildings: Base provides 10 support, House provides 6.
- Cancellation of unfinished construction with a partial resource refund through
  the API/env.
- First Pygame UI placement path: Peasant has House/Barracks build commands,
  world clicks place buildings, and a ghost preview shows placement validity.
- Production cancellation with a partial resource refund.
- Static gameplay data for current units/buildings and near-term RTS roles.
- Unit selection and movement orders.
- Basic A* pathfinding.
- Basic combat and targeting.
- Stop command through API/env, manager helper, and `S` hotkey.
- Fog of war in the game client.
- Headless simulation wrapper.
- Early public agent API through `RtsNanoEnv`.
- Stateful action masks with denial reasons for agent integrations.
- Observation snapshots that do not directly expose UI objects.
- Observation snapshots include production queues and population caps.
- Tests for maps, terrain, pathfinding, the headless wrapper, and env behavior.

## 5. Largest Gaps Against The Goal

### 5.1 Economy and Production

- The game needs a complete catalog of costs, build times, and tech
  requirements.
- Unit production has an initial queue/time implementation for peasants, but
  includes cancellation, partial refunds, and Barracks military production.
  Barracks can now be constructed by workers; additional production buildings
  and tech requirements are still missing.
- Buildings need RTS roles: base, population/support building, military
  production, upgrades, and defensive structure.
- Population capacity is started: completed support buildings provide cap, but
  balance, UI, and tech requirements still need refinement.
- Recommended resource direction: keep `wood` and `crystal` for simplicity and
  give them roles similar to wood and gold.

### 5.2 Construction

- Barracks and House have the first API/env placement path with cost, terrain,
  and collision validation.
- Construction takes time, exposes progress in observations, and activates
  building effects only after completion.
- UI placement has started, but richer UX messages, build hotkeys, full
  footprints, and additional building types are still missing.
- Buildings must block pathfinding according to their footprint.

### 5.3 Orders and Unit Behavior

- Stop command is implemented. Still needed: hold position, patrol,
  follow/guard, attack-move, repair/build, gather, and return cargo.
- Priorities must be unified: manual player order, auto-attack, return to work,
  path replanning, target death.
- The project needs a coherent `Order`/`Command` model instead of scattered flags
  across entities.

### 5.4 Combat

- Combat must be deterministic, testable, and independent from visual effects.
- Needed systems: damage/range types, cooldowns, target acquisition,
  fog-aware targeting, friendly fire if selected, and clear death rules.
- Projectiles may remain visual, but damage application must not depend on
  rendering.

### 5.5 Fog Of War And Information

- The player and agents need separate views: full state for debugging, team
  observation, and fog-limited observation.
- The game should support memory of last-seen buildings/terrain like classic RTS
  games.
- RL observations should work without images: entities, tile maps, resources,
  queues, and action masks.

### 5.6 Human UI

- The game needs a complete command panel for units and buildings.
- The UI needs production, building placement, minimap commands, costs,
  production progress, and population display.
- Control groups, type selection, double-click selection or basic hotkeys should
  be added at a practical level.
- The UI should be functional and clear, not visually heavy.

### 5.7 Training API

- The observation and action contracts need formal versioning.
- Action masks are required so agents do not have to guess legal actions.
- Training scenarios, reward functions, and steps/sec benchmarks are needed.
- Gymnasium or PettingZoo adapters are useful later, after the native lightweight
  API stabilizes.

## 6. Target Architecture

The game should move toward three clear layers.

### 6.1 Core Simulation

This layer has no Pygame, no images, and no UI. It owns the true game state.

Proposed elements:

- `GameState`
  World data: map, tick, seed, teams, entities, resources, queues, fog, and
  victory state. It should be snapshot-friendly and testable.

- `Simulation`
  High-level facade: `reset`, `step`, `apply_action`, `observe`,
  `available_actions`, and `is_done`.

- Systems:
  `OrderSystem`, `EconomySystem`, `ProductionSystem`, `ConstructionSystem`,
  `CombatSystem`, `MovementSystem`, `PathingSystem`, `VisionSystem`, and
  `VictorySystem`.

- Entities as data plus minimal local behavior.
  Cross-entity rules should move to systems instead of making `GameManager`
  larger again.

### 6.2 Adapters

Integration layer:

- `RtsNanoEnv` for the native training API.
- Future `GymnasiumRtsNanoEnv` or `PettingZooRtsNanoEnv`.
- Pygame adapter for rendering and human input.
- Map and asset loading adapters.

### 6.3 Presentation/UI

Pygame layer:

- Draw map and entities.
- HUD, minimap, command panel.
- Mouse/keyboard input translated into the same action DTOs used by agents.
- Visual effects as consequences of simulation state only.

## 7. Neural Network API

The minimal long-term contract should look like this:

```python
env = RtsNanoEnv(config)
obs = env.reset(seed=123)

while not obs.done:
    mask = env.available_actions(team_id=0)
    action = policy(obs, mask)
    obs, reward, done, info = env.step(action)
```

Requirements:

- `reset(seed=...)` guarantees a deterministic start.
- `step(action)` advances exactly one tick or a configured fixed number of ticks.
- `observe(team_id=...)` returns a serializable snapshot, not live game objects.
- `available_actions`/`action_mask` describes legal actions in the current state.
- Entity IDs are stable during an episode.
- Observation variants may include `full_state_debug`, `team_state`,
  `fog_limited`, and `spatial_grid`.
- The default observation is not an image, so many-instance training remains
  lightweight.
- Image/screenshot observation can exist as an optional adapter, not as the
  default API.
- Core must not import PyTorch, Gymnasium, or PettingZoo. Those dependencies
  belong in optional adapters.

## 8. Performance And Training Scale

Measure first, optimize second. Required benchmarks:

- headless steps/sec for one instance,
- headless steps/sec for many instances in one process,
- pathfinding cost with many units,
- observation cost for full-state and fog-limited modes,
- memory per instance.

Implementation rules:

- Rendering never runs during training.
- Observations should reuse data already computed during the tick where possible.
- Pathfinding should gain budgets, caching, or path reuse for groups when unit
  counts grow.
- Add a spatial index/grid for neighbor, target, and collision queries once
  entity counts justify it.
- Avoid allocating large temporary structures every tick.
- Simulation should use a fixed timestep.
- Performance tests must not require a GPU or window.

## 9. Work Plan

### Phase 0 - Quality Baseline

Goal: keep the repository safe to refactor.

- Keep `ruff`, `ty`, `pytest`, `tox`, and `pre-commit` green.
- Update and commit `EXECUTIVE_PLAN.md` when direction, sprint scope, or important
  repository state changes.
- Add a headless test for each gameplay change.
- Avoid mixing architecture changes, gameplay changes, and asset changes in one
  large commit.

### Phase 1 - Gameplay Specification

Goal: close the minimal scope of the full game.

- Write `GAME_DESIGN.md` or a data module defining units, buildings, costs,
  timings, population, and requirements.
- Decide final roles for `wood` and `crystal`.
- Define the minimal building list:
  base, population/support building, military production building, upgrade
  building, defensive tower.
- Define the minimal unit list:
  worker, melee, ranged, special/caster, and possibly siege later.
- Define victory conditions:
  base elimination, all units/buildings elimination, timeout/scenario rules.
- Define training scenarios:
  harvest, build order, micro combat, rush defense, full skirmish.

### Phase 2 - Extract The Simulation Core

Goal: reduce `GameManager` responsibility and prepare for many instances.

- Create an explicit `GameState` or equivalent state container without UI
  dependencies.
- Move gameplay update/tick mechanics into Pygame-independent systems.
- Turn `GameManager` into a Pygame adapter over `Simulation`, not the owner of all
  gameplay logic.
- Unify entity IDs and access through a repository/registry.
- Move victory detection into `VictorySystem`.
- Add deterministic replay tests: seed + actions = same final snapshot.

### Phase 3 - Full Economy And Production

Goal: create a real strategic loop.

- Add a cost and payment system.
- Add unit production queues.
- Add production times and progress.
- Add a population cap.
- Add production cancellation.
- Add clear action denial reasons for API and UI.
- Extend observations with queues, population, income/cargo, and available
  production options.

### Phase 4 - Building Construction

Goal: workers can expand the base on the map.

- Add placement mode in API and UI.
- Add building footprints.
- Validate terrain, collisions, resources, and fog during placement.
- Add unfinished buildings with progress.
- Workers perform construction over time.
- Buildings become active only after completion.
- Pathfinding and blocking account for new buildings.

### Phase 5 - Orders, Movement, And Combat

Goal: units behave like classic RTS units.

- Unify the order model.
- Add stop, hold, patrol, attack-move, gather-return, build, and repair.
- Add auto-attack with clear priorities.
- Add behavior for target death.
- Add lightweight group movement improvements.
- Separate visual projectiles from deterministic damage.
- Add combat tests without rendering.

### Phase 6 - Fog, Observations, And Training API

Goal: agents receive stable, complete, cheap data.

- Formalize the observation schema version.
- Add action masks.
- Add observation modes: full debug, team, fog-limited, spatial grid.
- Add training scenarios with rewards.
- Add headless steps/sec benchmarks.
- Add a batch runner for many episodes.
- Consider Gymnasium/PettingZoo adapters only after the native API stabilizes.

### Phase 7 - Full Game UI

Goal: a human can play a normal skirmish.

- Command panel for selected units and buildings.
- Unit production from UI.
- Building placement from UI.
- Minimap click/command.
- Costs, population, queues, and cooldown indicators.
- Error messages for no resources, invalid placement, and similar cases.
- Basic keyboard shortcuts.

### Phase 8 - Maps, Scenarios, And Balance

Goal: the game has content for playing and training.

- Prepare several skirmish maps.
- Prepare small training scenarios.
- Add map metadata: player count, start positions, resources, victory rules.
- Add a simple scripted AI opponent for testing and baseline comparisons.
- Establish first-pass balance for costs and stats.

### Phase 9 - Asset Hooks And Lightweight Polish

Goal: make asset replacement easy without affecting mechanics.

- Organize runtime and development asset directories.
- Add an asset manifest if the number of icons/sprites grows.
- Add fallbacks for missing assets.
- Do not make heavy animation a simulation requirement.
- Improve UI and icon clarity only where it helps gameplay.

## 10. Recommended Next Sprint

The best next step is work that improves both gameplay functionality and the
training API.

1. Add a simple game data specification.
   One module or document defining units, buildings, costs, times, population,
   and requirements. Status: implemented as `src/rts_nano/game/data.py`.

2. Add `ProductionSystem`.
   Start with the base production queue and peasant costs, then extend to more
   buildings and units. Status: implemented for base peasant queues.

3. Add action masks to `RtsNanoEnv`.
   Agents should know whether they can build, produce, move, attack, or harvest
   in the current state. Status: initial `action_mask` implemented.

4. Add a deterministic episode test.
   The same seed and action list must produce identical final observations.
   Status: implemented for movement plus queued production.

5. Continue extracting simulation state from `GameManager`.
   Avoid a large rewrite. Extract one system at a time: production, economy,
   construction, combat.

6. Production cancellation and clearer production UI feedback.
   Status: implemented for base peasant queues with partial refunds, API action,
   action mask support, observations, and command-panel cancellation.

7. Next task: expand production beyond base peasants.
   Status: implemented for Barracks, knights, and archers, including map schema,
   map editor, action masks, observations, and headless/env tests.

8. Worker construction for structures.
   Status: implemented for Barracks with `ConstructionSystem`,
   `ConstructAction`, action mask support, progress observations, and
   headless/env tests.

9. House and the target population model.
   Status: implemented. `ConstructionSystem` supports House, the schema/map
   editor know `house`, and `population_cap` comes from completed support
   buildings.

10. Construction cancellation with refund.
   Status: implemented. `CancelConstructionAction`, action mask support, and
   headless/env tests cover unfinished buildings.

11. UI placement.
   Status: first version implemented. Peasant has House/Barracks build buttons,
   world clicks perform placement, and a ghost preview shows placement validity.

12. Stop order.
   Status: implemented. `StopAction`, action mask support, manager helper, and
   `S` hotkey stop units and clear their current targets.

13. Next task: clean up the command panel and hotkeys.
   Add build shortcuts, clearer denial messages, and more complete buttons for
   hold/gather/return cargo/attack-move.

## 11. Definition Of Done For The Full Game

The game can be considered functionally complete when:

- A human can play a skirmish locally against another human or a simple scripted
  AI.
- The game can be won through explicit victory conditions.
- Workers gather resources, construct buildings, and return to work.
- Buildings produce units through queues with costs and time.
- Units support the standard RTS command set.
- Combat, movement, fog, and economy work in headless simulation.
- `RtsNanoEnv` lets an agent reset the game, execute actions, read observations,
  action masks, rewards, and terminal state.
- Simulation works without a window and without rendering.
- Steps/sec benchmarks and deterministic tests exist.
- `ruff`, `ty`, `pytest`, `tox`, and `pre-commit` pass.

## 12. Risks And Controls

- Risk: `GameManager` grows again.
  Control: every new cross-entity mechanic goes into a system or core module;
  `GameManager` only adapts UI.

- Risk: Pygame leaks into the training API.
  Control: headless tests must not require display surfaces, events, or assets.

- Risk: observations become too expensive.
  Control: benchmark observation modes and keep non-image variants as default.

- Risk: pathfinding becomes the bottleneck.
  Control: measure first, then add caching, budgets, spatial indexing, or group
  simplifications.

- Risk: scope expands too much at once.
  Control: each phase should end with a working game, even if still simple.

- Risk: the API is convenient for UI but awkward for agents.
  Control: each new mechanic needs an action DTO, observation data, and env test.

## 13. Rules For Future Sessions And Agents

- Start by reading this file and `ARCHITECTURE.md`.
- Check `git status` before making changes.
- Treat `EXECUTIVE_PLAN.md` as a tracked project document and update it when the
  plan or implementation state changes.
- Prefer small commits with green tests.
- Preserve public API compatibility during refactors unless the change is
  deliberate and documented.
- Always add headless tests for gameplay changes.
- Keep PyTorch/Gymnasium dependencies out of core. Use optional adapters for
  integrations.
- After larger changes, update this plan if the game state or work order changed.

## 14. Agentic Work, MCP, And Local Models

Agentic execution is allowed for this project. A lead agent may split work into
small, scoped tasks and coordinate helper agents when that improves throughput or
keeps context focused.

Allowed support tools:

- MCP tools and servers may be used to inspect local resources, browser state,
  docs, or other configured project context.
- Local Ollama models may be used for bounded support tasks, especially Gemma
  models. Good uses include summarizing files, reviewing a small design decision,
  comparing alternatives, or generating draft notes.
- Helper agents and local models must not be treated as final authority. Their
  output should be checked against the repository, tests, and project goals.
- Any code produced through an agentic workflow still needs normal engineering
  review: read the diff, run the relevant checks, and keep changes scoped.
- Do not let external tool use add heavy runtime dependencies to the game core.
  MCP, Ollama, Gemma, Gymnasium, PettingZoo, and PyTorch belong outside the core
  simulation unless there is an explicit adapter boundary.
