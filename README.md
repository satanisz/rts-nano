# rts-nano

A simple and easy real-time strategy (RTS) game built with Python and Pygame. 
The main goal of this project is to serve as an environment for learning Reinforcement Learning (RL) using PyTorch. 

## Overview
While the game features basic RTS mechanics (resource gathering, base building, unit production, and combat), it is intentionally designed to include certain unbalanced mechanics. These imbalances create unique challenges and complex scenarios for RL agents to explore and solve.

## Features
* **2D Game Engine:** A custom event-driven loop built on top of Pygame for rendering, logic, and state coordination.
* **Entities & Assets:** Includes units (Peasants, Knights, Archers, Mages), buildings (Bases), and resources (Wood, Crystal).
* **RL Sandbox:** The codebase is designed as a playground to apply PyTorch-based Reinforcement Learning algorithms to RTS macro and micro tasks.

## Getting Started

### Prerequisites
* Python 3.13 or newer
* Dependencies are managed via `uv` or `hatchling`.

### Installation

```bash
# Install dependencies (e.g., using pip or uv)
uv pip install -e .

# Optional test suite (if you want to run tests)
tox run
```

## Goals
* Learn and experiment with PyTorch by giving RL agents control over groups of units.
* Explore strategies in deliberately unbalanced gameplay.