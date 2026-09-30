# Simulation improvements

Ideas for making runs smoother and more repeatable. Nothing here is done yet.

## The bottleneck

- Vehicles move a fixed number of pixels per rendered frame (`self.x += self.speed` in `models/vehicle.py`).
- Signal timers, arrivals and the release clock run on wall time in threads.
- So any frame dip slows vehicles relative to the signals. This causes release drift (> 250 ms) and FPS divergence (> 5%).
- Render loop, generator, controller and init threads share one Python process and one GIL.
- `clock.tick(60)` sleeps, so pacing has jitter. pygame's `Clock` also truncates to whole ms.
- Two plans in parallel already caused a 5.49% FPS divergence.

## GPU

Not worth it. pygame blits on the CPU, and the scene is small (1008 px, a few dozen sprites). A GPU port would not fix physics being tied to frame count.

## No-invalidation changes (launch only, code untouched)

- Pin each run to its own cores: `taskset -c 0-1`, `2-3`, and so on.
- Close codex and other heavy apps before collecting.
- Start with 3 plans in parallel, go to 5 only if clean. Run heavy envs last, 1-2 at a time.
- Check `comparison.json` and `timing.json` for every run.
- `SDL_VIDEODRIVER=dummy` is an env change, not a code change. Probe one plan both ways and compare FPS, drift and results first.

## Simulator changes (need fresh validation, old runs become historical)

1. Time-based physics: move by `speed * dt` from `runclock`, or a fixed 60 Hz logic step on the run clock. FPS stops mattering.
2. Split update from draw so runs can go headless and faster than real time.
3. `convert()` / `convert_alpha()` on loaded images.
4. `tick_busy_loop(60)` for tighter frame pacing.
5. Use `time.perf_counter` as the only clock, not summed deltas.

## Decision

- Now: keep the current simulator, finish the remaining plans with pinned cores and limited parallelism.
- If heavy plans keep failing drift: treat time-based physics as a new study and rerun all 100 plans. Do not mix with old data.

## Sources

- [pygame fixed timestep discussion](https://groups.google.com/g/pygame-mirror-on-google-groups/c/QiP9LCS52Rs)
- [Pygame Clock tick drift](https://bugnet.io/blog/fix-pygame-clock-tick-drifting-over-time)
- [pygame headless wiki](https://www.pygame.org/wiki/HeadlessNoWindowsNeeded)
- [Stutter and desync in pygame loops](https://www.mindfulchase.com/explore/troubleshooting-tips/game-development-tools/fixing-frame-stuttering-and-timing-desync-in-pygame-game-loops.html)
