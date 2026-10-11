# Three-address IR

One instruction per line. A `#` starts a comment. Blank lines are ignored. Register and label names are identifiers: a letter or underscore, then letters, digits, or underscores. The words `block`, `if`, `goto`, and `return` are reserved.

## Blocks

```
block entry:
  a = 1
  b = a + 2
  if a goto left
block right:
  goto join
block left:
  b = b + 1
  goto join
block join:
  return b
```

The header is `block name:`. The colon is required.

A block may fall through only when its last instruction is not `goto`, `if`, or `return` and another block follows it. The last block in the program must end with `return` or `goto`.

`if cond goto label` is a terminator. The true edge goes to `label`. The false edge goes to the next block in source order. There is no `else` keyword.

## Instructions

| Form | Meaning |
| --- | --- |
| `name = 1` | Constant. Negative constants are written `-1`, with no space. |
| `name = other` | Copy. |
| `name = left + right` | Arithmetic. Operators are `+`, `-`, `*`, and `/`, with spaces around the operator. |
| `if cond goto label` | Conditional branch. `cond` is a register or an integer. |
| `goto label` | Unconditional jump. |
| `return` | Return with no value. |
| `return value` | Return a register or an integer. |

Operands of `+`, `-`, `*`, and `/` may each be a register or an integer. The same register used twice in one instruction counts as one use for spill cost. Example: `b = a + a` uses `a` once.

The analyzer does not execute the instructions. Division by zero is not diagnosed. A register that is read and never defined anywhere is reported as an undefined use. That check is not path-sensitive: a definition on only one branch still counts as a definition.

## Profiles

Profiles are not part of the text. Send them as JSON. Each profile maps every block label to a non-negative integer execution count. A count of 0 means you are stating that the block did not execute in that profile. Omitting a block is an error. The analyzer will not assume a count.

## Live ranges

Milestone 1 creates one live range per virtual register that is live at any instruction boundary. A definition whose new value is never live is reported as a dead definition and does not become a store in the spill-cost model. The allocation response does not rewrite the IR into spill code. It reports the live ranges, the spill sites, and the register or spill chosen for each range.
