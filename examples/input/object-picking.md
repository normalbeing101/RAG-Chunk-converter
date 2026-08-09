---
title: GDevelop Documentation
tags: [events, conditions, picking]
---

# Object Picking

Object picking determines which instances of an object are selected by
conditions. Understanding it is essential before writing non-trivial event
sheets, because almost every action operates on a *picked* set rather than on
every instance in the scene.

## How it works

When a condition is evaluated, GDevelop maintains a list of picked instances.
Actions can then operate only on those instances. If no condition touches an
object, every instance of that object is considered picked.

### Object picking in sub-events

Sub-events inherit the picked instances of their parent event. This is what
makes nested events useful: you narrow the selection once, then refine it.

### Resetting the selection

The picked list is reset at the start of every top-level event.

## Example

If the player overlaps an enemy, the enemy can be selected and an action can
modify its health. Only the overlapping instance is affected.

```javascript
// Approximation of the internal picking logic.
function pickColliding(instances, player) {
  return instances.filter((instance) => instance.collidesWith(player));
}
```

## Common conditions

- **Collision** - picks instances that overlap another object.
- **Distance** - picks instances within a radius.
- **Variable comparison** - picks instances whose variable matches.
- **Animation** - picks instances playing a given animation.

## Reference

| Condition | Picks | Cost |
| --- | --- | --- |
| Collision | Overlapping instances | Medium |
| Distance | Instances within a radius | Low |
| Variable | Instances matching a value | Low |
| Animation | Instances in an animation | Low |

> Picking is reset at the start of each top-level event. Rely on sub-events
> when you need to keep a narrowed selection.
