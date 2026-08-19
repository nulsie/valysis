import math
from typing import TYPE_CHECKING
from .common import VSADivisionByZero, _exgcd

class CircularStridedInterval:
    __slots__ = ('stride', 'lower', 'upper', 'bits', 'mask', 'modulus', 'is_empty')

    def __init__(self, stride: int, lower: int, upper: int, bits: int = 32, is_empty: bool = False):           
        self.bits = bits           
        self.mask = (1 << bits) - 1           
        self.modulus = 1 << bits           
        self.is_empty = is_empty           
                        
        if self.is_empty:           
            self.stride, self.lower, self.upper = 0, 0, 0           
            return           
                            
        self.lower = lower & self.mask           
        upper = upper & self.mask           
                        
        if self.lower == upper:           
            self.stride = 0           
            self.upper = self.lower           
        else:           
            self.stride = abs(stride)           
            if self.stride == 0:           
                self.stride = 1           
                                
            dist = (upper - self.lower) & self.mask           
            aligned_dist = dist - (dist % self.stride)           
            self.upper = (self.lower + aligned_dist) & self.mask           

    @classmethod           
    def empty(cls, bits: int = 32) -> 'CircularStridedInterval':           
        return cls(0, 0, 0, bits, is_empty=True)           
    
    @classmethod           
    def top(cls, bits: int = 32) -> 'CircularStridedInterval':           
        return cls(1, 0, (1 << bits) - 1, bits)           
    
    @classmethod           
    def value(cls, val: int, bits: int = 32) -> 'CircularStridedInterval':           
        return cls(0, val, val, bits)           

    def contains(self, val: int) -> bool:           
        if self.is_empty: return False           
            
        val = val & self.mask           
        dist = (self.upper - self.lower) & self.mask           
        val_dist = (val - self.lower) & self.mask           
            
        if val_dist > dist:            
            return False           
                
        if self.stride == 0:            
            return val == self.lower           
                
        return (val_dist % self.stride) == 0           
    
    def split_if_wrapped(self: 'CircularStridedInterval') -> list['CircularStridedInterval']:           
        if self.is_empty:           
            return []           
                    
        if self.lower <= self.upper:           
            return [self]           
                    
        dist_to_max = self.mask - self.lower           
        rem = dist_to_max % self.stride           
        first_upper = self.mask - rem           
        second_lower = (first_upper + self.stride) & self.mask           
                
        return [           
            self.__class__(self.stride, self.lower, first_upper, self.bits),           
            self.__class__(self.stride, second_lower, self.upper, self.bits)           
        ]
    
    def __eq__(self, other: object) -> bool:           
        if not isinstance(other, self.__class__): return False           
        if self.bits != other.bits: return False           
        if self.is_empty and other.is_empty: return True           
        if self.is_empty != other.is_empty: return False           
        return (self.stride, self.lower, self.upper) == (other.stride, other.lower, other.upper)           
    
    def __repr__(self):           
        if self.is_empty: return "⊥"           
        if self.stride == 0: return f"[{self.lower}]"           
        wrap_char = " ↺" if self.lower > self.upper else ""           
        return f"{self.stride}[{self.lower}, {self.upper}]{wrap_char} (b{self.bits})"           

    def __add__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during addition"           
        if self.is_empty or other.is_empty: return self.empty(self.bits)           
            
        dist_self = (self.upper - self.lower) & self.mask           
        dist_other = (other.upper - other.lower) & self.mask           
            
        if dist_self + dist_other >= self.mask:           
            return self.top(self.bits)           
    
        n_stride = math.gcd(self.stride, other.stride)           
        n_lower = (self.lower + other.lower) & self.mask           
        n_upper = (self.upper + other.upper) & self.mask           
            
        return self.__class__(n_stride, n_lower, n_upper, self.bits)           
    
    def __sub__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during subtraction"           
        if self.is_empty or other.is_empty: return self.empty(self.bits)           
            
        dist_self = (self.upper - self.lower) & self.mask           
        dist_other = (other.upper - other.lower) & self.mask           
            
        if dist_self + dist_other >= self.mask:           
            return self.top(self.bits)           
    
        n_stride = math.gcd(self.stride, other.stride)           
        n_lower = (self.lower - other.upper) & self.mask           
        n_upper = (self.upper - other.lower) & self.mask           
            
        return self.__class__(n_stride, n_lower, n_upper, self.bits)           
    
    def _mul_linear(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        candidates = (           
            self.lower * other.lower,           
            self.lower * other.upper,           
            self.upper * other.lower,           
            self.upper * other.upper            
        )
                    
        raw_min = min(candidates)           
        raw_max = max(candidates)           
                    
        n_stride = math.gcd(           
            math.gcd(self.stride * other.lower, other.stride * self.lower),           
            self.stride * other.stride           
        )
                    
        if (raw_max - raw_min) >= self.mask:           
            n_stride = math.gcd(n_stride, 1 << self.bits)           
            if n_stride <= 1:           
                return self.top(self.bits)           
                        
            n_lower = raw_min & self.mask           
            n_upper = (n_lower - n_stride) & self.mask           
                    
            return self.__class__(n_stride, n_lower, n_upper, self.bits)           
            
        n_lower = raw_min & self.mask           
        n_upper = raw_max & self.mask           
                    
        return self.__class__(n_stride, n_lower, n_upper, self.bits)           
    
    def __mul__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        if not isinstance(other, self.__class__):           
            return NotImplemented           
        assert self.bits == other.bits           
        if self.is_empty or other.is_empty:            
            return self.empty(self.bits)           
                    
        result = self.empty(self.bits)           
                
        for p1 in self.split_if_wrapped():           
            for p2 in other.split_if_wrapped():           
                linear_result = p1._mul_linear(p2)           
                result = result.union(linear_result)           
                        
        return result           
    
    def __floordiv__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        if not isinstance(other, self.__class__):           
            return NotImplemented           
        assert self.bits == other.bits, "Bit-width mismatch during division"           
        if self.is_empty or other.is_empty:            
            return self.empty(self.bits)           
                                
        if other.lower == 0 and other.upper == 0:           
            raise VSADivisionByZero("Guaranteed division by zero vulnerability.", self.empty(self.bits))           
                    
        result = self.empty(self.bits)           
        has_zero_div = False           
                            
        for p1 in self.split_if_wrapped():           
            for p2 in other.split_if_wrapped():           
                p2_lower = p2.lower           
                            
                if p2_lower == 0:           
                    has_zero_div = True           
                    if p2.stride == 0:           
                        continue            
                    p2_lower = p2.stride            
                            
                if p2.upper < p2_lower:           
                    continue           
                                        
                n_lower = p1.lower // p2.upper           
                n_upper = p1.upper // p2_lower           
                                    
                if p2.stride == 0 and p2.lower == p2.upper and p2.lower != 0:           
                    if p1.stride % p2.lower == 0:           
                        n_stride = p1.stride // p2.lower           
                    else:           
                        n_stride = 1           
                else:           
                    n_stride = 1           
                                        
                div_part = self.__class__(n_stride, n_lower, n_upper, self.bits)           
                result = result.union(div_part)           
                
        if has_zero_div:           
            raise VSADivisionByZero("Potential division by zero vulnerability.", result)           
                                    
        return result           
    
    def signed_floordiv(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        if not isinstance(other, self.__class__):           
            return NotImplemented           
        assert self.bits == other.bits, "Bit-width mismatch during signed division"           
                     
        if self.is_empty or other.is_empty:            
            return self.empty(self.bits)           
                                     
        if other.lower == 0 and other.upper == 0:           
            raise VSADivisionByZero("Guaranteed signed division by zero vulnerability.", self.empty(self.bits))           
                         
        result = self.empty(self.bits)           
        has_zero_div = False           
        sign_bit_val = 1 << (self.bits - 1)           
                     
        def to_signed(val: int) -> int:           
            return val - (1 << self.bits) if val >= sign_bit_val else val           
             
        def trunc_div(n: int, d: int) -> int:           
            sign = -1 if (n < 0) ^ (d < 0) else 1           
            return sign * (abs(n) // abs(d))           
             
        def split_signed(interval: 'CircularStridedInterval') -> list['CircularStridedInterval']:           
            sub_parts = []           
            for p in interval.split_if_wrapped():           
                if p.lower < sign_bit_val and p.upper >= sign_bit_val:           
                    pos_upper = sign_bit_val - 1           
                    dist_to_max_pos = pos_upper - p.lower           
                    aligned_pos_upper = p.lower + (dist_to_max_pos - (dist_to_max_pos % p.stride))           
                    sub_parts.append(           
                        self.__class__(p.stride, p.lower, aligned_pos_upper, interval.bits)           
                    )
                                 
                    dist = sign_bit_val - p.lower           
                    rem = dist % p.stride           
                    neg_lower = sign_bit_val if rem == 0 else sign_bit_val + (p.stride - rem)           
                    if neg_lower <= p.upper:           
                        sub_parts.append(           
                            self.__class__(p.stride, neg_lower, p.upper, interval.bits)           
                        )
                else:           
                    sub_parts.append(p)           
            return sub_parts           
             
        for sp1 in split_signed(self):           
            for sp2 in split_signed(other):           
                sp2_lower = sp2.lower           
                             
                if sp2_lower == 0:           
                    has_zero_div = True           
                    if sp2.stride == 0:           
                        continue            
                    sp2_lower = sp2.stride            
                    if sp2.upper < sp2_lower:           
                        continue           
             
                n_min_signed = to_signed(sp1.lower)           
                n_max_signed = to_signed(sp1.upper)           
                d_min_signed = to_signed(sp2_lower)           
                d_max_signed = to_signed(sp2.upper)           
                             
                candidates = (           
                    trunc_div(n_min_signed, d_min_signed),           
                    trunc_div(n_min_signed, d_max_signed),           
                    trunc_div(n_max_signed, d_min_signed),           
                    trunc_div(n_max_signed, d_max_signed)           
                )
                             
                s_lower = min(candidates)           
                s_upper = max(candidates)           
             
                n_lower = s_lower & self.mask           
                n_upper = s_upper & self.mask           
                                         
                if sp2.stride == 0 and sp2.lower == sp2.upper and sp2.lower != 0:           
                    abs_div = abs(d_min_signed)           
                    if sp1.stride % abs_div == 0:           
                        n_stride = sp1.stride // abs_div           
                    else:           
                        n_stride = 1           
                else:           
                    n_stride = 1           
                                             
                div_part = self.__class__(n_stride, n_lower, n_upper, self.bits)           
                result = result.union(div_part)           
                                         
        if has_zero_div:           
            raise VSADivisionByZero("Potential signed division by zero vulnerability.", result)           
                     
        return result            
    
    def __invert__(self: 'CircularStridedInterval') -> 'CircularStridedInterval':
        if self.is_empty: return self
        n_lower = (~self.upper) & self.mask
        n_upper = (~self.lower) & self.mask
        return self.__class__(self.stride, n_lower, n_upper, self.bits)
    
    def __and__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':
        assert self.bits == other.bits
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        if self == other: return self
            
        result = self.empty(self.bits)
            
        for p1 in self.split_if_wrapped():
            for p2 in other.split_if_wrapped():
                n_lower = _hd_min_and(p1.lower, p1.upper, p2.lower, p2.upper, self.bits)
                n_upper = _hd_max_and(p1.lower, p1.upper, p2.lower, p2.upper, self.bits)
                    
                part = self.__class__(1, n_lower, n_upper, self.bits)
                result = result.union(part)
                    
        return result
        
    def __or__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':
        assert self.bits == other.bits
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        if self == other: return self
            
        result = self.empty(self.bits)
            
        for p1 in self.split_if_wrapped():
            for p2 in other.split_if_wrapped():
                n_lower = _hd_min_or(p1.lower, p1.upper, p2.lower, p2.upper, self.bits)
                n_upper = _hd_max_or(p1.lower, p1.upper, p2.lower, p2.upper, self.bits)
                    
                part = self.__class__(1, n_lower, n_upper, self.bits)
                result = result.union(part)
                    
        return result
        
    def __xor__(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':
        assert self.bits == other.bits
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        if self == other: return self.value(0, self.bits)
            
        result = self.empty(self.bits)
            
        for p1 in self.split_if_wrapped():
            for p2 in other.split_if_wrapped():
                                                                                
                n_upper = _hd_max_or(p1.lower, p1.upper, p2.lower, p2.upper, self.bits)                                                                                                                             
                n_lower = 0 
                    
                part = self.__class__(1, n_lower, n_upper, self.bits)
                result = result.union(part)
                    
        return result
    
    def _extract_shift_amount(self, shift_val) -> int:
        """Helper to extract an integer shift amount from int or CircularStridedInterval."""
        if isinstance(shift_val, int):
            return shift_val
        
                                                                                
        if isinstance(shift_val, str):
            raise TypeError(
                f"Cannot shift by string register name '{shift_val}'. "
                f"Resolve '{shift_val}' to its register value before shifting."
            )
                                                                                          
        if hasattr(shift_val, 'lower') and not callable(shift_val.lower):
            return int(shift_val.lower)
            
        try:
            return int(shift_val)
        except (ValueError, TypeError):
            raise TypeError(f"Invalid shift amount type or value: {type(shift_val)} ({shift_val})")
    
    def __lshift__(self: 'CircularStridedInterval', shift_val) -> 'CircularStridedInterval':
        s_amount = self._extract_shift_amount(shift_val)
        if self.is_empty: return self
        if s_amount >= self.bits: return self.value(0, self.bits)
        if s_amount == 0: return self
        multiplier = self.value(1 << s_amount, self.bits)
        return self * multiplier
    
    def __rshift__(self: 'CircularStridedInterval', shift_val) -> 'CircularStridedInterval':
        s_amount = self._extract_shift_amount(shift_val)
        if self.is_empty: return self
        if s_amount >= self.bits: return self.value(0, self.bits)
        if s_amount == 0: return self
            
        parts = self.split_if_wrapped()
        result = self.empty(self.bits)
            
        for p in parts:
            n_lower = p.lower >> s_amount
            n_upper = p.upper >> s_amount
            divisor = 1 << s_amount
            n_stride = p.stride // divisor if (p.stride % divisor == 0) else 1
            result = result.union(self.__class__(n_stride, n_lower, n_upper, self.bits))
                
        return result
    
    def arithmetic_rshift(self: 'CircularStridedInterval', shift_val) -> 'CircularStridedInterval':
        s_amount = self._extract_shift_amount(shift_val)
        if self.is_empty: return self
        if s_amount == 0: return self
        if s_amount >= self.bits: s_amount = self.bits - 1
            
        result = self.empty(self.bits)
        sign_bit_val = 1 << (self.bits - 1)
            
        for p in self.split_if_wrapped():
            sub_parts = []
            if p.lower < sign_bit_val and p.upper >= sign_bit_val:
                pos_upper = sign_bit_val - 1
                dist_to_max_pos = pos_upper - p.lower
                aligned_pos_upper = p.lower + (dist_to_max_pos - (dist_to_max_pos % p.stride))
                sub_parts.append(self.__class__(p.stride, p.lower, aligned_pos_upper, self.bits))
                    
                dist = sign_bit_val - p.lower
                rem = dist % p.stride
                neg_lower = sign_bit_val if rem == 0 else sign_bit_val + (p.stride - rem)
                if neg_lower <= p.upper:
                    sub_parts.append(self.__class__(p.stride, neg_lower, p.upper, self.bits))
            else:
                sub_parts.append(p)
                    
            for sp in sub_parts:
                to_signed = lambda val: val - (1 << self.bits) if val >= sign_bit_val else val
                s_lower = to_signed(sp.lower) >> s_amount
                s_upper = to_signed(sp.upper) >> s_amount
                    
                divisor = 1 << s_amount
                n_stride = sp.stride // divisor if (sp.stride % divisor == 0) else 1
                shifted_part = self.__class__(n_stride, s_lower & self.mask, s_upper & self.mask, self.bits)
                result = result.union(shifted_part)
                    
        return result

    def widen(self: 'CircularStridedInterval', other: 'CircularStridedInterval', thresholds: list[int] = None) -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during widening"           
        if self.is_empty: return other           
        if other.is_empty: return self           
                        
        if self.union(other) == self:           
            return self           
                
        n_stride = math.gcd(self.stride, other.stride)           
        if n_stride == 0:           
            n_stride = 1           
        
        u = self.union(other)           
        if u.is_empty:           
            return self.top(self.bits)           
                            
        u_span = (u.upper - u.lower) & self.mask           
        if u_span >= self.mask:           
            return self.__class__(n_stride, 0, self.mask, self.bits)           
                
        lower_grew = (u.lower != self.lower)           
        upper_grew = (u.upper != self.upper)           
                        
        n_lower = u.lower           
        n_upper = u.upper           
                        
        if thresholds:           
            sorted_thresholds = sorted(list(set(t & self.mask for t in thresholds)))           
                            
            if lower_grew:           
                candidates = [t for t in sorted_thresholds if t <= u.lower]           
                n_lower = candidates[-1] if candidates else 0           
                                
            if upper_grew:           
                candidates = [t for t in sorted_thresholds if t >= u.upper]           
                n_upper = candidates[0] if candidates else self.mask           
        else:           
            if lower_grew:           
                n_lower = 0           
            if upper_grew:           
                n_upper = self.mask           
                                
        return self.__class__(n_stride, n_lower, n_upper, self.bits)           
    
    def narrow(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during narrowing"           
                                                                                                         
        if self.is_empty or other.is_empty: 
            return self.empty(self.bits) 
        
        span_self = (self.upper - self.lower) & self.mask
                
        if span_self >= self.mask:
            return other
        
        return self.intersect(other)
    
    def union(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during union"           
        if self.is_empty: return other
        if other.is_empty: return self
                
        mod_diff = (other.lower - self.lower) & self.mask           
        n_stride = math.gcd(math.gcd(self.stride, other.stride), mod_diff)           
                
        span_self = max(           
            (self.upper - self.lower) & self.mask,           
            (other.lower - self.lower) & self.mask,           
            (other.upper - self.lower) & self.mask           
        )
        span_other = max(           
            (other.upper - other.lower) & self.mask,           
            (self.lower - other.lower) & self.mask,           
            (self.upper - other.lower) & self.mask           
        )
                
        if span_self <= span_other:           
            n_lower = self.lower           
            total_span = span_self           
        else:           
            n_lower = other.lower           
            total_span = span_other           
                    
        if total_span >= self.mask:           
            return self.top(self.bits)           
                    
        n_upper = (n_lower + total_span) & self.mask           
        return self.__class__(n_stride, n_lower, n_upper, self.bits)           
    
    def intersect(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':           
        assert self.bits == other.bits, "Bit-width mismatch during intersect"           
        if self.is_empty or other.is_empty: return self.empty(self.bits)           
                        
        result = self.empty(self.bits)           
        
        for p1 in self.split_if_wrapped():           
            for p2 in other.split_if_wrapped():           
                        
                if p1.stride == 0 and p2.stride == 0:           
                    if p1.lower == p2.lower:           
                        result = result.union(p1)           
                    continue           
                        
                if p1.stride == 0:           
                    if p2.contains(p1.lower):           
                        result = result.union(p1)           
                    continue           
                        
                if p2.stride == 0:           
                    if p1.contains(p2.lower):           
                        result = result.union(p2)           
                    continue           
        
                diff = p2.lower - p1.lower           
                g, x_coeff, _ = _exgcd(p1.stride, p2.stride)           
                        
                if diff % g != 0:            
                    continue           
                        
                lcm_stride = (p1.stride * p2.stride) // g           
                scale = diff // g           
                        
                base_common = p1.lower + (x_coeff * scale) * p1.stride           
                        
                overlap_lower = max(p1.lower, p2.lower)           
                overlap_upper = min(p1.upper, p2.upper)           
                        
                if overlap_lower > overlap_upper:           
                    continue           
                        
                dist_to_overlap = overlap_lower - base_common           
                if dist_to_overlap > 0:           
                    steps = (dist_to_overlap + lcm_stride - 1) // lcm_stride            
                    first_valid = base_common + steps * lcm_stride           
                else:           
                    steps = (-dist_to_overlap) // lcm_stride           
                    first_valid = base_common - steps * lcm_stride           
                        
                if first_valid > overlap_upper:           
                    continue           
                        
                span = overlap_upper - first_valid           
                last_valid = first_valid + (span - (span % lcm_stride))           
                        
                intersected_part = self.__class__(           
                    lcm_stride,            
                    first_valid & self.mask,           
                    last_valid & self.mask,            
                    self.bits                          
                )
                result = result.union(intersected_part)           
                        
        return result           

                                                                             
                               
                                                                             
    
    def zero_extend(self: 'CircularStridedInterval', new_bits: int) -> 'CircularStridedInterval':
        if self.is_empty: return self.empty(new_bits)
        if new_bits == self.bits: return self
        if new_bits < self.bits:
            raise ValueError(f"Cannot zero_extend from {self.bits} bits to smaller width {new_bits} bits.")
            
        result = self.empty(new_bits)
                                                                      
        for p in self.split_if_wrapped():
            result = result.union(self.__class__(p.stride, p.lower, p.upper, new_bits))
        return result
    
    def sign_extend(self: 'CircularStridedInterval', new_bits: int) -> 'CircularStridedInterval':
        if self.is_empty: return self.empty(new_bits)
        if new_bits <= self.bits: return self
            
        result = self.empty(new_bits)
        sign_bit_val = 1 << (self.bits - 1)
        extension_mask = ((1 << new_bits) - 1) ^ self.mask
            
        for p in self.split_if_wrapped():
            sub_parts = []
                                                              
            if p.lower < sign_bit_val and p.upper >= sign_bit_val:
                pos_upper = sign_bit_val - 1
                dist = pos_upper - p.lower
                aligned_pos_upper = p.lower + (dist - (dist % p.stride))
                sub_parts.append(self.__class__(p.stride, p.lower, aligned_pos_upper, self.bits))
                    
                dist_neg = sign_bit_val - p.lower
                rem = dist_neg % p.stride
                neg_lower = sign_bit_val if rem == 0 else sign_bit_val + (p.stride - rem)
                if neg_lower <= p.upper:
                        sub_parts.append(self.__class__(p.stride, neg_lower, p.upper, self.bits))
            else:
                sub_parts.append(p)
                    
            for sp in sub_parts:
                if sp.upper >= sign_bit_val:
                                                                          
                    n_lower = sp.lower | extension_mask
                    n_upper = sp.upper | extension_mask
                else:
                                                        
                    n_lower = sp.lower
                    n_upper = sp.upper
                result = result.union(self.__class__(sp.stride, n_lower, n_upper, new_bits))
                    
        return result
    
    def truncate(self: 'CircularStridedInterval', new_bits: int) -> 'CircularStridedInterval':
        if self.is_empty: return self.empty(new_bits)
        if new_bits >= self.bits: return self
    
        new_mask = (1 << new_bits) - 1
    
        result = self.empty(new_bits)
        for p in self.split_if_wrapped():
            span = p.upper - p.lower
            num_elements = ((span // p.stride) + 1) if p.stride > 0 else 1
            
                                                                                                              
            if (p.stride == 1 and span >= new_mask) or num_elements >= (1 << new_bits):
                return self.top(new_bits)
    
            n_stride = p.stride % (1 << new_bits)
            if n_stride == 0 and p.lower != p.upper:
                n_stride = 1
    
            result = result.union(self.__class__(
                n_stride,
                p.lower & new_mask,
                p.upper & new_mask,
                new_bits
            ))
    
        return result
    
    def extract(self: 'CircularStridedInterval', high: int, low: int) -> 'CircularStridedInterval':
        new_bits = high - low + 1
        shifted = self >> low
        return shifted.truncate(new_bits)
    
    def concat(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> 'CircularStridedInterval':
        if self.is_empty or other.is_empty: 
            return self.empty(self.bits + other.bits)
                
        shifted_self = self.zero_extend(self.bits + other.bits) << other.bits
        extended_other = other.zero_extend(self.bits + other.bits)
            
                                                                                        
        return shifted_self + extended_other
                                                                                                                                                                                                             
    def assume_eq(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> tuple['CircularStridedInterval', 'CircularStridedInterval']:
        res = self.intersect(other)
        return res, res
    
    def assume_neq(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> tuple['CircularStridedInterval', 'CircularStridedInterval']:
        if self.intersect(other).is_empty:
            return self, other
                                                                               
        if other.stride == 0 and other.lower == other.upper:
            val = other.lower
            if self.stride != 0 and self.contains(val):
                if val == self.lower:
                    n_lower = (self.lower + self.stride) & self.mask
                    return self.__class__(self.stride, n_lower, self.upper, self.bits), other
                elif val == self.upper:
                    n_upper = (self.upper - self.stride) & self.mask
                    return self.__class__(self.stride, self.lower, n_upper, self.bits), other
                else:                                                                                                     
                    part1_upper = (val - self.stride) & self.mask
                    part2_lower = (val + self.stride) & self.mask
                            
                    part1 = self.__class__(self.stride, self.lower, part1_upper, self.bits)
                    part2 = self.__class__(self.stride, part2_lower, self.upper, self.bits)
                                                                                                                                
                    return part1.union(part2), other
                            
        return self, other
    
    def assume_ult(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> tuple['CircularStridedInterval', 'CircularStridedInterval']:
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), self.empty(self.bits)
    
        self_res = self.empty(self.bits)
        other_res = self.empty(self.bits)
    
        for p1 in self.split_if_wrapped():
            for p2 in other.split_if_wrapped():
                                                                                                    
                if p1.lower >= p2.upper:
                    continue
                                                                                    
                p1_upper = min(p1.upper, p2.upper - 1)
                                                                                  
                dist = p1_upper - p1.lower
                if p1.stride > 0:
                    p1_upper = p1.lower + (dist - (dist % p1.stride))
                    
                if p1_upper >= p1.lower:
                    self_res = self_res.union(self.__class__(p1.stride, p1.lower, p1_upper, self.bits))
                                                                                         
                p2_lower = max(p2.lower, p1.lower + 1)
                dist = p2.upper - p2_lower
                if p2.stride > 0:
                    p2_lower = p2.upper - (dist - (dist % p2.stride))
                    
                if p2_lower <= p2.upper:
                    other_res = other_res.union(self.__class__(p2.stride, p2_lower, p2.upper, self.bits))
    
        return self_res, other_res
    
    def assume_slt(self: 'CircularStridedInterval', other: 'CircularStridedInterval') -> tuple['CircularStridedInterval', 'CircularStridedInterval']:
        sign_bit_val = 1 << (self.bits - 1)
            
        def shift_domain(domain: 'CircularStridedInterval', offset: int) -> 'CircularStridedInterval':
            if domain.is_empty: return domain
            n_lower = (domain.lower + offset) & domain.mask
            n_upper = (domain.upper + offset) & domain.mask
            return domain.__class__(domain.stride, n_lower, n_upper, domain.bits)
                                                                                    
        u_self = shift_domain(self, sign_bit_val)
        u_other = shift_domain(other, sign_bit_val)
            
        ref_u_self, ref_u_other = u_self.assume_ult(u_other)
            
        ref_s_self = shift_domain(ref_u_self, sign_bit_val)
        ref_s_other = shift_domain(ref_u_other, sign_bit_val)
            
        return ref_s_self, ref_s_other

# ==============================================================================
# bitwise interval bounds algorithms
# based on Henry S. Warren, Jr., "Hacker's Delight"
# ==============================================================================

def _hd_min_and(a: int, b: int, c: int, d: int, bits: int) -> int:
    mask = (1 << bits) - 1
    m = 1 << (bits - 1)
    while m != 0:
        if (~a & ~c & m) != 0:
                                                                     
            temp = (a | ((-m) & mask)) & (~m & mask)
            if temp <= b:
                a = temp
                break
            temp = (c | ((-m) & mask)) & (~m & mask)
            if temp <= d:
                c = temp
                break
        m >>= 1
    return a & c
    
def _hd_max_and(a: int, b: int, c: int, d: int, bits: int) -> int:
    mask = (1 << bits) - 1
    m = 1 << (bits - 1)
    while m != 0:
        if (b & ~d & m) != 0:
            temp = (b & (~m & mask)) | (m - 1)
            if temp >= a:
                b = temp
                break
        elif (~b & d & m) != 0:
            temp = (d & (~m & mask)) | (m - 1)
            if temp >= c:
                d = temp
                break
        m >>= 1
    return b & d
    
def _hd_min_or(a: int, b: int, c: int, d: int, bits: int) -> int:
    mask = (1 << bits) - 1
    m = 1 << (bits - 1)
    while m != 0:
        if (~a & c & m) != 0:
            temp = (a | ((-m) & mask)) & (~m & mask)
            if temp <= b:
                a = temp
                break
        elif (a & ~c & m) != 0:
            temp = (c | ((-m) & mask)) & (~m & mask)
            if temp <= d:
                c = temp
                break
        m >>= 1
    return a | c
    
def _hd_max_or(a: int, b: int, c: int, d: int, bits: int) -> int:
    mask = (1 << bits) - 1
    m = 1 << (bits - 1)
    while m != 0:
        if (b & d & m) != 0:
            temp = (b & (~m & mask)) | (m - 1)
            if temp >= a:
                b = temp
                break
            temp = (d & (~m & mask)) | (m - 1)
            if temp >= c:
                d = temp
                break
        m >>= 1
    return b | d
