# The Seed – An LLM Agent Framework for Game Developers

[中文版README](https://github.com/anantheparty/The-Seed/blob/main/README_CN.md)

## Overview

**The Seed** is an open-source framework designed for game developers. Its goals are:

- Allow games to expose their **state / actions** to an LLM-Agent through a unified integration protocol, enabling the LLM to observe the game, issue actions, and interact with players.

- Enable LLMs and traditional game AI to form a complementary workflow, handling decision-making and execution together under a controlled compute budget.

---

## Design Principles

1. **Give the Agent a clear and well-defined entry point**

   - The basic assumption is that the game is willing to expose an interface layer of “observations / actions / events.”
   - Integration should be minimally invasive—more like attaching a module, not rewriting the game’s logic.
   - The framework aims to stay compatible with different engine architectures and allow light-weight, maintainable integration.

2. **LLM for high-level decisions, game for execution**

   - LLMs excel at: situational understanding, plan generation, strategy reasoning, and behavior explanation.
   - Game-native AI (behavior trees / state machines / rule systems) excel at: pathfinding, micro-actions, condition checks, and frame-level logic.
   - The Seed follows this separation of roles:  
     **LLM generates intentions → the game executes them.**  
     Achieve stable behavior with minimal model calls.

3. **Not tied to any specific gameplay**

   - Provides an extensible Action / Observation / Tool protocol.
   - Does not pre-define semantics such as “attack / gather / build”; each game defines its own actions and data structures.
   - The framework organizes these definitions into LLM-friendly prompts and tool interfaces so that different games can build their own Agent styles within a shared framework.

4. **Iterate from real integration experience**

   - The project is still under active development.
   - Priority: reduce the steps and code needed for a new game to “go from zero to having an Agent running.”
   - Use real projects to refine scaffolding, examples, debugging tools, and best practices.
   - The long-term goal is to provide a framework that is **practical, well-documented, and easy to introduce to your team.**

---

## Current Project Status

- **Stage: PoC / Early Prototype**
  - ✅ Completed: overall architecture draft & agent interaction workflow
  - ✅ Completed: initial version of the game-side API (observation / action / event)
  - ⏳ In progress:  
    - The Seed core Agent protocol  
    - Demo Agent for OpenRA (e.g., auto-econ / auto-battle)  
    - First version of README / documentation / integration guides

---

## Roadmap

### Phase 0 – OpenRA Validation (⏳ Ongoing, ~45–60 days)

- Define a basic RTS-oriented Agent protocol (observation / action / tick / event)
- Deliver an **“OpenRA + Agent Demo”** that works out-of-the-box
- Prepare developer documentation:
  - How to integrate The Seed into a game
  - How to write a minimal LLM-Agent controlling one faction

### Phase 1 – Framework Stabilization & Documentation

- Extract a **Core SDK** decoupled from any specific game
- Improve:
  - Agent lifecycle management
  - Tick / planning / memory / logging
  - Adapters for cloud or local LLM models

### Phase 2 – Multi-Game Integration & Community Growth

- Add a second supported game (priority: strategy / simulation)
- Build a **Sample Integrations Collection**
- Host developer-oriented activities:
  - Hackathon / Game Jam
  - Online workshops and technical sharing

### Phase 3 – Agent Ecosystem

- Propose an **Agent Description Standard** to support:
  - Sharing strategies across different games  
  - Community-created Agent roles
- Explore additional features:
  - Multi-Agent cooperation
  - Coach / spectator-type Agents
  - Replay analysis / explanation Agents

---

## How to Contribute

- ⭐ **Star the repo** — follow updates and support the project  
- 🐛 **Open Issues** — ideas, feedback, bug reports  
- 🔧 **Submit PRs** — docs, improvements, examples  
- 📣 **Spread the word** — share with game devs or AI enthusiasts

---

## Getting Started

TODO

### 1. Environment Setup

TODO