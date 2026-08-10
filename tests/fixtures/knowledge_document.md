# RAG Knowledge Document: GDevelop 5 Event Sheet Execution Order and Runtime Execution Pipeline

## 1. Metadata

### Chunk ID

`gdevelop5-event-sheet-execution-order-runtime-pipeline-rag-001`

### Topic

GDevelop 5 Event Sheet Execution Order, Frame Lifecycle, Scene Lifecycle, Runtime Execution Pipeline, Object Picking, Event Evaluation, Behaviors, Timers, Scene Transitions, and Runtime-Specific Behavior in GDJS and GDCpp.

### Category

Game Engine Internals / Runtime Execution Model / Event System / GDevelop 5 / Retrieval-Augmented Generation Knowledge Document.

### Difficulty

Advanced.

This document is intended for AI systems answering detailed technical questions about GDevelop 5 runtime execution, event order, state management, timing, and engine internals.

### Source Type

Provided technical exposition derived from claims about official GDevelop documentation, official engine source, official examples, and verified community patterns.

The provided source includes bracketed citation markers, but no bibliography or resolvable source list is included. Therefore, individual claims in this document are classified as **Provided Source Assertion** unless otherwise noted.

### Runtime Authority

For latest stable GDevelop 5 behavior, the provided source designates the JavaScript runtime, GDJS, as the primary authoritative runtime.

The native C++ runtime, GDCpp, is secondary and historical. GDJS and GDCpp behavior must not be merged or assumed identical.

### Evidence Classification

| Evidence Level Used in This Document | Meaning |
|---|---|
| PROVIDED SOURCE ASSERTION | The claim appears in the provided source text. |
| PROVIDED SOURCE COMMUNITY OBSERVATION | The provided source attributes the claim to community-observed patterns. |
| UNSPECIFIED BY PROVIDED SOURCE | The provided source does not contain enough information to state the behavior. |
| DERIVED FROM PROVIDED SOURCE | A logical clarification directly derived from statements already present in the provided source. |

### Tags

`GDevelop`, `GDevelop 5`, `GDJS`, `GDCpp`, `event sheet execution order`, `frame lifecycle`, `scene lifecycle`, `event evaluation`, `conditions`, `actions`, `parent events`, `sub-events`, `Trigger Once`, `Repeat event`, `While event`, `For Each event`, `object picking`, `instance selection`, `variables`, `global variables`, `scene variables`, `object variables`, `local variables`, `behaviors`, `doStepPreEvents`, `doStepPostEvents`, `physics timing`, `animation timing`, `camera timing`, `rendering pipeline`, `timers`, `Scene Timers`, `Object Timers`, `Wait action`, `scene transition`, `Change the scene`, `object creation`, `object destruction`, `external events`, `disabled events`, `event groups`, `performance`, `game loop`, `tick`, `runtime execution`, `AI retrieval document`.

### Keywords

GDevelop 5 event execution order; GDevelop runtime execution; GDevelop frame lifecycle; GDevelop scene lifecycle; GDevelop event sheet order; GDevelop event evaluation pipeline; GDevelop conditions and actions; GDevelop parent events; GDevelop sub-events; GDevelop Trigger Once; GDevelop Repeat event; GDevelop While event; GDevelop For Each event; GDevelop object picking; GDevelop instance picking; GDevelop instance filtering; GDevelop variable evaluation order; GDevelop global variables; GDevelop scene variables; GDevelop object variables; GDevelop local variables; GDevelop behavior execution; GDevelop doStepPreEvents; GDevelop doStepPostEvents; GDevelop physics update timing; GDevelop animation update timing; GDevelop camera update timing; GDevelop rendering pipeline; GDevelop TimeDelta; GDevelop asynchronous actions; GDevelop timers; GDevelop Scene Timers; GDevelop Object Timers; GDevelop delayed actions; GDevelop Wait X seconds; GDevelop scene changes; GDevelop Change the scene; GDevelop object creation timing; GDevelop object destruction timing; GDevelop event groups; GDevelop disabled groups; GDevelop external events; GDevelop execution order inside nested events; GDevelop function call order; GDevelop runtime lifecycle; GDevelop internal execution model; GDevelop GDJS; GDevelop GDCpp; GDevelop JavaScript runtime; GDevelop C++ runtime; GDevelop HTML5 runtime; GDevelop native runtime; GDevelop Pixi.js; GDevelop SFML; GDevelop game loop; GDevelop tick; GDevelop frame update; GDevelop per-frame events; GDevelop At the beginning of the scene; GDevelop scene initialization; GDevelop scene unloading; GDevelop state persistence; GDevelop global state; GDevelop scene state; GDevelop object state; GDevelop input polling; GDevelop keyboard input timing; GDevelop mouse input timing; GDevelop touch input timing; GDevelop collision evaluation; GDevelop physics forces; GDevelop physics torques; GDevelop camera position; GDevelop camera rotation; GDevelop camera zoom; GDevelop sprite animation; GDevelop animation frames; GDevelop event functions; GDevelop custom behaviors;

GDevelop external event links; GDevelop event debugging; GDevelop event performance; GDevelop event sheet optimization; GDevelop execution bugs; GDevelop timing bugs; GDevelop event order bugs.

### Alternative Terms and Search Aliases

GDevelop event order; GDevelop execution order; GDevelop event processing order; GDevelop event evaluation order; GDevelop event loop; GDevelop game loop; GDevelop main loop; GDevelop frame loop; GDevelop tick update; GDevelop frame update; GDevelop runtime pipeline; GDevelop engine pipeline; GDevelop per-frame execution; GDevelop frame lifecycle; GDevelop scene start; GDevelop scene initialization; GDevelop scene begin; GDevelop beginning of scene; GDevelop scene load; GDevelop scene unload; GDevelop scene change; GDevelop scene transition; GDevelop change scene; GDevelop switch scene; GDevelop move to another scene; GDevelop event conditions; GDevelop event actions; GDevelop event logic; GDevelop event tree; GDevelop nested events; GDevelop event hierarchy; GDevelop parent event; GDevelop child event; GDevelop subevent; GDevelop sub-event; GDevelop disabled event; GDevelop disabled event group; GDevelop event group; GDevelop external event sheet; GDevelop external events; GDevelop linked events; GDevelop event function; GDevelop behavior callback; GDevelop pre-events behavior step; GDevelop post-events behavior step; GDevelop object filtering; GDevelop instance filtering; GDevelop object selection; GDevelop picked objects; GDevelop picked instances; GDevelop Trigger Once; GDevelop one-shot event; GDevelop run once; GDevelop execute once; GDevelop Repeat; GDevelop loop event; GDevelop While; GDevelop conditional loop; GDevelop For Each; GDevelop per-object loop; GDevelop for each object; GDevelop timer; GDevelop scene timer; GDevelop object timer; GDevelop countdown; GDevelop delay; GDevelop Wait action; GDevelop delayed execution; GDevelop asynchronous execution; GDevelop async action; GDevelop global variable; GDevelop game variable; GDevelop persistent variable; GDevelop scene variable; GDevelop object variable; GDevelop instance variable; GDevelop local variable; GDevelop temporary variable; GDevelop variable scope; GDevelop state management; GDevelop save state; GDevelop carry data between scenes; GDevelop persist score;

GDevelop persist health; GDevelop persist inventory; GDevelop physics step; GDevelop physics timing; GDevelop collision timing; GDevelop animation timing; GDevelop sprite animation update; GDevelop camera update; GDevelop camera follow timing; GDevelop render order; GDevelop draw order; GDevelop rendering timing; GDevelop input timing; GDevelop keyboard timing; GDevelop mouse timing; GDevelop touch timing; GDevelop GDJS runtime; GDevelop JavaScript engine; GDevelop TypeScript runtime; GDevelop GDCpp runtime; GDevelop C++ engine; GDevelop native export runtime; GDevelop Pixi.js renderer; GDevelop SFML renderer.

### Related Topics

GDevelop event system; GDevelop behaviors; GDevelop physics behavior; GDevelop animation system; GDevelop camera system; GDevelop variables; GDevelop timers; GDevelop scene management; GDevelop external events; GDevelop event functions; GDevelop performance optimization; GDevelop debugging; GDevelop runtime exports; GDevelop HTML5 exports; GDevelop native exports; GDevelop object lifecycle; GDevelop input handling; GDevelop collision detection; GDevelop rendering pipeline.

## 2. Overview

GDevelop 5 executes game logic using a frame-based runtime model. The engine repeatedly processes frames, and each frame advances the game state by evaluating events, updating behaviors and subsystems, and rendering the result.

The provided source states that GDevelop’s central logic system is the event system. An event consists of conditions and actions. During each frame, the engine evaluates the event sheet from top to bottom. Event order does not create a global priority schedule where some events are checked earlier in time than others in a way that skips the rest of the sheet. Instead, all events are checked every frame, and the importance of vertical order comes from sequential state dependency: events higher in the sheet can change variables, objects, or scene state before lower events are evaluated within the same frame.

The primary runtime for current GDevelop 5 behavior is GDJS, the JavaScript/TypeScript runtime used for HTML5 and modern exports. The secondary runtime is GDCpp, the historical native C++ runtime associated with SFML and native executables. The provided source explicitly states that GDJS is authoritative for latest stable GDevelop 5 releases and that GDJS and GDCpp behavior must not be merged.

The document covers the scene lifecycle, frame lifecycle, event evaluation pipeline, object picking, parent and sub-event execution, special event types such as Trigger Once, Repeat, While, and For Each, variable scopes, behavior callbacks, timers, delayed execution, object creation and destruction timing, scene transitions, physics timing, animation timing, camera timing, rendering timing, and common timing-related mistakes.

The provided source does not specify every low-level implementation detail. Where information is missing, this document explicitly marks the detail as unspecified.

## 3. Evidence Classification and Source Limitations

### 3.1 Evidence Basis

The provided source claims to use:

- Official GDevelop documentation.
- Official examples.
- Official engine source.
- Official runtime implementation.
- Verified community patterns.

However, the provided source does not include a resolvable bibliography. Bracketed citation markers appear in the source text, but they cannot be independently resolved from the provided excerpt.

Therefore, this RAG document treats the content as **Provided Source Assertion** rather than independently verified official documentation.

### 3.2 Runtime Priority

The provided source establishes the following runtime priority:

1. **GDJS**, the GDevelop JavaScript runtime, is primary.
2. **GDCpp**, the native C++ runtime, is secondary.
3. Shared engine concepts and official documentation are used where applicable.

When GDJS and GDCpp differ, the difference must be documented separately. The latest stable GDevelop 5 behavior should be attributed primarily to GDJS.

### 3.3 Community Observations

The provided source allows community-observed behavior only when it is reproduced by multiple developers and supported by GitHub issues, official forum discussions, or repeatable testing.

In this document, community-derived statements are labeled as:

`PROVIDED SOURCE COMMUNITY OBSERVATION`

Community observations are not presented as official engine behavior unless the provided source explicitly states that they are official.

### 3.4 Missing Information

The provided source does not specify all details requested by the broader topic. Missing or underspecified areas include:

- Exact low-level call stack of the GDevelop runtime.
- Exact atomic ordering of all physics, animation, behavior, camera, and rendering subsystem updates.
- Exact implementation of inverted conditions.
- Exact implementation of TimeDelta().
- Exact internal scheduler implementation for delayed actions.
- Exact execution order inside all Event Functions beyond named behavior callbacks.
- Exact execution details of Include Events as a distinct event type.
- Exact collision evaluation internals.
- Exact version numbers for runtime differences.
- Exact affected versions for community-reported issues.
- Exact implementation differences between GDJS and GDCpp beyond architectural description.

Where these topics appear, this document states that the provided source does not specify them.

## 4. Definitions

### 4.1 Frame

A frame is one iteration of the engine’s main update cycle. GDevelop processes the game state once per frame and then renders the result.

### 4.2 Tick

A tick is synonymous with a frame update in this context. It represents one pass through the runtime update pipeline.

Synonyms: frame update, game loop iteration, runtime step.

### 4.3 Game Loop

The game loop is the continuous engine process that updates game logic and renders the game. The provided source states that the loop commonly targets the display refresh rate, often approximately 60 frames per second.

### 4.4 Event Sheet

An event sheet is the container for GDevelop event logic. It contains events made of conditions and actions, as well as special event types such as parent events, sub-events, Repeat events, While events, For Each events, and disabled events or groups.

### 4.5 Event

An event is a logical unit containing conditions and actions. If the event’s conditions are true, the engine executes the event’s actions.

### 4.6 Condition

A condition is a test evaluated by the engine. Conditions can test object state, variable state, input state, scene state, timer state, or other runtime properties.

### 4.7 Action

An action is an operation executed by the engine when the event’s conditions are satisfied. Actions can modify objects, variables, scenes, cameras, animations, timers, sounds, and other runtime state.

### 4.8 Parent Event

A parent event is an event that can contain sub-events. Sub-events are evaluated only if the parent event’s conditions are true.

### 4.9 Sub-event

A sub-event is an event nested under a parent event. The provided source states that sub-events inherit the conditions of their parents and are evaluated only when the parent event is true.

### 4.10 Object Picking

Object picking is the process by which conditions select or filter object instances. Later conditions and actions operate on the set of instances picked by earlier conditions.

Alternative terms: instance selection, object filtering, instance filtering.

### 4.11 Trigger Once

Trigger Once is a condition mechanism that prevents the same actions from executing repeatedly while the triggering conditions remain true.

### 4.12 Repeat Event

A Repeat event executes its actions a fixed number of times within a single frame.

### 4.13 While Event

A While event executes its actions repeatedly while its condition remains true. The provided source states that While loops execute synchronously within a single frame and can freeze the game if intensive or infinite.

### 4.14 For Each Event

A For Each event iterates over a collection of picked object instances. Its internal actions operate on one specific instance at a time.

### 4.15 GDJS

GDJS is the GDevelop JavaScript/TypeScript runtime. The provided source states that GDJS is the primary runtime for latest stable GDevelop 5 behavior and is associated with Pixi.js rendering and HTML5 exports.

### 4.16 GDCpp

GDCpp is the historical native C++ runtime. The provided source states that GDCpp is associated with SFML and native executables for Windows, macOS, and Linux.

### 4.17 Scene

A scene is a playable or logical section of a GDevelop project. Scenes contain objects, variables, behaviors, event sheets, cameras, and rendering state.

### 4.18 Scene Lifecycle

The scene lifecycle is the sequence from scene loading and initialization, through active frame updates, to scene transition and unloading.

### 4.19 At the beginning of the scene

“At the beginning of the scene” is a scene initialization event phase. The provided source states that these events run only once, on the first frame of the scene’s life.

### 4.20 Scene Timer

A Scene Timer is a timer scoped to the current scene. The provided source states that scene timers count upward from zero.

### 4.21 Object Timer

An Object Timer is a timer attached to a specific object instance.

### 4.22 Wait X seconds

“Wait X seconds” is an action that delays part of an event sequence. The provided source states that Wait pauses the execution of the event sheet for the specified duration while the rest of the game continues running.

### 4.23 Global Variable

A global variable persists throughout the entire game. The provided source states that global variables are essential for carrying state between scenes.

### 4.24 Scene Variable

A scene variable exists for the lifetime of a scene. The provided source states that scene variables are destroyed when the scene is unloaded.

### 4.25 Object Variable

An object variable is attached to a specific object instance. The provided source states that object variables persist as long as that instance exists.

### 4.26 Local Variable

A local variable is temporary. The provided source states that local variables only exist for the duration of a single event block.

### 4.27 Behavior

A behavior is a reusable component that adds functionality to objects. Examples mentioned by the provided source include platformer movement and physics simulation.

### 4.28 doStepPreEvents

`doStepPreEvents` is a behavior callback method called before the main event evaluation step.

### 4.29 doStepPostEvents

`doStepPostEvents` is a behavior callback method called after the main event evaluation step.

### 4.30 External Events

External events are event sheets used to modularize logic. The provided source states that external events allow large event sheets to be broken into smaller pieces and are included where needed.

### 4.31 Disabled Event or Disabled Group

A disabled event or disabled group is skipped by the engine during evaluation. The provided source states that events and groups can be manually disabled using a checkbox.

## 5. Core Concepts

### 5.1 GDevelop Uses a Frame-Based Execution Model

GDevelop 5 processes the game world once per frame. Every frame, the engine advances game state and renders the result.

The provided source states that the engine maintains a continuous loop, often called the game loop, which repeatedly executes a fixed sequence of steps.

This means:

- Game logic is not event-driven in the sense of running only when something changes.
- Event sheets are evaluated repeatedly, once per frame.
- Timing-dependent behavior depends on frame updates.
- Object state, variables, and scene state are processed in a per-frame pipeline.

### 5.2 Event Sheets Are Evaluated Top to Bottom Every Frame

The provided source states that GDevelop evaluates every event in an event sheet from top to bottom at the beginning of each frame.

Important consequence:

- Event order does not mean that an event is globally scheduled to run at a different time.
- All events are checked every frame.
- The vertical order matters because earlier events can modify state that later events read during the same frame.

Example derived from the provided source:

If an event higher in the sheet creates an object, a lower event can interact with that object during the same frame because object creation is immediate within the event evaluation phase.

### 5.3 GDJS Is the Primary Runtime for Latest Stable GDevelop 5

The provided source states that GDJS is the primary reference runtime for GDevelop 5. GDJS is a JavaScript/TypeScript runtime and powers exported HTML5 games.

GDJS is authoritative for latest stable GDevelop behavior.

### 5.4 GDCpp Is Secondary and Historical

The provided source states that GDCpp is the native C++ runtime historically used for native executables. It uses SFML for rendering and windowing, while GDJS uses Pixi.js.

GDCpp behavior must not be assumed identical to GDJS behavior.

### 5.5 Scene Lifecycle Controls State Lifetime

Scene state is bounded by the scene lifecycle.

When a scene loads:

- Objects are instantiated.
- Object properties are initialized.
- Variables are set to default values.
- “At the beginning of the scene” events run once on the first frame.

When a scene changes:

- The current scene is unloaded.
- Objects are removed.
- Scene-scoped variables are destroyed.
- Sounds or music tied to the scene are stopped.

Therefore, data that must persist across scenes must be copied to global variables before the scene transition.

### 5.6 The Frame Pipeline Contains Multiple Ordered Phases

The provided source describes a conceptual per-frame pipeline:

1. Pre-step callbacks.
2. Main event sheet evaluation.
3. Post-step callbacks.
4. Physics update.
5. Animation update.
6. Camera update.
7. Rendering.
8. Input polling feeding later event evaluation.

The exact atomic order of some subsystems is not fully specified by the provided source. The pipeline should be treated as a high-fidelity conceptual model, not a verbatim source-code trace.

### 5.7 Conditions Use Implicit AND Evaluation

Within a single event, conditions are implicitly connected by AND logic.

The provided source states:

- Conditions are tested in the order they appear.
- If any condition fails, the event is false.
- If the event is false, its actions are skipped.

### 5.8 Object Picking Filters Instances During Condition Evaluation

Object picking is a central execution concept.

Earlier conditions can narrow the set of object instances available to later conditions and actions.

The provided source gives an example:

1. A condition such as “Player object is overlapping Enemy object” picks Player instances that overlap Enemy instances.
2. A later condition testing Player health is then evaluated only against the already-picked Player instances.

This creates a filtering pipeline inside an event.

### 5.9 Special Event Types Change Control Flow

GDevelop includes special event types:

- Trigger Once.
- Repeat.
- While.
- For Each.
- Parent/sub-event nesting.
- Disabled events and groups.
- OR-condition groups.

Each has specific execution semantics described in later sections.

### 5.10 State Is Scoped by Variable Lifetime

GDevelop variables have different lifetimes:

| Variable Scope | Lifetime According to Provided Source |
|---|---|
| Local variable | Duration of a single event block. |
| Object variable | As long as the object instance exists. |
| Scene variable | Lifetime of the scene. |
| Global variable | Entire game. |

Scene transitions destroy scene variables unless values are copied to global variables.

### 5.11 Behaviors Integrate Through Pre-Event and Post-Event Callbacks

Custom behaviors can define:

- `doStepPreEvents`
- `doStepPostEvents`

The provided source states that these methods are called before or after main event evaluation.

This means behavior logic can affect object state before normal events run, or finalize state after normal events run.

### 5.12 Time-Based Logic Uses Timers and Wait Actions

The provided source identifies:

- Scene Timers.
- Object Timers.
- “Wait X seconds”.

Scene timers count upward. To implement a countdown, the provided source states that a developer must compare `(Timer Value - Duration)` to zero.

“Wait X seconds” delays event-sheet execution but does not stop the rest of the game.

## 6. Technical Details

## 6.1 Runtime Architecture: GDJS and GDCpp

### GDJS: Primary JavaScript Runtime

The provided source states that GDJS is the GDevelop JavaScript runtime and the primary runtime for modern exports, especially HTML5 games.

Key attributes of GDJS according to the provided source:

- Primary language: TypeScript/JavaScript.
- Rendering technology: Pixi.js.
- Target exports: web, mobile, and desktop through frameworks.
- Authoritative status for latest stable GDevelop 5: yes.
- Actively maintained: yes.
- Editor integration: the GDevelop editor itself uses a modern web technology stack including React, Electron, and Pixi.js.

The provided source also states that GDJS implementation details such as namespaces, including `gdjs`, and class structures are documented extensively.

### GDCpp: Secondary Native C++ Runtime

The provided source states that GDCpp is the historical C++ runtime used for native executables.

Key attributes of GDCpp according to the provided source:

- Primary language: C++.
- Rendering/windowing technology: SFML.
- Target exports: native executables for Windows, macOS, and Linux.
- Authoritative status for latest stable release: no.
- Status: legacy or historical relative to GDJS.

### Runtime Comparison Table

| Feature | GDJS | GDCpp |
|---|---|---|
| Primary language | TypeScript/JavaScript | C++ |
| Target export | Web, mobile, desktop via frameworks | Native executables for Windows, macOS, Linux |
| Rendering engine | Pixi.js | SFML |
| Authoritative for latest stable GDevelop 5 | Yes | No |
| Maintenance focus | Actively developed and maintained | Legacy/historical |
| Editor integration | Aligned with React, Electron, Pixi.js stack | Not applicable |

### Runtime Differences

The provided source states that behavioral differences between GDJS and GDCpp are most likely to originate from their different backend implementations.

Possible sources of difference mentioned by the provided source include:

- Floating-point precision calculations.
- Timer granularity.
- Physics engine integration.
- Object picking handling.
- Event callback handling.

These are stated as possible sources of variation, not as a confirmed list of specific discrepancies.

### Runtime Rules

When answering questions about runtime behavior:

- Use GDJS as the authoritative runtime for latest stable GDevelop 5.
- Do not merge GDJS and GDCpp behavior.
- Do not assume both runtimes are identical.
- Explicitly identify the runtime when a difference is relevant.
- Do not speculate where source code or documentation is inconclusive.

## 6.2 Scene Lifecycle

### Scene Loading

The scene lifecycle begins when a scene is loaded into memory. This can happen at game start or because of a scene transition action.

During scene loading, the provided source states that the engine performs preparatory steps before the main game loop for that scene begins.

These steps include:

- Instantiating all objects defined in the scene layout.
- Initializing object properties.
- Setting variables to default values.

### Scene Initialization: At the Beginning of the Scene

After setup, the engine triggers “At the beginning of the scene” events.

- These events run only once.
- They run specifically on the first frame of the scene’s life.
- They are suitable for initial setup tasks.

Examples of appropriate initialization tasks derived from the provided source:

- Spawning enemies.
- Setting up the UI.
- Initializing scene-specific variables.

The provided source references the internal function:

`gdjs.evtTools.runtimeScene.sceneJustBegins`

This suggests a dedicated internal hook for detecting the first frame of a scene.

### Active Scene Phase

Once initialized, the scene enters its active state.

During the active state:

- The core game loop runs.
- Every frame, the engine evaluates all events in the scene event sheet from top to bottom.
- Player input, logic, and interactions update the game state.

### Object Creation During the Active Scene

Objects can be created dynamically using the “Create Object” action.

The provided source states that object creation is atomic within the event evaluation step.

- The object is instantiated immediately.
- The object is positioned immediately.
- Its initial actions are processed within the same tick.
- Subsequent conditions and actions in the same event sheet can interact with the newly created object during the same frame.

### Object Destruction During the Active Scene

Objects can be destroyed using the “Destroy” action.

The provided source states that destruction is instantaneous.

When an object is destroyed:

- It is removed from the scene’s active pool of objects.
- References to it become invalid for the remainder of that frame.

### Scene Termination and Unloading

The scene lifecycle ends when a scene transition is initiated, typically through the “Change the scene” action.

The provided source states that this action instructs the engine to unload the current scene and launch a new scene.

During unloading:

- All objects associated with the departing scene are removed from memory.
- Sounds or music tied to the scene are stopped.
- Scene-scoped variables are destroyed.

The provided source states that scene unloading helps prevent memory leaks and references a fix in recent versions, but it does not specify the exact affected versions.

### Persistence Across Scenes

Because scene variables and object instances are destroyed during scene unloading, state does not automatically persist across scenes.

To preserve data:

- Copy relevant values to global variables before changing scenes.
- Restore those values into objects or scene variables after the new scene loads.

Examples of persistent data mentioned by the provided source:

- Player score.
- Inventory.
- Player health.
- Level progression.
- Save/load data.

## 6.3 Frame Lifecycle

### Conceptual Frame Lifecycle

The provided source describes a frame lifecycle consisting of multiple phases. The following is a conceptual, source-derived model.

```text
Frame Start
  |
  v
Pre-step callbacks
  |
  v
Main event sheet evaluation
  |
  v
Post-step callbacks
  |
  v
Physics update
  |
  v
Animation update
  |
  v
Camera update
  |
  v
Rendering
  |
  v
Frame End
```

Input polling is also part of the frame lifecycle. The provided source states that input polling feeds data into event evaluation, but it gives slightly different descriptions of timing:

- Input is queried at the beginning of each frame.
- Input feeds the event evaluation phase.
- Input can allow first-event conditions to react to input from the previous frame.

Because of this, the exact internal placement of input polling relative to all other steps should be treated as partially unspecified.

### Pre-Step Callbacks

The frame begins with pre-step callbacks.

- Pre-step callbacks are called before main event evaluation.
- They are often used by extensions and custom behaviors.
- They can execute cleanup or preliminary calculations.
- They can help maintain clean state before the rest of the frame.

### Main Event Evaluation

After pre-step callbacks, the engine evaluates the scene event sheet.

- Events are evaluated from top to bottom.
- All events are evaluated every frame.
- Conditions are tested.
- Actions are executed when conditions are true.
- Special event types are handled inside this evaluation loop.

### Post-Step Callbacks

After event evaluation, the engine calls post-step callbacks.

- Post-step callbacks run after all events have finished.
- They are suitable for finalizing calculations.
- They can be used for logging state.
- They can perform cleanup that depends on changes made during the tick.

### Physics Update

The provided source states that the physics engine receives forces and torques applied during the event phase.

Then:

- Physics integrates forces.
- Physics updates positions and velocities.
- Physics resolves collisions.

The provided source states that the physics update typically occurs after main event evaluation, but it may happen in a separate synchronous pass.

The exact low-level collision evaluation internals are not specified.

### Animation Update

Animation updates occur after physics and before final rendering according to the provided source.

During animation update:

- Animations advance based on elapsed time and frame rate.
- Sprite frames can change.
- Visual effects can be applied.

The provided source states that animation playback is handled independently after an animation change action.

### Camera Update

Camera updates occur after object positions and animations have been processed.

- The camera is updated based on final object positions determined in previous steps.
- Camera properties such as position, rotation, and zoom level are finalized before rendering.
- The camera defines the visible portion of the game world.

### Rendering

Rendering is the final stage described by the provided source.

During rendering:

- The accumulated scene state is drawn to the screen.
- Final object positions are used.
- Final animation frames are used.
- Camera view is used.
- Lighting and visual state are rendered.

### Input Timing

The provided source states that input polling is a recurring task.

Input sources mentioned:

- Keyboard.
- Mouse.
- Touch screen.

Input data is translated into events or conditions such as:

- “Key 'W' is pressed”.
- “Keyboard 'D' is down”.

The provided source states that input polling occurs slightly before main event evaluation and can allow conditions in the first event of the frame to react to player input from the previous frame.

The exact low-level input timing is not fully specified.

## 6.4 Conceptual Execution Diagrams

### Scene Lifecycle Diagram

```text
Load Scene
  |
  v
Instantiate Scene Objects
  |
  v
Initialize Object Properties
  |
  v
Initialize Variables to Defaults
  |
  v
Run "At the beginning of the scene" events once
  |
  v
Enter Active Scene Loop
  |
  v
Evaluate Events Every Frame
  |
  v
Trigger Scene Change with "Change the scene"
  |
  v
Unload Scene
  |
  v
Remove Objects
  |
  v
Stop Scene-Tied Sounds/Music
  |
  v
Destroy Scene Variables
  |
  v
Load Next Scene
```

### Frame Lifecycle Diagram

```text
Frame Begin
  |
  v
Pre-Step Callbacks
  |
  v
Event Sheet Evaluation
  |
  v
Post-Step Callbacks
  |
  v
Physics Integration and Collision Resolution
  |
  v
Animation Update
  |
  v
Camera Update
  |
  v
Render Final Scene State
  |
  v
Frame End
```

### Event Evaluation Diagram

```text
Start Event Sheet Evaluation
  |
  v
For each event from top to bottom:
  |
  +--> Is event/group disabled?
  |      |
  |      +--> Yes: skip event
  |      |
  |      +--> No: evaluate conditions
  |
  +--> Are all conditions true under implicit AND?
         |
         +--> No: skip actions and sub-events
         |
         +--> Yes: execute actions
                   |
                   v
                Evaluate sub-events if present
```

### Object Picking Diagram

```text
Start With Candidate Object Instances
  |
  v
Condition 1 filters instances
  |
  v
Condition 2 filters remaining instances
  |
  v
Condition N filters remaining instances
  |
  v
If instances remain:
  |
  v
Actions operate on picked instances
```

## 6.5 Pseudocode for Runtime Flow

The following pseudocode is a conceptual model derived from the provided source. It is not a verbatim copy of engine source code.

### Frame-Level Pseudocode

```pseudocode
function runFrame():
    call preStepCallbacks()

evaluateEventSheet()

call postStepCallbacks()

updatePhysics()
    updateAnimations()
    updateCamera()

renderScene()
```

### Event Sheet Pseudocode

```pseudocode
function evaluateEventSheet():
    for each event in eventSheet from top to bottom:
        if event is disabled:
            continue

if evaluateEventConditions(event) == true:
            executeEventActions(event)
            evaluateSubEvents(event)
```

### Parent/Sub-Event Pseudocode

```pseudocode
function evaluateSubEvents(parentEvent):
    for each subEvent in parentEvent.subEvents:
        if subEvent is disabled:
            continue

if evaluateEventConditions(subEvent) == true:
            executeEventActions(subEvent)
            evaluateSubEvents(subEvent)
```

### Object Picking Pseudocode

```pseudocode
function evaluateEventConditions(event):
    pickedInstances = initialCandidateInstances(event)

for each condition in event.conditions:
        pickedInstances = condition.filter(pickedInstances)

if pickedInstances is empty:
            return false

event.pickedInstances = pickedInstances
    return true
```

### Variable Assignment Pseudocode

```pseudocode
function executeSetVariableAction(action):
    newValue = evaluateExpression(action.rightHandSideExpression)
    assign newValue to action.targetVariable
```

The provided source states that the right-hand expression is fully evaluated before assignment.

### Scene Transition Pseudocode

```pseudocode
function changeScene(newSceneName):
    unloadCurrentScene()
    loadScene(newSceneName)

function unloadCurrentScene():
    remove all scene objects
    stop scene-tied sounds and music
    destroy scene variables
```

## 6.6 Event Evaluation Pipeline

### Event Composition

An event consists of:

- Conditions.
- Actions.

If conditions are true, actions execute.

### Top-to-Bottom Evaluation

The provided source states that the engine evaluates events from top to bottom.

- Events earlier in the sheet can modify state before later events are evaluated.
- Events later in the sheet can read changes made by earlier events.
- Event order creates logical dependency, not a separate global execution time.

### Every Event Is Evaluated Every Frame

The provided source states that every event is checked every frame.

- An event does not run only when its condition changes.
- An event does not run only when an object changes.
- An event does not run only when input changes.
- An event is tested each frame as part of the event sheet pass.

### Event Evaluation and State Changes

The provided source states that event outcomes can influence later conditions through modification of game state.

Examples of state changes mentioned:

- Object properties.
- Variables.
- Object creation.
- Object destruction.
- Scene state.

### Event Evaluation Is Synchronous

The provided source states that Repeat and While loops execute synchronously within a single frame. This implies that normal event evaluation is synchronous and frame-bound.

The provided source also states that “Wait X seconds” introduces delayed execution, but does not freeze the whole game.

## 6.7 Condition Evaluation Rules

### Implicit AND Conditions

Within a single event, conditions are connected by implicit AND logic.

Rule:

```text
Event is true only if:
Condition 1 is true
AND Condition 2 is true
AND Condition 3 is true
...
AND Condition N is true
```

If any condition is false, the event is false and its actions are skipped.

### Condition Order Matters

The provided source states that conditions are tested in the order they appear.

This matters because object picking can refine the set of instances available to later conditions.

### OR Conditions

The provided source states that an OR condition group makes the containing event true if any condition inside the OR group is true.

Example from the provided source:

```text
Condition group:
- Spacebar is pressed
OR
- Mouse button is clicked
```

If either condition is true, the OR group is true.

The provided source states that different actions can follow different OR paths.

### Inverted Conditions

The provided source does not specify inverted condition behavior.

Therefore, this document does not assert details about inverted conditions.

### Condition Failure

If a condition fails:

- The event is false.
- The event’s actions are skipped.
- Sub-events are not evaluated because the parent event is false.

## 6.8 Parent Events, Sub-Events, and Nested Execution

### Parent Event Behavior

A parent event contains conditions and actions and can contain sub-events.

The provided source states that sub-events are evaluated only if all conditions of the parent event are true.

### Sub-Event Inheritance

The provided source states that sub-events inherit the conditions of their parents.

This means a sub-event’s effective execution depends on:

- The parent’s conditions being true.
- The sub-event’s own conditions being true.

### Nested Execution Order

The provided source describes a tree-like dependency structure.

Derived execution rule:

1. Parent event conditions are evaluated.
2. If parent conditions are true, parent actions execute.
3. Sub-events are then evaluated.
4. Each sub-event follows the same rule recursively.

The provided source does not specify every low-level detail of recursion, but the tree-like dependency model is explicit.

### Disabled Events and Groups

The provided source states that events and groups of events can be manually disabled using a checkbox.

When disabled:

- The engine completely skips their evaluation during the frame.
- They do not execute conditions or actions.

This is useful for debugging or temporarily deactivating code.

## 6.9 Special Event Types

### Trigger Once

The provided source describes Trigger Once as a flag-based mechanism.

Behavior:

- When Trigger Once conditions become true, actions execute.
- Trigger Once prevents the same actions from running again in the next few frames while the conditions remain true.

Use cases mentioned:

- Preventing repeated weapon firing from a single button press.
- Preventing a sound effect from playing repeatedly from a single trigger.

The provided source does not specify the exact reset semantics of Trigger Once beyond this description.

### Repeat Event

A Repeat event executes its contained actions a fixed number of times.

- Repeat events execute within a single frame.
- Repeat events are synchronous.
- Intensive loops can cause performance problems.

### While Event

A While event executes its contained actions while its condition remains true.

- While events execute synchronously within a single frame.
- While events do not pause the main game loop by themselves.
- Intensive or infinite While loops can freeze the game.

### For Each Event

A For Each event iterates over picked object instances.

- For Each executes its block once for each unique instance of the specified object currently picked by preceding conditions.
- Inside the For Each block, actions operate on that single specific instance.
- For Each is suitable for applying individualized logic to each member of a group.

Example use case from the provided source:

- Setting a unique ID for each enemy spawned.

### Loop Execution Timing

Repeat, While, and For Each events execute inside the frame’s event evaluation phase.

They do not create separate engine frames. They do not pause the frame by themselves.

The provided source warns that intensive loops can cause freezes or slowdowns.

## 6.10 Object Picking During Execution

### Object Picking Defined

Object picking is the process of selecting object instances that satisfy conditions.

The provided source states that earlier conditions can narrow down the set of objects that later conditions act upon.

### Sequential Filtering

Conditions can be understood as filters.

Conceptual model:

```text
All candidate instances
  |
  v
Condition A filters instances
  |
  v
Condition B filters remaining instances
  |
  v
Actions affect remaining picked instances
```

### Example from Provided Source

Condition sequence:

1. “Player object is overlapping Enemy object”.
2. “On Player 'Health' variable is greater than 0”.

According to the provided source:

- The first condition picks Player instances overlapping Enemy instances.
- The second condition is tested only against those already-picked Player instances.

### Multiple Picked Instances

The provided source states that if multiple objects match a condition but a following action cannot handle multiple selections, the game may behave unpredictably or produce errors.

To handle multiple instances:

- Use conditions that pick the intended instance.
- Use For Each when per-instance processing is required.

### Object Picking and Event Order

Because event sheets evaluate top to bottom, object state changed by earlier events can affect what later conditions pick.

## 6.11 Variables and Variable Evaluation Order

### Variable Scopes

The provided source defines four variable scopes.

#### Local Variables

- Temporary.
- Exist only for the duration of a single event block.

#### Object Variables

- Attached to a specific object instance.
- Persist as long as that instance exists.

#### Scene Variables

- Exist for the lifetime of the scene.
- Useful for current score, level timer, or other scene-specific data.
- Destroyed when the scene unloads.

#### Global Variables

- Persist throughout the entire game.
- Essential for carrying state between scenes.

### Variable Assignment Evaluation Order

The provided source states that when an action such as “Set Variable to [Expression]” executes:

1. The engine fully evaluates the right-hand side expression.
2. The engine assigns the resulting value to the target variable.

Example:

```text
Set Health to Health - Damage
```

- The original value of `Health` is read.
- `Damage` is evaluated.
- The result is calculated.
- The result is assigned to `Health`.

This ensures that the assignment does not overwrite the variable before the expression is evaluated.

### Variables and Scene Transitions

Scene variables are destroyed when the scene unloads.

Object variables are lost if the object instance is destroyed during scene unloading.

To preserve values across scenes:

1. Copy scene variables or object variables to global variables before changing scenes.
2. Restore values from global variables in the new scene, often during “At the beginning of the scene”.

## 6.12 Behavior Execution

### Behaviors as Reusable Components

The provided source states that behaviors add predefined functionality to objects.

Examples:

- Platformer movement.
- Physics simulation.

### Behavior Callbacks

Custom behaviors created with event functions can define:

### doStepPreEvents Timing

`doStepPreEvents` is called before main event evaluation.

Implications from the provided source:

- A behavior can modify object properties before normal events run.
- Subsequent conditions and actions in the main event sheet can operate on the modified state during the current frame.

### doStepPostEvents Timing

`doStepPostEvents` is called after main event evaluation.

- A behavior can finalize calculations after normal events run.
- It can react to changes made during the event sheet pass.

### Behavior Execution and Frame Pipeline

Behavior callbacks are part of the frame pipeline.

Conceptual order:

```text
doStepPreEvents
  |
  v
Main event sheet evaluation
  |
  v
doStepPostEvents
```

The provided source does not specify all behavior-related internal execution details beyond these callbacks.

## 6.13 Timers, Wait, and Asynchronous Operations

### Scene Timers

The provided source states that Scene Timers are global to the current scene.

Scene timers count upward from zero.

To implement a countdown, the provided source states that a developer must compare:

```text
(Timer Value - Duration)
```

to zero.

### Object Timers

Object Timers are attached to a specific object instance.

The provided source does not specify additional implementation details beyond this scope distinction.

### Wait X Seconds

The “Wait X seconds” action introduces a delay directly within an event sequence.

- Wait pauses execution of the event sheet for the specified duration.
- The rest of the game continues to run normally.
- Wait is useful for sequences with pauses.

1. Animate a character walking.
2. Wait.
3. Attack.

### Internal Implementation of Wait

The provided source states that Wait involves scheduling an action to be executed after a certain number of frames have passed, managed by the engine’s internal scheduler.

The exact scheduler implementation is not specified.

### Asynchronous Behavior

The provided source describes timers and Wait as tools for time-based and non-blocking operations.

It does not specify a complete asynchronous action system beyond these mechanisms.

## 6.14 Object Creation Lifecycle

### Creation Action

The provided source identifies the “Create Object” action as the mechanism for dynamic object creation.

### Creation Timing

Object creation occurs atomically within event evaluation.

- The object is instantiated immediately.
- The object is positioned immediately.
- Initial actions are processed within the same tick.
- Subsequent conditions and actions in the same event can interact with the new object.

### Creation Example Derived from Source

If Event 1 creates an object, Event 2 below it can test conditions involving that object during the same frame.

This is possible because creation is immediate within the event evaluation phase.

## 6.15 Object Destruction Lifecycle

### Destruction Action

The provided source identifies the “Destroy” action as the mechanism for object destruction.

### Destruction Timing

Destruction is instantaneous.

- The object is removed from the scene’s active object pool.
- References to the destroyed object become invalid for the remainder of the frame.

### Destruction Consequence

If an object is destroyed, later events in the same frame should not assume that the object remains available.

The provided source identifies attempting to access a destroyed object as a common timing mistake.

## 6.16 Scene Changes

### Scene Change Action

The provided source identifies “Change the scene” as the typical scene transition action.

### Scene Change Effects

When “Change the scene” executes:

1. The current scene is unloaded.
2. A new scene is launched.
3. Objects from the old scene are removed.
4. Scene-tied sounds or music are stopped.
5. Scene variables are destroyed.

### State Continuity

State continuity across scenes requires explicit transfer to global variables.

The provided source states that failing to transfer data is a common source of bugs where game state appears to reset unexpectedly.

### Common Scene Transition Bug

The provided source states that a player might trigger a transition multiple times rapidly.

A stated workaround is using a toggle variable to ensure the transition can only be activated once until the player moves out of the trigger zone.

## 6.17 Physics Timing

### Physics Update Position in Pipeline

The provided source states that physics update typically occurs after main event evaluation.

It may occur in a separate synchronous pass.

### Forces and Torques

During event evaluation, events can apply forces and torques.

The physics engine then:

- Receives those forces and torques.
- Integrates them.
- Updates positions and velocities.
- Resolves collisions.

### Collision Evaluation

The provided source states that physics resolves collisions during the physics update.

The exact collision evaluation internals are not specified.

## 6.18 Animation Timing

### Animation Update Position in Pipeline

The provided source states that animation updates occur after physics simulation and before final rendering.

### Animation Changes

When an action such as “Change animation to...” executes, the provided source states that the engine immediately switches to the specified animation for the given object instance.

### Animation Playback

Animation playback is handled independently.

The engine increments the current animation frame based on:

- Elapsed time.
- Animation frame rate.

### Animation-Triggered Effects

The provided source states that animation timing can trigger events on specific frames.

- Playing a sound effect at a precise moment.
- Spawning a particle effect during an attack animation.

### Animation Problems

The provided source states that animation issues are often traced to:

- Conflicting animation change events elsewhere in the event sheet.
- Incorrect looping settings.
- Incorrect pausing settings.

## 6.19 Camera Timing

### Camera Update Position in Pipeline

The provided source states that the camera is updated based on final object positions determined in previous steps.

Camera properties are finalized just before rendering.

### Camera Properties

The provided source mentions:

- Camera position.
- Camera rotation.
- Camera zoom level.

### Camera Purpose

The camera acts as a viewport defining which portion of the game world is visible.

The provided source states that camera timing ensures the player sees the world from the correct perspective at that moment in time.

## 6.20 Rendering Timing

### Rendering Is Final

The provided source states that rendering occurs after the engine has processed events, updated physics, and modified animations.

### Render Inputs

Rendering uses:

- Final object positions.
- Final rendered frames.
- Camera view.
- Lighting.
- Visual state.

### Rendering Technology

GDJS uses Pixi.js according to the provided source.

GDCpp uses SFML according to the provided source.

## 6.21 Input Timing

### Input Polling

The provided source states that at the beginning of each frame, the engine queries input devices.

Input devices mentioned:

### Input Translation

Raw input data is translated into events or conditions.

### Input and Event Evaluation

The provided source states that input polling timing is slightly before main event evaluation.

It also states that conditions can react to player input from the previous frame.

Because these statements are not fully reconciled, exact input timing should be treated as partially unspecified.

## 6.22 External Events

### Purpose

The provided source states that external events allow developers to modularize code.

They break large event sheets into smaller, manageable pieces.

### Inclusion

External events are included where needed.

### Benefits

The provided source states that external events improve:

- Editor performance.
- Logical clarity.

### Execution Order

The provided source does not specify the exact execution order inside external events beyond the general top-to-bottom event evaluation model.

## 6.23 Event Groups and Disabled Groups

### Event Groups

The provided source states that groups of events can be disabled.

### Disabled Groups

When a group is disabled:

- The engine skips evaluation of the group.
- Conditions and actions inside the disabled group are not processed during the frame.

### Use Case

The provided source states that disabling groups is useful for temporarily deactivating large sections of code for debugging.

## 6.24 Event Functions

The provided source mentions event functions in relation to custom behaviors.

It states that custom behaviors created with event functions can define:

The provided source does not specify the complete Event Function execution model beyond these behavior callbacks.

## 6.25 Include Events

The provided source does not specify a distinct event type called Include Events.

It only describes external events as being included where needed.

Therefore, no additional behavior is asserted for Include Events.

## 6.26 TimeDelta()

The provided source mentions elapsed time but does not explicitly specify the `TimeDelta()` expression.

Therefore, this document does not assert detailed behavior for `TimeDelta()`.

## 6.27 Explicitly Unspecified Details

The following details are not specified by the provided source:

1. Exact atomic order of all subsystem updates.
2. Exact internal call stack of GDJS.
3. Exact internal call stack of GDCpp.
4. Exact implementation of inverted conditions.
5. Exact implementation of collision detection internals.
6. Exact implementation of `TimeDelta()`.
7. Exact scheduler implementation for delayed actions.
8. Exact Trigger Once reset frame semantics.
9. Exact version numbers where runtime behavior changed.
10. Exact runtime-specific discrepancies between GDJS and GDCpp.
11. Exact execution order for all Event Functions.
12. Exact behavior of Include Events as a distinct feature.
13. Exact object picking algorithm internals.
14. Exact camera follow internals.
15. Exact rendering batching or draw order internals.
16. Exact asynchronous action system beyond timers and Wait.
17. Exact behavior of delayed actions beyond Wait and timers.
18. Exact object creation initialization order for all object types.
19. Exact behavior when an object is created and destroyed in the same event chain beyond the general immediate creation/destruction rule.
20. Exact community issue identifiers, affected versions, or fix versions.

## 7. Rules

The following rules are derived directly from the provided source.

### Event Execution Rules

1. GDevelop evaluates events from top to bottom.
2. GDevelop evaluates every event every frame.
3. Event order creates logical dependency, not a separate global execution schedule.
4. Earlier events can modify state used by later events in the same frame.
5. Disabled events are skipped.
6. Disabled event groups are skipped.
7. Sub-events are evaluated only if the parent event is true.
8. Sub-events inherit parent conditions.
9. Nested events follow a tree-like dependency structure.
10. External events are included where needed and improve modularity.

### Condition Rules

11. Conditions inside a single event are connected by implicit AND logic.
12. Conditions are tested in the order they appear.
13. If any condition in an AND sequence fails, the event is false.
14. If an event is false, its actions are skipped.
15. OR condition groups are true if any condition inside the group is true.
16. Conditions can filter object instances through object picking.

### Action Rules

17. Actions execute when the event’s conditions are true.
18. Actions can modify object state, variable state, scene state, animation state, camera state, and other runtime state.
19. Variable assignment evaluates the right-hand expression before assigning the result.

### Object Lifecycle Rules

20. “Create Object” creates an object immediately within event evaluation.
21. Newly created objects can be used by subsequent conditions and actions in the same frame.
22. “Destroy” removes an object immediately.
23. References to destroyed objects become invalid for the remainder of the frame.

### Scene Rules

24. “At the beginning of the scene” events run once on the first frame of the scene.
25. Scene variables exist for the lifetime of the scene.
26. Scene variables are destroyed when the scene unloads.
27. Objects are removed when the scene unloads.
28. Scene-tied sounds or music stop when the scene unloads.
29. “Change the scene” unloads the current scene and launches a new scene.
30. Global variables persist throughout the entire game.
31. Data must be explicitly copied to global variables to persist across scenes.

### Special Event Rules

32. Trigger Once prevents repeated execution while triggering conditions remain true.
33. Repeat events execute a fixed number of times within one frame.
34. While events execute while their condition remains true.
35. While and Repeat loops execute synchronously within one frame.
36. Intensive or infinite loops can freeze the game.
37. For Each iterates over picked object instances.
38. For Each actions operate on one instance at a time.

### Variable Rules

39. Local variables exist only for a single event block.
40. Object variables persist as long as the object instance exists.
41. Scene variables persist for the scene lifetime.
42. Global variables persist for the entire game.

### Behavior Rules

43. `doStepPreEvents` runs before main event evaluation.
44. `doStepPostEvents` runs after main event evaluation.
45. Behavior pre-event changes can affect conditions in the same frame.

### Timing Rules

46. Scene timers count upward from zero.
47. Countdown logic can be implemented by comparing `(Timer Value - Duration)` to zero.
48. “Wait X seconds” delays event-sheet execution while the rest of the game continues.
49. Physics update typically occurs after event evaluation.
50. Animation update occurs after physics and before rendering.
51. Camera properties are finalized before rendering.
52. Rendering uses the final accumulated scene state.

53. GDJS is the primary authoritative runtime for latest stable GDevelop 5.
54. GDCpp is secondary and historical.
55. GDJS and GDCpp behavior must not be merged.
56. Runtime-specific differences must be explicitly identified.
57. Do not speculate where source code or documentation is inconclusive.

## 8. Procedures

### 8.1 How to Reason About Event Order in GDevelop

Use this procedure when diagnosing event-order bugs.

1. Remember that all events are evaluated every frame.
2. Read the event sheet from top to bottom.
3. Identify which events modify state.
4. Identify which later events read that state.
5. Determine whether a lower event depends on a change made by an upper event.
6. Check whether object creation or destruction changes the set of available instances.
7. Check whether object picking filters instances before actions execute.
8. Check whether disabled events or groups are being skipped.
9. Check whether sub-events are blocked by false parent conditions.
10. Check whether loops execute entirely within the same frame.

### 8.2 How to Debug a Timing Bug

1. Identify the frame where the unexpected behavior appears.
2. Determine whether the cause is event order, object picking, variable scope, or scene lifecycle.
3. Check whether an object was created too late or destroyed too early.
4. Check whether a scene variable was destroyed by a scene transition.
5. Check whether a global variable was not copied before scene change.
6. Check whether a Trigger Once condition is preventing repeated execution.
7. Check whether a While loop is blocking the frame.
8. Check whether a behavior callback runs before or after main events.
9. Check whether physics, animation, or camera timing affects the final state.
10. Separate GDJS and GDCpp behavior if the bug may be runtime-specific.

### 8.3 How to Persist State Across Scenes

1. Identify the values that must persist.
2. Before executing “Change the scene”, copy those values into global variables.
3. In the new scene, use “At the beginning of the scene” events to restore values.
4. Assign restored global values to object variables or scene variables as needed.
5. Do not rely on scene variables or object variables to survive scene unloading.

### 8.4 How to Use Trigger Once Correctly

1. Place Trigger Once in an event whose actions should execute only once per activation.
2. Ensure the other conditions define the activation correctly.
3. Do not expect the event to run repeatedly while the same conditions remain true.
4. If repeated behavior is required, do not use Trigger Once.
5. If one-shot behavior is required, use Trigger Once to prevent repeated execution.

### 8.5 How to Use For Each Correctly

1. Ensure the target object instances are picked before the For Each event.
2. Use For Each when each instance requires individual processing.
3. Inside the For Each block, actions operate on the current instance.
4. Do not use For Each if the logic should apply to the whole picked set at once.
5. Be aware that large For Each loops can affect performance.

### 8.6 How to Use Wait Correctly

1. Use “Wait X seconds” when an event sequence needs a delay.
2. Remember that the rest of the game continues running.
3. Do not use Wait if the entire game must freeze.
4. Use Wait for sequences such as animation, pause, then attack.
5. Understand that Wait is scheduled internally and is not an immediate continuation.

### 8.7 How to Use Timers Correctly

1. Decide whether the timer should be scene-scoped or object-scoped.
2. Use Scene Timers for scene-level timing.
3. Use Object Timers for per-instance timing.
4. Remember that scene timers count upward.
5. For countdown behavior, compare `(Timer Value - Duration)` to zero.

### 8.8 How to Reduce Event Sheet Performance Problems

1. Disable unused events and groups.
2. Use external events to modularize large sheets.
3. Avoid infinite While loops.
4. Avoid excessive nested loops.
5. Reduce the number of active objects where possible.
6. Cache repeated calculations in variables.
7. Use arrays for data storage instead of many individual variables where appropriate.
8. Identify hotspots in event evaluation.
9. Test on the target runtime.
10. Separate GDJS and GDCpp performance observations.

## 9. Examples

All examples below are illustrative examples derived strictly from statements in the provided source.

### 9.1 Example: Sequential State Dependency

Illustrative event logic:

```text
Event 1:
Condition: Always true
Action: Set Variable Score to 10

Event 2:
Condition: Variable Score is 10
Action: Do something
```

Why this works according to the provided source:

- Events evaluate top to bottom.
- Event 1 changes the variable before Event 2 is evaluated.
- Event 2 can see the new value during the same frame.

### 9.2 Example: Object Creation in the Same Frame

```text
Event 1:
Condition: Some spawn condition
Action: Create Object Enemy

Event 2:
Condition: Enemy exists
Action: Move Enemy
```

- Object creation is atomic within event evaluation.
- The created object is available to subsequent conditions and actions in the same frame.

### 9.3 Example: Object Destruction Invalidates Later References

```text
Event 1:
Condition: Enemy health is zero
Action: Destroy Enemy

Event 2:
Condition: Enemy overlaps Player
Action: Damage Player
```

Why this matters according to the provided source:

- Destruction is immediate.
- If the Enemy was destroyed earlier in the frame, later references to that destroyed instance are invalid.

### 9.4 Example: Trigger Once for One-Shot Behavior

```text
Event:
Condition: Spacebar is pressed
Condition: Trigger Once
Action: Play sound effect
```

- Trigger Once prevents the sound effect from playing repeatedly while the triggering condition remains true.

### 9.5 Example: For Each Over Picked Instances

```text
Condition: Enemy is picked
For Each Enemy:
Action: Set Enemy UniqueID to a unique value
```

- For Each iterates over picked instances.
- Actions inside For Each operate on one specific instance.

### 9.6 Example: Scene Transition Persistence

Illustrative event logic before scene change:

```text
Event:
Condition: Player reaches exit
Action: Set Global Variable PlayerHealth to Scene Variable Health
Action: Set Global Variable PlayerScore to Scene Variable Score
Action: Change the scene to NextLevel
```

Illustrative event logic in next scene:

```text
At the beginning of the scene:
Action: Set Scene Variable Health to Global Variable PlayerHealth
Action: Set Scene Variable Score to Global Variable PlayerScore
```

- Scene variables are destroyed during scene unloading.
- Global variables persist throughout the game.
- Explicit copying preserves state.

### 9.7 Example: Wait Sequence

```text
Event:
Condition: Player attacks
Action: Change animation to Attack
Action: Wait 0.3 seconds
Action: Deal damage
```

- “Wait X seconds” delays part of the event sequence.
- The rest of the game continues running during the wait.

### 9.8 Example: Disabled Group for Debugging

Illustrative action:

```text
Disable a group of enemy-spawning events.
```

- Disabled groups are skipped completely.
- This temporarily deactivates large sections of logic for debugging.

## 10. Edge Cases

### 10.1 Object Created and Used in the Same Frame

The provided source states that object creation is immediate within event evaluation. Therefore, later events in the same frame can interact with a newly created object.

### 10.2 Object Destroyed and Referenced Later in the Same Frame

The provided source states that destruction is immediate and references to destroyed objects become invalid for the remainder of the frame.

### 10.3 Multiple Picked Objects with Single-Instance Logic

The provided source states that if multiple objects match a condition but a following action cannot handle multiple selections, behavior may be unpredictable or produce errors.

### 10.4 Trigger Once with Conditions Remaining True

The provided source states that Trigger Once prevents repeated execution while conditions remain true.

### 10.5 Infinite While Loop

The provided source states that intensive or infinite While loops can freeze the game because loops execute synchronously within a frame.

### 10.6 Rapid Scene Transition Triggering

The provided source states that a player might trigger a transition multiple times rapidly. A stated workaround is a toggle variable.

### 10.7 Scene Variables Lost During Scene Change

The provided source states that scene variables are destroyed when the scene unloads.

### 10.8 Object Variables Lost When Object Is Destroyed

The provided source states that object variables persist as long as the instance exists. If the instance is destroyed during scene unloading, the object variables do not persist.

### 10.9 Behavior Modifying State Before Events

Because `doStepPreEvents` runs before main event evaluation, behavior changes can affect conditions in the same frame.

### 10.10 Behavior Modifying State After Events

Because `doStepPostEvents` runs after main event evaluation, behavior changes can finalize state after normal events.

### 10.11 Physics After Event Evaluation

Because physics update typically occurs after event evaluation, forces applied during events are integrated later in the frame.

### 10.12 Camera Uses Final Positions

Because camera update occurs after object positions are finalized, the camera sees the frame’s final object positions.

### 10.13 Animation Changes Are Immediate but Playback Is Independent

The provided source states that changing animation is immediate, but playback is handled independently based on elapsed time and frame rate.

### 10.14 Input Timing Ambiguity

The provided source gives multiple statements about input polling timing. Exact placement should be treated as partially unspecified.

### 10.15 GDJS and GDCpp Differences

The provided source states that differences can arise from architecture, but exact discrepancies are not specified.

### 10.16 External Events Execution Details

The provided source states that external events are included where needed but does not specify exact execution internals beyond normal event evaluation.

### 10.17 Event Function Execution Beyond Callbacks

The provided source specifies `doStepPreEvents` and `doStepPostEvents`, but not the full Event Function execution model.

### 10.18 TimeDelta Not Specified

The provided source does not explicitly specify `TimeDelta()` behavior.

### 10.19 Inverted Conditions Not Specified

### 10.20 Collision Evaluation Internals Not Specified

The provided source states that physics resolves collisions but does not specify collision evaluation internals.

## 11. Best Practices

The following best practices are derived from the provided source. Some are explicit; others are directly derived from the source’s warnings and recommendations.

### Runtime Best Practices

1. Treat GDJS as the authoritative runtime for latest stable GDevelop 5.
2. Do not assume GDJS and GDCpp behave identically.
3. Identify the runtime when documenting a bug or behavior.
4. Do not merge runtime-specific behavior into a single claim.
5. Do not speculate where engine source or documentation is inconclusive.
6. Test behavior on the target runtime when runtime differences are possible.
7. Label community-observed behavior separately from official behavior.
8. Preserve runtime context when answering timing-related questions.

### Event Order Best Practices

9. Think in terms of top-to-bottom evaluation every frame.
10. Do not assume event order creates separate global execution times.
11. Place state-modifying events before events that depend on that state.
12. Be careful when lower events depend on object creation from upper events.
13. Be careful when lower events depend on object destruction from upper events.
14. Use disabled events or groups to temporarily remove logic during debugging.
15. Use external events to modularize large event sheets.
16. Keep related logic grouped to reduce ordering mistakes.
17. Review nested parent/sub-event dependencies when events do not run.
18. Remember that sub-events require parent conditions to be true.
19. Remember that disabled groups are skipped completely.

### Object Picking Best Practices

20. Use conditions to explicitly pick the intended object instances.
21. Use For Each when each picked instance needs individual processing.
22. Avoid assuming an action can handle multiple picked instances if it cannot.
23. Use earlier conditions to filter instances before later actions.
24. Check whether object creation or destruction changes picking results.
25. Check whether variable changes affect picking conditions.

### Variable Best Practices

26. Use local variables for temporary event-block calculations.
27. Use object variables for instance-specific state.
28. Use scene variables for scene-specific state.
29. Use global variables for state that must persist across scenes.
30. Copy important scene variables to global variables before scene changes.
31. Restore persisted global variables during “At the beginning of the scene”.
32. Remember that right-hand expressions are evaluated before assignment.
33. Avoid assuming scene variables survive scene unloading.
34. Avoid assuming object variables survive object destruction.

### Behavior Best Practices

35. Use `doStepPreEvents` for behavior logic that must run before main events.
36. Use `doStepPostEvents` for behavior logic that must run after main events.
37. Be aware that pre-event behavior changes can affect same-frame conditions.
38. Be aware that post-event behavior changes can finalize same-frame state.
39. Keep behavior callbacks focused to reduce timing complexity.

### Timing Best Practices

40. Use Scene Timers for scene-scoped timing.
41. Use Object Timers for object-instance timing.
42. Remember that scene timers count upward.
43. Use `(Timer Value - Duration)` for countdown logic.
44. Use “Wait X seconds” for delayed event sequences.
45. Remember that Wait does not freeze the whole game.
46. Avoid using Wait when whole-game freezing is required.
47. Avoid infinite While loops.
48. Be cautious with intensive Repeat loops.
49. Be cautious with intensive For Each loops.
50. Understand that loops execute synchronously within a frame.

## 12. Common Mistakes

The following common mistakes are derived from the provided source.

### Event Order Mistakes

1. Believing event order creates a global priority schedule rather than sequential state dependency.
2. Assuming events run only when something changes.
3. Assuming events run only once unless explicitly repeated.
4. Forgetting that all events are evaluated every frame.
5. Placing state-dependent events above the events that modify the state.
6. Assuming lower events cannot see changes made by upper events in the same frame.
7. Assuming object creation is delayed until the next frame.
8. Assuming object destruction is delayed until the next frame.
9. Ignoring disabled events during debugging.
10. Ignoring disabled groups during debugging.

### Parent/Sub-Event Mistakes

11. Expecting sub-events to run when the parent event is false.
12. Forgetting that sub-events inherit parent conditions.
13. Creating deeply nested dependencies without tracking condition flow.
14. Assuming sub-events execute independently of parent state.
15. Misreading nested event order during debugging.

### Condition Mistakes

16. Assuming conditions are connected by OR when they are implicitly AND.
17. Assuming an OR group requires all conditions to be true.
18. Ignoring condition order when object picking filters instances.
19. Assuming a failed condition only skips one condition instead of the event.
20. Assuming conditions do not affect object picking.

### Object Picking Mistakes

21. Allowing multiple objects to be picked when only one is intended.
22. Using actions that cannot handle multiple picked instances.
23. Forgetting to use For Each for per-instance logic.
24. Assuming actions automatically apply to all instances when picking is ambiguous.
25. Not checking whether earlier conditions filtered the intended instances.

### Variable Mistakes

26. Assuming scene variables persist after scene change.
27. Assuming object variables persist after object destruction.
28. Assuming local variables persist beyond the event block.
29. Forgetting to copy important values to global variables before scene transition.
30. Assuming global variables are automatically restored into scene variables.
31. Assuming assignment overwrites a variable before the right-hand expression is evaluated.
32. Using the wrong variable scope for the intended lifetime.

### Scene Transition Mistakes

33. Forgetting that scene unloading destroys scene variables.
34. Forgetting that scene unloading removes objects.
35. Forgetting that scene-tied sounds or music stop during unloading.
36. Allowing rapid repeated scene transitions without a toggle variable.
37. Assuming player state automatically carries into the next scene.
38. Assuming inventory automatically carries into the next scene.
39. Assuming score automatically carries into the next scene.
40. Not restoring persisted values during “At the beginning of the scene”.

### Loop Mistakes

41. Creating infinite While loops.
42. Using intensive Repeat loops inside large event sheets.
43. Assuming loops pause the main game loop.
44. Assuming loops execute across multiple frames by default.
45. Using For Each on too many instances without considering performance.

### Timing Mistakes

46. Assuming “Wait X seconds” freezes the entire game.
47. Assuming scene timers count downward by default.
48. Implementing countdowns without using `(Timer Value - Duration)`.
49. Assuming Trigger Once allows repeated execution while conditions remain true.
50. Assuming behavior callbacks run at the same time as normal events.

### Runtime Mistakes

51. Assuming GDJS and GDCpp behavior is identical.
52. Merging runtime-specific behaviors into one explanation.
53. Failing to identify which runtime a bug affects.
54. Speculating about engine internals without source or documentation.
55. Treating community observations as official behavior without labeling.

## 13. Performance Considerations

### Event Sheet Size

The provided source states that large event sheets can become slow and unresponsive, leading to editor freezes and slower game performance.

Reason:

- The engine evaluates every event in the sheet every frame.
- This occurs regardless of whether every event is relevant to the current gameplay state.

### Event Evaluation Bottlenecks

The provided source states that bottlenecks can exist within the event evaluation step.

Potential contributing factors mentioned:

- Large numbers of events.
- Complex conditions.
- Loops.
- Large numbers of active objects.
- Inefficient object picking.

### Loop Performance

The provided source warns that intensive or infinite loops can cause freezes or slowdowns.

Loop types affected:

- Repeat.
- While.
- For Each, when iterating over many instances.

### Optimization Strategies from Provided Source

The provided source mentions several optimization strategies:

1. Disable unused events.
2. Disable unused event groups.
3. Use external events to modularize code.
4. Avoid inefficient loops.
5. Avoid nested loops where possible.
6. Cache values in variables to avoid repeated calculations.
7. Use arrays for data storage instead of numerous individual variables.
8. Minimize the number of active objects in the scene.

These are labeled as provided source recommendations or community-derived optimization patterns.

### Rendering and Physics Considerations

The provided source does not provide detailed rendering or physics performance profiling guidance.

However, it states that rendering is the final stage and physics occurs after event evaluation. Therefore, performance issues in event evaluation can affect the entire frame before rendering.

### Runtime-Specific Performance

The provided source does not specify detailed performance differences between GDJS and GDCpp.

Performance observations should be labeled by runtime and not assumed to apply universally.

## 14. Related Topics

### Directly Related Systems

- GDevelop event system.
- GDevelop event sheet editor.
- GDevelop scene editor.
- GDevelop object system.
- GDevelop variable system.
- GDevelop behavior system.
- GDevelop physics behavior.
- GDevelop animation system.
- GDevelop camera system.
- GDevelop timer system.
- GDevelop scene manager.
- GDevelop external events.
- GDevelop event functions.
- GDevelop input system.
- GDevelop rendering system.
- GDevelop sound system.
- GDevelop export system.

### Runtime-Related Topics

- GDJS JavaScript runtime.
- GDCpp native runtime.
- Pixi.js rendering.
- SFML rendering.
- HTML5 export.
- Native desktop export.
- Mobile export through frameworks.

### Debugging-Related Topics

- Event order debugging.
- Object picking debugging.
- Scene transition debugging.
- Variable scope debugging.
- Timer debugging.
- Behavior callback debugging.
- Performance profiling.
- Runtime-specific bug isolation.

## 15. Glossary

### Action

An operation executed when an event’s conditions are true.

The period after scene initialization where the frame loop evaluates events every frame.

### At the beginning of the scene

A scene initialization event phase that runs once on the first frame of a scene.

### Behavior

A reusable component that adds functionality to an object.

### Camera

The viewport defining which part of the game world is visible.

### Change the scene

An action that unloads the current scene and launches a new scene.

### Condition

A test evaluated by the engine.

### Create Object

An action that creates a new object instance during event evaluation.

### Destroy

An action that immediately removes an object instance.

### Disabled Event

An event skipped by the engine during evaluation.

### Disabled Group

A group of events skipped by the engine during evaluation.

### doStepPostEvents

A behavior callback executed after main event evaluation.

### doStepPreEvents

A behavior callback executed before main event evaluation.

### Event

A combination of conditions and actions.

### Event Sheet

A container for events and event logic.

### External Events

Event sheets used to modularize logic and included where needed.

### For Each

An event type that iterates over picked object instances.

### Frame

One iteration of the engine update cycle.

### Game Loop

The continuous process that updates and renders the game.

### GDCpp

The historical native C++ runtime associated with SFML.

### GDJS

The primary JavaScript/TypeScript runtime associated with Pixi.js.

### Global Variable

A variable that persists throughout the entire game.

### Local Variable

A temporary variable that exists for the duration of a single event block.

### Object Picking

The process of selecting object instances through conditions.

### Object Timer

A timer attached to a specific object instance.

### Object Variable

A variable attached to a specific object instance.

### OR Condition

A condition group that is true if any contained condition is true.

### Parent Event

An event that can contain sub-events.

An event that executes actions a fixed number of times within one frame.

### Scene

A logical or playable section of a GDevelop project.

### Scene Timer

A timer scoped to the current scene.

### Scene Variable

A variable that exists for the lifetime of a scene.

### Sub-event

An event nested under a parent event.

### Tick

A frame update or game loop iteration.

A mechanism preventing repeated execution while conditions remain true.

### Wait X seconds

An action that delays event-sheet execution while the rest of the game continues.

An event that executes actions while a condition remains true.

## 16. AI Retrieval Notes

### Important Keywords

GDevelop event execution order; GDevelop frame lifecycle; GDevelop scene lifecycle; GDevelop event evaluation; GDevelop top-to-bottom events; GDevelop conditions; GDevelop actions; GDevelop parent events; GDevelop sub-events; GDevelop Trigger Once; GDevelop Repeat event; GDevelop While event; GDevelop For Each event; GDevelop object picking; GDevelop instance filtering; GDevelop variable scope; GDevelop global variables; GDevelop scene variables; GDevelop object variables; GDevelop local variables; GDevelop behaviors; GDevelop doStepPreEvents; GDevelop doStepPostEvents; GDevelop physics timing; GDevelop animation timing; GDevelop camera timing; GDevelop rendering timing; GDevelop timers; GDevelop Wait action; GDevelop scene transition; GDevelop Change the scene; GDevelop object creation; GDevelop object destruction; GDevelop GDJS; GDevelop GDCpp; GDevelop performance; GDevelop external events; GDevelop disabled events; GDevelop event groups.

### Synonyms and Search Aliases

GDevelop event order; GDevelop execution order; GDevelop event processing; GDevelop event loop; GDevelop game loop; GDevelop frame loop; GDevelop tick; GDevelop frame update; GDevelop runtime pipeline; GDevelop engine pipeline; GDevelop scene start; GDevelop scene begin; GDevelop beginning of scene; GDevelop scene load; GDevelop scene unload; GDevelop scene change; GDevelop scene transition; GDevelop switch scene; GDevelop object selection; GDevelop picked objects; GDevelop picked instances; GDevelop instance filtering; GDevelop one-shot event; GDevelop run once; GDevelop delay action; GDevelop delayed execution; GDevelop async execution; GDevelop persistent variables; GDevelop game variables; GDevelop global state; GDevelop scene state; GDevelop object state; GDevelop behavior callback; GDevelop pre-events step; GDevelop post-events step; GDevelop physics step; GDevelop collision timing; GDevelop animation update; GDevelop camera update; GDevelop render order; GDevelop draw timing; GDevelop input timing; GDevelop keyboard timing; GDevelop mouse timing; GDevelop touch timing.

### Common User Questions This Document Answers

1. How does GDevelop execute events?
2. What is the event execution order in GDevelop?
3. Does GDevelop evaluate events top to bottom?
4. Does GDevelop evaluate every event every frame?
5. Does event order matter in GDevelop?
6. Why does event order matter if all events run every frame?
7. What is the GDevelop frame lifecycle?
8. What is the GDevelop scene lifecycle?
9. When do “At the beginning of the scene” events run?
10. Do “At the beginning of the scene” events run every frame?
11. How do GDevelop conditions work?
12. Are GDevelop conditions AND conditions?
13. How do OR conditions work in GDevelop?
14. What happens if a GDevelop condition fails?
15. How do GDevelop actions execute?
16. When do GDevelop actions execute?
17. What are parent events in GDevelop?
18. What are sub-events in GDevelop?
19. Do sub-events run if the parent event is false?
20. Do sub-events inherit parent conditions?
21. How does Trigger Once work in GDevelop?
22. Why does Trigger Once stop an event from repeating?
23. How does the Repeat event work?
24. How does the While event work?
25. Can a While event freeze GDevelop?
26. How does the For Each event work?
27. What is object picking in GDevelop?
28. How does object picking affect conditions?
29. How does object picking affect actions?
30. Why do actions affect only some object instances?
31. How are variables evaluated in GDevelop?
32. What is the order of variable assignment in GDevelop?
33. What are local variables in GDevelop?
34. What are object variables in GDevelop?
35. What are scene variables in GDevelop?
36. What are global variables in GDevelop?
37. Do scene variables persist after a scene change?
38. Do object variables persist after object destruction?
39. How do I keep data between GDevelop scenes?
40. How do global variables work across scenes?
41. How do behaviors execute in GDevelop?

42. What is `doStepPreEvents`?
43. What is `doStepPostEvents`?
44. Do behaviors run before or after events?
45. How do Scene Timers work?
46. How do Object Timers work?
47. Do GDevelop timers count up or down?
48. How do I make a countdown timer in GDevelop?
49. How does “Wait X seconds” work?
50. Does “Wait X seconds” freeze the game?
51. When are objects created in GDevelop?
52. Can a newly created object be used in the same frame?
53. When are objects destroyed in GDevelop?
54. Can a destroyed object be used later in the same frame?
55. How does “Change the scene” work?
56. What happens when a GDevelop scene unloads?
57. Why does my score reset after changing scenes?
58. Why does my health reset after changing scenes?
59. Why does my inventory disappear after changing scenes?
60. How can I prevent multiple scene transitions?
61. When does physics update in GDevelop?
62. Does physics update before or after events?
63. When do animations update in GDevelop?
64. When does the camera update in GDevelop?
65. When does rendering happen in GDevelop?
66. What is GDJS?
67. What is GDCpp?
68. Which GDevelop runtime is authoritative?
69. Are GDJS and GDCpp identical?
70. Why are large GDevelop event sheets slow?
71. How can I optimize GDevelop event sheets?
72. What are external events in GDevelop?
73. What are disabled events in GDevelop?
74. What are disabled event groups in GDevelop?
75. What details are unspecified by the provided source?

### Frequently Searched Phrases

- GDevelop event order not working
- GDevelop events run every frame
- GDevelop top to bottom event execution
- GDevelop Trigger Once not working
- GDevelop event runs twice
- GDevelop event runs repeatedly
- GDevelop object created too late
- GDevelop object destroyed too early
- GDevelop object not picked
- GDevelop wrong object selected
- GDevelop multiple objects picked
- GDevelop For Each object
- GDevelop While loop freeze
- GDevelop Repeat loop performance
- GDevelop scene variables reset
- GDevelop global variables between scenes
- GDevelop change scene keep variables
- GDevelop keep score between scenes
- GDevelop keep health between scenes
- GDevelop keep inventory between scenes
- GDevelop Wait action not freezing game
- GDevelop timer countdown
- GDevelop scene timer counts up
- GDevelop object timer
- GDevelop behavior before events
- GDevelop behavior after events
- GDevelop doStepPreEvents
- GDevelop doStepPostEvents
- GDevelop physics after events
- GDevelop animation after physics
- GDevelop camera before render
- GDevelop rendering order
- GDevelop GDJS vs GDCpp
- GDevelop JavaScript runtime
- GDevelop C++ runtime
- GDevelop external events execution
- GDevelop disabled event group
- GDevelop debug event order
- GDevelop event sheet slow
- GDevelop performance optimization

### Related Concepts for Retrieval

- Frame-based game loop.
- Sequential event evaluation.
- State dependency.
- Object instance filtering.
- Variable lifetime.
- Scene boundary.
- Runtime authority.
- Behavior callback timing.
- Physics integration timing.
- Animation playback timing.
- Camera finalization timing.
- Rendering final state.
- Delayed event execution.
- Scene persistence.
- Event modularization.
- Debugging through disabling.
- Performance bottleneck in event evaluation.

### Common Misconceptions

1. Misconception: Event order controls when events are scheduled across time.
   Correction: Event order controls sequential state dependency within the same frame.

2. Misconception: Events run only when their conditions change.
   Correction: Events are evaluated every frame.

3. Misconception: Object creation happens on the next frame.
   Correction: The provided source states object creation is immediate within event evaluation.

4. Misconception: Object destruction happens at the end of the frame.
   Correction: The provided source states destruction is immediate.

5. Misconception: Scene variables persist across scenes.
   Correction: Scene variables are destroyed when the scene unloads.

6. Misconception: Object variables persist after scene change.
   Correction: Object variables persist only as long as the instance exists; scene unloading removes objects.

7. Misconception: Global variables are automatically copied into scene variables.
   Correction: Persistence requires explicit copying and restoration.

8. Misconception: Sub-events run independently.
   Correction: Sub-events require the parent event to be true.

9. Misconception: OR conditions require all conditions to be true.
   Correction: OR groups are true if any condition inside the group is true.

10. Misconception: While loops run across multiple frames automatically.
   Correction: The provided source states While loops execute synchronously within a single frame.

11. Misconception: “Wait X seconds” freezes the entire game.
   Correction: The provided source states Wait delays event-sheet execution while the rest of the game continues.

12. Misconception: Scene timers count down by default.
   Correction: The provided source states scene timers count upward.

13. Misconception: GDJS and GDCpp behavior can be treated as identical.
   Correction: The provided source states they must not be merged and GDJS is authoritative.

14. Misconception: Disabled events still evaluate conditions.
   Correction: The provided source states disabled events and groups are skipped completely.

15. Misconception: External events have a completely separate execution model.
   Correction: The provided source does not specify separate execution internals beyond inclusion and normal event evaluation.

### Important Entities

- GDevelop 5.
- GDJS.
- GDCpp.
- Pixi.js.
- SFML.
- Event sheet.
- Event.
- Condition.
- Action.
- Parent event.
- Sub-event.
- Trigger Once.
- Repeat event.
- While event.
- For Each event.
- Object picking.
- Local variable.
- Object variable.
- Scene variable.
- Global variable.
- Scene Timer.
- Object Timer.
- Wait X seconds.
- Change the scene.
- At the beginning of the scene.
- Create Object.
- Destroy.
- External Events.
- Disabled events.
- Disabled groups.
- `gdjs.evtTools.runtimeScene.sceneJustBegins`.
- `doStepPreEvents`.
- `doStepPostEvents`.
- Physics update.
- Animation update.
- Camera update.
- Rendering.
- Input polling.

### Recommended Chunk Boundaries

For vector database chunking, the following boundaries are recommended:

1. Metadata and keywords as one retrieval chunk.
2. Overview as one chunk.
3. Evidence classification and source limitations as one chunk.
4. Definitions as one or more chunks by definition group.
5. Core concepts as separate chunks per concept.
6. Runtime architecture: GDJS and GDCpp as one chunk.
7. Scene lifecycle as one chunk.
8. Frame lifecycle as one chunk.
9. Execution diagrams and pseudocode as one chunk or separate diagram/pseudocode chunks.
10. Event evaluation pipeline as one chunk.
11. Condition evaluation rules as one chunk.
12. Parent/sub-event execution as one chunk.
13. Special event types as separate chunks for Trigger Once, Repeat, While, and For Each.
14. Object picking as one chunk.
15. Variable scopes and assignment order as one chunk.
16. Behavior execution and callbacks as one chunk.
17. Timers and Wait as one chunk.
18. Object creation and destruction as one chunk.
19. Scene changes and persistence as one chunk.
20. Physics, animation, camera, rendering, and input timing as separate chunks.
21. External events, event groups, event functions, and unspecified features as separate chunks.
22. Rules as a standalone chunk.
23. Procedures as separate chunks by procedure.
24. Examples as separate chunks by example.
25. Edge cases as one or more chunks.
26. Best practices as one chunk or grouped chunks.
27. Common mistakes as one chunk or grouped chunks.
28. Performance considerations as one chunk.
29. Glossary as one chunk or grouped chunks.
30. AI retrieval notes as a final metadata chunk.