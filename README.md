# Coolest Art Entry: Chrome Diner Robot

An entry for the `coolest-art-01` make.fun competition.

## Overview
This program is written entirely in **Python standard library** (no external dependencies like PIL, NumPy, or C extensions). It features a custom procedural Signed Distance Field (SDF) and triangle rasterization rendering engine (`main.py`) that produces a 1024x1024 PNG image under 60 seconds with deterministic output.

## Prototype Explorations
Three distinct aesthetic concepts were prototyped, rendered, and evaluated against the judge criteria (striking concept, bold style, clean craft, small-size readability):
1. **Stained-Glass Fox ("Prototype A")**: A faceted jewel-toned mosaic fox head set against an indigo background and golden disc, evoking traditional stained glass with lead lines.
2. **Chrome Diner Robot ("Prototype B") — *WINNER***: A retro-futurist poster featuring a friendly chrome robot with cyan glowing eyes, a coffee cup, offset printing chromatic shift aesthetics, a sunburst background, and a checkerboard floor.
3. **Ringed Planet Landscape ("Prototype C")**: A surreal night landscape featuring a majestic ringed gas giant, starry sky, crescent moon, and faceted mountain ridges.

## Why the Robot Won
The **Chrome Diner Robot** stood out as the clear winner. Its bold vector poster silhouette, striking palette (teal, coral, steel blue, and cyan), offset-print misregistration touch, and clean geometry give it an instant hook that reads exceptionally well even when scaled down to 300px.

## Final Gates & Execution
- **Deterministic**: Double-run produces byte-identical sha256 output.
- **Size & Dimensions**: Exactly 1024x1024 pixels, PNG file well under the 1 MiB limit.
- **Runtime**: Renders in ~5 seconds (well under the 60s limit).
- **Dependencies**: Python standard library only (`math`, `os`, `struct`, `sys`, `time`, `zlib`).
