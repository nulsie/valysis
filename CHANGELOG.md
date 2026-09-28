# Changelog

as the name suggests, this is a file where changes are logged :3

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
