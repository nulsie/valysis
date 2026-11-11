# changelog

as the name suggests, this is a file where changes are logged :3

## [v1.1.4] - 2026-11-13

### Fixed

- added signed modulo methods for supporting signed modulo tracking in `CircularStridedInterval`, `TristateBitVectors`, `VSAReducedState`, `DualInterval`

- added missing modulo methods for `DualIntervals` and `VSAReducedState`

- introduced a `StackRegion` method to properly model function stack frames and local variables without causing false alias collisions or collapsing stack-relative pointers into global/absolute states

- hardened the relational assumptions(`assume_ult`,`assume_slt`) in CSI and TBV to prevent extreme wrapping intervals, sparse strides, and Python's infinite-precision negative bitwise (~) evaluation traps

- tuned memory tainting in `memory.py` using an absolute precedence method to prevent full chunk taints from polluting already precise entires

### Changed

## [v1.1.3] - 2026-10-27

### Fixed

- chunk tainting granularity & over-approximation(`memory.py`)

- hybrid set intersection logic prone to bitwise mismatch(`product.py`)

- lazy sync precision drift (`dual_interval.py`)

### Changed

- refactored the `__mul__` in `tristate.py` to use an optimized method of 64-bit multiplication than the former of iterating bit-by-bit

## [v1.1.2] - 2026-10-15

### Fixed

- `VSAReducedState.assume_slt` ignores Tristate refinement

- `TristateBitVector.assume_ult` missing emptiness check on high-bit masking

- memory state weak/strong update slice interleaving inconsistency

- a division-by-zero surviving state type mismatch in `signed_floordiv` 

## [v1.1.1] - 2026-09-28

### Added

- Bitwise Shifts (`__lshift__`, `__rshift__`, and arithmetic shifts) and Multiplication for `TristateBitVector` and `VSAReducedState` domains

- `__sub__` implementation in ValueSet(`memory.py`)

- Modulo(`__mod__`) operations in CSI and TBV

- Some Fast-Path Constant Folding & Algebraic Reductions for some new stuff(CSI mostly)

- Hierarchical memory tainting (The "chunk" model) for optimization

### Fixed

- Cross-Byte Correlation Loss (over-approximation via phantom states) during unaligned or partial memory loads.

- Subtraction Precision Leak (`product.py`)

- Zero-Division Bypass (`intervals.py`)

- Pointer Slicing Corruption (`memory.py`)

- Unconstrained Write Clobbering (`memory.py`)

- Invalid Pointer Addition(`memory.py`)

- The Identity Fast-Path Bug in `__and__`, `__or__`, and `__xor__`(`intervals.py`)

- The Overshift Truncation Bug(`intervals.py`)

- `DualInterval` signed domain bias initialization and sync immutability

### Changed

- Refactored `memory.py` with new chunk model

## [v1.1.0] - 2026-08-24

### Added

- Fast-Pathing & Early Returns for Constants/Singletons

- Singleton Object Caching

- Generator-Based Splitting

- Lazy Synchronization & Reduction

- Memory State Lookup Optimization

### Fixed

- False Inconsistency Bug in `VSAReducedState._reduce()`

- Systematic Empty ( ⊥ ) State in `DualInterval` Arithmetic

- Invalid Bounds in `CircularStridedInterval.__xor__`

- Memory Region Wiping in `MemoryState.store()`

- Shift Offset Cancellation in `DualInterval.__add__`

### Changed

- None

## [v1.0.0] - 2026-08-19

### Added

- Project files

### Fixed

- None

### Changed

- None
