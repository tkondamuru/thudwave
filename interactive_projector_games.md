# Interactive Projector Games: Post-Impact Whiteboard System

## 1. Overview & The Core Breakthrough

During our dual-camera trajectory experiments, we discovered that while predicting the future flight path *before* impact is mathematically challenging (due to ball speed variance, spin, drag, and camera sync), **detecting the exact physical point of impact post-hit is 100% deterministic and highly accurate**.

### Why Post-Hit Detection is a Game-Changer:
1. **Single Camera Simplicity:** Post-hit impact detection only requires **one camera** (Front View). The Side Camera and inter-camera time synchronization are not even required!
2. **Deterministic Physics:** When a ball strikes a rigid whiteboard, its velocity vector reverses ($\Delta X < 0$ or sharp rebound direction change). The vertex of that directional change marks the physical $(X, Y)$ impact coordinate down to the pixel.
3. **Whiteboard Homography:** Using the 4 corner ArUco tags on the whiteboard, any impact $(X_{\text{cam}}, Y_{\text{cam}})$ maps directly to the projector's screen resolution $(X_{\text{proj}}, Y_{\text{proj}})$ via a 2D planar perspective transform (Homography matrix $H$):
   $$\begin{bmatrix} X_{\text{proj}} \\ Y_{\text{proj}} \\ 1 \end{bmatrix} = \mathbf{H} \begin{bmatrix} X_{\text{cam}} \\ Y_{\text{cam}} \\ 1 \end{bmatrix}$$
4. **Near-Zero Latency:** Rebound detection triggers within **$33\text{ ms}$ (1 frame)** of contact, allowing the projector to trigger animations and sound effects immediately.

---

## 2. Game Catalog & Implementation Difficulty Ratings

Difficulty Scale:
* **★☆☆☆☆ (1/5 - Very Easy):** Static targets, simple bounding-box collision, no complex timers or state. 1–2 days.
* **★★☆☆☆ (2/5 - Easy):** Moving targets, basic score counter, sound effects, single-screen game loop. 2–3 days.
* **★★★☆☆ (3/5 - Moderate):** Multi-stage rounds, timer countdowns, particle effects, multiple target states. 3–5 days.
* **★★★★☆ (4/5 - Challenging):** 2-player turn mechanics, procedural level generation, dynamic grid physics. 5–7 days.
* **★★★★★ (5/5 - Advanced):** Complex physics simulations, real-time multiplayer networking, adaptive difficulty. 1–2 weeks.

---

### Game 1: 🎯 Arcade Bullseye / Darts
* **Difficulty:** **★☆☆☆☆ (1/5 - Very Easy)**
* **Concept:** Projector casts a glowing circular dartboard or archery target with concentric score zones (Bullseye = 100 pts, Inner Ring = 50 pts, Middle = 25 pts, Outer = 10 pts).
* **Mechanics:**
  1. Player throws 5 balls.
  2. Each hit creates a visual paint splatter or ripple animation at the exact impact point.
  3. Displays points scored with audio feedback (*"BULLSEYE!"*, cheers).
  4. Keeps a running total and high score leaderboard.
* **Why it's Easy:** Targets are static circles. Collision logic is pure Euclidean distance:
  $$\text{dist} = \sqrt{(X_{\text{hit}} - X_{\text{center}})^2 + (Y_{\text{hit}} - Y_{\text{center}})^2}$$
  If $\text{dist} \le R_{\text{bullseye}}$, award 100 points!

---

### Game 2: 🎈 Carnival Balloon Pop
* **Difficulty:** **★★☆☆☆ (2/5 - Easy)**
* **Concept:** 10–15 colorful balloons float gently across the whiteboard canvas with strings dangling.
* **Mechanics:**
  1. Player has 30 seconds to pop all balloons.
  2. Throwing the ball and hitting a balloon causes it to pop with an audio *"POP!"* and confetti particle burst.
  3. Popped balloons disappear; remaining balloons continue drifting.
  4. Bonus balloons (e.g. golden balloon = 3x points, bomb balloon = -5 seconds).
* **Why it's Easy:** Simple circular/elliptical collision detection with linear upwards velocity for floating targets.

---

### Game 3: 🧱 Physical "Breakout" (Brick Breaker)
* **Difficulty:** **★★☆☆☆ (2/5 - Easy)**
* **Concept:** A wall of colorful bricks is projected across the top half of the whiteboard.
* **Mechanics:**
  1. Player acts as the "paddle" by throwing physical balls directly at the bricks.
  2. Hitting a brick causes it to crack or shatter into pieces with sound effects.
  3. Different brick types: regular bricks (1 hit), steel bricks (2 hits), TNT bricks (explodes surrounding bricks).
  4. Goal: Clear all bricks in the fewest throws.
* **Why it's Easy:** Bricks are arranged in a static 2D grid (`AABB` bounding box collision). Destroying a brick is simply removing an item from a list.

---

### Game 4: 👾 Whack-A-Mole / Alien Blaster
* **Difficulty:** **★★★☆☆ (3/5 - Moderate)**
* **Concept:** 6 holes are projected on the whiteboard. Moles, zombies, or alien creatures pop out of the holes for 1.5–3 seconds and then duck back down.
* **Mechanics:**
  1. Player must react quickly and hit the active mole before it retreats.
  2. Hitting a mole triggers a "bonk" animation and stars circling its head.
  3. Speed increases as the player scores more points (adaptive reaction timer).
  4. "Decoy" characters (e.g. cute bunny) that deduct points if hit.
* **Why it's Moderate:** Requires asynchronous timers for mole appearance/disappearance states and randomized scheduling.

---

### Game 5: 🧠 Interactive Trivia / Multiple Choice Quiz
* **Difficulty:** **★★☆☆☆ (2/5 - Easy to Moderate)**
* **Concept:** Great for family game nights or kids' educational play. A question appears at the top with 4 large answer quadrants (A, B, C, D).
* **Mechanics:**
  1. Question: *"Which planet is closest to the Sun?"*
  2. Four large colored boxes: [A: Venus] [B: Mercury] [C: Mars] [D: Jupiter].
  3. Player physically throws the ball at the answer box they choose.
  4. Correct answer turns green with fireworks and victory fanfare.
  5. Wrong answer turns red with an arcade buzzer and reveals the correct answer.
* **Why it's Easy/Moderate:** The 4 quadrants divide the screen into simple rectangular zones ($X < W/2$, $Y < H/2$, etc.). Questions can be loaded easily from a JSON or text file.

---

### Game 6: ❌ Tic-Tac-Toe / Connect Four (2-Player Duel)
* **Difficulty:** **★★★☆☆ (3/5 - Moderate)**
* **Concept:** 2 players take turns throwing the ball at a projected 3x3 (or 7x6 Connect-4) grid.
* **Mechanics:**
  1. Player 1 throws at an empty square $\rightarrow$ turns to blue "X".
  2. Player 2 throws at an empty square $\rightarrow$ turns to red "O".
  3. If a player hits an already occupied square, they lose their turn or must retry.
  4. First player to achieve 3-in-a-row wins with animated winning line and celebration sound.
* **Why it's Moderate:** Requires turn-based state management, checking win conditions across rows/columns/diagonals, and detecting accidental hits on already claimed tiles.

---

### Game 7: 🔠 Word Spell / Boggle Wall
* **Difficulty:** **★★★★☆ (4/5 - Challenging)**
* **Concept:** A 4x4 grid of letters is projected on the board.
* **Mechanics:**
  1. Players spell words by throwing balls at letters sequentially (e.g., C - A - T).
  2. Each hit highlights the letter and adds it to the active word tray.
  3. A "SUBMIT" button box at the bottom is hit to lock in the word.
  4. Validates words against an English dictionary and awards points based on word length.
* **Why it's Challenging:** Requires dictionary lookup, sequence tracking, undo/submit target zones, and word validation logic.

---

### Game 8: 🏃 Simon Says / Memory Sequence
* **Difficulty:** **★★☆☆☆ (2/5 - Easy)**
* **Concept:** 4 large colored pads (Red, Blue, Green, Yellow) light up in an expanding sequence.
* **Mechanics:**
  1. Computer flashes: Red $\rightarrow$ Green.
  2. Player must throw the ball to hit Red, then Green.
  3. Next round adds another step: Red $\rightarrow$ Green $\rightarrow$ Yellow.
  4. How far can you go before making a mistake?
* **Why it's Easy:** 4 large quadrants, simple array comparison (`sequence[step] == hit_pad`).

---

## 3. Implementation Difficulty Matrix

| Game | Difficulty Rating | Single Camera Capable? | Development Time | Fun / Engagement Factor |
| :--- | :---: | :---: | :---: | :---: |
| **1. Arcade Bullseye** | ★☆☆☆☆ (1/5) | Yes (100%) | 1 – 2 Days | High (Instant arcade gratification) |
| **2. Carnival Balloon Pop** | ★★☆☆☆ (2/5) | Yes (100%) | 2 – 3 Days | Very High (Super satisfying pops) |
| **3. Brick Breaker (Breakout)** | ★★☆☆☆ (2/5) | Yes (100%) | 2 – 3 Days | High (Classic retro arcade feel) |
| **4. Whack-A-Mole** | ★★★☆☆ (3/5) | Yes (100%) | 3 – 4 Days | Very High (Fast-paced physical workout) |
| **5. Trivia Quiz** | ★★☆☆☆ (2/5) | Yes (100%) | 2 – 3 Days | High (Great for kids/education) |
| **6. Tic-Tac-Toe Duel** | ★★★☆☆ (3/5) | Yes (100%) | 3 – 4 Days | High (Competitive 2-player) |
| **7. Simon Says (Memory)** | ★★☆☆☆ (2/5) | Yes (100%) | 2 – 3 Days | Medium (Brain & agility challenge) |
| **8. Word Spell Wall** | ★★★★☆ (4/5) | Yes (100%) | 5 – 7 Days | Medium/High (Educational) |

---

## 4. Recommended Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       LAPTOP / PC                           │
│                                                             │
│   [ Front Camera Feed ]                                     │
│            │                                                │
│            ▼                                                │
│   1. Rebound Detection (Post-Hit Vertex):                   │
│      Find frame where horizontal velocity reverses          │
│      -> Coordinates (X_cam, Y_cam)                          │
│            │                                                │
│            ▼                                                │
│   2. Homography Transform (4 ArUco Markers):                │
│      (X_cam, Y_cam) ---> (X_proj, Y_proj)                   │
│            │                                                │
│            ▼                                                │
│   3. Game Logic Engine (HTML5 Canvas / Flutter / Pygame):   │
│      - Collision Check: Is (X_proj, Y_proj) inside target?  │
│      - State Update: Pop Balloon / Add Score / Play Audio   │
│            │                                                │
│            ▼                                                │
│   4. Fullscreen Output to HDMI / Wireless                   │
└────────────┬────────────────────────────────────────────────┘
             │ HDMI (Zero-Lag)
             ▼
   [ Magcubic HY300 PRO Projector ]
             │
             ▼
   [ Physical Whiteboard Canvas ]
```

---

## 5. Recommended Starter Project: "Arcade Bullseye & Balloon Pop"

To get the quickest win with the highest fun factor:
1. **Phase 1 (Day 1):** Build **Arcade Bullseye**.
   - Draws a full-screen bullseye on the projector.
   - Front camera detects the hit coordinate and projects a glowing splat with audio.
   - Perfect test to calibrate projector-to-camera alignment.
2. **Phase 2 (Day 2):** Add **Balloon Pop**.
   - Adds floating targets with particle burst animations and sound effects.
