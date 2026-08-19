import math
from typing import Set, Optional, Callable
from .intervals import CircularStridedInterval
from .tristate import TristateBitVector

class HybridSetDomain:
    __slots__ = ('bits', 'mask', 'max_cardinality', 'discrete_set', 'abstract_state', 'is_empty')

    def __init__(
        self, 
        bits: int = 32, 
        max_cardinality: int = 8, 
        discrete_set: Optional[Set[int]] = None, 
        abstract_state: Optional[VSAReducedState] = None,
        is_empty: bool = False
    ):
        self.bits = bits
        self.mask = (1 << bits) - 1
        self.max_cardinality = max_cardinality
        self.is_empty = is_empty

        if self.is_empty:
            self.discrete_set = None
            self.abstract_state = None
            return

        if discrete_set is not None:
            clean_set = {v & self.mask for v in discrete_set}
            if not clean_set:
                self.is_empty = True
                self.discrete_set = None
                self.abstract_state = None
            elif len(clean_set) <= self.max_cardinality:
                self.discrete_set = clean_set
                self.abstract_state = None
            else:
                                                                               
                self.discrete_set = None
                self.abstract_state = self._set_to_abstract(clean_set)
        elif abstract_state is not None:
            self.discrete_set = None
            self.abstract_state = abstract_state
            if self.abstract_state.is_empty:
                self.is_empty = True
        else:
            self.is_empty = True
                                                                                                                                                                                            
    def _set_to_abstract(self, values: Set[int]) -> VSAReducedState:
        sorted_vals = sorted(values)
        min_val, max_val = sorted_vals[0], sorted_vals[-1]

                                                 
        if len(sorted_vals) > 1:
            diffs = [sorted_vals[i+1] - sorted_vals[i] for i in range(len(sorted_vals) - 1)]
            stride = math.gcd(*diffs)
        else:
            stride = 0

                                                      
        ones = self.mask
        zeros = self.mask
        for val in values:
            ones &= val
            zeros &= (~val & self.mask)

        csi = CircularStridedInterval(stride, min_val, max_val, self.bits)
        tbv = TristateBitVector(self.bits, ones, zeros)
        return VSAReducedState(csi, tbv)

    def to_abstract(self) -> VSAReducedState:
        if self.is_empty:
            return VSAReducedState(
                CircularStridedInterval.empty(self.bits),
                TristateBitVector.empty(self.bits)
            )
        if self.abstract_state is not None:
            return self.abstract_state
        return self._set_to_abstract(self.discrete_set)

    @classmethod
    def value(cls, val: int, bits: int = 32, max_cardinality: int = 8) -> 'HybridSetDomain':
        return cls(bits=bits, max_cardinality=max_cardinality, discrete_set={val})

    @classmethod
    def from_set(cls, values: Set[int], bits: int = 32, max_cardinality: int = 8) -> 'HybridSetDomain':
        return cls(bits=bits, max_cardinality=max_cardinality, discrete_set=values)

    @classmethod
    def empty(cls, bits: int = 32, max_cardinality: int = 8) -> 'HybridSetDomain':
        return cls(bits=bits, max_cardinality=max_cardinality, is_empty=True)
                                                                                                                                                                                            
    def _apply_binop(
        self, 
        other: 'HybridSetDomain', 
        set_op: Callable[[int, int], int], 
        abstract_op: Callable[[VSAReducedState, VSAReducedState], VSAReducedState]
    ) -> 'HybridSetDomain':
        if self.is_empty or other.is_empty:
            return self.empty(self.bits, self.max_cardinality)
                                                  
        if self.discrete_set is not None and other.discrete_set is not None:
            res_set = {set_op(a, b) & self.mask for a in self.discrete_set for b in other.discrete_set}
            return HybridSetDomain(self.bits, self.max_cardinality, discrete_set=res_set)
                                               
        res_abs = abstract_op(self.to_abstract(), other.to_abstract())
        return HybridSetDomain(self.bits, self.max_cardinality, abstract_state=res_abs)

    def __add__(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        return self._apply_binop(other, lambda a, b: a + b, lambda a, b: a + b)

    def __sub__(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        return self._apply_binop(other, lambda a, b: a - b, lambda a, b: a - b)

    def __and__(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        return self._apply_binop(other, lambda a, b: a & b, lambda a, b: a & b)

    def __or__(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        return self._apply_binop(other, lambda a, b: a | b, lambda a, b: a | b)

    def __xor__(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        return self._apply_binop(other, lambda a, b: a ^ b, lambda a, b: a ^ b)
                                                                                                                                                                             
    def union(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        if self.is_empty: return other
        if other.is_empty: return self
    
        if self.discrete_set is not None and other.discrete_set is not None:
            return HybridSetDomain(self.bits, self.max_cardinality, discrete_set=self.discrete_set | other.discrete_set)
                                                
        res_abs = self.to_abstract().union(other.to_abstract())
        return HybridSetDomain(self.bits, self.max_cardinality, abstract_state=res_abs)

    def intersect(self, other: 'HybridSetDomain') -> 'HybridSetDomain':
        if self.is_empty or other.is_empty:
            return self.empty(self.bits, self.max_cardinality)
                                    
        if self.discrete_set is not None and other.discrete_set is not None:
            return HybridSetDomain(self.bits, self.max_cardinality, discrete_set=self.discrete_set & other.discrete_set)
                                                          
        if self.discrete_set is not None:
            abs_other = other.to_abstract()
            filtered = {
                v for v in self.discrete_set 
                if abs_other.interval.contains(v) 
                and ((v & abs_other.tristate.ones) == abs_other.tristate.ones)
                and ((~v & abs_other.tristate.zeros) == (abs_other.tristate.zeros & self.mask))
            }
            return HybridSetDomain(self.bits, self.max_cardinality, discrete_set=filtered)

        if other.discrete_set is not None:
            return other.intersect(self)
                                       
        a_abs, b_abs = self.to_abstract(), other.to_abstract()
        res_csi = a_abs.interval.intersect(b_abs.interval)
        res_tbv = a_abs.tristate & b_abs.tristate
        return HybridSetDomain(self.bits, self.max_cardinality, abstract_state=VSAReducedState(res_csi, res_tbv))

    def __repr__(self):
        if self.is_empty: return "⊥"
        if self.discrete_set is not None:
            return f"Set{{{', '.join(hex(x) for x in sorted(self.discrete_set))}}}"
        return f"Hybrid({self.abstract_state})"

class VSAReducedState:
    __slots__ = ('interval', 'tristate', 'bits', 'is_empty')

    def __init__(self, interval: CircularStridedInterval, tristate: TristateBitVector):
        assert interval.bits == tristate.bits
        self.bits = interval.bits
        self.interval = interval
        self.tristate = tristate
        self.is_empty = interval.is_empty or tristate.is_empty
        if not self.is_empty:
            self._reduce()

    def _reduce(self):
        tri_min, tri_max = self.tristate.get_min_max()
        if self.interval.stride > 0 and self.interval.lower <= self.interval.upper:
            n_lower = max(self.interval.lower, tri_min)
            n_upper = min(self.interval.upper, tri_max)
            if n_lower > self.interval.lower:
                rem = (n_lower - self.interval.lower) % self.interval.stride
                if rem != 0: n_lower += (self.interval.stride - rem)
            if n_upper < self.interval.upper:
                rem = (n_upper - self.interval.lower) % self.interval.stride
                if rem != 0: n_upper -= rem
            if n_lower > n_upper:
                self.is_empty = True
                return
            self.interval = CircularStridedInterval(self.interval.stride, n_lower, n_upper, self.bits)

        align_zeros = (self.interval.stride & -self.interval.stride) - 1 if self.interval.stride > 0 else 0
        diff = self.interval.lower ^ self.interval.upper if self.interval.lower <= self.interval.upper else -1
        known_mask = self.tristate.mask if diff == 0 else (self.tristate.mask & ~((1 << diff.bit_length()) - 1) if diff > 0 else 0)
        
        merged_ones = self.tristate.ones | (self.interval.lower & known_mask)
        merged_zeros = self.tristate.zeros | ((~self.interval.lower & known_mask) | align_zeros)
        self.tristate = TristateBitVector(self.bits, merged_ones, merged_zeros)
        if self.tristate.is_empty: self.is_empty = True

    def __add__(self, other: 'VSAReducedState') -> 'VSAReducedState':
        return VSAReducedState(self.interval + other.interval, TristateBitVector.top(self.bits))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VSAReducedState): return False
        if self.is_empty and other.is_empty: return True
        if self.is_empty != other.is_empty: return False
        return self.interval == other.interval and self.tristate.ones == other.tristate.ones and self.tristate.zeros == other.tristate.zeros
                                                                                                                                                                                           
    def zero_extend(self, new_bits: int) -> 'VSAReducedState':
        return VSAReducedState(
            self.interval.zero_extend(new_bits), 
            self.tristate.zero_extend(new_bits)
        )
    
    def sign_extend(self, new_bits: int) -> 'VSAReducedState':
        return VSAReducedState(
            self.interval.sign_extend(new_bits), 
            self.tristate.sign_extend(new_bits)
        )
    
    def truncate(self, new_bits: int) -> 'VSAReducedState':
        return VSAReducedState(
            self.interval.truncate(new_bits), 
            self.tristate.truncate(new_bits)
        )
    
    def extract(self, high: int, low: int) -> 'VSAReducedState':
        return VSAReducedState(
            self.interval.extract(high, low), 
            self.tristate.extract(high, low)
        )
    
    def concat(self, other: 'VSAReducedState') -> 'VSAReducedState':
        return VSAReducedState(
            self.interval.concat(other.interval), 
            self.tristate.concat(other.tristate)
        )
                                                                                                                                                                                                           
    def assume_eq(self, other: 'VSAReducedState') -> tuple['VSAReducedState', 'VSAReducedState']:
        i1, i2 = self.interval.assume_eq(other.interval)
        t1, t2 = self.tristate.assume_eq(other.tristate)
        return VSAReducedState(i1, t1), VSAReducedState(i2, t2)
    
    def assume_neq(self, other: 'VSAReducedState') -> tuple['VSAReducedState', 'VSAReducedState']:
        i1, i2 = self.interval.assume_neq(other.interval)
        t1, t2 = self.tristate.assume_neq(other.tristate)
        return VSAReducedState(i1, t1), VSAReducedState(i2, t2)
    
    def assume_ult(self, other: 'VSAReducedState') -> tuple['VSAReducedState', 'VSAReducedState']:
        i1, i2 = self.interval.assume_ult(other.interval)
        return VSAReducedState(i1, self.tristate), VSAReducedState(i2, other.tristate)
    
    def assume_slt(self, other: 'VSAReducedState') -> tuple['VSAReducedState', 'VSAReducedState']:
        i1, i2 = self.interval.assume_slt(other.interval)
        return VSAReducedState(i1, self.tristate), VSAReducedState(i2, other.tristate)

    def __or__(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval | other.interval
        res_tbv = self.tristate | other.tristate
        return VSAReducedState(res_csi, res_tbv)
    
    def __and__(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval & other.interval
        res_tbv = self.tristate & other.tristate
        return VSAReducedState(res_csi, res_tbv)

    def __sub__(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval - other.interval
        return VSAReducedState(res_csi, TristateBitVector.top(self.bits))
    
    def __xor__(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval ^ other.interval
        res_tbv = self.tristate ^ other.tristate
        return VSAReducedState(res_csi, res_tbv)

    def union(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval.union(other.interval)
        res_tbv = self.tristate.join(other.tristate)
        return VSAReducedState(res_csi, res_tbv)

    def intersect(self, other: 'VSAReducedState') -> 'VSAReducedState':
        res_csi = self.interval.intersect(other.interval)
        res_tbv = self.tristate.intersect(other.tristate)
        return VSAReducedState(res_csi, res_tbv)
